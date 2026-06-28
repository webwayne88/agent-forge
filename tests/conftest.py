"""Фикстуры для тестов Agent Forge.

FakeLLM — переиспользуемый фейк, заменяющий GigaChat в тестах.
Контракт: объект с методом with_structured_output(Schema) → объект с async ainvoke(messages).
"""

import pytest

from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict


class FakeStructuredOutput:
    """Возвращает фиксированный Pydantic-объект при ainvoke."""

    def __init__(self, response_obj):
        self._response = response_obj

    async def ainvoke(self, messages):
        return self._response


class FakeLLM:
    """Фейковый LLM: with_structured_output возвращает нужный объект по типу схемы.

    responses — dict {SchemaClass: instance}, для незарегистрированных схем падает.
    Также ведёт счётчики вызовов по схеме для проверки количества итераций.
    """

    def __init__(self, responses: dict):
        self._responses = responses
        self.call_counts: dict = {}

    def with_structured_output(self, schema):
        if schema not in self._responses:
            raise ValueError(f"FakeLLM: нет ответа для схемы {schema}")
        self.call_counts[schema] = self.call_counts.get(schema, 0)

        outer = self

        class _Invoker:
            async def ainvoke(self, messages):
                outer.call_counts[schema] = outer.call_counts.get(schema, 0) + 1
                return outer._responses[schema]

        return _Invoker()


# --- Готовые объекты-ответы ---

FAKE_PLAN = Plan(
    steps=["Написать функцию", "Покрыть тестами"],
    summary="Суммарное описание задачи",
)

FAKE_CODE = GeneratedCode(
    code="def hello(): return 'hello'",
    language="python",
    explanation="Простая функция hello",
)

FAKE_VERDICT_PASS = ReviewVerdict(
    verdict="pass",
    issues=[],
    feedback="Всё хорошо",
)

FAKE_VERDICT_FIX = ReviewVerdict(
    verdict="fix",
    issues=["Нет docstring"],
    feedback="Добавь docstring к функции",
)


@pytest.fixture
def fake_llm_pass():
    """Фейк: reviewer всегда возвращает pass."""
    return FakeLLM(
        {
            Plan: FAKE_PLAN,
            GeneratedCode: FAKE_CODE,
            ReviewVerdict: FAKE_VERDICT_PASS,
        }
    )


@pytest.fixture
def fake_llm_always_fix():
    """Фейк: reviewer всегда возвращает fix — для проверки остановки reflection-петли."""
    return FakeLLM(
        {
            Plan: FAKE_PLAN,
            GeneratedCode: FAKE_CODE,
            ReviewVerdict: FAKE_VERDICT_FIX,
        }
    )


@pytest.fixture
def initial_state():
    """Начальное состояние графа для тестов."""
    return {
        "task": "Напиши функцию hello world",
        "plan": None,
        "context": "",
        "code": None,
        "verdict": None,
        "iterations": 0,
        "status": "new",
    }
