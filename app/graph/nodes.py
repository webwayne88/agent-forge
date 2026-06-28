from langchain_core.messages import SystemMessage

from app.graph.prompts import load_prompt
from app.graph.state import GraphState
from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict


def make_planner_node(llm):
    """Узел planner: декомпозирует ТЗ в Pydantic-план, кода не пишет."""
    structured = llm.with_structured_output(Plan)

    async def planner_node(state: GraphState) -> dict:
        prompt = load_prompt("planner", user_task=state["task"])
        plan = await structured.ainvoke([SystemMessage(content=prompt)])
        return {"plan": plan, "status": "planned"}

    return planner_node


async def retrieve_node(state: GraphState) -> dict:
    """Заглушка RAG: возвращает пустой контекст (pgvector — следующая итерация)."""
    return {"context": ""}


def make_coder_node(llm):
    """Узел coder: генерирует код по плану, на повторной итерации учитывает
    feedback ревьюера и инкрементит счётчик reflection-петли."""
    structured = llm.with_structured_output(GeneratedCode)

    async def coder_node(state: GraphState) -> dict:
        verdict = state.get("verdict")
        feedback = verdict.feedback if verdict else ""
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
