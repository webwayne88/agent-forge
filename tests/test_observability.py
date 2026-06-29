"""Тесты Langfuse observability: no-op без ключей, handler при ключах, граф не падает.

Langfuse не вызывает сеть в тестах — всё через monkeypatch/mock.
lru_cache у get_langfuse_handler требует cache_clear() между тестами.
"""

from unittest.mock import MagicMock

import pytest

from app.observability.langfuse import get_callbacks, get_langfuse_handler


@pytest.fixture(autouse=True)
def clear_lru_cache():
    """Сбрасываем lru_cache перед каждым тестом — иначе состояние просачивается."""
    get_langfuse_handler.cache_clear()
    yield
    get_langfuse_handler.cache_clear()


# ---------------------------------------------------------------------------
# no-op при отсутствии ключей
# ---------------------------------------------------------------------------


class TestNoOpWithoutKeys:
    def test_handler_none_when_no_keys(self, monkeypatch):
        """get_langfuse_handler() возвращает None при пустых ключах."""
        monkeypatch.setattr("app.observability.langfuse._LANGFUSE_AVAILABLE", True)
        monkeypatch.setattr("app.config.settings.langfuse_public_key", "")
        monkeypatch.setattr("app.config.settings.langfuse_secret_key", "")
        monkeypatch.setattr("app.config.settings.langfuse_enabled", True)
        result = get_langfuse_handler()
        assert result is None

    def test_callbacks_empty_when_no_keys(self, monkeypatch):
        """get_callbacks() возвращает [] при пустых ключах."""
        monkeypatch.setattr("app.observability.langfuse._LANGFUSE_AVAILABLE", True)
        monkeypatch.setattr("app.config.settings.langfuse_public_key", "")
        monkeypatch.setattr("app.config.settings.langfuse_secret_key", "")
        monkeypatch.setattr("app.config.settings.langfuse_enabled", True)
        assert get_callbacks() == []

    def test_handler_none_when_disabled(self, monkeypatch):
        """get_langfuse_handler() возвращает None при langfuse_enabled=False."""
        monkeypatch.setattr("app.observability.langfuse._LANGFUSE_AVAILABLE", True)
        monkeypatch.setattr("app.config.settings.langfuse_public_key", "pub-key")
        monkeypatch.setattr("app.config.settings.langfuse_secret_key", "sec-key")
        monkeypatch.setattr("app.config.settings.langfuse_enabled", False)
        result = get_langfuse_handler()
        assert result is None

    def test_handler_none_when_package_missing(self, monkeypatch):
        """get_langfuse_handler() возвращает None если langfuse недоступен."""
        monkeypatch.setattr("app.observability.langfuse._LANGFUSE_AVAILABLE", False)
        result = get_langfuse_handler()
        assert result is None


# ---------------------------------------------------------------------------
# handler возвращается при наличии ключей (CallbackHandler замокан)
# ---------------------------------------------------------------------------


class TestHandlerWithKeys:
    def test_handler_returned_when_keys_present(self, monkeypatch):
        """get_langfuse_handler() возвращает handler при наличии обоих ключей."""
        fake_handler = MagicMock()
        fake_langfuse_cls = MagicMock()
        fake_callback_cls = MagicMock(return_value=fake_handler)

        monkeypatch.setattr("app.observability.langfuse._LANGFUSE_AVAILABLE", True)
        monkeypatch.setattr("app.observability.langfuse.Langfuse", fake_langfuse_cls)
        monkeypatch.setattr("app.observability.langfuse.CallbackHandler", fake_callback_cls)
        monkeypatch.setattr("app.config.settings.langfuse_public_key", "pub-key")
        monkeypatch.setattr("app.config.settings.langfuse_secret_key", "sec-key")
        monkeypatch.setattr("app.config.settings.langfuse_enabled", True)

        result = get_langfuse_handler()
        assert result is fake_handler

    def test_langfuse_client_initialized_with_keys(self, monkeypatch):
        """При наличии ключей Langfuse-клиент инициализируется с public_key и secret_key."""
        fake_langfuse_cls = MagicMock()
        fake_callback_cls = MagicMock(return_value=MagicMock())

        monkeypatch.setattr("app.observability.langfuse._LANGFUSE_AVAILABLE", True)
        monkeypatch.setattr("app.observability.langfuse.Langfuse", fake_langfuse_cls)
        monkeypatch.setattr("app.observability.langfuse.CallbackHandler", fake_callback_cls)
        monkeypatch.setattr("app.config.settings.langfuse_public_key", "my-pub")
        monkeypatch.setattr("app.config.settings.langfuse_secret_key", "my-sec")
        monkeypatch.setattr("app.config.settings.langfuse_enabled", True)

        get_langfuse_handler()

        call_kwargs = fake_langfuse_cls.call_args[1]
        assert call_kwargs["public_key"] == "my-pub"
        assert call_kwargs["secret_key"] == "my-sec"

    def test_callbacks_contains_handler_when_keys_present(self, monkeypatch):
        """get_callbacks() возвращает [handler] при наличии ключей."""
        fake_handler = MagicMock()
        fake_langfuse_cls = MagicMock()
        fake_callback_cls = MagicMock(return_value=fake_handler)

        monkeypatch.setattr("app.observability.langfuse._LANGFUSE_AVAILABLE", True)
        monkeypatch.setattr("app.observability.langfuse.Langfuse", fake_langfuse_cls)
        monkeypatch.setattr("app.observability.langfuse.CallbackHandler", fake_callback_cls)
        monkeypatch.setattr("app.config.settings.langfuse_public_key", "pub")
        monkeypatch.setattr("app.config.settings.langfuse_secret_key", "sec")
        monkeypatch.setattr("app.config.settings.langfuse_enabled", True)

        result = get_callbacks()
        assert result == [fake_handler]


# ---------------------------------------------------------------------------
# Ошибка инициализации — fallback на None, не исключение
# ---------------------------------------------------------------------------


class TestInitFailureFallback:
    def test_handler_none_on_init_exception(self, monkeypatch):
        """При ошибке инициализации Langfuse get_langfuse_handler() возвращает None (не кидает)."""
        monkeypatch.setattr("app.observability.langfuse._LANGFUSE_AVAILABLE", True)
        monkeypatch.setattr("app.observability.langfuse.Langfuse", MagicMock(side_effect=RuntimeError("сбой")))
        monkeypatch.setattr("app.observability.langfuse.CallbackHandler", MagicMock())
        monkeypatch.setattr("app.config.settings.langfuse_public_key", "pub")
        monkeypatch.setattr("app.config.settings.langfuse_secret_key", "sec")
        monkeypatch.setattr("app.config.settings.langfuse_enabled", True)

        result = get_langfuse_handler()
        assert result is None

    def test_callbacks_empty_on_init_failure(self, monkeypatch):
        """При ошибке get_callbacks() возвращает [], граф не падает."""
        monkeypatch.setattr("app.observability.langfuse._LANGFUSE_AVAILABLE", True)
        monkeypatch.setattr("app.observability.langfuse.Langfuse", MagicMock(side_effect=Exception("нет сети")))
        monkeypatch.setattr("app.observability.langfuse.CallbackHandler", MagicMock())
        monkeypatch.setattr("app.config.settings.langfuse_public_key", "pub")
        monkeypatch.setattr("app.config.settings.langfuse_secret_key", "sec")
        monkeypatch.setattr("app.config.settings.langfuse_enabled", True)

        assert get_callbacks() == []


# ---------------------------------------------------------------------------
# Граф работает с пустым callbacks (no-op сквозной тест)
# ---------------------------------------------------------------------------


class TestGraphPassesCallbacks:
    async def test_forge_endpoint_passes_callbacks_no_op(self):
        """POST /forge не падает при пустых Langfuse callbacks (no-op path)."""
        from httpx import ASGITransport, AsyncClient
        from unittest.mock import patch as patch_fn
        from app.graph.graph import build_graph
        from app.main import app
        from tests.conftest import FAKE_CODE, FAKE_PLAN, FAKE_VERDICT_PASS, FakeLLM
        from app.schemas.pipeline import GeneratedCode, Plan, ReviewVerdict

        fake_llm = FakeLLM(
            {Plan: FAKE_PLAN, GeneratedCode: FAKE_CODE, ReviewVerdict: FAKE_VERDICT_PASS}
        )
        graph = build_graph(fake_llm)

        # Убеждаемся, что get_callbacks() вернёт [] (без ключей)
        with patch_fn("app.routers.forge._graph", graph), \
             patch_fn("app.observability.langfuse.get_langfuse_handler", return_value=None):
            async with AsyncClient(
                transport=ASGITransport(app=app), base_url="http://test"
            ) as client:
                response = await client.post("/forge", json={"task": "Тест callbacks"})

        assert response.status_code == 200
