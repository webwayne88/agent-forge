import asyncio
from pathlib import Path

from app.db.pool import close_pool, get_pool
from app.llm.embeddings import get_embeddings
from app.repositories.documents import PgDocumentRepository
from app.schemas.rag import DocumentChunk

# Корень проекта (на уровень выше scripts/)
_ROOT = Path(__file__).resolve().parent.parent
# Источники доки/конвенций проекта для индексации
_SOURCES = [
    _ROOT / "CLAUDE.md",
    _ROOT / "README.md",
    _ROOT / "prompts",
    _ROOT / "docs",
]
# Максимальный размер чанка в символах (чанкинг по абзацам с укрупнением)
_MAX_CHUNK_CHARS = 1500
# Размер батча эмбеддингов: GigaChat Embeddings API ограничивает число текстов на
# вызов — большой объём доки бьём на батчи, иначе HTTP 413/429 или высокая латентность.
_EMBED_BATCH_SIZE = 32


def _iter_files(paths: list[Path]):
    """Рекурсивно собирает .md/.txt из переданных файлов и директорий."""
    for path in paths:
        if path.is_file() and path.suffix in (".md", ".txt"):
            yield path
        elif path.is_dir():
            for sub in sorted(path.rglob("*")):
                if sub.is_file() and sub.suffix in (".md", ".txt"):
                    yield sub


def _chunk_text(text: str) -> list[str]:
    """Чанкинг по абзацам: соседние абзацы склеиваются, пока не превышен лимит."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > _MAX_CHUNK_CHARS:
            chunks.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def _collect_chunks() -> list[DocumentChunk]:
    """Читает все источники и режет на чанки с привязкой к относительному пути."""
    result: list[DocumentChunk] = []
    for file in _iter_files(_SOURCES):
        text = file.read_text(encoding="utf-8")
        source = str(file.relative_to(_ROOT))
        for chunk in _chunk_text(text):
            result.append(DocumentChunk(content=chunk, source=source))
    return result


async def _embed_in_batches(embeddings_client, texts: list[str]) -> list[list[float]]:
    """Считает эмбеддинги батчами по _EMBED_BATCH_SIZE, сохраняя порядок текстов.

    Батчи идут последовательно — не перегружаем API параллельными запросами
    (rate-limit). Возвращает плоский список векторов в порядке исходных текстов.
    """
    vectors: list[list[float]] = []
    for start in range(0, len(texts), _EMBED_BATCH_SIZE):
        batch = texts[start : start + _EMBED_BATCH_SIZE]
        vectors.extend(await embeddings_client.aembed_documents(batch))
    return vectors


async def _apply_schema(pool) -> None:
    """Применяет DDL из schema.sql (extension, таблица, индексы)."""
    schema_sql = (_ROOT / "app" / "db" / "schema.sql").read_text(encoding="utf-8")
    async with pool.acquire() as conn:
        await conn.execute(schema_sql)


async def main() -> None:
    """Ingestion: применяет схему, считает эмбеддинги доки и пишет в pgvector.

    Требует живого Postgres и реального ключа GigaChat — в CI/тестах не
    запускается, только импортируется (smoke). Запуск: python -m scripts.ingest
    """
    pool = await get_pool()
    try:
        await _apply_schema(pool)
        chunks = _collect_chunks()
        if not chunks:
            print("Нет документов для индексации.")
            return
        embeddings_client = get_embeddings()
        vectors = await _embed_in_batches(embeddings_client, [c.content for c in chunks])
        repo = PgDocumentRepository(pool)
        await repo.add_chunks(chunks, vectors)
        print(f"Проиндексировано чанков: {len(chunks)}")
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(main())
