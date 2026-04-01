from app.providers.base import BaseLLMProvider


class ProviderRegistry:

    def __init__(self):
        self._providers: dict[str, BaseLLMProvider] = {}

    def register(self, name: str, provider: BaseLLMProvider) -> None:
        self._providers[name.lower()] = provider

    def get(self, name: str) -> BaseLLMProvider:
        provider = self._providers.get(name.lower())
        if not provider:
            available = ", ".join(self._providers.keys())
            raise KeyError(f"Provider '{name}' not found. Available: {available}")
        return provider

    def list_all(self) -> list[str]:
        return list(self._providers.keys())
