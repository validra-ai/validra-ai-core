from typing import Optional
from app.providers.base import BaseProviderConfig


class OpenAIConfig(BaseProviderConfig):
    model: str = "gpt-4o-mini"
    temperature: float = 0.3
    max_tokens: int = 700
    timeout: int = 60
    api_key: Optional[str] = None
    base_url: str = "https://api.openai.com/v1/chat/completions"
