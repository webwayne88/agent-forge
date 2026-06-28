import asyncio

import asyncpg
from pgvector.asyncpg import register_vector

from app.config import settings

# Ленивый singleton пула: не создаётся при импорте, т.к. database_url может быть
# пуст (тесты/каркас без живой БД). Создаётся только по первому запросу/в ingestion.
_pool: asyncpg.Pool | None = None
# Защита от гонки: при параллельных первых вызовах без lock create_pool мог бы
# выполниться несколько раз, и лишние пулы утекли бы без закрытия.
_pool_lock = asyncio.Lock()


async def _init_connection(conn: asyncpg.Connection) -> None:
    """Регистрирует кодек pgvector на каждом новом соединении пула —
    иначе тип vector не сериализуется/десериализуется asyncpg."""
    await register_vector(conn)


async def get_pool() -> asyncpg.Pool:
    """Возвращает (создавая при первом вызове) пул соединений asyncpg."""
    global _pool
    # Double-checked locking: быстрый путь без захвата lock, если пул уже готов.
    if _pool is None:
        async with _pool_lock:
            if _pool is None:
                _pool = await asyncpg.create_pool(
                    settings.database_url,
                    init=_init_connection,
                    min_size=settings.db_pool_min_size,
                    max_size=settings.db_pool_max_size,
                )
    return _pool


async def close_pool() -> None:
    """Закрывает пул (graceful shutdown)."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None
