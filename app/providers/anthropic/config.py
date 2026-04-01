from typing import Optional
from app.providers.base import BaseProviderConfig


class AnthropicConfig(BaseProviderConfig):
    model: str = "claude-sonnet-4-6"
    temperature: float = 0.7
    max_tokens: int = 700
    timeout: int = 60
    api_key: Optional[str] = None
    base_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_version: str = "2023-06-01"
