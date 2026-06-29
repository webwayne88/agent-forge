## Summary
<!-- Что и зачем меняется (1-3 пункта) -->

## Changes
<!-- Краткий список изменений по файлам/модулям -->

## Test plan
- [ ] `ruff check app/ tests/ evals/` — чисто
- [ ] `DATABASE_URL="" LANGFUSE_ENABLED="false" GIGACHAT_AUTH_KEY="" pytest -q` — зелёный
- [ ] `python -m evals.runner` — pass-rate в норме
- [ ] <!-- ручная проверка, если применимо -->

## Checklist
- [ ] Изменения минимальны и относятся к задаче
- [ ] Промпты (если менялись) — в `prompts/`, не в коде
- [ ] Документация (README/CHANGELOG) обновлена при необходимости
