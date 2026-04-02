import pytest

from app.plugins.registry import PluginRegistry
from app.providers.registry import ProviderRegistry


class TestPluginRegistry:
    def test_register_and_get(self):
        registry = PluginRegistry()
        plugin = object()
        registry.register("FUZZ", plugin)
        assert registry.get("FUZZ") is plugin

    def test_get_is_case_insensitive(self):
        registry = PluginRegistry()
        plugin = object()
        registry.register("fuzz", plugin)
        assert registry.get("FUZZ") is plugin
        assert registry.get("fuzz") is plugin

    def test_missing_raises_key_error(self):
        registry = PluginRegistry()
        with pytest.raises(KeyError, match="Plugin 'MISSING' not found"):
            registry.get("MISSING")

    def test_error_message_lists_available(self):
        registry = PluginRegistry()
        registry.register("FUZZ", object())
        with pytest.raises(KeyError, match="FUZZ"):
            registry.get("UNKNOWN")

    def test_list_all(self):
        registry = PluginRegistry()
        registry.register("A", object())
        registry.register("B", object())
        assert set(registry.list_all()) == {"A", "B"}


class TestProviderRegistry:
    def test_register_and_get(self):
        registry = ProviderRegistry()
        provider = object()
        registry.register("openai", provider)
        assert registry.get("openai") is provider

    def test_get_is_case_insensitive(self):
        registry = ProviderRegistry()
        provider = object()
        registry.register("OpenAI", provider)
        assert registry.get("openai") is provider
        assert registry.get("OPENAI") is provider

    def test_missing_raises_key_error(self):
        registry = ProviderRegistry()
        with pytest.raises(KeyError, match="Provider 'missing' not found"):
            registry.get("missing")

    def test_list_all(self):
        registry = ProviderRegistry()
        registry.register("ollama", object())
        registry.register("openai", object())
        assert set(registry.list_all()) == {"ollama", "openai"}
