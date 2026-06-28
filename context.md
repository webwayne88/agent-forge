Я была на конференции, где круная фин-тех компания рассказывала о появлении у них новой роли: Enterprise Vibe Coding (EVC) Engineer.
## Что такое EVC Engineer:
По сути это гибрид сразу нескольких профессий.

### Выполняет роль:
- архитектора
- менеджера AI-агентов
- разработчика
- prompt/context инженера
- AI Systems Engineer
- LLM Architect
- Agent Systems Designer

То есть человек уже не пишет промпты.
Он проектирует целые AI-производственные системы.

# Roadmap подготовки к роли Enterprise Vibe Coding (EVC) Engineer

> Цель — стать инженером нового поколения, который умеет проектировать, строить и сопровождать корпоративные AI-системы, мультиагентные платформы и AI-first продукты.

---

# 1. Требования к должности

## 1. LLM Architecture

Необходимо понимать внутреннее устройство современных LLM.

### Темы

- Transformer Architecture
- Attention Is All You Need
- Flash Attention
- Sparse Attention
- Sliding Window Attention
- Attention Sinks
- KV Cache
- Rotary Embeddings (RoPE)
- Mixture of Experts (MoE)
- Long Context
- Lost in the Middle
- Inference Pipeline
- Tokenization
- Context Window
- Sampling (Temperature / Top-P / Top-K)

---

## 2. Prompt & Context Engineering

Уметь проектировать промпты как инженерные контракты, а не как обычный текст.

### Темы

- Prompt as Contract
- Structured Prompting
- Few-shot Learning
- Zero-shot Learning
- Chain of Thought
- Tree of Thoughts
- ReAct
- Reflection
- Self-Consistency
- Prompt Chaining
- Prompt Versioning

### Context Engineering

- Context Assembly
- Semantic Chunking
- Context Compression
- Memory Management
- Context Prioritization
- Context Windows
- Long-term Memory
- Episodic Memory
- Semantic Memory

---

## 3. Agent Engineering

Понимать архитектуру мультиагентных систем.

### Темы

- Multi-Agent Systems
- Agent Orchestration
- Planner → Executor → Reviewer Pipeline
- Hierarchical Agents
- Swarm Architecture
- State Machines
- Retry Strategies
- Reflection Loops
- Task Decomposition
- Dynamic Agent Routing
- Shared Memory
- Agent Communication
- Event-driven Architecture

---

## 4. Tool Calling & Integration

LLM должны уметь безопасно взаимодействовать с внешним миром.

### Темы

- Function Calling
- Structured Outputs
- JSON Schema
- MCP (Model Context Protocol)
- API Integration
- Tool Selection
- Validation
- Error Recovery
- Retry Logic
- Sandbox Execution

---

## 5. Knowledge Engineering

Уметь проектировать интеллектуальную память системы.

### Темы

- Embeddings
- Vector Databases
- RAG
- Hybrid Search
- Semantic Search
- Knowledge Graph
- Neo4j
- GraphRAG
- Context Retrieval
- Retrieval Ranking

---

## 6. Software Engineering

AI-инженер должен быть полноценным разработчиком.

### Навыки

- Python
- TypeScript
- Git
- Docker
- REST API
- CI/CD
- Testing
- Architecture Patterns
- Async Programming
- Design Patterns

---

## 📊 7. AI Evaluation & Observability

Одна из самых недооценённых компетенций.

### Темы

- AI Evaluation
- LLM Benchmarks
- Hallucination Detection
- Prompt Regression Testing
- Observability
- OpenTelemetry
- Langfuse
- Cost Tracking
- Latency Monitoring
- Token Usage
- Quality Metrics

---

## 8. Enterprise AI Architecture

Навыки проектирования промышленных AI-систем.

### Темы

- AI Governance
- Security
- Permission Management
- Human-in-the-loop
- Compliance
- AI Pipelines
- Workflow Automation
- Enterprise Architecture
- Scalability
- Fault Tolerance

---

# 2. Вопросы для подготовки к собеседованию

## LLM Architecture

- Как работает механизм Attention?
- Почему появился Flash Attention?
- Чем Sparse Attention отличается от обычного?
- Что такое KV Cache?
- Почему длинный контекст ухудшает качество модели?
- Что означает Lost in the Middle?
- Когда Long Context лучше RAG?
- Когда RAG лучше Long Context?
- Что такое MoE?
- Как влияет Temperature?

---

## Prompt Engineering

- Что такое Prompt as Contract?
- Как писать устойчивые промпты?
- Что такое Structured Outputs?
- Когда использовать Few-shot?
- Когда Chain of Thought ухудшает результат?
- Как бороться с Prompt Injection?
- Как проектировать промпты для production?

---

## Context Engineering

- Как формируется контекст?
- Какие части контекста самые важные?
- Как проектировать память агента?
- Что такое Semantic Chunking?
- Как уменьшить стоимость длинного контекста?
- Как бороться с Lost in the Middle?
- Когда использовать компрессию контекста?

---

## Agent Engineering

- Когда достаточно одного агента?
- Когда нужна мультиагентная архитектура?
- Как разделять роли?
- Как избежать бесконечных циклов?
- Как организовать коммуникацию между агентами?
- Как строить shared memory?
- Как проектировать Planner?
- Почему Planner не должен писать код?
- Что такое Reflection?
- Как масштабировать систему агентов?

---

## Knowledge Engineering

- Как работают Embeddings?
- Почему Vector DB не хранит знания?
- Что такое Hybrid Search?
- Когда нужен GraphRAG?
- Чем отличается Knowledge Graph от Vector DB?
- Как оценивать качество Retrieval?

---

## Tool Calling

- Как работает Function Calling?
- Что такое MCP?
- Как валидировать Structured Outputs?
- Что делать при ошибке инструмента?
- Как проектировать безопасные Tool Calls?
- Как ограничивать доступ агентов к инструментам?

---

## Software Engineering

- Как организовать архитектуру AI-платформы?
- Как тестировать AI?
- Как проектировать CI/CD для LLM?
- Как версионировать промпты?
- Как организовать конфигурацию моделей?

---

## Enterprise

- Как считать стоимость AI?
- Как оценивать качество AI?
- Как логировать работу агентов?
- Как проектировать отказоустойчивость?
- Какие метрики важны для Enterprise AI?
- Как организовать Human-in-the-loop?

---

# 3. Проект для портфолио

# Enterprise AI Engineering Platform

## Идея

Создать платформу, которая автоматически превращает бизнес-задачу в готовое программное решение с помощью мультиагентной команды.

Вместо демонстрации одного AI-агента проект показывает полноценную инженерную организацию, где каждый агент выполняет свою профессиональную роль.

---

## Архитектура

```text
Business Request
        │
        ▼
 Product Manager
        │
        ▼
 Requirements Analyst
        │
        ▼
 System Architect
        │
        ▼
 Technical Planner
        │
        ▼
 Research Agent
        │
        ▼
 Coding Team
        │
        ▼
 Code Reviewer
        │
        ▼
 QA Engineer
        │
        ▼
 Security Review
        │
        ▼
 Documentation
        │
        ▼
 DevOps
        │
        ▼
 Ready Product
```

---

## Что демонстрирует проект

### LLM Architecture

- работа с длинным контекстом
- управление памятью
- контекстная инженерия

---

### Agent Engineering

- оркестрация агентов
- маршрутизация задач
- распределение ролей
- автоматический выбор исполнителя

---

### Tool Calling

- MCP
- Function Calling
- Git
- Docker
- IDE
- терминал
- браузер
- внешние API

---

### Knowledge

- RAG
- Vector Search
- Knowledge Graph
- документация проекта
- долговременная память

---

### Evaluation

- автоматический Review
- автоматические тесты
- оценка качества решений
- self-reflection
- regression testing

---

### Enterprise Features

- observability
- telemetry
- стоимость каждого запуска
- время выполнения
- логирование
- retries
- checkpoints
- human approval
- rollback

---

## Почему именно этот проект?

Большинство кандидатов демонстрируют чат-ботов, простые RAG-системы или одного AI-агента.

Такой проект показывает совершенно другой уровень инженерного мышления: не отдельную модель, а полноценную AI-платформу, способную автоматически организовывать процесс разработки.

Он одновременно демонстрирует понимание архитектуры LLM, проектирование контекста, построение мультиагентных систем, интеграцию инструментов, инженерные практики разработки и эксплуатацию AI в production.

---

## В чём его уникальность

Проект объединяет практически все современные направления AI Engineering в единую систему:

- Context Engineering
- Agent Engineering
- Enterprise Architecture
- Knowledge Engineering
- AI Evaluation
- Observability
- Tool Calling
- Prompt Engineering
- Software Engineering
- DevOps

По сути, это не демонстрация одной технологии, а прототип корпоративной AI-платформы следующего поколения.

---

## Почему проект производит "вау"-эффект

Во время демонстрации можно показать не просто ответ модели, а полный жизненный цикл разработки:

1. Пользователь формулирует бизнес-задачу.
2. AI автоматически декомпозирует её.
3. Формируется команда специализированных агентов.
4. Каждый агент выполняет свою часть работы.
5. Код автоматически проходит ревью и тестирование.
6. Генерируется документация.
7. Выполняется деплой.
8. Пользователь наблюдает весь процесс в режиме реального времени через визуальный граф выполнения, метрики стоимости, логи и состояние каждого агента.

Такой уровень демонстрации показывает способность проектировать не отдельные AI-функции, а сложные корпоративные AI-системы, что максимально соответствует ожиданиям от роли Enterprise Vibe Coding Engineer.