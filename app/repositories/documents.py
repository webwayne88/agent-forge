import asyncpg

from app.repositories.base import DocumentRepository
from app.schemas.rag import DocumentChunk, RetrievedChunk

# Лексический поиск через ts_rank: основной путь для русскоязычных запросов.
_LEXICAL_SQL = """
SELECT source, content, ts_rank(content_tsv, plainto_tsquery('russian', $1)) AS score
FROM documents
WHERE content_tsv @@ plainto_tsquery('russian', $1)
ORDER BY score DESC
LIMIT $2
"""

# Fallback на ILIKE: plainto_tsquery может вернуть пусто на коротких/спецсимвольных
# запросах — тогда без fallback лексическая ветка молча пустая и hybrid вырождается.
_LEXICAL_FALLBACK_SQL = """
SELECT source, content, 0.0::float4 AS score
FROM documents
WHERE content ILIKE '%' || $1 || '%'
LIMIT $2
"""

# Векторный поиск: оператор <=> — косинусное расстояние; score = 1 - distance.
_VECTOR_SQL = """
SELECT source, content, 1 - (embedding <=> $1) AS score
FROM documents
WHERE embedding IS NOT NULL
ORDER BY embedding <=> $1
LIMIT $2
"""

_INSERT_SQL = "INSERT INTO documents (source, content, embedding) VALUES ($1, $2, $3)"


class PgDocumentRepository(DocumentRepository):
    """Реализация репозитория поверх PostgreSQL + pgvector (asyncpg).

    Все запросы параметризованы ($1, $2, ...) — пользовательский query никогда
    не конкатенируется в SQL (защита от инъекций).
    """

    def __init__(self, pool: asyncpg.Pool):
        self._pool = pool

    async def lexical_search(self, query: str, limit: int) -> list[RetrievedChunk]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_LEXICAL_SQL, query, limit)
            # На пустой результат ts_rank пробуем ILIKE (короткие запросы без лексем)
            if not rows:
                rows = await conn.fetch(_LEXICAL_FALLBACK_SQL, query, limit)
        return [
            RetrievedChunk(content=r["content"], source=r["source"], score=float(r["score"]))
            for r in rows
        ]

    async def vector_search(
        self, embedding: list[float], limit: int
    ) -> list[RetrievedChunk]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(_VECTOR_SQL, embedding, limit)
        return [
            RetrievedChunk(content=r["content"], source=r["source"], score=float(r["score"]))
            for r in rows
        ]

    async def add_chunks(
        self, chunks: list[DocumentChunk], embeddings: list[list[float]]
    ) -> None:
        records = [
            (chunk.source, chunk.content, emb)
            for chunk, emb in zip(chunks, embeddings)
        ]
        async with self._pool.acquire() as conn:
            await conn.executemany(_INSERT_SQL, records)
