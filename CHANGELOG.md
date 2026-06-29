# Changelog

Все значимые изменения проекта документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
проект придерживается [семантического версионирования](https://semver.org/lang/ru/).

## [Unreleased]

## [0.2.0] — 2026-06-28

### Added
- RAG: PostgreSQL + pgvector, гибридный поиск (lexical tsvector + векторный
  `halfvec(2560)` по GigaChat Embeddings) со слиянием через RRF; узел `retrieve`
  стал реальным, ingestion-скрипт проектной доки (`python -m scripts.ingest`).
- Observability: трейсинг cost/latency/tokens через Langfuse (no-op без ключей).
- Human-in-the-loop: `interrupt_before` перед approval, эндпоинты
  `/forge/{id}/approve`, `/reject`, `/rollback`, `/history`.
- Evaluation: датасет (`evals/`) + раннер (pass-rate / latency / cost),
  eval-gate в CI на фейк-LLM без сети.

### Fixed
- Устойчивость structured output: retry + guard (`_invoke_structured`) — на
  невалидный вывод понятный `RuntimeError` вместо `AttributeError`.
- GigaChat structured output: `method="format_instructions"` (дефолтный
  `function_calling` стабильно возвращает `None` у GigaChat-2-Max).
- Размерность эмбеддингов: схема под `halfvec(2560)` (реальная размерность
  GigaChat Embeddings = 2560; лимит HNSW для типа `vector` = 2000).
- CI: установка ruff в lint-job, триггеры на ветку `dev`.

## [0.1.0] — 2026-06-28

### Added
- Каркас: FastAPI + LangGraph граф `planner → retrieve → coder → reviewer`
  с reflection-петлёй (двойной ограничитель: счётчик в state + `max_iterations`).
- GigaChat-2-Max через langchain-gigachat, structured output на Pydantic-схемах.
- LLM инжектируется в узлы фабриками — граф тестируется на фейке без сети.
- Инфраструктура: Docker Compose, `.env.example`, pytest, эндпоинты
  `GET /health`, `POST /forge`.

[Unreleased]: https://github.com/webwayne88/agent-forge/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/webwayne88/agent-forge/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/webwayne88/agent-forge/releases/tag/v0.1.0
