from functools import lru_cache

from langchain_gigachat import GigaChatEmbeddings

from app.config import settings


@lru_cache(maxsize=1)
def get_embeddings() -> GigaChatEmbeddings:
    """Создаёт клиент GigaChat Embeddings по параметрам из конфига.

    Единственная точка реального подключения к сети для эмбеддингов: узел
    retrieve и ingestion получают клиент как зависимость — так в тестах он
    подменяется фейком без обращения к API (аналогично get_llm()).
    """
    return GigaChatEmbeddings(
        credentials=settings.gigachat_auth_key,
        scope=settings.gigachat_scope,
        model=settings.gigachat_embeddings_model,
        verify_ssl_certs=False,
    )
