"""Eval-раннер: прогон датасета через граф на фейк-LLM, агрегаты метрик.

Раннер детерминирован и сетенезависим:
- latency меряется wall-clock (time.perf_counter) вокруг graph.ainvoke;
- cost оценивается детерминированной токен-эвристикой (см. evals/fakes.py),
  т.к. реальных токенов/Langfuse в окружении нет;
- pass определяется per-case критериями (verdict/language/code_contains/status).

Дизайн совместим с будущим реальным LLM: источник cost/latency можно заменить на
метаданные Langfuse без смены интерфейса run_case/run_dataset.
"""

import asyncio
import json
import time
import uuid
from pathlib import Path

from app.graph.graph import build_graph
from app.graph.state import initial_state
from evals.fakes import estimate_cost, make_fake_llm
from evals.schema import CaseResult, EvalDataset, EvalReport


def load_dataset(path) -> EvalDataset:
    """Читает JSON-датасет и валидирует через Pydantic (в т.ч. уникальность id)."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return EvalDataset(**raw)


def _evaluate(case, values: dict) -> list[str]:
    """Применяет критерии кейса к финальному state. Возвращает список причин провала
    (пустой список => кейс прошёл)."""
    reasons: list[str] = []

    verdict = values.get("verdict")
    if case.expect_verdict is not None:
        actual = verdict.verdict if verdict is not None else None
        if actual != case.expect_verdict:
            reasons.append(f"verdict: ожидалось '{case.expect_verdict}', получено '{actual}'")

    code = values.get("code")
    if case.expect_language is not None:
        actual_lang = code.language if code is not None else None
        if actual_lang != case.expect_language:
            reasons.append(
                f"language: ожидалось '{case.expect_language}', получено '{actual_lang}'"
            )

    if case.expect_code_contains:
        actual_code = code.code if code is not None else ""
        for needle in case.expect_code_contains:
            if needle not in actual_code:
                reasons.append(f"code не содержит '{needle}'")

    if case.expect_status is not None:
        actual_status = values.get("status")
        if actual_status != case.expect_status:
            reasons.append(
                f"status: ожидалось '{case.expect_status}', получено '{actual_status}'"
            )

    return reasons


async def run_case(case, llm, graph=None) -> CaseResult:
    """Прогоняет один кейс через граф на инжектируемом llm и оценивает результат.

    Граф останавливается на interrupt_before=['approval'], поэтому финальное
    состояние читаем через aget_state (как в роутере). Уникальный thread_id —
    MemorySaver требует, иначе состояния кейсов пересекутся.

    graph можно передать готовым (run_dataset переиспользует один граф на режим,
    чтобы не компилировать StateGraph на каждый кейс). Если не передан — собирается
    из llm (обратная совместимость с прямыми вызовами в тестах).
    """
    if graph is None:
        graph = build_graph(llm)
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    start = time.perf_counter()
    await graph.ainvoke(initial_state(case.task), config=config)
    snapshot = await graph.aget_state(config)
    latency_s = time.perf_counter() - start

    values = snapshot.values
    reasons = _evaluate(case, values)
    return CaseResult(
        id=case.id,
        passed=not reasons,
        latency_s=latency_s,
        cost_units=estimate_cost(values),
        iterations=values.get("iterations", 0),
        reasons=reasons,
    )


async def run_dataset(dataset: EvalDataset, llm_factory=make_fake_llm) -> EvalReport:
    """Прогоняет все кейсы (async-first, gather) и агрегирует метрики.

    llm_factory(mode) даёт отдельный llm на кейс — режимы pass/fix не перемешиваются.
    Граф компилируется один раз на каждый встреченный режим (а не на каждый кейс):
    компиляция StateGraph не бесплатна, а thread_id уникален на кейс — MemorySaver
    одного графа корректно изолирует состояния кейсов одного режима.
    """
    graphs_by_mode: dict[str, object] = {}
    for case in dataset.cases:
        if case.fake_mode not in graphs_by_mode:
            graphs_by_mode[case.fake_mode] = build_graph(llm_factory(case.fake_mode))

    results = await asyncio.gather(
        *(
            run_case(case, llm_factory(case.fake_mode), graphs_by_mode[case.fake_mode])
            for case in dataset.cases
        )
    )
    total = len(results)
    passed_count = sum(1 for r in results if r.passed)
    pass_rate = passed_count / total if total else 0.0
    avg_latency = sum(r.latency_s for r in results) / total if total else 0.0
    avg_cost = sum(r.cost_units for r in results) / total if total else 0.0
    return EvalReport(
        total=total,
        passed_count=passed_count,
        pass_rate=pass_rate,
        avg_latency_s=avg_latency,
        avg_cost_units=avg_cost,
        results=list(results),
    )


def format_report(report: EvalReport) -> str:
    """Текстовая печать метрик без эмодзи (для CLI/CI-лога)."""
    lines = [
        "=== Agent Forge eval report ===",
        f"total cases : {report.total}",
        f"passed      : {report.passed_count}/{report.total}",
        f"pass-rate   : {report.pass_rate:.2%}",
        f"avg latency : {report.avg_latency_s:.4f} s",
        f"avg cost    : {report.avg_cost_units:.4f} units (детерминированная эвристика, не реальные токены)",
        "--- per case ---",
    ]
    for r in report.results:
        status = "PASS" if r.passed else "FAIL"
        line = (
            f"[{status}] {r.id}: iters={r.iterations}, "
            f"latency={r.latency_s:.4f}s, cost={r.cost_units:.4f}"
        )
        if r.reasons:
            line += " | " + "; ".join(r.reasons)
        lines.append(line)
    return "\n".join(lines)


def gate(report: EvalReport, min_pass_rate: float) -> int:
    """Eval-gate: 0 если pass-rate >= порога, иначе 1 (для CI exit code)."""
    return 0 if report.pass_rate >= min_pass_rate else 1


if __name__ == "__main__":
    # Запуск как модуль: python -m evals.runner — прогон дефолтного датасета и печать
    # метрик с дефолтным порогом 1.0 (на фейках pass-rate детерминирован).
    _DEFAULT_DATASET = Path(__file__).with_name("dataset.json")
    _report = asyncio.run(run_dataset(load_dataset(_DEFAULT_DATASET)))
    print(format_report(_report))
    raise SystemExit(gate(_report, 1.0))
