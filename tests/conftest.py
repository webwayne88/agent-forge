"""Фикстуры для тестов Agent Forge.

FakeLLM и готовые FAKE_* объекты живут в app/testing/fakes.py (общий с evals/),
здесь они только реэкспортируются для совместимости импортов в тестах.
Контракт: объект с методом with_structured_output(Schema) → объект с async ainvoke(messages).
"""

import pytest

from app.config import settings
from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict
from app.testing.fakes import (
    FAKE_CODE,
    FAKE_PLAN,
    FAKE_VERDICT_FIX,
    FAKE_VERDICT_PASS,
    FakeLLM,
)

__all__ = [
    "FAKE_CODE",
    "FAKE_PLAN",
    "FAKE_VERDICT_FIX",
    "FAKE_VERDICT_PASS",
    "FakeLLM",
]


@pytest.fixture
def fake_llm_pass():
    """Фейк: reviewer всегда возвращает pass."""
    return FakeLLM(
        {
            Plan: FAKE_PLAN,
            GeneratedCode: FAKE_CODE,
            ReviewVerdict: FAKE_VERDICT_PASS,
        }
    )


@pytest.fixture
def fake_llm_always_fix():
    """Фейк: reviewer всегда возвращает fix — для проверки остановки reflection-петли."""
    return FakeLLM(
        {
            Plan: FAKE_PLAN,
            GeneratedCode: FAKE_CODE,
            ReviewVerdict: FAKE_VERDICT_FIX,
        }
    )


@pytest.fixture
def initial_state():
    """Начальное состояние графа для тестов (включает HITL-поля)."""
    return {
        "task": "Напиши функцию hello world",
        "plan": None,
        "context": "",
        "code": None,
        "verdict": None,
        "iterations": 0,
        "status": "new",
        "approval_decision": None,
        "approval_feedback": "",
    }


class FakeDocumentRepository:
    """Фейк-репозиторий для RAG-тестов без живой БД.

    Возвращает заранее заданные списки чанков по методам lexical/vector search.
    Реализует контракт DocumentRepository.
    """

    def __init__(self, lexical_results=None, vector_results=None):

        self._lexical = lexical_results if lexical_results is not None else []
        self._vector = vector_results if vector_results is not None else []
        self.lexical_calls = 0
        self.vector_calls = 0

    async def lexical_search(self, query: str, limit: int):
        self.lexical_calls += 1
        return self._lexical[:limit]

    async def vector_search(self, embedding: list, limit: int):
        self.vector_calls += 1
        return self._vector[:limit]

    async def add_chunks(self, chunks, embeddings):
        pass


class FakeEmbeddings:
    """Фейк эмбеддингов для RAG-тестов без сети.

    aembed_query возвращает вектор нужной размерности.
    """

    def __init__(self, dim: int = settings.embedding_dim):
        self._dim = dim
        self.embed_calls = 0

    async def aembed_query(self, text: str) -> list[float]:
        self.embed_calls += 1
        return [0.1] * self._dim

    async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
        return [[0.1] * self._dim for _ in texts]


@pytest.fixture
def fake_repo():
    """Фейк-репозиторий с тестовыми чанками."""
    from app.schemas.rag import RetrievedChunk

    lexical = [
        RetrievedChunk(content="Контент документа 1", source="doc1.md", score=0.9),
        RetrievedChunk(content="Контент документа 2", source="doc2.md", score=0.7),
    ]
    vector = [
        RetrievedChunk(content="Контент документа 2", source="doc2.md", score=0.8),
        RetrievedChunk(content="Контент документа 3", source="doc3.md", score=0.6),
    ]
    return FakeDocumentRepository(lexical_results=lexical, vector_results=vector)


@pytest.fixture
def fake_embeddings():
    """Фейк эмбеддингов."""
    return FakeEmbeddings(dim=settings.embedding_dim)
