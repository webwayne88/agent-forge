from functools import lru_cache

from langchain_gigachat import GigaChat

from app.config import settings


@lru_cache(maxsize=1)
def get_llm() -> GigaChat:
    """Создаёт клиент GigaChat по параметрам из конфига.

    Это единственная точка реального подключения к сети: узлы графа не
    создают LLM сами, а получают его как зависимость (см. фабрику) — так в
    тестах LLM подменяется фейком без обращения к API.
    """
    return GigaChat(
        credentials=settings.gigachat_auth_key,
        scope=settings.gigachat_scope,
        model=settings.gigachat_model,
        temperature=settings.gigachat_temperature,
        timeout=settings.gigachat_timeout,
        verify_ssl_certs=False,
        profanity_check=False,
    )
