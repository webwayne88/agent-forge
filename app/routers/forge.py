import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.graph.graph import build_graph
from app.graph.state import initial_state
from app.observability.langfuse import get_callbacks
from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict

router = APIRouter(prefix="/forge", tags=["forge"])

# Граф компилируется один раз на старте приложения, переиспользуется между запросами.
# ВАЖНО: approve/reject/rollback используют этот же _graph (тот же MemorySaver),
# иначе состояние thread_id потеряется.
_graph = build_graph()


class ForgeRequest(BaseModel):
    # Ограничение от пустого ввода и от раздувания контекста LLM
    task: str = Field(min_length=1, max_length=8000)


class RejectRequest(BaseModel):
    # Человеческий комментарий при отклонении — уйдёт в coder как приоритетный feedback
    feedback: str = Field(min_length=1, max_length=8000)


class RollbackRequest(BaseModel):
    # Идентификатор чекпойнта из /history, к которому откатываемся
    checkpoint_id: str = Field(min_length=1)


class HistoryEntry(BaseModel):
    checkpoint_id: str
    next: list[str]
    status: str | None


class ForgeResponse(BaseModel):
    thread_id: str
    plan: Plan | None
    code: GeneratedCode | None
    verdict: ReviewVerdict | None
    iterations: int
    status: str
    approval_decision: str | None


def _run_config(thread_id: str) -> dict:
    # callbacks наследуются всеми узлами/LLM-вызовами графа (трейсинг без правок узлов).
    # Без ключей Langfuse get_callbacks() вернёт [] — no-op, граф не падает.
    return {
        "configurable": {"thread_id": thread_id},
        "callbacks": get_callbacks(),
    }


def _state_to_response(thread_id: str, values: dict, on_pause: bool) -> ForgeResponse:
    """Собирает ответ из values чекпойнтера. on_pause=True => граф стоит на approval."""
    status = "awaiting_approval" if on_pause else values.get("status", "new")
    return ForgeResponse(
        thread_id=thread_id,
        plan=values.get("plan"),
        code=values.get("code"),
        verdict=values.get("verdict"),
        iterations=values.get("iterations", 0),
        status=status,
        approval_decision=values.get("approval_decision"),
    )


async def _finalize_response(thread_id: str) -> ForgeResponse:
    """Читает финальный snapshot и собирает ответ: непустой next с 'approval' =>
    граф стоит на HITL-паузе (awaiting_approval). Единая точка финализации для
    forge/approve/reject/rollback."""
    snapshot = await _graph.aget_state(_run_config(thread_id))
    on_pause = "approval" in snapshot.next
    return _state_to_response(thread_id, snapshot.values, on_pause)


async def _require_paused_state(thread_id: str):
    """Возвращает snapshot, если thread существует и стоит на паузе approval, иначе 404/409."""
    config = _run_config(thread_id)
    snapshot = await _graph.aget_state(config)
    # Пустой next и пустые values => такого thread нет в чекпойнтере
    if not snapshot.next and not snapshot.values:
        raise HTTPException(status_code=404, detail="thread_id не найден")
    if "approval" not in snapshot.next:
        raise HTTPException(
            status_code=409, detail="Граф не ожидает approval (уже завершён или на другом шаге)"
        )
    return snapshot


@router.post("", response_model=ForgeResponse)
async def forge(request: ForgeRequest) -> ForgeResponse:
    # Каждый запрос — отдельный thread в checkpointer, чтобы состояния не пересекались.
    thread_id = str(uuid.uuid4())
    config = _run_config(thread_id)
    # Граф остановится на interrupt в узле approval. Финальное состояние читаем
    # через aget_state: snapshot.next непустой => граф на паузе (awaiting_approval).
    await _graph.ainvoke(initial_state(request.task), config=config)
    return await _finalize_response(thread_id)


@router.post("/{thread_id}/approve", response_model=ForgeResponse)
async def approve(thread_id: str) -> ForgeResponse:
    await _require_paused_state(thread_id)
    config = _run_config(thread_id)
    # Проставляем решение человека в state, затем резюмим граф — он дойдёт до END.
    await _graph.aupdate_state(config, {"approval_decision": "approved"})
    await _graph.ainvoke(None, config=config)
    return await _finalize_response(thread_id)


@router.post("/{thread_id}/reject", response_model=ForgeResponse)
async def reject(thread_id: str, request: RejectRequest) -> ForgeResponse:
    await _require_paused_state(thread_id)
    config = _run_config(thread_id)
    # Проставляем reject + человеческий feedback в state и резюмим: граф либо
    # вернётся к coder (новая итерация по feedback) и снова встанет перед approval,
    # либо завершится rejected (лимит итераций исчерпан).
    await _graph.aupdate_state(
        config,
        {"approval_decision": "rejected", "approval_feedback": request.feedback},
    )
    await _graph.ainvoke(None, config=config)
    return await _finalize_response(thread_id)


@router.get("/{thread_id}/history", response_model=list[HistoryEntry])
async def history(thread_id: str) -> list[HistoryEntry]:
    config = _run_config(thread_id)
    entries: list[HistoryEntry] = []
    async for snap in _graph.aget_state_history(config):
        entries.append(
            HistoryEntry(
                checkpoint_id=snap.config["configurable"]["checkpoint_id"],
                next=list(snap.next),
                status=snap.values.get("status") if snap.values else None,
            )
        )
    if not entries:
        raise HTTPException(status_code=404, detail="thread_id не найден")
    return entries


@router.post("/{thread_id}/rollback", response_model=ForgeResponse)
async def rollback(thread_id: str, request: RollbackRequest) -> ForgeResponse:
    config = _run_config(thread_id)
    # Ищем нужный чекпойнт в истории по checkpoint_id.
    target = None
    async for snap in _graph.aget_state_history(config):
        if snap.config["configurable"]["checkpoint_id"] == request.checkpoint_id:
            target = snap
            break
    if target is None:
        raise HTTPException(status_code=404, detail="checkpoint_id не найден")
    # Откат к историческому чекпойнту паузы: aupdate_state форкает состояние от
    # target.config и делает форк новой головой thread. Одновременно сбрасываем
    # approval_decision -> None, иначе форк унаследует решение из прошлого approve
    # ('approved') и граф проскочит interrupt насквозь (BUG-ROLLBACK-STATE).
    # ainvoke(None) здесь НЕ вызываем: форк уже стоит на interrupt_before approval
    # (next == 'approval') и ждёт нового решения человека — это и есть rollback.
    rollback_config = {**target.config, "callbacks": get_callbacks()}
    await _graph.aupdate_state(rollback_config, {"approval_decision": None})
    return await _finalize_response(thread_id)
