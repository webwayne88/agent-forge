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


settings = Settings()
