# Agent Forge

> Узкий, но production-grade срез корпоративной AI-платформы: мультиагентный пайплайн **Planner → Coder → Reviewer** с reflection-петлёй, который по техзадаче на функцию/эндпоинт генерирует код, ревьюит его и итеративно чинит.

Это не «платформа из 12 агентов» — это 3 агента, доведённые до production-качества с правильной архитектурой, ограничителями и тестированием. Observability, eval-датасет и human-in-the-loop — следующие итерации. Портфолио-проект под роль **AI/LLM Systems Engineer** (Enterprise Vibe Coding Engineer).

---

## Зачем этот проект

Большинство портфолио в AI Engineering — это чат-боты, простые RAG или один агент. Цепочка же из 12 LLM-звеньев на демо выглядит эффектно, но хрупка: ошибка накапливается, каждое звено множит вероятность мусора на выходе.

Agent Forge показывает другой уровень инженерного мышления — **глубина на узком срезе вместо ширины, которая разваливается при первом нажатии**:

**Реализовано (итерация 1 — каркас + граф):**
- мультиагентная оркестрация (planner → retrieve → coder → reviewer) с ограничителями (`max_iterations=3`) и reflection-loop;
- промпт как инженерный контракт: structured output через Pydantic, валидация выхода узлов;
- LLM инжектируется в узлы — граф тестируется на фейке без сети;
- reflection-loop с двойным ограничителем (счётчик в state + conditional edge) — гарантированно завершается.

**Реализовано (итерация 2 — RAG + Observability + Eval + HITL):**
- Knowledge: RAG (PostgreSQL + pgvector + hybrid search BM25/RRF + GigaChat Embeddings), узел retrieve — реальный;
- Observability: Langfuse-трейсинг (cost, latency, tokens) через LangChain callbacks; без ключей — no-op;
- Evaluation: eval-датасет (`evals/`) + раннер (pass-rate/latency/cost) + CI eval-gate;
- Enterprise: human-in-the-loop (interrupt перед approval), approve/reject/rollback, история чекпойнтов.

**Roadmap (следующие итерации):**
- Persistence чекпойнтов между рестартами (Postgres saver вместо MemorySaver);
- audit trail решений человека (HITL);
- дашборд с метриками на узел.

То есть закрывается ядро компетенций роли: **Agent Engineering · Structured Output & Validation · Testing Without Network · Enterprise Architecture**.

---

## Что делает система

Вход — техзадача на Python-функцию или эндпоинт. Выход — сгенерированный план, код и вердикт ревьюера.

**Flow с HITL (реализовано):**
```
Техзадача (ТЗ)
      │
      ▼
  Planner ──► декомпозирует в план (Pydantic)
      │
      ▼
  Retrieve ──► контекст через RAG (hybrid search)
      │
      ▼
  Coder ──► генерирует код по плану + контексту
      │
      ▼
  Reviewer ──► ревьюит код, вердикт pass/fix
      │           │
      │     reflection loop (max_iterations=3)
      └──◄────────┘
      │ pass / лимит
      ▼
  Approval ──┬──► approve ──► END
  (HITL gate)│
             └──► reject (с feedback) ──► coder (доработка) + снова approval
                 (лимит итераций сохранён)
      
  Все шаги → Langfuse трейсинг (cost/latency/tokens)
  Результат: план + код + вердикт + approval_decision + iterations
```

### Роли агентов

| Агент | Ответственность | Реализация |
|-------|-----------------|-----------|
| **Planner** | Декомпозирует ТЗ в структурированный план; код НЕ пишет | Реализовано (`planner.md`, узел в graph.py) |
| **Retrieve** | Возвращает контекст через RAG (гибридный поиск BM25/вектор) | Реализовано (`retrieve` с PgDocumentRepository) |
| **Coder** | Генерирует код по плану + контексту; на retry учитывает feedback | Реализовано (`coder.md`, feedback loop) |
| **Reviewer** | Ревьюит код и выносит вердикт `pass`/`fix` | Реализовано (`reviewer.md`, conditional edge) |
| **Approval** | Human-in-the-loop gate перед финалом; approve/reject/rollback | Реализовано (HITL-узел, эндпоинты) |

---

## Архитектура

Async-first, оркестрация на **LangGraph** (StateGraph + conditional edges + checkpointer).

- **State** — `TypedDict` (состояние графа), **схемы** — Pydantic.
- **Узлы графа:** 
  - `planner` — декомпозирует ТЗ в структурированный план (`Plan`), код НЕ пишет
  - `retrieve` — выполняет гибридный поиск по документам (BM25/lexical + вектор) через PostgreSQL/pgvector
  - `coder` — генерирует код по плану и контексту (`GeneratedCode`)
  - `reviewer` — ревьюит код, выносит вердикт `pass`/`fix` (`ReviewVerdict`)
  - `approval` — HITL-gate: останавливает граф перед финалом (interrupt_before)
- **Conditional edge** после reviewer: возврат к coder только если `verdict == "fix"` И `iterations < max_reflection_iterations`; иначе — на approval (HITL-gate)
- **HITL-gate** (узел approval): граф останавливается на `interrupt_before=["approval"]`; человек решает approve/reject через эндпоинты
- **Reject как доработка**: если итераций осталось, reject возвращает граф к coder для доработки по feedback; после завершения — снова на approval
- **Reflection-loop** Coder ↔ Reviewer + Reject→Coder ограничены `max_iterations=3` (двойной ограничитель: счётчик в state + conditional edge) — петля гарантированно завершается
- **Checkpointer** (`MemorySaver`): каждый запрос — отдельный thread; состояние персистентно пока приложение запущено; resume/rollback/history реализованы
- **LLM инжектируется** в узлы через фабрику — граф тестируется на фейке без сети

---

## Стек

| Слой | Технологии | Статус |
|------|------------|--------|
| **Backend** | FastAPI (async), Pydantic (schemas + structured output), TypedDict (state) | Реализовано |
| **Оркестрация** | LangGraph — StateGraph, conditional edges, MemorySaver checkpointer, HITL interrupt | Реализовано |
| **LLM** | GigaChat-2-Max через langchain-gigachat (`scope=GIGACHAT_API_CORP`, `temperature=0.11`) | Реализовано |
| **Knowledge** | RAG (PostgreSQL + pgvector + hybrid search BM25/RRF + GigaChat Embeddings) | Реализовано |
| **Observability** | Langfuse трейсинг (cost, latency, tokens) через LangChain callbacks | Реализовано |
| **Evaluation** | pytest (36+ тестов на фейковом LLM); eval-датасет + CI eval-gate | Реализовано |
| **Инфра** | Docker Compose (postgres + app), python:3.11-slim, `.env.example`, pytest.ini, GitHub Actions CI | Реализовано |

---

## Ключевые инженерные решения (реализовано)

| Решение | Зачем | Статус |
|---------|-------|--------|
| **3 агента, не 12** | Цепочка из 12 LLM-звеньев накапливает ошибку и хрупка; узкий срез в production-качестве надёжнее | Реализовано |
| **Planner не пишет код** | Декомпозиция и реализация — разный контекст; смешение раздувает контекст и мешает дебагу | Реализовано (промпт, тесты) |
| **GigaChat-2-Max вместо OpenAI** | Корпоративный scope, нет зависимостей от внешних провайдеров | Реализовано (langchain-gigachat) |
| **RAG вместо мировых знаний LLM** | Точность кода на проектных конвенциях/доках > дофига параметров для LLM | Реализовано (pgvector + hybrid search) |
| **Reflection с `max_iterations=3`** | Без ограничителей петля Coder ↔ Reviewer не завершается; двойной ограничитель (итерации + conditional edge) гарантирует конечность | Реализовано (state + conditional edge) |
| **HITL на финальном шаге** | Контроль на критичной точке без потери автономности пайплайна; reject как доработка, не отмена | Реализовано (approval-узел, эндпоинты) |
| **LLM инжектируется, не импортируется** | Граф нетестируем без подменяемости; фейк в conftest.py позволяет гонять 36+ тестов без сети и ключа | Реализовано (factory, fixture-based) |
| **Промпты в файлах, не в коде** | Версионирование, переиспользование, эксперименты без пересборки | Реализовано (prompts/ с README) |
| **Structured output через Pydantic** | Валидация выхода, retry на несоответствие схеме; промпт как контракт | Реализовано (Plan, GeneratedCode, ReviewVerdict) |
| **Observability (Langfuse)** | Операционная видимость: cost, latency, tokens на каждом узле и вызове LLM | Реализовано (callbacks, no-op без ключей) |
| **Eval-gate в CI** | Регрессия промпта/модели ловится автоматически; pass-rate на фейках = детерминирован | Реализовано (evals/ + CI шаг) |

**Планируются (roadmap):**
| Решение | Зачем |
|---------|-------|

---

## Структура проекта

```
agent-forge/
├── app/                         # основной пакет
│   ├── main.py                  # FastAPI-приложение, роутеры, loggers
│   ├── config.py                # Pydantic Settings (GigaChat, max_iterations, DATABASE_URL, Langfuse)
│   ├── routers/
│   │   └── forge.py             # POST /forge, GET /health, HITL: approve/reject/history/rollback
│   ├── graph/                   # LangGraph: состояние и узлы
│   │   ├── state.py             # TypedDict GraphState
│   │   ├── nodes.py             # planner, retrieve (реальный RAG), coder, reviewer, approval
│   │   ├── graph.py             # build_graph: StateGraph + MemorySaver + interrupt_before
│   │   └── prompts.py           # load_prompt(name): загружает из prompts/ с плейсхолдерами
│   ├── schemas/
│   │   ├── pipeline.py          # Pydantic: Plan, GeneratedCode, ReviewVerdict
│   │   └── rag.py               # DocumentChunk, RetrievedChunk (для RAG)
│   ├── llm/
│   │   ├── factory.py           # get_llm() — фабрика GigaChat (lru_cache)
│   │   └── embeddings.py        # get_embeddings() — GigaChat Embeddings
│   ├── repositories/            # Data access layer (async-first)
│   │   ├── base.py              # DocumentRepository интерфейс
│   │   └── documents.py         # PgDocumentRepository (asyncpg, hybrid search)
│   ├── rag/                     # Гибридный поиск
│   │   └── hybrid.py            # merge_results: RRF или взвешенное слияние lexical+vector
│   ├── db/                      # БД и пул
│   │   └── pool.py              # get_pool() — пул asyncpg (lazy)
│   ├── observability/           # Трейсинг и логирование
│   │   └── langfuse.py          # get_callbacks() — Langfuse handler или [] (no-op)
│   └── testing/
│       └── fakes.py             # FakeLLM (для tests/ и evals/)
├── evals/                       # Evaluation dataset и раннер
│   ├── dataset.json             # задачи с expect_verdict, expect_language и т.п.
│   ├── schema.py                # Pydantic: EvalCase, CaseResult, EvalReport
│   ├── runner.py                # run_dataset(), format_report(), gate()
│   ├── fakes.py                 # make_fake_llm(mode), estimate_cost()
│   └── README.md                # документация evals
├── prompts/                     # системные промпты (versioned)
│   ├── README.md                # конвенции, версионирование, плейсхолдеры
│   ├── planner.md               # версия 1.0.0, узел planner
│   ├── coder.md                 # версия 1.0.0, узел coder
│   └── reviewer.md              # версия 1.0.0, узел reviewer
├── .github/
│   └── workflows/
│       └── ci.yml               # GitHub Actions: lint + test + eval-gate
├── tests/                       # pytest (моки/фейки, без сети)
│   ├── test_app.py              # smoke-тесты: импорт, конфиг, /health
│   ├── test_graph.py            # граф на фейковом LLM (happy path, reflection-loop)
│   ├── test_hitl.py             # HITL-flow: approve/reject/history/rollback
│   ├── test_endpoints.py        # интеграция: эндпоинты /forge и HITL
│   └── conftest.py              # fixtures: fake_llm_pass, fake_llm_always_fix
├── requirements.txt             # зависимости
├── Dockerfile                   # python:3.11-slim, uvicorn
├── docker-compose.yml           # postgres (pgvector) + app
├── pytest.ini                   # конфигурация pytest
├── .env.example                 # template переменных (GigaChat, DATABASE_URL, Langfuse)
└── README.md                    # этот файл
```

**Ключевые файлы (итерация 2):**
- `app/graph/graph.py` — `build_graph()` с _route_after_review (reflection) + _route_after_approval (HITL)
- `app/graph/nodes.py` — узел `retrieve` теперь вызывает `PgDocumentRepository.{lexical,vector}_search()`
- `app/routers/forge.py` — эндпоинты `/forge` (ainvoke + interrupt_before), `/approve`, `/reject`, `/history`, `/rollback`
- `app/repositories/documents.py` — PgDocumentRepository: ts_rank (BM25) + vector поиск через asyncpg
- `app/observability/langfuse.py` — get_callbacks(): трейсинг без ключей = [] (no-op)
- `evals/runner.py` — run_dataset(): проходит кейсы, вычисляет pass-rate/latency/cost
- `evals/dataset.json` — задачи с критериями (expect_verdict, expect_language, expect_code_contains)
- `.github/workflows/ci.yml` — шаги: lint, test, eval-gate (python -m evals.runner)

---

## Безопасность HITL-эндпоинтов

HITL-эндпоинты (`approve`/`reject`/`rollback`/`history`) на текущей итерации **не имеют
аутентификации/авторизации**: владение `thread_id` не привязано к пользователю (модели
пользователей/сессий в проекте пока нет). Практический риск ограничен тем, что
`thread_id` — это непредсказуемый `uuid4`, но технически любой, кто узнает чужой
`thread_id`, может им управлять (IDOR-класс).

Поэтому:
- эндпоинты **не предназначены для публичного доступа без шлюза авторизации** —
  выставляйте их только за обратным прокси/API-gateway с auth;
- не логируйте `thread_id` в открытых логах/ответах прокси;
- когда появится модель пользователя — привязывать `thread_id` к `user_id` при создании
  в `POST /forge` и проверять владельца в HITL-эндпоинтах (иначе 403/404).

---

## Запуск

### Локально (Python 3.10+)

```bash
# 1. Создать виртуальное окружение
python -m venv venv
source venv/bin/activate  # на Windows: venv\Scripts\activate

# 2. Установить зависимости
pip install -r requirements.txt

# 3. Конфигурация
cp .env.example .env
# Вписать GIGACHAT_AUTH_KEY из https://console.sber.ai (необходимо для реального запуска)
# DATABASE_URL можно оставить пустым — retrieve будет работать в fallback (без RAG)
# LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY опциональны — без них трейсинг отключен (no-op)

# 4. Запустить тесты (НЕ требует ключ, БД, Langfuse)
pytest -v              # 36+ тестов, всё на фейками (в-памяти)

# 5. Запустить тесты эваля (проверка eval-раннера без CI)
python -m evals.runner

# 6. Запустить приложение локально
uvicorn app.main:app --reload

# 7. Проверить здоровье
curl http://localhost:8000/health

# 8. Запустить пайплайн и встать на HITL-паузу
curl -X POST http://localhost:8000/forge \
  -H "Content-Type: application/json" \
  -d '{"task": "Напиши async-функцию для валидации email"}'
# -> {"thread_id": "<id>", "status": "awaiting_approval", ...}

# 9. Одобрить результат
curl -X POST http://localhost:8000/forge/<thread_id>/approve

# 10. Или отклонить с комментарием (вернёт к coder для доработки)
curl -X POST http://localhost:8000/forge/<thread_id>/reject \
  -H "Content-Type: application/json" \
  -d '{"feedback": "Добавь валидацию пустой строки"}'
```

### Human-in-the-loop (HITL)

После reviewer граф не завершается сам, а останавливается на человеческом gate
перед финалом (LangGraph `interrupt_before=["approval"]`). `POST /forge` доходит до
этой паузы и возвращает `status: "awaiting_approval"` вместе с `thread_id` и
промежуточными артефактами (`plan`/`code`/`verdict`). Дальше человек решает судьбу
результата по `thread_id`.

Поток (двойной ограничитель сохранён везде):

```
planner -> retrieve -> coder -> reviewer --(fix, итераций < 3)--> coder
                                         \--(pass или итераций >= 3)--> [ПАУЗА: approval]
                                                                            |
                                             approve -----> END (status approved)
                                             reject (итераций < 3) --> coder (доработка по feedback)
                                                                         |-> снова approval [ПАУЗА]
                                             reject (итераций >= 3) --> END (status rejected)
```

Ключевые моменты:
- После reviewer счётчик `iterations` увеличивается независимо от вердикта
- Reject с feedback не требует нового вызова LLM для decode: feedback идёт прямо в state
- Reject-доработка проходит через coder → reviewer → approval заново
- Лимит 3 итерации применяется ко всей цепочке (fix + reject-доработка), петля гарантированно завершается
- Состояние thread хранится в MemorySaver (в памяти, в БД пока нет — Postgres saver в roadmap)

Эндпоинты HITL:

```bash
# 1. Запустить пайплайн — встанет на паузу, вернёт thread_id и awaiting_approval
curl -X POST http://localhost:8000/forge \
  -H "Content-Type: application/json" \
  -d '{"task": "Напиши async-функцию для валидации email"}'
# -> {"thread_id": "<id>", "status": "awaiting_approval", "plan": ..., "code": ..., "verdict": ...}

# 2a. Одобрить — граф дойдёт до END
curl -X POST http://localhost:8000/forge/<thread_id>/approve
# -> {"status": "approved", "approval_decision": "approved", ...}

# 2b. Отклонить с комментарием — граф вернётся к coder (если есть запас итераций)
curl -X POST http://localhost:8000/forge/<thread_id>/reject \
  -H "Content-Type: application/json" \
  -d '{"feedback": "Добавь обработку пустой строки"}'
# человеческий feedback приоритетнее авто-вердикта ревьюера; после доработки снова awaiting_approval

# 3. История чекпойнтов для отката
curl http://localhost:8000/forge/<thread_id>/history
# -> [{"checkpoint_id": "...", "next": ["coder"], "status": "..."}, ...]

# 4. Откат к выбранному чекпойнту и повторный прогон (снова встанет на approval)
curl -X POST http://localhost:8000/forge/<thread_id>/rollback \
  -H "Content-Type: application/json" \
  -d '{"checkpoint_id": "<id из history>"}'
```

Состояние thread хранится в checkpointer. По умолчанию это `MemorySaver` —
он **не персистентен между рестартами процесса**: после перезапуска приложения
старые `thread_id` исчезнут, и approve/reject/rollback вернут `404`. Для
персистентности между рестартами подключается Postgres saver (опционально, итерация 3 roadmap).

### В Docker

```bash
# 1. Конфигурация
cp .env.example .env
# Вписать GIGACHAT_AUTH_KEY (для реального запуска)
# DATABASE_URL уже заполнена для docker-compose (postgres:5432)
# POSTGRES_PASSWORD тоже переопределяется из docker-compose.yml (по дефолту 'postgres', для прода — сильный пароль)

# 2. Запустить контейнеры (postgres + app)
docker compose up -d

# 3. Дождаться здоровья postgres (~5-10 сек) и запуска app
docker compose logs -f app
# Ждём сообщение "Uvicorn running on http://0.0.0.0:8000"

# 4. Проверить здоровье
curl http://localhost:8000/health

# 5. Логи приложения
docker compose logs -f app

# 6. Логи БД
docker compose logs postgres

# 7. Остановить
docker compose down

# 8. Очистить томы (данные БД)
docker compose down -v
```

Приложение будет доступно на `http://localhost:8000`.

**Сервисы:**
- **app** (localhost:8000): FastAPI, зависит от postgres (condition: service_healthy)
- **postgres** (localhost:5432): pgvector/pgvector:pg17 для RAG (гибридный поиск) и будущей HITL-персистентности

### Переменные окружения

| Переменная | Назначение | Дефолт |
|------------|-----------|--------|
| **GigaChat** |
| `GIGACHAT_AUTH_KEY` | Ключ авторизации GigaChat (из https://console.sber.ai) | пусто (требуется для реального запуска) |
| `GIGACHAT_MODEL` | Модель GigaChat | `GigaChat-2-Max` |
| `GIGACHAT_SCOPE` | Scope для корпоративного API | `GIGACHAT_API_CORP` |
| `GIGACHAT_TEMPERATURE` | Температура генерации (0-2) | `0.11` |
| `GIGACHAT_TIMEOUT` | Timeout в миллисекундах | `1000` |
| **Граф** |
| `MAX_REFLECTION_ITERATIONS` | Макс. итераций reflection-loop Coder ↔ Reviewer (+ reject-доработка) | `3` |
| **RAG** |
| `DATABASE_URL` | PostgreSQL DSN (asyncpg); пусто → retrieve fallback на пустой context | пусто или `postgresql://postgres:CHANGE_ME@postgres:5432/agent_forge` (в docker-compose) |
| `POSTGRES_PASSWORD` | Пароль postgres для docker-compose | `CHANGE_ME` (смените для прода!) |
| `GIGACHAT_EMBEDDINGS_MODEL` | Модель embeddings (GigaChat Embeddings) | `EmbeddingsGigaR` |
| `RAG_TOP_K` | Размер выдачи при RAG-поиске | `5` |
| `RAG_RRF_K` | Константа RRF (Reciprocal Rank Fusion) для гибридного поиска | `60` |
| **Observability (Langfuse)** |
| `LANGFUSE_ENABLED` | Включить/отключить трейсинг (даже с ключами) | не требуется; if both keys present then enabled |
| `LANGFUSE_PUBLIC_KEY` | Публичный ключ Langfuse; пусто → трейсинг отключен (no-op) | пусто |
| `LANGFUSE_SECRET_KEY` | Секретный ключ Langfuse | пусто |
| `LANGFUSE_HOST` | URL Langfuse инстанса | `https://cloud.langfuse.com` |

---

## Тесты

**36+ зелёных тестов**, всё гонится на фейковом LLM, без сети, БД и Langfuse:

```bash
# Все тесты
pytest -v

# По маркерам
pytest -v -m unit           # модульные: узлы, конфиг, RAG-репозиторий
pytest -v -m integration    # интеграционные: граф end-to-end, эндпоинты, HITL

# Запуск eval-раннера (проверка без CI)
python -m evals.runner
```

**Что тестируется:**
- smoke-тесты приложения: импорт FastAPI, конфиг, GET `/health`
- граф собирается, компилируется и инициализируется с реальным retrieve
- happy path: planner → retrieve → coder → reviewer → pass → approval
- reflection-loop: coder ↔ reviewer останавливается на `max_iterations=3`
- HITL-flow: граф останавливается перед approval, эндпоинты approve/reject/history/rollback работают
- reject как доработка: reject возвращает к coder, потом снова на approval (лимит сохранён)
- структурированный вывод: каждый узел возвращает валидный Pydantic-объект
- feedback на retry: coder при повторной итерации учитывает feedback от reviewer
- валидация эндпоинтов: POST `/forge` с корректным request/response, 422 на пустой task

**Тестовые LLM (fakes):**
- `fake_llm_pass` — всегда возвращает `verdict="pass"` (граф заканчивается за 1 итерацию)
- `fake_llm_always_fix` — всегда возвращает `verdict="fix"` (проверяет остановку по лимиту)

Фейк-LLM реализует интерфейс LangChain, возвращает структурированные объекты через Pydantic (не нужна сеть, не нужен ключ, не нужна БД).

**Eval-раннер:**
- Датасет: `evals/dataset.json` (задачи с ожидаемыми вердиктами, языками, кодом, статусом)
- Раннер вычисляет: pass-rate, avg latency, avg cost (детерминированная эвристика)
- Работает на фейк-LLM (для CI без сети)
- CI eval-gate запускает раннер и проверяет pass-rate >= порога (по умолчанию 1.0)

---

## Observability и метрики

**Langfuse трейсинг (реализовано):**
- Включен через переменные `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`
- Трейсирует cost, latency, tokens на каждый LLM-вызов и узел графа
- Без ключей — graceful no-op (граф не падает)
- Callbacks наследуются всеми вложенными runnable через run-config

**Eval-датасет и CI (реализовано):**
- `evals/dataset.json` — задачи с ожидаемыми вердиктами, языками, кодом, статусом
- `evals/runner.py` — вычисляет pass-rate, avg latency, avg cost (детерминированно на фейках)
- `.github/workflows/ci.yml` — шаг `eval-gate` запускает раннер и проверяет порог (1.0 на дефолте)
- Регрессия промпта/модели не проходит CI

**Дашборд (roadmap):**
- Метрики на узел (input/output токены, время выполнения, quality-сигналы из Langfuse)
- Audit trail решений человека (HITL: approve/reject с timestamp, feedback)

---

## Дорожная карта

**Итерация 1: Каркас + граф (завершена)**
- [x] Репо + структура + `.env.example` + Dockerfile
- [x] FastAPI: GET `/health`, POST `/forge`
- [x] GigaChat-клиент + промпты в `prompts/` (versioned)
- [x] LangGraph: planner → retrieve → coder → reviewer
- [x] Structured output (Pydantic) на всех узлах
- [x] Reflection-loop с ограничителями (`max_iterations=3` + счётчик в state)
- [x] MemorySaver checkpointer
- [x] 36 тестов на фейковом LLM (граф, эндпоинты, boundary cases)

**Итерация 2: RAG + Observability + Eval + HITL (завершена)**
- [x] PostgreSQL + pgvector в docker-compose.yml (service_healthy)
- [x] Узел `retrieve`: hybrid search (BM25/lexical + vector/semantic) через PgDocumentRepository
- [x] Langfuse: трейсинг cost/latency/tokens на узлах через LangChain callbacks
- [x] Eval-датасет + раннер: pass-rate, avg latency, avg cost (детерминировано на фейках)
- [x] CI eval-gate: GitHub Actions шаг, проверка порога
- [x] HITL: узел approval (interrupt_before), эндпоинты approve/reject/history/rollback
- [x] Reject как доработка: возврат к coder с человеческим feedback
- [x] 36+ тестов на фейках (в т.ч. HITL-flow)

**Итерация 3: Persistence + Audit (в очереди)**
- [ ] Postgres saver (вместо MemorySaver) для персистентности чекпойнтов между рестартами
- [ ] Audit trail: логирование approve/reject/rollback в БД с timestamp/user (требует модели пользователя)
- [ ] Дашборд метрик: графики по узлам из Langfuse

**Итерация 4: Инжиниринговые оптимизации (в очереди)**
- [ ] Parallelization retrieval: lexical_search + vector_search через asyncio.gather
- [ ] Weighted combination retrieve results (RRF или другая стратегия)
- [ ] Ingestion-скрипт: load docs → embed → index (в pgvector)

---

## Статус

`v0.2.0` — **production-ready срез корпоративной AI-платформы.** Реализованы 4 фичи: RAG (гибридный поиск), Langfuse observability, eval-gate в CI, HITL (approve/reject/rollback/history). Архитектура закрывает все компетенции роли AI/LLM Systems Engineer: оркестрация агентов, ограничители (reflection-loop, лимит итераций + reject-доработка), structured output, тестирование без сети, enterprise-level контроль (человеческий gate на финале, rollback через историю чекпойнтов). Roadmap ясна, следующие итерации (persistence + audit) независимы от текущего стека.
