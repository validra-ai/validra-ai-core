from abc import ABC, abstractmethod
from typing import ClassVar
from pydantic import BaseModel


class BaseProviderConfig(BaseModel):
    model: str
    temperature: float = 0.7
    max_tokens: int = 700

    model_config = {"extra": "forbid"}


class BaseLLMProvider(ABC):
    name: str = "base"
    config_class: ClassVar[type] = BaseProviderConfig

    @abstractmethod
    def complete(self, prompt: str, config: BaseProviderConfig) -> str:
        """Send prompt to LLM and return raw text response."""
        raise NotImplementedError

    @abstractmethod
    def default_config(self) -> BaseProviderConfig:
        """Return a config instance populated from application settings."""
        raise NotImplementedError
