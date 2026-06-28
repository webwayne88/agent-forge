"""Langfuse observability: трейсинг cost/latency/tokens на узлах графа.

Точка интеграции — get_callbacks(): возвращает список LangChain callbacks,
который прокидывается в run-config при ainvoke графа. LangGraph наследует
эти callbacks во все вложенные runnable (LLM-вызовы узлов), поэтому трейсинг
покрывает весь граф без правок самих узлов.

Без ключей трейсинг — no-op: get_callbacks() возвращает пустой список,
граф и эндпоинт не падают.
"""

import logging
import os
from functools import lru_cache

from app.config import settings

logger = logging.getLogger(__name__)

# Импорт langfuse под try/except: отсутствие пакета (например в урезанном CI без сети)
# не должно ломать импорт приложения. Флаг доступности проверяется при создании handler.
try:
    from langfuse import Langfuse
    from langfuse.langchain import CallbackHandler

    _LANGFUSE_AVAILABLE = True
except ImportError:
    Langfuse = None
    CallbackHandler = None
    _LANGFUSE_AVAILABLE = False


def _should_init_langfuse() -> bool:
    """Все условия готовности трейсинга одной проверкой: пакет доступен,
    трейсинг включён и заданы оба ключа. Иначе — no-op."""
    return bool(
        _LANGFUSE_AVAILABLE
        and settings.langfuse_enabled
        and settings.langfuse_public_key
        and settings.langfuse_secret_key
    )


@lru_cache(maxsize=1)
def get_langfuse_handler():
    """Возвращает Langfuse CallbackHandler или None (no-op).

    Handler создаётся только когда выполнены все условия готовности
    (см. _should_init_langfuse). Любая ошибка инициализации (например, проблемы
    auth/сети) логируется без значений ключей и возвращает None — обзёрвабилити
    не валит граф.
    """
    if not _should_init_langfuse():
        return None

    try:
        # langfuse v4 CallbackHandler читает креды из глобального клиента/окружения,
        # а не из аргументов конструктора. Выставляем env и инициализируем клиент,
        # чтобы трейсы реально уходили.
        os.environ["LANGFUSE_PUBLIC_KEY"] = settings.langfuse_public_key
        os.environ["LANGFUSE_SECRET_KEY"] = settings.langfuse_secret_key
        os.environ["LANGFUSE_HOST"] = settings.langfuse_host
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return CallbackHandler()
    except Exception as exc:
        # Не логируем значения ключей, только факт ошибки
        logger.warning("Не удалось инициализировать Langfuse, трейсинг выключен: %s", exc)
        return None


def get_callbacks() -> list:
    """Список callbacks для прокидывания в run-config графа.

    [handler] если трейсинг активен, иначе [] — это и есть no-op.
    """
    handler = get_langfuse_handler()
    return [handler] if handler is not None else []
