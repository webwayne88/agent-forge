# Agent Forge — правила разработки

Стек: Python 3.10 (локально 3.10.11; в Docker 3.11-slim — код держим совместимым с 3.10), FastAPI (async), LangGraph, langchain-gigachat, Pydantic v2.
ВАЖНО: на 3.10 для LangGraph state используй `from typing_extensions import TypedDict` (не `typing`) — иначе Pydantic падает при интроспекции графа.
Архитектура: Routers → Services → Repositories → Models. Граф вынесен в `app/graph/`.
ORM/данные: PostgreSQL + pgvector через asyncpg (RAG). Доступ — через `app/repositories/` (async). Состояние графа — LangGraph checkpointer (MemorySaver по умолчанию; для HITL-персистентности возможен Postgres saver).
Тесты: pytest + pytest-asyncio, лежат в `tests/`. LLM в тестах — мок (фейковый узел, без сети). БД/внешние сервисы (pgvector, Langfuse) в тестах — моки/фейки репозиториев, без реальной сети.
CI: GitHub Actions (`.github/workflows/`) — ruff (lint) + pytest + eval-gate (прогон eval-раннера на фейк-LLM с порогом pass-rate).

Компоненты (итерация 2 — RAG / Langfuse / eval / HITL):
- RAG: pgvector + hybrid search (BM25/lexical + векторный по GigaChat Embeddings). Ingestion-скрипт для доки/конвенций проекта. Узел `retrieve` — реальный поиск (больше не заглушка). Embeddings — через langchain-gigachat (GigaChatEmbeddings), креды из .env.
- Observability: Langfuse — трейсинг cost/latency/tokens на узлах графа через LangChain callback handler. Ключи из .env; при отсутствии ключей трейсинг — no-op (не падать).
- Eval: `evals/` — датасет эталонных задач + раннер (pass-rate, avg latency, avg cost). Раннер должен гоняться на фейк-LLM без сети (для CI eval-gate).
- HITL: LangGraph `interrupt` перед финальным approval; эндпоинты approve/reject; resume по thread_id; rollback через историю чекпойнтов. Без ключей/БД — на MemorySaver.

LLM: GigaChat-2-Max + GigaChat Embeddings через `langchain-gigachat`.
- Параметры клиента: `scope="GIGACHAT_API_CORP"`, `verify_ssl_certs=False`, `model="GigaChat-2-Max"`, `temperature=0.11`, `timeout=1000`, `profanity_check=False`.
- `credentials` — из `.env` (`GIGACHAT_AUTH_KEY`), НЕ хардкодить.
- Структурированный вывод — через `.with_structured_output(Schema)`; на невалидный вывод — retry.

Доменные правила:
- Граф: `planner` → `retrieve`(реальный RAG) → `coder` → `reviewer` → conditional edge (`fix` → coder / `done` → human approval (HITL interrupt) → END).
- Planner НЕ пишет код — только декомпозиция в Pydantic-план.
- Reflection-loop Coder↔Reviewer ограничен `max_iterations` (дефолт 3) И счётчиком в state — без ограничителя петля бесконечна.
- LLM инжектируется в узлы как зависимость (фабрика), чтобы в тестах подменяться фейком. Никаких прямых вызовов сети внутри узла без возможности подмены.
- Промпты — в `prompts/` отдельными файлами (versioned), НЕ в коде.
- Конфиг — Pydantic Settings из `.env`, не hardcode.

Глобальные правила (из ~/.claude/CLAUDE.md): русский в общении/комментариях бизнес-логики, async-first, минимальный diff, без зависимостей Google, без эмодзи в UI/выводе, import только на уровне модуля.
