from app.providers.base import BaseProviderConfig


class OllamaConfig(BaseProviderConfig):
    model: str = "llama3:8b-instruct-q4_0"
    temperature: float = 0.3
    max_tokens: int = 700
    top_p: float = 0.9
    url: str = "http://localhost:11434/api/generate"
    timeout: int = 600
