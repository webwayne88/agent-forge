"""Детерминированная оценка cost для eval-раннера + реэкспорт фейка.

FakeLLM, make_fake_llm и FAKE_* живут в app/testing/fakes.py (общий с tests/),
здесь реэкспортируются для совместимости импортов evals/. Сеть не трогается.
"""

from app.testing.fakes import (  # noqa: F401  реэкспорт для evals/tests
    FAKE_CODE,
    FAKE_PLAN,
    FAKE_VERDICT_FIX,
    FAKE_VERDICT_PASS,
    FakeLLM,
    make_fake_llm,
)

# Стоимость 1000 условных токенов в условных единицах. Реальной цены и токенов
# в окружении нет (GigaChat/Langfuse недоступны), поэтому держим фиксированной —
# так cost детерминирован и CI eval-gate воспроизводим. В будущей итерации
# источник cost заменяется на usage_metadata/Langfuse без смены интерфейса раннера.
COST_PER_1K_UNITS = 1.0
# Грубая оценка токенов: 4 символа на токен (стандартная эвристика).
CHARS_PER_TOKEN = 4


def estimate_cost(state: dict) -> float:
    """Детерминированная оценка cost прогона по объёму текста в финальном state.

    Считаем токены как (длина task + плана + кода + контекста) / CHARS_PER_TOKEN
    и переводим в условные единицы. Не зависит от сети — одинаковый вход даёт
    одинаковый результат (нужно для стабильного гейта).
    """
    plan = state.get("plan")
    code = state.get("code")
    parts = [
        state.get("task", "") or "",
        str(plan) if plan is not None else "",
        code.code if code is not None else "",
        state.get("context", "") or "",
    ]
    chars = sum(len(p) for p in parts)
    tokens = chars / CHARS_PER_TOKEN
    return tokens / 1000.0 * COST_PER_1K_UNITS
