"""Pydantic-модели eval-харнеса: датасет эталонных задач и отчёт раннера.

Сети/БД не трогают. Стиль типов — как в app/schemas/pipeline.py (Literal, Field,
default_factory).
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator


class EvalCase(BaseModel):
    """Один эталонный кейс: задача + критерии прохождения.

    Любой из expect_* может быть None/пустым — тогда соответствующий критерий
    не проверяется. passed кейса = конъюнкция всех заданных критериев.
    """

    id: str
    task: str
    expect_verdict: Literal["pass", "fix"] | None = None
    expect_language: str | None = None
    expect_code_contains: list[str] = Field(default_factory=list)
    expect_status: str | None = None
    # Режим фейк-LLM для прогона кейса: 'pass' (reviewer -> pass) или 'fix'
    # (reviewer всегда fix, для проверки остановки reflection-петли).
    fake_mode: Literal["pass", "fix"] = "pass"


class EvalDataset(BaseModel):
    """Набор эталонных кейсов с гарантией уникальности id."""

    cases: list[EvalCase]

    @field_validator("cases")
    @classmethod
    def _unique_ids(cls, cases: list[EvalCase]) -> list[EvalCase]:
        ids = [c.id for c in cases]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"Дублирующиеся id кейсов: {sorted(duplicates)}")
        return cases


class CaseResult(BaseModel):
    """Результат прогона одного кейса с метриками и причинами провала."""

    id: str
    passed: bool
    latency_s: float
    cost_units: float
    iterations: int
    reasons: list[str] = Field(default_factory=list)


class EvalReport(BaseModel):
    """Агрегированный отчёт по всему датасету."""

    total: int
    passed_count: int
    pass_rate: float
    avg_latency_s: float
    avg_cost_units: float
    results: list[CaseResult] = Field(default_factory=list)
