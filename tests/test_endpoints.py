"""Тесты эндпоинтов: /health и опционально /forge через подмену графа."""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict
from tests.conftest import FAKE_CODE, FAKE_PLAN, FAKE_VERDICT_PASS


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
# /forge — через мок графа (граф компилируется на уровне модуля с реальным LLM,
# поэтому патчим _graph напрямую, не трогая build_graph)
# ---------------------------------------------------------------------------


def _make_fake_graph_result():
    return {
        "plan": FAKE_PLAN,
        "code": FAKE_CODE,
        "verdict": FAKE_VERDICT_PASS,
        "iterations": 1,
        "status": "reviewed",
    }


class TestForgeEndpoint:
    async def test_forge_returns_200_with_mock(self):
        """/forge возвращает 200 при замоканном графе."""
        fake_result = _make_fake_graph_result()
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = fake_result

        with patch("app.routers.forge._graph", mock_graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/forge", json={"task": "Напиши hello world"})

        assert response.status_code == 200

    async def test_forge_response_structure(self):
        """/forge возвращает ожидаемые поля ответа."""
        fake_result = _make_fake_graph_result()
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = fake_result

        with patch("app.routers.forge._graph", mock_graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/forge", json={"task": "Задача"})

        data = response.json()
        assert "plan" in data
        assert "code" in data
        assert "verdict" in data
        assert "iterations" in data
        assert "status" in data

    async def test_forge_iterations_correct(self):
        """/forge возвращает правильное количество итераций."""
        fake_result = _make_fake_graph_result()
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = fake_result

        with patch("app.routers.forge._graph", mock_graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/forge", json={"task": "Задача"})

        assert response.json()["iterations"] == 1
        assert response.json()["status"] == "reviewed"

    async def test_forge_passes_task_to_graph(self):
        """/forge передаёт task из запроса в граф."""
        fake_result = _make_fake_graph_result()
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = fake_result

        with patch("app.routers.forge._graph", mock_graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post("/forge", json={"task": "Конкретная задача"})

        call_args = mock_graph.ainvoke.call_args
        initial_state = call_args[0][0]
        assert initial_state["task"] == "Конкретная задача"

    async def test_forge_uses_unique_thread_id(self):
        """/forge передаёт уникальный thread_id для каждого запроса."""
        fake_result = _make_fake_graph_result()
        mock_graph = AsyncMock()
        mock_graph.ainvoke.return_value = fake_result

        with patch("app.routers.forge._graph", mock_graph):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                await client.post("/forge", json={"task": "Задача 1"})
                await client.post("/forge", json={"task": "Задача 2"})

        calls = mock_graph.ainvoke.call_args_list
        thread_id_1 = calls[0][1]["config"]["configurable"]["thread_id"]
        thread_id_2 = calls[1][1]["config"]["configurable"]["thread_id"]
        assert thread_id_1 != thread_id_2

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
