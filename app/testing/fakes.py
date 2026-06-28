"""Переиспользуемые фейки для тестов и eval-раннера (без сети).

Живёт в prod-пакете app/, поэтому от него могут зависеть и tests/, и evals/
без перекрёстной зависимости test-пакета от prod-кода и наоборот.
Контракт FakeLLM: объект с with_structured_output(Schema) -> объект с
async ainvoke(messages). Возвращает фиксированные Pydantic-объекты.
"""

from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict

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


class FakeLLM:
    """Фейковый LLM: with_structured_output возвращает объект по типу схемы.

    responses — dict {SchemaClass: instance}; для незарегистрированной схемы падает.
    Ведёт счётчики вызовов по схеме для проверки количества итераций.
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


def make_fake_llm(mode: str = "pass") -> FakeLLM:
    """Фабрика фейка под режим кейса.

    mode='pass' — reviewer выносит pass (happy-path).
    mode='fix'  — reviewer всегда fix (проверка остановки reflection-петли).
    Отдельный экземпляр на кейс важен при asyncio.gather: общие call_counts
    и режимы кейсов не должны перемешиваться.
    """
    verdict = FAKE_VERDICT_FIX if mode == "fix" else FAKE_VERDICT_PASS
    return FakeLLM(
        {
            Plan: FAKE_PLAN,
            GeneratedCode: FAKE_CODE,
            ReviewVerdict: verdict,
        }
    )
