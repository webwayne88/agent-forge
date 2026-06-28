"""Тесты RAG: hybrid_search (чистая функция), retrieve_node, RRF-слияние.

БД и сеть не используются — всё на фейках из conftest.
"""

import pytest

from app.graph.nodes import make_retrieve_node, _format_context
from app.rag.hybrid import hybrid_search, reciprocal_rank_fusion
from app.schemas.rag import RetrievedChunk
from tests.conftest import FakeDocumentRepository, FakeEmbeddings


# ---------------------------------------------------------------------------
# reciprocal_rank_fusion — чистая функция, мокать ничего не нужно
# ---------------------------------------------------------------------------


class TestReciprocalRankFusion:
    def _chunk(self, content, source, score=0.0):
        return RetrievedChunk(content=content, source=source, score=score)

    def test_empty_lists_return_empty(self):
        """RRF на пустых списках возвращает пустой результат."""
        result = reciprocal_rank_fusion([], [], k=60, top_k=5)
        assert result == []

    def test_single_list_returns_top_k(self):
        """RRF с одним источником возвращает top_k из него."""
        lexical = [self._chunk(f"doc{i}", f"src{i}") for i in range(10)]
        result = reciprocal_rank_fusion(lexical, [], k=60, top_k=3)
        assert len(result) == 3

    def test_intersection_ranked_higher(self):
        """Документ, встречающийся в обоих списках, ранжируется выше одиночных."""
        shared = self._chunk("общий контент", "shared.md")
        lexical_only = self._chunk("только в лексическом", "lex.md")
        vector_only = self._chunk("только в векторном", "vec.md")

        lexical = [shared, lexical_only]
        vector = [shared, vector_only]

        result = reciprocal_rank_fusion(lexical, vector, k=60, top_k=3)
        assert len(result) > 0
        # Shared должен быть первым — он в обоих списках, score выше
        assert result[0].source == "shared.md"

    def test_deduplication_by_source_and_content(self):
        """RRF не дублирует одинаковые чанки (дедупликация по ключу)."""
        chunk = self._chunk("контент", "doc.md")
        result = reciprocal_rank_fusion([chunk, chunk], [chunk], k=60, top_k=10)
        sources = [r.source for r in result]
        assert sources.count("doc.md") == 1

    def test_top_k_limits_output(self):
        """RRF не возвращает больше top_k результатов."""
        lexical = [self._chunk(f"l{i}", f"src{i}") for i in range(5)]
        vector = [self._chunk(f"v{i}", f"vsrc{i}") for i in range(5)]
        result = reciprocal_rank_fusion(lexical, vector, k=60, top_k=3)
        assert len(result) == 3

    def test_rrf_score_assigned(self):
        """Каждый чанк в результате получает ненулевой RRF-score."""
        lexical = [self._chunk("a", "a.md")]
        vector = [self._chunk("b", "b.md")]
        result = reciprocal_rank_fusion(lexical, vector, k=60, top_k=5)
        for r in result:
            assert r.score > 0

    def test_k_parameter_affects_score(self):
        """Меньший k даёт более крутую убывающую кривую (первый чанк выше при k=1)."""
        doc = self._chunk("x", "x.md")
        result_k1 = reciprocal_rank_fusion([doc], [], k=1, top_k=1)
        result_k60 = reciprocal_rank_fusion([doc], [], k=60, top_k=1)
        # При k=1 score = 1/(1+0) = 1.0; при k=60 score = 1/(60+0) ≈ 0.017
        assert result_k1[0].score > result_k60[0].score


# ---------------------------------------------------------------------------
# hybrid_search — на фейках (без БД и сети)
# ---------------------------------------------------------------------------


class TestHybridSearch:
    @pytest.fixture
    def chunks(self):
        return {
            "lex1": RetrievedChunk(content="лексический 1", source="lex1.md", score=0.9),
            "lex2": RetrievedChunk(content="лексический 2", source="lex2.md", score=0.7),
            "vec1": RetrievedChunk(content="лексический 1", source="lex1.md", score=0.8),  # пересечение
            "vec2": RetrievedChunk(content="векторный 2", source="vec2.md", score=0.6),
        }

    async def test_hybrid_search_returns_list(self, chunks):
        """hybrid_search возвращает список RetrievedChunk."""
        repo = FakeDocumentRepository(
            lexical_results=[chunks["lex1"], chunks["lex2"]],
            vector_results=[chunks["vec1"], chunks["vec2"]],
        )
        emb = FakeEmbeddings()
        result = await hybrid_search(repo, emb, "запрос", top_k=5, rrf_k=60)
        assert isinstance(result, list)
        assert all(isinstance(r, RetrievedChunk) for r in result)

    async def test_hybrid_search_respects_top_k(self, chunks):
        """hybrid_search не возвращает больше top_k чанков."""
        repo = FakeDocumentRepository(
            lexical_results=[chunks["lex1"], chunks["lex2"]],
            vector_results=[chunks["vec1"], chunks["vec2"]],
        )
        emb = FakeEmbeddings()
        result = await hybrid_search(repo, emb, "запрос", top_k=1, rrf_k=60)
        assert len(result) <= 1

    async def test_hybrid_search_calls_both_sources(self, chunks):
        """hybrid_search обращается к lexical и vector поиску."""
        repo = FakeDocumentRepository(
            lexical_results=[chunks["lex1"]],
            vector_results=[chunks["vec2"]],
        )
        emb = FakeEmbeddings()
        await hybrid_search(repo, emb, "запрос", top_k=5, rrf_k=60)
        assert repo.lexical_calls == 1
        assert repo.vector_calls == 1

    async def test_hybrid_search_calls_embeddings(self, chunks):
        """hybrid_search запрашивает эмбеддинг запроса."""
        repo = FakeDocumentRepository(lexical_results=[], vector_results=[])
        emb = FakeEmbeddings()
        await hybrid_search(repo, emb, "запрос", top_k=5, rrf_k=60)
        assert emb.embed_calls == 1

    async def test_hybrid_search_intersection_ranked_first(self):
        """Чанк из обоих источников получает наивысший rank (RRF-слияние)."""
        shared = RetrievedChunk(content="общий", source="shared.md", score=0.0)
        unique_lex = RetrievedChunk(content="только lex", source="only_lex.md", score=0.0)
        unique_vec = RetrievedChunk(content="только vec", source="only_vec.md", score=0.0)

        repo = FakeDocumentRepository(
            lexical_results=[shared, unique_lex],
            vector_results=[shared, unique_vec],
        )
        emb = FakeEmbeddings()
        result = await hybrid_search(repo, emb, "запрос", top_k=5, rrf_k=60)
        assert result[0].source == "shared.md"

    async def test_hybrid_search_empty_results(self):
        """hybrid_search с пустыми репозиториями возвращает пустой список."""
        repo = FakeDocumentRepository(lexical_results=[], vector_results=[])
        emb = FakeEmbeddings()
        result = await hybrid_search(repo, emb, "запрос", top_k=5, rrf_k=60)
        assert result == []


# ---------------------------------------------------------------------------
# _format_context — форматирование чанков для промпта
# ---------------------------------------------------------------------------


class TestFormatContext:
    def test_format_single_chunk(self):
        """_format_context форматирует один чанк с источником."""
        chunks = [RetrievedChunk(content="текст", source="doc.md")]
        result = _format_context(chunks)
        assert "[Источник: doc.md]" in result
        assert "текст" in result

    def test_format_multiple_chunks_separated_by_double_newline(self):
        """Несколько чанков разделяются двойным переносом строки."""
        chunks = [
            RetrievedChunk(content="первый", source="a.md"),
            RetrievedChunk(content="второй", source="b.md"),
        ]
        result = _format_context(chunks)
        assert "\n\n" in result
        assert result.count("[Источник:") == 2

    def test_format_empty_list_returns_empty_string(self):
        """Пустой список чанков → пустая строка."""
        assert _format_context([]) == ""


# ---------------------------------------------------------------------------
# make_retrieve_node — узел retrieve на фейках
# ---------------------------------------------------------------------------


class TestRetrieveNode:
    async def test_retrieve_node_puts_context_in_state(self, fake_repo, fake_embeddings):
        """retrieve_node кладёт непустой context в state при наличии чанков."""
        node = make_retrieve_node(fake_repo, fake_embeddings)
        state = {
            "task": "Запрос для поиска",
            "plan": None,
            "context": "",
            "code": None,
            "verdict": None,
            "iterations": 0,
            "status": "planned",
            "approval_decision": None,
            "approval_feedback": "",
        }
        result = await node(state)
        assert "context" in result
        assert isinstance(result["context"], str)
        assert len(result["context"]) > 0

    async def test_retrieve_node_fallback_when_repo_none(self):
        """retrieve_node возвращает пустой context при repo=None (graceful fallback)."""
        node = make_retrieve_node(None, None)
        state = {
            "task": "Задача",
            "plan": None,
            "context": "",
            "code": None,
            "verdict": None,
            "iterations": 0,
            "status": "planned",
            "approval_decision": None,
            "approval_feedback": "",
        }
        result = await node(state)
        assert result == {"context": ""}

    async def test_retrieve_node_fallback_when_embeddings_none(self):
        """retrieve_node возвращает пустой context при embeddings=None."""
        repo = FakeDocumentRepository()
        node = make_retrieve_node(repo, None)
        state = {
            "task": "Задача",
            "plan": None,
            "context": "",
            "code": None,
            "verdict": None,
            "iterations": 0,
            "status": "planned",
            "approval_decision": None,
            "approval_feedback": "",
        }
        result = await node(state)
        assert result == {"context": ""}

    async def test_retrieve_node_context_format(self, fake_repo, fake_embeddings):
        """context в state содержит маркер [Источник:] из _format_context."""
        node = make_retrieve_node(fake_repo, fake_embeddings)
        state = {
            "task": "Запрос",
            "plan": None,
            "context": "",
            "code": None,
            "verdict": None,
            "iterations": 0,
            "status": "planned",
            "approval_decision": None,
            "approval_feedback": "",
        }
        result = await node(state)
        assert "[Источник:" in result["context"]

    async def test_retrieve_node_empty_repo_returns_empty_context(self):
        """При пустом репозитории context == '' (но не None)."""
        repo = FakeDocumentRepository(lexical_results=[], vector_results=[])
        emb = FakeEmbeddings()
        node = make_retrieve_node(repo, emb)
        state = {
            "task": "Запрос",
            "plan": None,
            "context": "",
            "code": None,
            "verdict": None,
            "iterations": 0,
            "status": "planned",
            "approval_decision": None,
            "approval_feedback": "",
        }
        result = await node(state)
        assert result["context"] == ""
