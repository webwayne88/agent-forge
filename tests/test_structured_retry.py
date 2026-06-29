"""Регресс-тесты на хелпер _invoke_structured (фикс бага: GigaChat → None → AttributeError).

Баг: узлы графа звали llm.with_structured_output(Schema).ainvoke(...), GigaChat иногда
возвращал None → reviewer брал state["code"].code → AttributeError: 'NoneType'... → 500.

Фикс: _invoke_structured повторяет вызов до retries раз; при исчерпании — RuntimeError
вместо протекания None. Тесты здесь верифицируют именно это поведение.
"""

import pytest

from app.config import settings
from app.graph.nodes import make_coder_node, make_planner_node, make_reviewer_node
from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict
from tests.conftest import FAKE_CODE, FAKE_PLAN


# ---------------------------------------------------------------------------
# Вспомогательные фейки
# ---------------------------------------------------------------------------


class _NullInvoker:
    """Invoker, который всегда возвращает None (имитация GigaChat-сбоя)."""

    async def ainvoke(self, messages):
        return None


class AlwaysNullLLM:
    """Фейк LLM, чей with_structured_output всегда возвращает None через ainvoke.

    Используется для проверки, что после retries узел бросает RuntimeError,
    а не пропускает None дальше по графу.
    """

    def with_structured_output(self, schema):
        return _NullInvoker()


class _TransientNullInvoker:
    """Invoker, возвращающий None первые `null_count` раз, затем валидный объект.

    Используется для проверки retry: один сбой → потом успех.
    """

    def __init__(self, null_count: int, valid_response):
        self._null_count = null_count
        self._valid = valid_response
        self.call_count = 0

    async def ainvoke(self, messages):
        self.call_count += 1
        if self.call_count <= self._null_count:
            return None
        return self._valid


class TransientNullLLM:
    """Фейк LLM: первые null_count вызовов для каждой схемы возвращает None, затем — valid.

    Каждый вызов with_structured_output создаёт новый invoker с независимым счётчиком.
    """

    def __init__(self, null_count: int, responses: dict):
        self._null_count = null_count
        self._responses = responses
        self.invokers: dict = {}

    def with_structured_output(self, schema):
        invoker = _TransientNullInvoker(self._null_count, self._responses[schema])
        self.invokers[schema] = invoker
        return invoker


# ---------------------------------------------------------------------------
# Базовый state для узлов
# ---------------------------------------------------------------------------

_BASE_STATE = {
    "task": "Тестовая задача",
    "plan": FAKE_PLAN,
    "context": "",
    "code": FAKE_CODE,
    "verdict": None,
    "iterations": 0,
    "status": "planned",
    "approval_decision": None,
    "approval_feedback": "",
}


# ---------------------------------------------------------------------------
# Тест 1: стабильно невалидный → RuntimeError (НЕ AttributeError, НЕ None)
# Регресс на исходный баг: раньше None протекал дальше и вызывал AttributeError
# ---------------------------------------------------------------------------


class TestAlwaysNullRaisesRuntimeError:
    """AlwaysNullLLM исчерпывает все retries → должен подняться RuntimeError."""

    @pytest.mark.unit
    async def test_planner_none_raises_runtime_error(self):
        """planner с Always-None LLM поднимает RuntimeError, а не пропускает None."""
        node = make_planner_node(AlwaysNullLLM())
        state = {**_BASE_STATE, "plan": None}
        with pytest.raises(RuntimeError, match="невалидный структурированный вывод"):
            await node(state)

    @pytest.mark.unit
    async def test_coder_none_raises_runtime_error(self):
        """coder с Always-None LLM поднимает RuntimeError."""
        node = make_coder_node(AlwaysNullLLM())
        state = {**_BASE_STATE, "code": None}
        with pytest.raises(RuntimeError, match="невалидный структурированный вывод"):
            await node(state)

    @pytest.mark.unit
    async def test_reviewer_none_raises_runtime_error(self):
        """reviewer с Always-None LLM поднимает RuntimeError.

        Это критичный путь исходного бага: reviewer звал state['code'].code
        после None-вывода → AttributeError. Теперь RuntimeError поднимается
        раньше, чем None попадёт в state.
        """
        node = make_reviewer_node(AlwaysNullLLM())
        state = {**_BASE_STATE}
        with pytest.raises(RuntimeError, match="невалидный структурированный вывод"):
            await node(state)

    @pytest.mark.unit
    async def test_planner_none_not_attribute_error(self):
        """Убеждаемся: исходный AttributeError больше не протекает из planner."""
        node = make_planner_node(AlwaysNullLLM())
        state = {**_BASE_STATE, "plan": None}
        with pytest.raises(RuntimeError):
            await node(state)
        # Если бы AttributeError протёк — pytest.raises(RuntimeError) сам бы упал

    @pytest.mark.unit
    async def test_coder_none_not_attribute_error(self):
        """Убеждаемся: исходный AttributeError больше не протекает из coder."""
        node = make_coder_node(AlwaysNullLLM())
        state = {**_BASE_STATE, "code": None}
        with pytest.raises(RuntimeError):
            await node(state)

    @pytest.mark.unit
    async def test_reviewer_none_not_attribute_error(self):
        """Убеждаемся: исходный AttributeError больше не протекает из reviewer.

        Это основной регресс-тест: до фикса state['code'].code бросал AttributeError,
        т.к. code был None; теперь RuntimeError поднимается внутри _invoke_structured.
        """
        node = make_reviewer_node(AlwaysNullLLM())
        state = {**_BASE_STATE}
        with pytest.raises(RuntimeError):
            await node(state)


# ---------------------------------------------------------------------------
# Тест 2: транзиентный сбой → retry помогает (один None, потом валидный объект)
# ---------------------------------------------------------------------------


class TestTransientNullRetrySucceeds:
    """При null_count < retries — retry срабатывает, узел возвращает валидный результат."""

    @pytest.mark.unit
    async def test_planner_recovers_after_one_null(self):
        """planner: 1 None → retry → успех; retries по умолчанию = 2 (т.е. 3 попытки)."""
        llm = TransientNullLLM(
            null_count=1,
            responses={Plan: FAKE_PLAN},
        )
        node = make_planner_node(llm)
        state = {**_BASE_STATE, "plan": None}
        result = await node(state)
        assert isinstance(result["plan"], Plan)
        assert result["status"] == "planned"
        # Убеждаемся, что invoker действительно вызвался дважды (1 None + 1 успех)
        assert llm.invokers[Plan].call_count == 2

    @pytest.mark.unit
    async def test_coder_recovers_after_one_null(self):
        """coder: 1 None → retry → успех."""
        llm = TransientNullLLM(
            null_count=1,
            responses={GeneratedCode: FAKE_CODE},
        )
        node = make_coder_node(llm)
        state = {**_BASE_STATE, "code": None}
        result = await node(state)
        assert isinstance(result["code"], GeneratedCode)
        assert result["status"] == "coded"
        assert llm.invokers[GeneratedCode].call_count == 2

    @pytest.mark.unit
    async def test_reviewer_recovers_after_one_null(self):
        """reviewer: 1 None → retry → успех; основной путь исходного бага."""
        from app.testing.fakes import FAKE_VERDICT_PASS

        llm = TransientNullLLM(
            null_count=1,
            responses={ReviewVerdict: FAKE_VERDICT_PASS},
        )
        node = make_reviewer_node(llm)
        state = {**_BASE_STATE}
        result = await node(state)
        assert isinstance(result["verdict"], ReviewVerdict)
        assert result["status"] == "reviewed"
        assert llm.invokers[ReviewVerdict].call_count == 2

    @pytest.mark.unit
    async def test_coder_recovers_after_two_nulls(self):
        """coder: 2 None → retry на 3-й попытке (retries=2 → 3 total) → успех."""
        retries = settings.structured_output_retries  # ожидаем 2
        llm = TransientNullLLM(
            null_count=retries,  # = 2: последняя, 3-я попытка даёт результат
            responses={GeneratedCode: FAKE_CODE},
        )
        node = make_coder_node(llm)
        state = {**_BASE_STATE, "code": None}
        result = await node(state)
        assert isinstance(result["code"], GeneratedCode)
        assert llm.invokers[GeneratedCode].call_count == retries + 1

    @pytest.mark.unit
    async def test_reviewer_raises_when_null_count_exceeds_retries(self):
        """reviewer: null_count > retries → RuntimeError (все попытки исчерпаны)."""
        retries = settings.structured_output_retries  # ожидаем 2
        llm = TransientNullLLM(
            null_count=retries + 1,  # = 3: больше доступных попыток (3 total)
            responses={ReviewVerdict: ReviewVerdict(
                verdict="pass", issues=[], feedback="ok"
            )},
        )
        node = make_reviewer_node(llm)
        state = {**_BASE_STATE}
        with pytest.raises(RuntimeError, match="невалидный структурированный вывод"):
            await node(state)


# ---------------------------------------------------------------------------
# Тест 3: проверка числа попыток (retries+1 total)
# ---------------------------------------------------------------------------


class TestRetryCount:
    """Верифицируем, что _invoke_structured делает ровно retries+1 попыток."""

    @pytest.mark.unit
    async def test_always_null_calls_retries_plus_one_times_for_coder(self):
        """coder c AlwaysNullLLM: ровно retries+1 вызовов ainvoke до RuntimeError."""

        class _CountingInvoker:
            def __init__(self):
                self.call_count = 0

            async def ainvoke(self, messages):
                self.call_count += 1
                return None

        class _CountingLLM:
            def __init__(self):
                self.invoker = _CountingInvoker()

            def with_structured_output(self, schema):
                return self.invoker

        llm = _CountingLLM()
        node = make_coder_node(llm)
        state = {**_BASE_STATE, "code": None}

        expected_calls = settings.structured_output_retries + 1

        with pytest.raises(RuntimeError):
            await node(state)

        assert llm.invoker.call_count == expected_calls, (
            f"Ожидалось {expected_calls} вызовов ainvoke, "
            f"получено {llm.invoker.call_count}"
        )

    @pytest.mark.unit
    async def test_always_null_calls_retries_plus_one_times_for_reviewer(self):
        """reviewer c AlwaysNullLLM: ровно retries+1 вызовов ainvoke до RuntimeError."""

        class _CountingInvoker:
            def __init__(self):
                self.call_count = 0

            async def ainvoke(self, messages):
                self.call_count += 1
                return None

        class _CountingLLM:
            def __init__(self):
                self.invoker = _CountingInvoker()

            def with_structured_output(self, schema):
                return self.invoker

        llm = _CountingLLM()
        node = make_reviewer_node(llm)
        state = {**_BASE_STATE}

        expected_calls = settings.structured_output_retries + 1

        with pytest.raises(RuntimeError):
            await node(state)

        assert llm.invoker.call_count == expected_calls, (
            f"Ожидалось {expected_calls} вызовов ainvoke, "
            f"получено {llm.invoker.call_count}"
        )
