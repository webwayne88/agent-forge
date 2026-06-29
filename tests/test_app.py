"""Smoke-тесты для приложения: импорт, запуск, конфиг."""

from fastapi.testclient import TestClient

from app.main import app
from app.config import settings


def test_app_imports():
    """Приложение импортируется без ошибок."""
    assert app.title == "Agent Forge"
    assert app.version == "0.1.0"


def test_settings_load():
    """Конфигурация загружается с правильными дефолтами."""
    assert settings.max_reflection_iterations == 3
    assert settings.gigachat_model == "GigaChat-2-Max"
    assert settings.gigachat_scope == "GIGACHAT_API_CORP"
    assert settings.gigachat_temperature == 0.11


def test_health_endpoint():
    """Эндпоинт /health возвращает статус."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
