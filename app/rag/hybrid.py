import asyncio

from app.repositories.base import DocumentRepository
from app.schemas.rag import RetrievedChunk


def _chunk_key(chunk: RetrievedChunk) -> tuple[str, str]:
    """Ключ дедупликации: один и тот же фрагмент из обоих списков — один документ."""
    return (chunk.source, chunk.content)


def reciprocal_rank_fusion(
    lexical: list[RetrievedChunk],
    vector: list[RetrievedChunk],
    k: int,
    top_k: int,
) -> list[RetrievedChunk]:
    """Слияние лексического и векторного списков через RRF.

    Для каждого документа суммируется 1/(k + rank) по обоим спискам (rank с 0).
    Документ, встретившийся в обоих списках, получает больший суммарный score и
    ранжируется выше. Детерминированно, без сети и БД.
    """
    scores: dict[tuple[str, str], float] = {}
    chunks: dict[tuple[str, str], RetrievedChunk] = {}

    for ranked in (lexical, vector):
        for rank, chunk in enumerate(ranked):
            key = _chunk_key(chunk)
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank)
            # Первое вхождение фиксирует объект чанка (дедупликация по ключу)
            chunks.setdefault(key, chunk)

    fused = [
        RetrievedChunk(content=chunks[key].content, source=chunks[key].source, score=score)
        for key, score in scores.items()
    ]
    # Сортировка по RRF-score убыванием; стабильна по порядку появления при равенстве
    fused.sort(key=lambda c: c.score, reverse=True)
    return fused[:top_k]


async def hybrid_search(
    repo: DocumentRepository,
    embeddings,
    query: str,
    top_k: int,
    rrf_k: int,
) -> list[RetrievedChunk]:
    """Гибридный поиск: параллельно лексический поиск и векторный (по эмбеддингу
    запроса), затем слияние через RRF.

    repo и embeddings принимаются как аргументы — полностью мокаются в тестах.
    """
    # Лексический поиск и подсчёт эмбеддинга запроса идут параллельно
    lexical_task = repo.lexical_search(query, top_k)
    embed_task = embeddings.aembed_query(query)
    lexical, query_embedding = await asyncio.gather(lexical_task, embed_task)

    vector = await repo.vector_search(query_embedding, top_k)
    return reciprocal_rank_fusion(lexical, vector, rrf_k, top_k)
