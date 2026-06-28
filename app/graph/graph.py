from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

from app.config import settings
from app.graph.nodes import (
    make_coder_node,
    make_planner_node,
    make_reviewer_node,
    retrieve_node,
)
from app.graph.state import GraphState
from app.llm.factory import get_llm


def _route_after_review(state: GraphState) -> str:
    """Conditional edge после reviewer: двойной ограничитель reflection-петли.

    Возврат к coder только если ревью требует правок (verdict == "fix") И
    счётчик итераций ещё не достиг лимита. Иначе — END. Так петля
    Coder <-> Reviewer гарантированно завершается.
    """
    verdict = state.get("verdict")
    if (
        verdict is not None
        and verdict.verdict == "fix"
        and state.get("iterations", 0) < settings.max_reflection_iterations
    ):
        return "coder"
    return END


def build_graph(llm=None):
    """Собирает и компилирует граф planner -> retrieve -> coder -> reviewer.

    llm инжектируется в узлы; если не передан — создаётся лениво через
    get_llm() (так тесты подменяют фейк и не дёргают сеть). Структура графа
    сети не требует — обращение к LLM происходит только при run узлов.
    """
    if llm is None:
        llm = get_llm()

    builder = StateGraph(GraphState)
    builder.add_node("planner", make_planner_node(llm))
    builder.add_node("retrieve", retrieve_node)
    builder.add_node("coder", make_coder_node(llm))
    builder.add_node("reviewer", make_reviewer_node(llm))

    builder.set_entry_point("planner")
    builder.add_edge("planner", "retrieve")
    builder.add_edge("retrieve", "coder")
    builder.add_edge("coder", "reviewer")
    builder.add_conditional_edges(
        "reviewer", _route_after_review, {"coder": "coder", END: END}
    )

    return builder.compile(checkpointer=MemorySaver())
