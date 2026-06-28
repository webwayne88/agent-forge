from abc import ABC, abstractmethod

from app.schemas.rag import DocumentChunk, RetrievedChunk


class DocumentRepository(ABC):
    """Интерфейс доступа к документам RAG.

    Узел retrieve и оркестратор hybrid_search зависят от этой абстракции, а не
    от asyncpg — поэтому в тестах подставляется фейк-репозиторий без живой БД.
    """

    @abstractmethod
    async def lexical_search(self, query: str, limit: int) -> list[RetrievedChunk]:
        """Лексический поиск (ts_rank с ILIKE-fallback)."""

    @abstractmethod
    async def vector_search(
        self, embedding: list[float], limit: int
    ) -> list[RetrievedChunk]:
        """Векторный поиск по косинусной близости."""

    @abstractmethod
    async def add_chunks(
        self, chunks: list[DocumentChunk], embeddings: list[list[float]]
    ) -> None:
        """Батчевая запись фрагментов с эмбеддингами (ingestion)."""
