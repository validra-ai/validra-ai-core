from typing import Optional
from app.providers.base import BaseProviderConfig


class AnthropicConfig(BaseProviderConfig):
    # Default to Haiku for generation (fast + cheap). The route overrides this
    # to claude-sonnet-4-6 when building the validation-specific config.
    model: str = "claude-haiku-4-5-20251001"
    temperature: float = 0.3
    max_tokens: int = 700
    timeout: int = 60
    api_key: Optional[str] = None
    base_url: str = "https://api.anthropic.com/v1/messages"
    anthropic_version: str = "2023-06-01"
