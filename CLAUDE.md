# Agent Forge — правила разработки

Стек: Python 3.10 (локально 3.10.11; в Docker 3.11-slim — код держим совместимым с 3.10), FastAPI (async), LangGraph, langchain-gigachat, Pydantic v2.
ВАЖНО: на 3.10 для LangGraph state используй `from typing_extensions import TypedDict` (не `typing`) — иначе Pydantic падает при интроспекции графа.
Архитектура: Routers → Services → Repositories → Models. Граф вынесен в `app/graph/`.
ORM/данные: в объёме «каркас + граф» БД НЕ подключаем (pgvector/RAG — следующая итерация). Состояние графа — in-memory + LangGraph checkpointer (MemorySaver).
Тесты: pytest + pytest-asyncio, лежат в `tests/`. LLM в тестах — мок (фейковый узел, без сети).
CI: в этом объёме не настраиваем (следующая итерация).

LLM: GigaChat-2-Max + GigaChat Embeddings через `langchain-gigachat`.
- Параметры клиента: `scope="GIGACHAT_API_CORP"`, `verify_ssl_certs=False`, `model="GigaChat-2-Max"`, `temperature=0.11`, `timeout=1000`, `profanity_check=False`.
- `credentials` — из `.env` (`GIGACHAT_AUTH_KEY`), НЕ хардкодить.
- Структурированный вывод — через `.with_structured_output(Schema)`; на невалидный вывод — retry.

Доменные правила:
- Граф: `planner` → `retrieve`(заглушка в этом объёме) → `coder` → `reviewer` → conditional edge (`fix` → coder / `done` → END/human).
- Planner НЕ пишет код — только декомпозиция в Pydantic-план.
- Reflection-loop Coder↔Reviewer ограничен `max_iterations` (дефолт 3) И счётчиком в state — без ограничителя петля бесконечна.
- LLM инжектируется в узлы как зависимость (фабрика), чтобы в тестах подменяться фейком. Никаких прямых вызовов сети внутри узла без возможности подмены.
- Промпты — в `prompts/` отдельными файлами (versioned), НЕ в коде.
- Конфиг — Pydantic Settings из `.env`, не hardcode.

Глобальные правила (из ~/.claude/CLAUDE.md): русский в общении/комментариях бизнес-логики, async-first, минимальный diff, без зависимостей Google, без эмодзи в UI/выводе, import только на уровне модуля.
