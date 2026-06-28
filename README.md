# Agent Forge

> Узкий, но production-grade срез корпоративной AI-платформы: мультиагентный пайплайн **Planner → Coder → Reviewer** с reflection-петлёй, который по техзадаче на функцию/эндпоинт генерирует код, ревьюит его и итеративно чинит.

Это не «платформа из 12 агентов» — это 3 агента, доведённые до production-качества с правильной архитектурой, ограничителями и тестированием. Observability, eval-датасет и human-in-the-loop — следующие итерации. Портфолио-проект под роль **AI/LLM Systems Engineer** (Enterprise Vibe Coding Engineer).

---

## Зачем этот проект

Большинство портфолио в AI Engineering — это чат-боты, простые RAG или один агент. Цепочка же из 12 LLM-звеньев на демо выглядит эффектно, но хрупка: ошибка накапливается, каждое звено множит вероятность мусора на выходе.

Agent Forge показывает другой уровень инженерного мышления — **глубина на узком срезе вместо ширины, которая разваливается при первом нажатии**:

**Реализовано сейчас:**
- мультиагентная оркестрация (planner → retrieve → coder → reviewer) с ограничителями (`max_iterations=3`) и reflection-loop;
- промпт как инженерный контракт: structured output через Pydantic, валидация выхода узлов;
- LLM инжектируется в узлы — граф нетестируем без подменяемости, 36 тестов гонятся на фейке без сети;
- reflection-loop с двойным ограничителем (счётчик в state + conditional edge) — гарантированно завершается.

**Roadmap (следующие итерации):**
- Knowledge: RAG (pgvector + hybrid search);
- Observability: Langfuse (cost, latency, tokens на узел);
- Evaluation: eval-датасет + CI eval-gate;
- Enterprise: human-in-the-loop, checkpoint/rollback.

То есть закрывается ядро компетенций роли: **Agent Engineering · Structured Output & Validation · Testing Without Network · Enterprise Architecture**.

---

## Что делает система

Вход — техзадача на Python-функцию или эндпоинт. Выход — сгенерированный план, код и вердикт ревьюера.

**Базовый flow (реализовано):**
```
Техзадача (ТЗ)
      │
      ▼
  Planner ──► декомпозирует в план (Pydantic)
      │
      ▼
  Retrieve ──► контекст (заглушка, RAG в roadmap)
      │
      ▼
  Coder ──► генерирует код по плану + контексту
      │
      ▼
  Reviewer ──► ревьюит код, вердикт pass/fix
      │           │
      │     reflection loop (max_iterations=3)
      └──◄────────┘
      │ pass
      ▼
  Результат: план + код + вердикт + iterations
```

**Будущие шаги (roadmap):**
```
  pass → Human approval (HITL, checkpoint) ──► rollback при reject (итерация 4)
  
  Все шаги → Langfuse трейсинг (cost/latency/tokens) (итерация 2)
```

### Роли агентов

| Агент | Ответственность | Реализация |
|-------|-----------------|-----------|
| **Planner** | Декомпозирует ТЗ в структурированный план; код НЕ пишет | Реализовано (`planner.md`, узел в graph.py) |
| **Retrieve** | Возвращает контекст для кодера | Заглушка (пустой контекст), RAG в roadmap |
| **Coder** | Генерирует код по плану + контексту; на retry учитывает feedback | Реализовано (`coder.md`, feedback loop) |
| **Reviewer** | Ревьюит код и выносит вердикт `pass`/`fix` | Реализовано (`reviewer.md`, conditional edge) |

---

## Архитектура

Async-first, оркестрация на **LangGraph** (StateGraph + conditional edges + checkpointer).

- **State** — `TypedDict` (состояние графа), **схемы** — Pydantic.
- **Узлы графа:** 
  - `planner` — декомпозирует ТЗ в структурированный план (`Plan`), код НЕ пишет
  - `retrieve` — **заглушка** (возвращает пустой контекст, RAG в roadmap)
  - `coder` — генерирует код по плану и контексту (`GeneratedCode`)
  - `reviewer` — ревьюит код, выносит вердикт `pass`/`fix` (`ReviewVerdict`)
- **Conditional edge** после reviewer: возврат к coder только если `verdict == "fix"` И `iterations < max_reflection_iterations`; иначе END
- **Reflection-loop** Coder ↔ Reviewer ограничен `max_iterations=3` (счётчик в state) — иначе петля крутится бесконечно
- **Checkpointer** (`MemorySaver`): каждый запрос — отдельный thread; resume готов, rollback/HITL в roadmap
- **LLM инжектируется** в узлы через фабрику — граф тестируется на фейке без сети

---

## Стек

| Слой | Технологии | Статус |
|------|------------|--------|
| **Backend** | FastAPI (async), Pydantic (schemas + structured output), TypedDict (state) | Реализовано |
| **Оркестрация** | LangGraph — StateGraph, conditional edges, MemorySaver checkpointer | Реализовано |
| **LLM** | GigaChat-2-Max через langchain-gigachat (`scope=GIGACHAT_API_CORP`, `temperature=0.11`) | Реализовано |
| **Knowledge** | Узел retrieve — заглушка; RAG (pgvector + hybrid search) | Roadmap (итерация 2) |
| **Observability** | Langfuse трейсинг (cost, latency, tokens) | Roadmap (итерация 2) |
| **Evaluation** | pytest (36 тестов на фейковом LLM); eval-датасет + CI gate | Roadmap (итерация 3) |
| **Инфра** | Docker Compose (app), python:3.11-slim, `.env.example`, pytest.ini | Реализовано |

---

## Ключевые инженерные решения (реализовано)

| Решение | Зачем | Статус |
|---------|-------|--------|
| **3 агента, не 12** | Цепочка из 12 LLM-звеньев накапливает ошибку и хрупка; узкий срез в production-качестве надёжнее | Реализовано |
| **Planner не пишет код** | Декомпозиция и реализация — разный контекст; смешение раздувает контекст и мешает дебагу | Реализовано (промпт, тесты) |
| **GigaChat-2-Max вместо OpenAI** | Корпоративный scope, нет зависимостей от внешних провайдеров | Реализовано (langchain-gigachat) |
| **Reflection с `max_iterations=3`** | Без ограничителей петля Coder ↔ Reviewer не завершается; двойной ограничитель (итерации + conditional edge) гарантирует конечность | Реализовано (state + conditional edge) |
| **LLM инжектируется, не импортируется** | Граф нетестируем без подменяемости; фейк в conftest.py позволяет гонять 36 тестов без сети и ключа | Реализовано (factory, fixture-based) |
| **Промпты в файлах, не в коде** | Версионирование, переиспользование, эксперименты без пересборки | Реализовано (prompts/ с README) |
| **Structured output через Pydantic** | Валидация выхода, retry на несоответствие схеме; промпт как контракт | Реализовано (Plan, GeneratedCode, ReviewVerdict) |

**Планируются (roadmap):**
| Решение | Зачем |
|---------|-------|
| **Hybrid search (BM25 + pgvector)** | Лексика ловит точные имена/термины кода, вектор — смысл; вместе выше recall |
| **Eval-gate в CI** | Регрессия промпта/модели ловится автоматически, не руками |
| **HITL на финальном шаге** | Контроль на критичной точке без потери автономности пайплайна |
| **Langfuse трейсинг** | Операционная видимость: cost, latency, tokens — метрики качества на нод |

---

## Структура проекта

```
agent-forge/
├── app/                         # основной пакет
│   ├── main.py                  # FastAPI-приложение
│   ├── config.py                # Pydantic Settings (GigaChat, max_iterations и т.п.)
│   ├── routers/
│   │   └── forge.py             # POST /forge
│   ├── graph/                   # LangGraph: состояние и узлы
│   │   ├── state.py             # TypedDict GraphState
│   │   ├── nodes.py             # planner, retrieve, coder, reviewer
│   │   ├── graph.py             # сборка StateGraph + MemorySaver
│   │   └── prompts.py           # загрузчик промптов из файлов
│   ├── schemas/
│   │   └── pipeline.py          # Pydantic: Plan, GeneratedCode, ReviewVerdict
│   └── llm/
│       └── factory.py           # get_llm() — фабрика GigaChat-клиента
├── prompts/                     # системные промпты (versioned)
│   ├── README.md                # конвенции, версионирование, плейсхолдеры
│   ├── planner.md               # версия 1.0.0, узел planner
│   ├── coder.md                 # версия 1.0.0, узел coder
│   └── reviewer.md              # версия 1.0.0, узел reviewer
├── tests/                       # pytest
│   ├── test_app.py              # smoke-тесты: импорт, конфиг, /health
│   ├── test_graph.py            # граф на фейковом LLM (happy path, loop boundary)
│   ├── test_endpoints.py        # интеграция: /forge endpoint
│   └── conftest.py              # fixtures: fake_llm_pass, fake_llm_always_fix
├── requirements.txt             # зависимости
├── Dockerfile                   # python:3.11-slim
├── docker-compose.yml           # один сервис: app (FastAPI)
├── pytest.ini                   # конфигурация pytest
├── .env.example                 # template переменных окружения
└── README.md                    # этот файл
```

**Ключевые файлы:**
- `app/graph/prompts.py` — загружает промпты из `prompts/*.md` при запуске узла (шаблонизация через плейсхолдеры)
- `app/graph/graph.py` — conditional edge после reviewer: `verdict == "fix"` И `iterations < max_reflection_iterations` → возврат к coder, иначе END
- `tests/conftest.py` — фейк-LLM, который возвращает структурированный вывод без обращения к API

---

## Что реализовано сейчас (каркас + граф)

**Полный граф Planner → Coder → Reviewer с reflection-loop и ограничителями**, готов к запуску:

- FastAPI-приложение (`app/main.py`): эндпоинты GET `/health` и POST `/forge`
- LangGraph-граф: planner (декомпозиция) → retrieve (заглушка, RAG в roadmap) → coder (генерация кода) → reviewer (статический разбор) → conditional edge с reflection-loop
- Structured output через Pydantic: `Plan`, `GeneratedCode`, `ReviewVerdict`
- GigaChat-2-Max через `langchain-gigachat` с `.with_structured_output()`
- Промпты в отдельных файлах (`prompts/` — planner.md, coder.md, reviewer.md) с версионированием
- LLM инжектируется в узлы — граф тестируется на фейковом LLM без сети
- Reflection-loop с двойным ограничителем: счётчик `iterations` в state + `max_reflection_iterations=3` в конфиге
- Checkpointer: `MemorySaver` для resume (rollback/HITL — roadmap)
- Тесты: pytest (36 зелёных), граф на фейковом LLM, smoke-тесты приложения
- Инфра: `requirements.txt`, `Dockerfile` (python:3.11-slim), `docker-compose.yml` (один сервис app), `.env.example`

**Пока нет** (следующие итерации):
- RAG (узел `retrieve` — заглушка)
- Langfuse / трейсинг
- Eval-датасет и CI eval-gate
- Human-in-the-loop (HITL-эндпоинт)
- PostgreSQL и pgvector

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
# Остальные переменные имеют дефолты и опциональны

# 4. Запустить тесты (НЕ требует ключ)
pytest -v              # 36 тестов, граф на фейковом LLM

# 5. Запустить приложение
uvicorn app.main:app --reload

# 6. Проверить здоровье
curl http://localhost:8000/health

# 7. Запустить пайплайн
curl -X POST http://localhost:8000/forge \
  -H "Content-Type: application/json" \
  -d '{"task": "Напиши async-функцию для валидации email"}'
```

### В Docker

```bash
# 1. Конфигурация
cp .env.example .env
# Вписать GIGACHAT_AUTH_KEY (для реального запуска)

# 2. Запустить контейнер
docker compose up -d

# 3. Логи
docker compose logs -f app

# 4. Остановить
docker compose down
```

Приложение будет доступно на `http://localhost:8000`.

### Переменные окружения

| Переменная | Назначение | Дефолт |
|------------|-----------|--------|
| `GIGACHAT_AUTH_KEY` | Ключ авторизации GigaChat (из console.sber.ai) | пусто |
| `GIGACHAT_MODEL` | Модель GigaChat | `GigaChat-2-Max` |
| `GIGACHAT_SCOPE` | Scope для корпоративного API | `GIGACHAT_API_CORP` |
| `GIGACHAT_TEMPERATURE` | Температура генерации (0-2) | `0.11` |
| `GIGACHAT_TIMEOUT` | Timeout в миллисекундах | `1000` |
| `MAX_REFLECTION_ITERATIONS` | Макс. итераций reflection-loop Coder ↔ Reviewer | `3` |

---

## Тесты

**36 зелёных тестов**, всё гонится на фейковом LLM без сети:

```bash
pytest -v           # все тесты (быстро, ~2 сек)
pytest -v -m unit   # модульные тесты узлов
pytest -v -m integration  # интеграционные тесты графа end-to-end
```

**Что тестируется:**
- smoke-тесты приложения: импорт FastAPI, конфиг, GET `/health`
- граф собирается и компилируется
- happy path: плanner → retrieve → coder → reviewer → pass
- reflection-loop: coder ↔ reviewer останавливается на `max_iterations=3`
- структурированный вывод: каждый узел возвращает валидный Pydantic-объект
- feedback на retry: coder при повторной итерации учитывает feedback от reviewer
- валидация эндпоинтов: POST `/forge` с корректным request/response, 422 на пустой task

**Тестовые LLM:**
- `fake_llm_pass` — всегда возвращает `verdict="pass"` (граф заканчивается за 1 итерацию)
- `fake_llm_always_fix` — всегда возвращает `verdict="fix"` (проверяет остановку по лимиту)

Фейк-LLM реализует интерфейс LangChain и возвращает структурированные объекты через `BaseModel` (не нужна сеть, не нужен ключ).

---

## Метрики и измеримость (roadmap)

На следующих итерациях:

- **Langfuse трейсинг:** каждый узел будет логировать cost, latency, tokens
- **Eval-датасет:** 10-15 эталонных задач с ground truth (код, который должен быть сгенерирован)
- **CI eval-gate:** регрессия промпта или модели не пройдут пайплайн — pass-rate, avg cost, avg latency
- **Метрики на узел:** input/output токены, время выполнения, quality-сигналы (reflection-iterations, feedback sentiment и т.п.)

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

**Итерация 2: RAG + Observability (в очереди)**
- [ ] PostgreSQL + pgvector в docker-compose.yml
- [ ] Узел `retrieve`: hybrid search (BM25 + semantic) по документации
- [ ] Langfuse: трейсинг, cost / latency / token на узел
- [ ] Метрики на эндпоинт `/forge`

**Итерация 3: Evaluation + CI (в очереди)**
- [ ] Eval-датасет: 10-15 задач с ground truth
- [ ] Eval-раннер: pass-rate, avg cost, avg latency
- [ ] GitHub Actions: lint + test + eval-gate (регрессия не проходит)
- [ ] Badge в README

**Итерация 4: Human-in-the-loop (в очереди)**
- [ ] Эндпоинт HITL: `/forge/{run_id}/approve` и `/forge/{run_id}/reject`
- [ ] Checkpoint/rollback: сохранение промежуточных состояний в БД
- [ ] Audit trail: логирование всех решений человека

---

## Статус

`v0.1.0` — **каркас + граф готовы, протестированы, готовы к запуску и расширению.** Архитектура закрывает все компетенции роли AI/LLM Systems Engineer (инженерия агентов, ограничители, structured output, тестирование без сети). Roadmap ясна, следующие итерации независимы (можно доделать любую).
