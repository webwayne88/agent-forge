"""Тесты графа Agent Forge: сборка, happy path, reflection-loop, типы вывода."""

import uuid

import pytest

from app.config import settings
from app.graph.graph import build_graph
from app.graph.nodes import make_coder_node, make_planner_node, make_reviewer_node
from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict
from tests.conftest import (
    FAKE_CODE,
    FAKE_PLAN,
    FAKE_VERDICT_FIX,
    FAKE_VERDICT_PASS,
    FakeLLM,
)


def _config():
    """Уникальный thread_id для каждого вызова графа (MemorySaver требует)."""
    return {"configurable": {"thread_id": str(uuid.uuid4())}}


# ---------------------------------------------------------------------------
# D1-1: Сборка графа
# ---------------------------------------------------------------------------


class TestBuildGraph:
    def test_build_graph_returns_compiled(self, fake_llm_pass):
        """build_graph(fake) возвращает скомпилированный граф без сетевых вызовов."""
        graph = build_graph(fake_llm_pass)
        assert graph is not None

    def test_graph_has_required_nodes(self, fake_llm_pass):
        """Граф содержит узлы planner, retrieve, coder, reviewer."""
        graph = build_graph(fake_llm_pass)
        # LangGraph хранит узлы в graph.nodes (dict)
        node_names = set(graph.nodes.keys())
        assert "planner" in node_names
        assert "retrieve" in node_names
        assert "coder" in node_names
        assert "reviewer" in node_names

    def test_build_graph_without_llm_does_not_crash_import(self):
        """build_graph(None) вызывает get_llm() — это мы не тестируем (сеть),
        но build_graph(fake) не должен падать при подстановке фейка."""
        # Просто убеждаемся, что фабрика принимает fake без TypeErrors
        fake = FakeLLM(
            {Plan: FAKE_PLAN, GeneratedCode: FAKE_CODE, ReviewVerdict: FAKE_VERDICT_PASS}
        )
        graph = build_graph(fake)
        assert graph is not None


# ---------------------------------------------------------------------------
# D1-2: Happy path — reviewer сразу возвращает pass
# ---------------------------------------------------------------------------


class TestHappyPath:
    @pytest.mark.integration
    async def test_happy_path_full_run(self, fake_llm_pass, initial_state):
        """Граф проходит planner->retrieve->coder->reviewer, verdict=pass, итерация=1."""
        graph = build_graph(fake_llm_pass)
        result = await graph.ainvoke(initial_state, config=_config())

        assert result["plan"] is not None
        assert result["code"] is not None
        assert result["verdict"] is not None
        assert result["iterations"] == 1

    @pytest.mark.integration
    async def test_happy_path_status_reviewed(self, fake_llm_pass, initial_state):
        """После прохода граф заканчивается со статусом reviewed."""
        graph = build_graph(fake_llm_pass)
        result = await graph.ainvoke(initial_state, config=_config())
        assert result["status"] == "reviewed"

    @pytest.mark.integration
    async def test_happy_path_verdict_is_pass(self, fake_llm_pass, initial_state):
        """Вердикт в финальном состоянии — pass."""
        graph = build_graph(fake_llm_pass)
        result = await graph.ainvoke(initial_state, config=_config())
        assert result["verdict"].verdict == "pass"

    @pytest.mark.integration
    async def test_happy_path_plan_is_pydantic(self, fake_llm_pass, initial_state):
        """plan в финальном состоянии — экземпляр Plan."""
        graph = build_graph(fake_llm_pass)
        result = await graph.ainvoke(initial_state, config=_config())
        assert isinstance(result["plan"], Plan)

    @pytest.mark.integration
    async def test_happy_path_code_is_pydantic(self, fake_llm_pass, initial_state):
        """code в финальном состоянии — экземпляр GeneratedCode."""
        graph = build_graph(fake_llm_pass)
        result = await graph.ainvoke(initial_state, config=_config())
        assert isinstance(result["code"], GeneratedCode)

    @pytest.mark.integration
    async def test_happy_path_verdict_is_pydantic(self, fake_llm_pass, initial_state):
        """verdict в финальном состоянии — экземпляр ReviewVerdict."""
        graph = build_graph(fake_llm_pass)
        result = await graph.ainvoke(initial_state, config=_config())
        assert isinstance(result["verdict"], ReviewVerdict)


# ---------------------------------------------------------------------------
# D1-3: Reflection-loop стоп — reviewer всегда возвращает fix
# ---------------------------------------------------------------------------


class TestReflectionLoopStop:
    @pytest.mark.integration
    async def test_loop_stops_at_max_iterations(
        self, fake_llm_always_fix, initial_state
    ):
        """Граф останавливается при iterations == max_reflection_iterations, не зависает."""
        graph = build_graph(fake_llm_always_fix)
        result = await graph.ainvoke(initial_state, config=_config())
        assert result["iterations"] == settings.max_reflection_iterations

    @pytest.mark.integration
    async def test_loop_coder_called_max_times(
        self, fake_llm_always_fix, initial_state
    ):
        """Coder вызывается ровно max_reflection_iterations раз."""
        graph = build_graph(fake_llm_always_fix)
        await graph.ainvoke(initial_state, config=_config())
        assert (
            fake_llm_always_fix.call_counts.get(GeneratedCode, 0)
            == settings.max_reflection_iterations
        )

    @pytest.mark.integration
    async def test_loop_verdict_still_fix_at_end(
        self, fake_llm_always_fix, initial_state
    ):
        """При принудительной остановке последний вердикт — fix (петля прервана, не исправлена)."""
        graph = build_graph(fake_llm_always_fix)
        result = await graph.ainvoke(initial_state, config=_config())
        assert result["verdict"].verdict == "fix"

    @pytest.mark.integration
    async def test_loop_does_not_exceed_max(self, fake_llm_always_fix, initial_state):
        """iterations не превышает max_reflection_iterations."""
        graph = build_graph(fake_llm_always_fix)
        result = await graph.ainvoke(initial_state, config=_config())
        assert result["iterations"] <= settings.max_reflection_iterations

    @pytest.mark.integration
    async def test_loop_planner_called_once(self, fake_llm_always_fix, initial_state):
        """Planner вызывается ровно один раз (не входит в reflection-петлю)."""
        graph = build_graph(fake_llm_always_fix)
        await graph.ainvoke(initial_state, config=_config())
        assert fake_llm_always_fix.call_counts.get(Plan, 0) == 1


# ---------------------------------------------------------------------------
# D1-4: Structured output узлов (юнит-тесты узлов напрямую)
# ---------------------------------------------------------------------------


class TestStructuredOutput:
    @pytest.mark.unit
    async def test_planner_returns_plan(self, fake_llm_pass):
        """make_planner_node возвращает dict с ключом plan типа Plan."""
        node = make_planner_node(fake_llm_pass)
        state = {"task": "Тестовая задача", "plan": None, "context": "", "code": None,
                 "verdict": None, "iterations": 0, "status": "new"}
        result = await node(state)
        assert "plan" in result
        assert isinstance(result["plan"], Plan)
        assert result["status"] == "planned"

    @pytest.mark.unit
    async def test_planner_plan_fields(self, fake_llm_pass):
        """Plan содержит steps (list) и summary (str)."""
        node = make_planner_node(fake_llm_pass)
        state = {"task": "Задача", "plan": None, "context": "", "code": None,
                 "verdict": None, "iterations": 0, "status": "new"}
        result = await node(state)
        plan = result["plan"]
        assert isinstance(plan.steps, list)
        assert len(plan.steps) > 0
        assert isinstance(plan.summary, str)

    @pytest.mark.unit
    async def test_coder_returns_generated_code(self, fake_llm_pass):
        """make_coder_node возвращает dict с ключом code типа GeneratedCode."""
        node = make_coder_node(fake_llm_pass)
        state = {"task": "Задача", "plan": FAKE_PLAN, "context": "", "code": None,
                 "verdict": None, "iterations": 0, "status": "planned"}
        result = await node(state)
        assert "code" in result
        assert isinstance(result["code"], GeneratedCode)
        assert result["status"] == "coded"

    @pytest.mark.unit
    async def test_coder_increments_iterations(self, fake_llm_pass):
        """Coder инкрементит iterations на 1."""
        node = make_coder_node(fake_llm_pass)
        state = {"task": "Задача", "plan": FAKE_PLAN, "context": "", "code": None,
                 "verdict": None, "iterations": 0, "status": "planned"}
        result = await node(state)
        assert result["iterations"] == 1

    @pytest.mark.unit
    async def test_coder_increments_from_nonzero(self, fake_llm_pass):
        """Coder инкрементит iterations на 1 от ненулевого значения."""
        node = make_coder_node(fake_llm_pass)
        state = {"task": "Задача", "plan": FAKE_PLAN, "context": "", "code": FAKE_CODE,
                 "verdict": FAKE_VERDICT_FIX, "iterations": 2, "status": "reviewed"}
        result = await node(state)
        assert result["iterations"] == 3

    @pytest.mark.unit
    async def test_coder_uses_feedback_on_retry(self, fake_llm_always_fix):
        """При повторной итерации coder получает feedback из verdict."""
        node = make_coder_node(fake_llm_always_fix)
        state = {"task": "Задача", "plan": FAKE_PLAN, "context": "", "code": FAKE_CODE,
                 "verdict": FAKE_VERDICT_FIX, "iterations": 1, "status": "reviewed"}
        # Просто проверяем, что не падает и возвращает код
        result = await node(state)
        assert isinstance(result["code"], GeneratedCode)

    @pytest.mark.unit
    async def test_reviewer_returns_verdict(self, fake_llm_pass):
        """make_reviewer_node возвращает dict с ключом verdict типа ReviewVerdict."""
        node = make_reviewer_node(fake_llm_pass)
        state = {"task": "Задача", "plan": FAKE_PLAN, "context": "", "code": FAKE_CODE,
                 "verdict": None, "iterations": 1, "status": "coded"}
        result = await node(state)
        assert "verdict" in result
        assert isinstance(result["verdict"], ReviewVerdict)
        assert result["status"] == "reviewed"

    @pytest.mark.unit
    async def test_reviewer_verdict_literal(self, fake_llm_pass):
        """Вердикт reviewer содержит допустимое значение pass или fix."""
        node = make_reviewer_node(fake_llm_pass)
        state = {"task": "Задача", "plan": FAKE_PLAN, "context": "", "code": FAKE_CODE,
                 "verdict": None, "iterations": 1, "status": "coded"}
        result = await node(state)
        assert result["verdict"].verdict in ("pass", "fix")

    @pytest.mark.unit
    async def test_reviewer_verdict_fix(self, fake_llm_always_fix):
        """Фейк с verdict=fix возвращает ReviewVerdict с verdict=='fix'."""
        node = make_reviewer_node(fake_llm_always_fix)
        state = {"task": "Задача", "plan": FAKE_PLAN, "context": "", "code": FAKE_CODE,
                 "verdict": None, "iterations": 1, "status": "coded"}
        result = await node(state)
        assert result["verdict"].verdict == "fix"
        assert isinstance(result["verdict"].issues, list)
        assert isinstance(result["verdict"].feedback, str)
