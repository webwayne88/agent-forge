# Contributing

Спасибо за интерес к Agent Forge. Ниже — как развернуть проект, прогнать
проверки и оформить вклад.

## Окружение

```bash
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # заполнить GIGACHAT_AUTH_KEY (и DATABASE_URL для RAG)
```

## Проверки перед коммитом

Линт и тесты должны быть зелёными — ровно как в CI:

```bash
ruff check app/ tests/ evals/
DATABASE_URL="" LANGFUSE_ENABLED="false" GIGACHAT_AUTH_KEY="" pytest -q
```

> Тесты гоняются в **герметичном окружении** (пустые DSN/ключи): LLM подменяется
> фейком, БД/внешние сервисы не дёргаются. Если оставить локальный `.env` с
> реальным `DATABASE_URL`, тесты потянут сеть и дадут ложные падения.

Eval-gate (на фейк-LLM, без сети):

```bash
python -m evals.runner
```

## Стиль и архитектура

- Python 3.10-совместимый код (в LangGraph state — `from typing_extensions import TypedDict`).
- Архитектура: Routers → Services → Repositories → Models; граф — в `app/graph/`.
- Промпты — в `prompts/` отдельными файлами, не в коде.
- Конфиг — Pydantic Settings из `.env`, без hardcode.
- LLM/эмбеддинги инжектируются в узлы (тестируемость без сети).
- Минимальный diff: меняй только то, что относится к задаче.

## Коммиты и ветки

- Формат сообщений — [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `docs:`, `test:`, `ci:`, `refactor:`, `chore:`.
- Заголовок — на английском, тело (если нужно) — на русском.
- Рабочая ветка — `dev`, стабильная — `main`. PR открывается в `dev`/`main`,
  CI (ruff + pytest + eval-gate) должен быть зелёным.

## Pull Request

1. Форкни репозиторий и создай ветку от `dev`.
2. Внеси изменения + тесты на новую логику.
3. Прогони линт и тесты локально.
4. Оформи PR по шаблону; опиши, что и зачем менялось.
