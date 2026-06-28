# Agent Forge

> Узкий, но production-grade срез корпоративной AI-платформы: мультиагентный пайплайн **Planner → Coder → Reviewer** с reflection-петлёй, который по техзадаче на функцию/эндпоинт генерирует код, ревьюит его и итеративно чинит.

Это не «платформа из 12 агентов» — это 3 агента, доведённые до production-качества с полной observability, eval-датасетом и human-in-the-loop. Портфолио-проект под роль **AI/LLM Systems Engineer** (Enterprise Vibe Coding Engineer).

---

## Зачем этот проект

Большинство портфолио в AI Engineering — это чат-боты, простые RAG или один агент. Цепочка же из 12 LLM-звеньев на демо выглядит эффектно, но хрупка: ошибка накапливается, каждое звено множит вероятность мусора на выходе.

Agent Forge показывает другой уровень инженерного мышления — **глубина на узком срезе вместо ширины, которая разваливается при первом нажатии**:

- мультиагентная оркестрация с ограничителями и reflection;
- промпт как инженерный контракт (structured output + валидация);
- измеримость: eval-датасет, regression-тесты, трейсинг стоимости/латентности;
- enterprise-обвязка: retries, checkpoints, rollback, human-in-the-loop.

То есть закрывается ядро компетенций роли: **Agent Engineering · Tool Calling/Structured Output · Knowledge (RAG) · Evaluation & Observability · Enterprise Architecture**.

---

## Что делает система

Вход — техзадача на Python-функцию или эндпоинт. Выход — сгенерированный, отревьюенный и протестированный код + полный трейс прогона (стоимость, латентность, токены, качество).

```
Business task (ТЗ)
      │
      ▼
  Planner ──► декомпозиция в план (Pydantic), НЕ пишет код
      │
      ▼
  RAG retrieval ──► hybrid search по доке/конвенциям проекта → контекст
      │
      ▼
  Coder ──► генерит код по плану + контексту (structured output)
      │
      ▼
  Reviewer ──► статический разбор + прогон тестов → вердикт (pass/fix)
      │           │
      │     reflection loop (max_iterations=3, token budget)
      └──◄────────┘
      │ pass
      ▼
  Human approval (HITL, checkpoint) ──► rollback при reject
      │
      ▼
  Ready code + trace (Langfuse: cost/latency/tokens/quality)
```

### Роли агентов

| Агент | Ответственность | Принцип |
|-------|-----------------|---------|
| **Planner** | Декомпозирует ТЗ в структурированный план | Не пишет код — разделение ролей, разный контекст |
| **Coder** | Генерирует код по плану + контексту из RAG | Structured output, валидируется по схеме |
| **Reviewer** | Статический разбор + прогон тестов, вердикт `pass`/`fix` | Замыкает reflection-петлю на Coder |

---

## Архитектура

Async-first, оркестрация на **LangGraph** (StateGraph + conditional edges + checkpointer). Бэкенд по слоям: **Routers → Services → Repositories → Models**.

- **State** — `TypedDict` (состояние графа), **схемы** — Pydantic.
- **Узлы графа:** `planner` → `retrieve` → `coder` → `reviewer` → conditional edge (`fix` → coder / `done` → human).
- **Reflection-loop** Coder ↔ Reviewer ограничен `max_iterations=3` и token budget — иначе петля крутится бесконечно.
- **Checkpointer** даёт resume и rollback при reject на шаге human approval.

---

## Стек

| Слой | Технологии |
|------|------------|
| Backend | FastAPI (async), Pydantic (schemas + structured output), TypedDict (state) |
| Оркестрация | LangGraph — StateGraph, conditional edges, checkpointer |
| LLM | GigaChat-2-Max + GigaChat Embeddings (`scope=GIGACHAT_API_CORP`, `temperature=0.11`) |
| Knowledge | PostgreSQL + pgvector, hybrid search (BM25 + vector) |
| Observability | Langfuse (трейсинг, cost / latency / token), structured logging |
| Eval | pytest + кастомный eval-раннер по датасету задач |
| Инфра | Docker Compose, `.env` / `.env.example`, GitHub Actions (lint + test + eval-gate) |

---

## Ключевые инженерные решения

| Решение | Почему |
|---------|--------|
| 3 агента, не 12 | Цепочка из 12 LLM-звеньев накапливает ошибку и хрупка; узкий срез в production-качестве надёжнее и впечатляет сильнее |
| Planner не пишет код | Декомпозиция и реализация — разный контекст; смешение раздувает контекст и мешает дебагу |
| GigaChat-2-Max вместо OpenAI/Google | Корпоративный scope, без зависимостей от внешних провайдеров |
| Reflection с `max_iterations=3` + token budget | Без ограничителей петля Coder ↔ Reviewer не завершается |
| Hybrid search (BM25 + pgvector) | Лексика ловит точные имена/термины кода, вектор — смысл; вместе выше recall |
| Eval-gate в CI | Регрессия промпта/модели ловится автоматически, а не руками |
| Structured output через Pydantic | Промпт как контракт: валидация выхода, retry на несоответствие схеме |
| HITL на финальном шаге, не на каждом | Контроль на критичной точке без потери автономности пайплайна |

---

## Структура проекта

```
agent-forge/
├── app/
│   ├── routers/          # FastAPI-эндпоинты
│   ├── services/         # бизнес-логика, запуск графа
│   ├── repositories/     # доступ к данным (Postgres/pgvector)
│   ├── models/           # ORM-модели
│   ├── graph/            # LangGraph: state, nodes, edges
│   │   ├── state.py      # TypedDict state
│   │   ├── nodes.py      # planner / coder / reviewer / retrieve
│   │   └── graph.py      # сборка StateGraph + checkpointer
│   ├── schemas/          # Pydantic-схемы (план, код, вердикт)
│   └── llm/              # GigaChat-клиент
├── prompts/              # промпты отдельными файлами (versioned)
├── evals/                # eval-датасет + раннер
├── tests/                # pytest + regression-тесты промптов
├── .env.example
├── docker-compose.yml
└── README.md
```

> Промпты вынесены в `prompts/` отдельными файлами и версионируются — не хардкодятся в коде.

---

## Запуск

> Проект в стадии `idea` — раздел заполняется по мере реализации каркаса.

```bash
# 1. Конфигурация
cp .env.example .env
# заполнить GIGACHAT_AUTH_KEY и параметры подключения

# 2. Поднять окружение
docker compose up -d        # FastAPI + PostgreSQL(pgvector) + Langfuse

# 3. Запустить пайплайн на задаче
curl -X POST http://localhost:8000/forge \
  -H "Content-Type: application/json" \
  -d '{"task": "Напиши async-эндпоинт для создания пользователя с валидацией email"}'
```

### Переменные окружения

| Переменная | Назначение |
|------------|-----------|
| `GIGACHAT_AUTH_KEY` | Ключ авторизации GigaChat (из `.env`, не коммитить) |
| `DATABASE_URL` | Подключение к PostgreSQL + pgvector |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Трейсинг и метрики |

---

## Метрики и измеримость

Каждый прогон трассируется в Langfuse, на узел собираются:

- **cost** — токены (input/output) × цена модели, агрегировано на запуск;
- **latency** — время каждого шага и сквозное;
- **tokens** — потребление по агентам;
- **quality** — pass-rate по eval-датасету.

Eval-раннер прогоняет датасет из 10-15 эталонных задач; результаты (pass-rate, avg cost, avg latency) используются как **eval-gate в CI** — регрессия промпта или смена модели не проходят пайплайн молча.

---

## Дорожная карта

- [ ] Репо + структура + `.env.example`
- [ ] FastAPI-каркас + Docker Compose
- [ ] GigaChat-клиент + промпты в `prompts/` (versioned)
- [ ] LangGraph: planner → coder → reviewer (без reflection)
- [ ] Structured output (Pydantic) на всех узлах + retry на невалидный вывод
- [ ] Reflection-loop с ограничителями (`max_iterations`, token budget)
- [ ] RAG: pgvector + hybrid search по доке + retrieval-метрики
- [ ] Langfuse: трейсинг + cost / latency / token на каждый узел
- [ ] Eval-датасет (10-15 задач) + eval-раннер
- [ ] Regression-тесты промптов + CI eval-gate
- [ ] Human-in-the-loop + checkpoint / rollback
- [ ] Демо-видео + README с метриками

---

## Статус

`idea` — проектирование завершено (архитектура, ключевые решения, дорожная карта), реализация впереди.
