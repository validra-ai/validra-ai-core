from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    default_provider: str = "ollama"
    executor_timeout: int = 60

    # Deployment-specific (changes between local/docker)
    ollama_url: str = "http://localhost:11434/api/generate"

    # Secrets — no defaults, must be set to use that provider
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
