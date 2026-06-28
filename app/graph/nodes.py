from langchain_core.messages import SystemMessage

from app.config import settings
from app.graph.prompts import load_prompt
from app.graph.state import GraphState
from app.rag.hybrid import hybrid_search
from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict


def make_planner_node(llm):
    """Узел planner: декомпозирует ТЗ в Pydantic-план, кода не пишет."""
    structured = llm.with_structured_output(Plan)

    async def planner_node(state: GraphState) -> dict:
        prompt = load_prompt("planner", user_task=state["task"])
        plan = await structured.ainvoke([SystemMessage(content=prompt)])
        return {"plan": plan, "status": "planned"}

    return planner_node


def _format_context(chunks) -> str:
    """Форматирует найденные фрагменты в строку для промпта coder (с указанием source)."""
    blocks = [f"[Источник: {c.source}]\n{c.content}" for c in chunks]
    return "\n\n".join(blocks)


def make_retrieve_node(repo, embeddings):
    """Узел retrieve: реальный RAG-поиск по задаче, кладёт найденное в context.

    repo и embeddings инжектируются (как llm в make_planner_node) — в тестах
    подменяются фейками без БД и сети. Если репозиторий не сконфигурирован
    (repo=None, напр. пустой DATABASE_URL) — graceful fallback на пустой context,
    граф не падает.
    """

    async def retrieve_node(state: GraphState) -> dict:
        if repo is None or embeddings is None:
            return {"context": ""}
        chunks = await hybrid_search(
            repo, embeddings, state["task"], settings.rag_top_k, settings.rag_rrf_k
        )
        return {"context": _format_context(chunks)}

    return retrieve_node


def make_coder_node(llm):
    """Узел coder: генерирует код по плану, на повторной итерации учитывает
    feedback ревьюера и инкрементит счётчик reflection-петли."""
    structured = llm.with_structured_output(GeneratedCode)

    async def coder_node(state: GraphState) -> dict:
        verdict = state.get("verdict")
        # Человеческий feedback при reject важнее авто-вердикта ревьюера
        human_feedback = state.get("approval_feedback") or ""
        feedback = human_feedback if human_feedback else (verdict.feedback if verdict else "")
        prompt = load_prompt(
            "coder",
            plan=str(state["plan"]),
            retrieved_context=state.get("context", ""),
            reviewer_feedback=feedback,
        )
        code = await structured.ainvoke([SystemMessage(content=prompt)])
        return {
            "code": code,
            "iterations": state.get("iterations", 0) + 1,
            "status": "coded",
        }

    return coder_node


def make_reviewer_node(llm):
    """Узел reviewer: выносит вердикт pass/fix, замыкает reflection-петлю."""
    structured = llm.with_structured_output(ReviewVerdict)

    async def reviewer_node(state: GraphState) -> dict:
        prompt = load_prompt(
            "reviewer",
            plan=str(state["plan"]),
            generated_code=state["code"].code,
        )
        verdict = await structured.ainvoke([SystemMessage(content=prompt)])
        return {"verdict": verdict, "status": "reviewed"}

    return reviewer_node


async def approval_node(state: GraphState) -> dict:
    """HITL-узел: финализирует статус по решению человека.

    Граф ставится на паузу ПЕРЕД этим узлом через interrupt_before=["approval"]
    (статический interrupt). Решение человека роутер проставляет в state
    (approval_decision/approval_feedback) через update_state перед резюмом, а этот
    узел лишь переводит его в финальный status. Сеть/LLM не использует.

    Статический interrupt выбран вместо динамического interrupt(): на Python 3.10
    interrupt() опирается на contextvar runnable-контекста, который при async-прогоне
    графа (и в async-, и в sync-узле через executor) до 3.11 не пробрасывается.
    interrupt_before не зависит от contextvar и работает на 3.10 и 3.11.
    """
    if state.get("approval_decision") == "rejected":
        return {"status": "rejected"}
    return {"approval_decision": "approved", "approval_feedback": "", "status": "approved"}
