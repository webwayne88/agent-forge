"""Тесты эндпоинтов: /health, /forge, /forge/{id}/approve, /forge/{id}/reject.

Стратегия для /forge и HITL-эндпоинтов: используем реальный граф на фейк-LLM
(build_graph(fake_llm)), подменяя _graph через patch. Это позволяет тестировать
aget_state/aupdate_state в реальном MemorySaver без сети.
Для тестов, проверяющих только структуру ответа, используем
заглушку через AsyncMock со сконфигурированным snapshot.
"""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.graph.graph import build_graph
from app.main import app
from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict
from tests.conftest import (
    FAKE_CODE,
    FAKE_PLAN,
    FAKE_VERDICT_PASS,
    FakeLLM,
)


def _make_fake_llm_pass():
    return FakeLLM(
        {Plan: FAKE_PLAN, GeneratedCode: FAKE_CODE, ReviewVerdict: FAKE_VERDICT_PASS}
    )


def _snapshot(values: dict, next_nodes: tuple = ()):
    """Вспомогательный helper: создаёт объект, имитирующий snapshot LangGraph."""
    snap = SimpleNamespace()
    snap.values = values
    snap.next = next_nodes
    return snap


def _paused_snapshot(values: dict):
    """Snapshot, где граф стоит на паузе перед approval."""
    return _snapshot(values, next_nodes=("approval",))


def _make_state_values():
    return {
        "plan": FAKE_PLAN,
        "code": FAKE_CODE,
        "verdict": FAKE_VERDICT_PASS,
        "iterations": 1,
        "status": "reviewed",
        "approval_decision": None,
        "approval_feedback": "",
        "task": "Тест",
        "context": "",
    }


# ---------------------------------------------------------------------------
# /health
# ---------------------------------------------------------------------------


class TestHealthEndpoint:
    def test_health_returns_200(self):
        """/health возвращает HTTP 200."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_ok(self):
        """/health возвращает {"status": "ok"}."""
        client = TestClient(app)
        response = client.get("/health")
        assert response.json() == {"status": "ok"}

    async def test_health_async(self):
        """/health работает через async-клиент."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


# ---------------------------------------------------------------------------
# /forge — реальный граф на фейк-LLM (MemorySaver, без сети)
# ---------------------------------------------------------------------------


def _forge_graph():
    """Реальный граф на фейк-LLM для endpoint-тестов."""
    return build_graph(_make_fake_llm_pass())


class TestForgeEndpoint:
    async def test_forge_returns_200_with_real_graph(self):
        """/forge возвращает 200 при реальном графе на фейк-LLM."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/forge", json={"task": "Напиши hello world"})
        assert response.status_code == 200

    async def test_forge_response_structure(self):
        """/forge возвращает ожидаемые поля ответа (включая HITL-поля)."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/forge", json={"task": "Задача"})
        data = response.json()
        for field in ("thread_id", "plan", "code", "verdict", "iterations", "status", "approval_decision"):
            assert field in data, f"Поле '{field}' отсутствует в ответе"

    async def test_forge_thread_id_is_uuid(self):
        """/forge возвращает thread_id в формате UUID."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/forge", json={"task": "Задача"})
        tid = response.json()["thread_id"]
        uuid.UUID(tid)  # бросит ValueError если не UUID

    async def test_forge_status_awaiting_approval(self):
        """/forge возвращает status=awaiting_approval (граф стоит перед interrupt)."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/forge", json={"task": "Задача"})
        assert response.json()["status"] == "awaiting_approval"

    async def test_forge_iterations_is_int(self):
        """/forge возвращает целое число iterations."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/forge", json={"task": "Задача"})
        assert isinstance(response.json()["iterations"], int)
        assert response.json()["iterations"] >= 1

    async def test_forge_passes_task_to_graph(self):
        """/forge передаёт task из запроса в граф (проверяем через Mock)."""
        mock_graph = AsyncMock()
        values = _make_state_values()
        mock_graph.aget_state.return_value = _paused_snapshot(values)

        with patch("app.routers.forge._graph", mock_graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post("/forge", json={"task": "Конкретная задача"})

        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]
        assert initial_state["task"] == "Конкретная задача"

    async def test_forge_uses_unique_thread_id(self):
        """/forge передаёт разные thread_id для двух запросов."""
        mock_graph = AsyncMock()
        values = _make_state_values()
        mock_graph.aget_state.return_value = _paused_snapshot(values)

        with patch("app.routers.forge._graph", mock_graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post("/forge", json={"task": "Задача 1"})
                await client.post("/forge", json={"task": "Задача 2"})

        calls = mock_graph.ainvoke.call_args_list
        tid1 = calls[0][1]["config"]["configurable"]["thread_id"]
        tid2 = calls[1][1]["config"]["configurable"]["thread_id"]
        assert tid1 != tid2

    def test_forge_empty_task_returns_422(self):
        """/forge с пустым телом возвращает 422 (Pydantic validation)."""
        client = TestClient(app)
        response = client.post("/forge", json={})
        assert response.status_code == 422

    def test_forge_missing_task_field_returns_422(self):
        """/forge без поля task возвращает 422."""
        client = TestClient(app)
        response = client.post("/forge", json={"not_task": "value"})
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# /forge/{thread_id}/approve — реальный граф на фейк-LLM
# ---------------------------------------------------------------------------


class TestApproveEndpoint:
    async def test_approve_returns_200_and_approved_status(self):
        """approve резюмит граф, финальный status == approved."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                # Сначала инициируем задачу, получаем thread_id
                forge_resp = await client.post("/forge", json={"task": "Напиши hello"})
                assert forge_resp.status_code == 200
                thread_id = forge_resp.json()["thread_id"]
                assert forge_resp.json()["status"] == "awaiting_approval"

                # Теперь approve
                approve_resp = await client.post(f"/forge/{thread_id}/approve")
        assert approve_resp.status_code == 200
        data = approve_resp.json()
        assert data["status"] == "approved"
        assert data["approval_decision"] == "approved"

    async def test_approve_unknown_thread_returns_404(self):
        """approve на несуществующий thread_id возвращает 404."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(f"/forge/{uuid.uuid4()}/approve")
        assert response.status_code == 404

    async def test_approve_already_approved_returns_409(self):
        """Повторный approve на завершённый граф возвращает 409."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                forge_resp = await client.post("/forge", json={"task": "Задача"})
                thread_id = forge_resp.json()["thread_id"]
                # Первый approve завершает граф
                await client.post(f"/forge/{thread_id}/approve")
                # Второй approve должен вернуть 409 (граф не на паузе)
                response = await client.post(f"/forge/{thread_id}/approve")
        assert response.status_code == 409


# ---------------------------------------------------------------------------
# /forge/{thread_id}/reject — реальный граф на фейк-LLM
# ---------------------------------------------------------------------------


class TestRejectEndpoint:
    async def test_reject_returns_200(self):
        """reject возвращает 200."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                forge_resp = await client.post("/forge", json={"task": "Задача"})
                thread_id = forge_resp.json()["thread_id"]
                response = await client.post(
                    f"/forge/{thread_id}/reject",
                    json={"feedback": "Нужно доработать"},
                )
        assert response.status_code == 200

    async def test_reject_returns_to_approval_or_rejected(self):
        """reject с лимитом итераций завершает граф со статусом rejected."""
        from app.config import settings

        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                forge_resp = await client.post("/forge", json={"task": "Задача"})
                thread_id = forge_resp.json()["thread_id"]
                # Серия reject до исчерпания лимита (max_reflection_iterations раз)
                last_resp = None
                for _ in range(settings.max_reflection_iterations):
                    last_resp = await client.post(
                        f"/forge/{thread_id}/reject",
                        json={"feedback": "Не устраивает"},
                    )
                    if last_resp.json()["status"] == "rejected":
                        break
        assert last_resp is not None
        # Финальный статус должен быть rejected (лимит исчерпан) или awaiting_approval
        assert last_resp.json()["status"] in ("rejected", "awaiting_approval")

    async def test_reject_unknown_thread_returns_404(self):
        """reject на несуществующий thread_id возвращает 404."""
        graph = _forge_graph()
        with patch("app.routers.forge._graph", graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post(
                    f"/forge/{uuid.uuid4()}/reject",
                    json={"feedback": "Причина"},
                )
        assert response.status_code == 404

    async def test_reject_requires_feedback(self):
        """reject без поля feedback возвращает 422."""
        client = TestClient(app)
        response = client.post(f"/forge/{uuid.uuid4()}/reject", json={})
        assert response.status_code == 422
