from pathlib import Path

# Промпты узлов лежат отдельными файлами в prompts/ (versioned), не в коде
PROMPTS_DIR = Path(__file__).resolve().parents[2] / "prompts"

# Кэш содержимого файлов: промпты в runtime не меняются, читаем один раз на имя
# (read_text — sync-блокирующий вызов, недопустим на каждый вызов async-узла)
_PROMPT_CACHE: dict[str, str] = {}


def load_prompt(name: str, **placeholders: str) -> str:
    """Читает промпт из prompts/<name>.md и подставляет плейсхолдеры.

    В файлах используется синтаксис {{ key }} (с пробелами). Отсутствующие
    значения подставляются как пустая строка — на первой итерации
    reviewer_feedback и retrieved_context пусты.
    """
    text = _PROMPT_CACHE.get(name)
    if text is None:
        text = (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
        _PROMPT_CACHE[name] = text
    for key, value in placeholders.items():
        text = text.replace("{{ " + key + " }}", value or "")
    return text
