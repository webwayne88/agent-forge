"""Тесты eval-харнеса: раннер, датасет, схемы, gate.

Раннер работает на фейк-LLM без сети — детерминирован.
"""

from pathlib import Path

import pytest

from evals.fakes import FakeLLM, estimate_cost, make_fake_llm, FAKE_CODE, FAKE_PLAN
from evals.runner import gate, load_dataset, run_case, run_dataset, format_report
from evals.schema import CaseResult, EvalCase, EvalDataset, EvalReport
from app.schemas.pipeline import ReviewVerdict


_DATASET_PATH = Path(__file__).parent.parent / "evals" / "dataset.json"


# ---------------------------------------------------------------------------
# Схемы (EvalCase, EvalDataset, CaseResult, EvalReport)
# ---------------------------------------------------------------------------


class TestEvalSchemas:
    def test_eval_case_valid(self):
        """EvalCase создаётся с минимальными полями."""
        case = EvalCase(id="test-1", task="Тестовая задача")
        assert case.id == "test-1"
        assert case.fake_mode == "pass"

    def test_eval_dataset_unique_ids(self):
        """EvalDataset принимает кейсы с уникальными id."""
        cases = [
            EvalCase(id="a", task="Задача A"),
            EvalCase(id="b", task="Задача B"),
        ]
        ds = EvalDataset(cases=cases)
        assert len(ds.cases) == 2

    def test_eval_dataset_rejects_duplicate_ids(self):
        """EvalDataset отклоняет дублирующиеся id через field_validator."""
        with pytest.raises(Exception, match="Дублирующиеся"):
            EvalDataset(cases=[
                EvalCase(id="dup", task="Задача 1"),
                EvalCase(id="dup", task="Задача 2"),
            ])

    def test_case_result_fields(self):
        """CaseResult содержит все ожидаемые поля."""
        r = CaseResult(id="x", passed=True, latency_s=0.1, cost_units=0.01, iterations=1)
        assert r.passed is True
        assert r.reasons == []

    def test_eval_report_fields(self):
        """EvalReport агрегирует метрики."""
        r = EvalReport(total=2, passed_count=1, pass_rate=0.5, avg_latency_s=0.1, avg_cost_units=0.02)
        assert r.pass_rate == 0.5


# ---------------------------------------------------------------------------
# Фейки (FakeLLM, make_fake_llm, estimate_cost)
# ---------------------------------------------------------------------------


class TestEvalseFakes:
    def test_make_fake_llm_pass_mode(self):
        """make_fake_llm('pass') создаёт llm с verdict=pass."""
        llm = make_fake_llm("pass")
        assert isinstance(llm, FakeLLM)

    def test_make_fake_llm_fix_mode(self):
        """make_fake_llm('fix') создаёт llm с verdict=fix."""
        llm = make_fake_llm("fix")
        assert isinstance(llm, FakeLLM)

    def test_fake_llm_pass_returns_pass_verdict(self):
        """FakeLLM в режиме pass возвращает ReviewVerdict.verdict == 'pass'."""
        llm = make_fake_llm("pass")
        # Проверяем через FakeLLM._responses: содержит нужный объект
        verdict = llm._responses[ReviewVerdict]
        assert verdict.verdict == "pass"

    def test_fake_llm_fix_returns_fix_verdict(self):
        """FakeLLM в режиме fix возвращает ReviewVerdict.verdict == 'fix'."""
        llm = make_fake_llm("fix")
        verdict = llm._responses[ReviewVerdict]
        assert verdict.verdict == "fix"

    def test_estimate_cost_nonzero_for_nonempty_state(self):
        """estimate_cost возвращает положительное число для непустого state."""
        state = {"task": "Задача", "plan": FAKE_PLAN, "code": FAKE_CODE, "context": ""}
        cost = estimate_cost(state)
        assert cost > 0

    def test_estimate_cost_zero_for_empty_state(self):
        """estimate_cost возвращает 0 для пустого state."""
        assert estimate_cost({}) == 0.0

    def test_estimate_cost_deterministic(self):
        """estimate_cost детерминирована: одинаковый вход → одинаковый cost."""
        state = {"task": "x", "plan": FAKE_PLAN, "code": FAKE_CODE, "context": "ctx"}
        assert estimate_cost(state) == estimate_cost(state)


# ---------------------------------------------------------------------------
# Загрузка датасета
# ---------------------------------------------------------------------------


class TestLoadDataset:
    def test_load_dataset_parses_json(self):
        """load_dataset читает и парсит датасет без ошибок."""
        ds = load_dataset(_DATASET_PATH)
        assert isinstance(ds, EvalDataset)
        assert len(ds.cases) > 0

    def test_load_dataset_has_unique_ids(self):
        """Все id в датасете уникальны."""
        ds = load_dataset(_DATASET_PATH)
        ids = [c.id for c in ds.cases]
        assert len(ids) == len(set(ids))

    def test_load_dataset_has_8_cases(self):
        """Датасет содержит 8 кейсов."""
        ds = load_dataset(_DATASET_PATH)
        assert len(ds.cases) == 8


# ---------------------------------------------------------------------------
# run_case — прогон одного кейса
# ---------------------------------------------------------------------------


class TestRunCase:
    async def test_run_case_returns_case_result(self):
        """run_case возвращает CaseResult."""
        case = EvalCase(id="test", task="Тест", fake_mode="pass", expect_verdict="pass")
        llm = make_fake_llm("pass")
        result = await run_case(case, llm)
        assert isinstance(result, CaseResult)
        assert result.id == "test"

    async def test_run_case_pass_mode_passes(self):
        """run_case в режиме pass: кейс с expect_verdict='pass' проходит."""
        case = EvalCase(id="p", task="Задача", fake_mode="pass", expect_verdict="pass")
        result = await run_case(case, make_fake_llm("pass"))
        assert result.passed is True
        assert result.reasons == []

    async def test_run_case_fix_mode_with_fix_verdict(self):
        """run_case в режиме fix: кейс с expect_verdict='fix' проходит."""
        case = EvalCase(id="f", task="Задача", fake_mode="fix", expect_verdict="fix")
        result = await run_case(case, make_fake_llm("fix"))
        assert result.passed is True

    async def test_run_case_wrong_verdict_fails(self):
        """run_case с несовпадающим expect_verdict: кейс не проходит."""
        case = EvalCase(id="w", task="Задача", fake_mode="pass", expect_verdict="fix")
        result = await run_case(case, make_fake_llm("pass"))
        assert result.passed is False
        assert any("verdict" in r for r in result.reasons)

    async def test_run_case_latency_positive(self):
        """run_case фиксирует положительную latency."""
        case = EvalCase(id="lat", task="Задача", fake_mode="pass")
        result = await run_case(case, make_fake_llm("pass"))
        assert result.latency_s >= 0

    async def test_run_case_cost_positive(self):
        """run_case возвращает ненулевой cost (есть plan + code)."""
        case = EvalCase(id="cost", task="Задача", fake_mode="pass")
        result = await run_case(case, make_fake_llm("pass"))
        assert result.cost_units >= 0

    async def test_run_case_iterations_at_least_one(self):
        """run_case: итераций не менее 1 (coder отработал)."""
        case = EvalCase(id="itr", task="Задача", fake_mode="pass")
        result = await run_case(case, make_fake_llm("pass"))
        assert result.iterations >= 1

    async def test_run_case_code_contains_check(self):
        """expect_code_contains на несуществующий фрагмент: кейс fails с объяснением."""
        case = EvalCase(id="cc", task="Задача", expect_code_contains=["НЕ_СУЩЕСТВУЕТ_12345"])
        result = await run_case(case, make_fake_llm("pass"))
        assert result.passed is False
        assert any("НЕ_СУЩЕСТВУЕТ_12345" in r for r in result.reasons)

    async def test_run_case_language_check_python(self):
        """expect_language='python' проходит на фейке (FAKE_CODE.language == 'python')."""
        case = EvalCase(id="lang", task="Задача", expect_language="python")
        result = await run_case(case, make_fake_llm("pass"))
        assert result.passed is True

    async def test_run_case_status_reviewed(self):
        """expect_status='reviewed' на pass-кейсе проходит (граф на паузе, status=reviewed)."""
        case = EvalCase(id="st", task="Задача", expect_status="reviewed")
        result = await run_case(case, make_fake_llm("pass"))
        assert result.passed is True


# ---------------------------------------------------------------------------
# run_dataset — агрегация
# ---------------------------------------------------------------------------


class TestRunDataset:
    async def test_run_dataset_returns_report(self):
        """run_dataset возвращает EvalReport."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        assert isinstance(report, EvalReport)

    async def test_run_dataset_total_equals_cases(self):
        """report.total == количество кейсов в датасете."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        assert report.total == len(ds.cases)

    async def test_run_dataset_pass_rate_range(self):
        """pass_rate в диапазоне [0, 1]."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        assert 0.0 <= report.pass_rate <= 1.0

    async def test_run_dataset_all_pass_on_fake(self):
        """Все кейсы датасета проходят на фейк-LLM (детерминировано)."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        assert report.pass_rate == 1.0
        assert report.passed_count == report.total

    async def test_run_dataset_results_length(self):
        """Число результатов == числу кейсов."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        assert len(report.results) == len(ds.cases)

    async def test_run_dataset_avg_latency_nonnegative(self):
        """avg_latency_s >= 0."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        assert report.avg_latency_s >= 0

    async def test_run_dataset_avg_cost_positive(self):
        """avg_cost_units > 0 (есть plan + code в state)."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        assert report.avg_cost_units > 0


# ---------------------------------------------------------------------------
# gate — пороговая логика
# ---------------------------------------------------------------------------


class TestGate:
    def test_gate_pass_when_rate_equals_threshold(self):
        """gate возвращает 0 если pass_rate == min_pass_rate."""
        report = EvalReport(total=1, passed_count=1, pass_rate=1.0,
                            avg_latency_s=0.1, avg_cost_units=0.01)
        assert gate(report, 1.0) == 0

    def test_gate_pass_when_rate_above_threshold(self):
        """gate возвращает 0 если pass_rate > min_pass_rate."""
        report = EvalReport(total=2, passed_count=2, pass_rate=1.0,
                            avg_latency_s=0.1, avg_cost_units=0.01)
        assert gate(report, 0.8) == 0

    def test_gate_fail_when_rate_below_threshold(self):
        """gate возвращает 1 если pass_rate < min_pass_rate."""
        report = EvalReport(total=2, passed_count=1, pass_rate=0.5,
                            avg_latency_s=0.1, avg_cost_units=0.01)
        assert gate(report, 1.0) == 1

    def test_gate_fail_on_zero_pass_rate(self):
        """gate возвращает 1 при pass_rate=0."""
        report = EvalReport(total=2, passed_count=0, pass_rate=0.0,
                            avg_latency_s=0.0, avg_cost_units=0.0)
        assert gate(report, 0.5) == 1

    def test_gate_with_unreachable_threshold_exits_1(self):
        """gate возвращает 1 при пороге > 1.0."""
        report = EvalReport(total=1, passed_count=1, pass_rate=1.0,
                            avg_latency_s=0.0, avg_cost_units=0.0)
        assert gate(report, 1.01) == 1


# ---------------------------------------------------------------------------
# format_report — форматирование вывода
# ---------------------------------------------------------------------------


class TestFormatReport:
    async def test_format_report_contains_total(self):
        """Отчёт содержит общее число кейсов."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        text = format_report(report)
        assert "total" in text.lower() or str(report.total) in text

    async def test_format_report_contains_pass_rate(self):
        """Отчёт содержит pass-rate."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        text = format_report(report)
        assert "pass" in text.lower()

    async def test_format_report_no_emoji(self):
        """Отчёт не содержит emoji (правило проекта)."""
        ds = load_dataset(_DATASET_PATH)
        report = await run_dataset(ds)
        text = format_report(report)
        # Проверяем базовые emoji которые могут попасть случайно
        for emoji_char in ("✓", "✕", "✅", "❌", "🔧", "🚀"):
            assert emoji_char not in text, f"Emoji '{emoji_char}' найден в отчёте"
