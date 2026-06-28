# Eval-харнес Agent Forge

Прогоняет эталонные задачи через граф (planner -> retrieve -> coder -> reviewer)
на фейк-LLM **без сети** и считает агрегаты: pass-rate, avg latency, avg cost.
Используется как CI eval-gate.

## Структура

- `dataset.json` — эталонные кейсы.
- `schema.py` — Pydantic-модели (`EvalCase`, `EvalDataset`, `CaseResult`, `EvalReport`).
- `fakes.py` — самодостаточный фейк-LLM (тот же контракт, что `tests/conftest.FakeLLM`) и детерминированная оценка cost.
- `runner.py` — ядро: `run_case`, `run_dataset`, `load_dataset`, `format_report`, `gate`.
- `__main__.py` — CLI-вход.

## Формат датасета

```json
{
  "cases": [
    {
      "id": "hello-happy",
      "task": "Напиши функцию hello...",
      "fake_mode": "pass",
      "expect_verdict": "pass",
      "expect_language": "python",
      "expect_code_contains": ["def hello"],
      "expect_status": "reviewed"
    }
  ]
}
```

Поля кейса:

- `id` — уникальный (валидатор `EvalDataset` падает на дублях).
- `task` — ТЗ для графа.
- `fake_mode` — режим фейка: `pass` (reviewer -> pass) или `fix` (reviewer всегда fix, проверка остановки reflection-петли).
- `expect_verdict` / `expect_language` / `expect_code_contains` / `expect_status` — критерии; любой опускается, тогда не проверяется. `passed` кейса = все заданные критерии выполнены.

## Запуск

```bash
source venv/bin/activate

# как модуль-пакет с CLI
python -m evals
python -m evals --dataset evals/dataset.json --min-pass-rate 1.0

# как раннер напрямую
python -m evals.runner
```

Exit code: `0` если pass-rate >= порога, иначе `1` (eval-gate роняет CI-билд).

## Смысл метрик

- **pass-rate** — доля прошедших кейсов; **единственная метрика гейта**.
- **avg latency** — wall-clock на прогон; информативна (на фейках близка к нулю и шумна — не гейтить).
- **avg cost** — детерминированная токен-эвристика (символы/4 как токены, фиксированная цена за 1k). Реальных токенов/Langfuse в окружении нет, поэтому cost **не реальный** и служит только для воспроизводимости — гейтить по нему нельзя.

Дизайн совместим с реальным LLM: источник cost/latency можно заменить на
метаданные Langfuse без смены интерфейса раннера.

> Граф останавливается на `interrupt_before=["approval"]` (HITL-gate), поэтому
> финальный `status` на прогоне = `reviewed` (последний выполненный узел —
> reviewer), а не `approved`. Это учтено в критериях датасета.
