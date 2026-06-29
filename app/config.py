from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # GigaChat: ключ может быть пустым в каркасе/тестах — реальный вызов идёт только в get_llm()
    gigachat_auth_key: str = ""
    gigachat_model: str = "GigaChat-2-Max"
    gigachat_scope: str = "GIGACHAT_API_CORP"
    gigachat_temperature: float = 0.11
    gigachat_timeout: int = 1000

    # Ограничитель reflection-петли Coder <-> Reviewer
    max_reflection_iterations: int = 3

    # Число повторов structured output при None/ошибке парсинга (реальный GigaChat
    # иногда отдаёт пустой/невалидный структурированный вывод)
    structured_output_retries: int = 2

    # Способ structured output langchain-gigachat. Дефолт библиотеки "function_calling"
    # с GigaChat-2-Max СТАБИЛЬНО возвращает None (модель не вызывает tool), а
    # "json_schema" даёт 500 на эндпоинте. Рабочий способ — "format_instructions":
    # библиотека сама добавляет JSON-format-instructions trailing-сообщением и
    # парсит ответ через PydanticOutputParser (промпты в prompts/ менять не нужно).
    structured_output_method: str = "format_instructions"

    # RAG: asyncpg DSN (пуст в каркасе/тестах — пул создаётся только при ingestion/живом запуске)
    database_url: str = ""
    # Размер пула соединений asyncpg (тюнинг под нагрузку без пересборки образа)
    db_pool_min_size: int = 2
    db_pool_max_size: int = 10
    # GigaChat Embeddings: модель и размерность вектора (должна совпадать с DDL).
    # Реальные GigaChat Embeddings отдают 2560-мерный вектор. 2560 > 2000 (лимит
    # HNSW для типа vector), поэтому в схеме колонка — halfvec(2560) + HNSW по
    # halfvec_cosine_ops (halfvec поддерживает HNSW до 4000 измерений).
    gigachat_embeddings_model: str = "EmbeddingsGigaR"
    embedding_dim: int = 2560
    # Параметры hybrid search
    rag_top_k: int = 5
    rag_rrf_k: int = 60

    # Langfuse observability: ключи пустые в каркасе/тестах — реальный трейсинг
    # включается только при наличии обоих ключей (см. app/observability/langfuse.py)
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    langfuse_enabled: bool = True


settings = Settings()
