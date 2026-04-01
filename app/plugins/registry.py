from app.plugins.base import BasePlugin


class PluginRegistry:

    def __init__(self):
        self._plugins: dict[str, BasePlugin] = {}

    def register(self, name: str, plugin: BasePlugin) -> None:
        self._plugins[name.upper()] = plugin

    def get(self, name: str) -> BasePlugin:
        plugin = self._plugins.get(name.upper())
        if not plugin:
            available = ", ".join(self._plugins.keys())
            raise KeyError(f"Plugin '{name}' not found. Available: {available}")
        return plugin

    def list_all(self) -> list[str]:
        return list(self._plugins.keys())
