import asyncio

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.config import settings
from app.db.pool import get_pool
from app.graph.nodes import (
    approval_node,
    make_coder_node,
    make_planner_node,
    make_retrieve_node,
    make_reviewer_node,
)
from app.graph.state import GraphState
from app.llm.embeddings import get_embeddings
from app.llm.factory import get_llm
from app.repositories.documents import PgDocumentRepository


def _route_after_review(state: GraphState) -> str:
    """Conditional edge после reviewer: двойной ограничитель reflection-петли.

    Возврат к coder только если ревью требует правок (verdict == "fix") И
    счётчик итераций ещё не достиг лимита. Иначе — на HITL-узел approval
    (человеческий gate перед финалом). Так петля Coder <-> Reviewer
    гарантированно завершается, а финал всегда проходит через approval.
    """
    verdict = state.get("verdict")
    if (
        verdict is not None
        and verdict.verdict == "fix"
        and state.get("iterations", 0) < settings.max_reflection_iterations
    ):
        return "coder"
    return "approval"


def _route_after_approval(state: GraphState) -> str:
    """Conditional edge после approval: reject как доработка, но без вечной петли.

    При reject с запасом итераций — назад к coder (доработать по человеческому
    feedback); иначе (approved или лимит исчерпан) — END. Двойной ограничитель
    iterations < max сохранён, поэтому петля reject -> coder -> ... завершается.
    """
    if (
        state.get("approval_decision") == "rejected"
        and state.get("iterations", 0) < settings.max_reflection_iterations
    ):
        return "coder"
    return END


def _default_repo():
    """Лениво строит реальный репозиторий, если задан DATABASE_URL.

    Пул не создаётся здесь (только при первом запросе внутри узла) — импорт и
    сборка графа остаются зелёными без живой БД. Без DATABASE_URL возвращает
    None, и узел retrieve уходит в graceful fallback на пустой context.
    """
    if not settings.database_url:
        return None
    return _LazyPgRepository(get_pool, PgDocumentRepository)


class _LazyPgRepository:
    """Обёртка: получает пул при первом async-вызове и делегирует методы
    реальному PgDocumentRepository. Нужна потому, что build_graph синхронна, а
    создание пула asyncpg — async."""

    # Методы DocumentRepository, которые прозрачно делегируются реальному репозиторию
    _DELEGATED = frozenset({"lexical_search", "vector_search", "add_chunks"})

    def __init__(self, get_pool, repo_cls):
        self._get_pool = get_pool
        self._repo_cls = repo_cls
        self._repo = None
        # Защита от гонки: lexical_search и vector_search идут через asyncio.gather,
        # без lock _ensure создал бы PgDocumentRepository дважды (нарушение singleton).
        self._lock = asyncio.Lock()

    async def _ensure(self):
        # Double-checked locking: быстрый путь, если репозиторий уже создан.
        if self._repo is None:
            async with self._lock:
                if self._repo is None:
                    self._repo = self._repo_cls(await self._get_pool())
        return self._repo

    def __getattr__(self, name):
        # Делегируем методы репозитория без ручного дублирования: возвращаем
        # async-обёртку, которая ленивым _ensure() получает реальный объект.
        if name not in type(self)._DELEGATED:
            raise AttributeError(name)

        async def _delegate(*args, **kwargs):
            repo = await self._ensure()
            return await getattr(repo, name)(*args, **kwargs)

        return _delegate


def build_graph(llm=None, repo=None, embeddings=None):
    """Собирает и компилирует граф planner -> retrieve -> coder -> reviewer.

    llm/repo/embeddings инжектируются в узлы; если не переданы — создаются лениво
    (llm через get_llm(), embeddings через get_embeddings(), repo через
    _default_repo()). Так тесты подменяют фейки и не дёргают сеть/БД, а пустой
    DATABASE_URL даёт repo=None и graceful fallback retrieve на пустой context.
    Параметры опциональны — сигнатура обратно совместима с build_graph().
    """
    if llm is None:
        llm = get_llm()
    if repo is None:
        repo = _default_repo()
    if embeddings is None and repo is not None:
        embeddings = get_embeddings()

    builder = StateGraph(GraphState)
    builder.add_node("planner", make_planner_node(llm))
    builder.add_node("retrieve", make_retrieve_node(repo, embeddings))
    builder.add_node("coder", make_coder_node(llm))
    builder.add_node("reviewer", make_reviewer_node(llm))
    builder.add_node("approval", approval_node)

    builder.set_entry_point("planner")
    builder.add_edge("planner", "retrieve")
    builder.add_edge("retrieve", "coder")
    builder.add_edge("coder", "reviewer")
    builder.add_conditional_edges(
        "reviewer", _route_after_review, {"coder": "coder", "approval": "approval"}
    )
    builder.add_conditional_edges(
        "approval", _route_after_approval, {"coder": "coder", END: END}
    )

    # Статический HITL-gate: граф останавливается ПЕРЕД узлом approval и ждёт
    # решения человека (approve/reject через router). interrupt_before надёжно
    # работает на Python 3.10 (в отличие от динамического interrupt()).
    return builder.compile(
        checkpointer=MemorySaver(), interrupt_before=["approval"]
    )
