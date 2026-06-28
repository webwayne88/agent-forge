import uuid

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.graph.graph import build_graph
from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict

router = APIRouter(prefix="/forge", tags=["forge"])

# Граф компилируется один раз на старте приложения, переиспользуется между запросами
_graph = build_graph()


class ForgeRequest(BaseModel):
    # Ограничение от пустого ввода и от раздувания контекста LLM
    task: str = Field(min_length=1, max_length=8000)


class ForgeResponse(BaseModel):
    plan: Plan | None
    code: GeneratedCode | None
    verdict: ReviewVerdict | None
    iterations: int
    status: str


@router.post("", response_model=ForgeResponse)
async def forge(request: ForgeRequest) -> ForgeResponse:
    # Каждый запрос — отдельный thread в checkpointer, чтобы состояния не пересекались
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}
    initial: dict = {
        "task": request.task,
        "plan": None,
        "context": "",
        "code": None,
        "verdict": None,
        "iterations": 0,
        "status": "new",
    }
    result = await _graph.ainvoke(initial, config=config)
    return ForgeResponse(
        plan=result["plan"],
        code=result["code"],
        verdict=result["verdict"],
        iterations=result["iterations"],
        status=result["status"],
    )
