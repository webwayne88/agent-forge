from typing_extensions import TypedDict

from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict


class GraphState(TypedDict):
    """Состояние графа Planner -> retrieve -> Coder -> Reviewer.

    iterations считает витки reflection-петли Coder <-> Reviewer и вместе с
    max_reflection_iterations не даёт петле крутиться бесконечно.
    """

    task: str
    plan: Plan | None
    context: str
    code: GeneratedCode | None
    verdict: ReviewVerdict | None
    iterations: int
    status: str
    # HITL: решение человека на этапе approval ('approved'|'rejected'|None)
    approval_decision: str | None
    # HITL: комментарий человека при reject — приоритетнее авто-feedback ревьюера
    approval_feedback: str


def initial_state(task: str) -> dict:
    """Начальное состояние графа по задаче — единая точка инициализации
    для роутера и eval-раннера (схема меняется в одном месте)."""
    return {
        "task": task,
        "plan": None,
        "context": "",
        "code": None,
        "verdict": None,
        "iterations": 0,
        "status": "new",
        "approval_decision": None,
        "approval_feedback": "",
    }
