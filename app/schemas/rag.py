from pydantic import BaseModel, Field


class RetrievedChunk(BaseModel):
    """Найденный фрагмент документа — контракт между репозиторием,
    RRF-слиянием и узлом retrieve."""

    content: str = Field(description="Текст фрагмента")
    source: str = Field(description="Источник (путь к файлу)")
    score: float = Field(default=0.0, description="Релевантность (ts_rank или 1 - cosine_distance)")


class DocumentChunk(BaseModel):
    """Фрагмент для ingestion: текст + источник (эмбеддинг считается отдельно)."""

    content: str = Field(description="Текст фрагмента")
    source: str = Field(description="Источник (путь к файлу)")
