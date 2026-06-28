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
