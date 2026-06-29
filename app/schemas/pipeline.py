from typing import Literal

from pydantic import BaseModel, Field


class Plan(BaseModel):
    """План от Planner: декомпозиция ТЗ, без кода."""

    steps: list[str] = Field(description="Упорядоченные шаги реализации")
    summary: str = Field(description="Краткое резюме задачи")


class GeneratedCode(BaseModel):
    """Вывод Coder: сгенерированный код по плану."""

    code: str = Field(description="Исходный код")
    language: str = Field(default="python", description="Язык кода")
    explanation: str = Field(description="Пояснение к реализации")


class ReviewVerdict(BaseModel):
    """Вывод Reviewer: вердикт ревью, замыкает reflection-петлю."""

    verdict: Literal["pass", "fix"] = Field(description="Итог ревью")
    issues: list[str] = Field(default_factory=list, description="Найденные проблемы")
    feedback: str = Field(description="Обратная связь для Coder")
