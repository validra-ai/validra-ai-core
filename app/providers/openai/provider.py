import requests

from app.providers.base import BaseLLMProvider
from app.providers.openai.config import OpenAIConfig


class OpenAIProvider(BaseLLMProvider):
    name = "openai"
    config_class = OpenAIConfig

    def default_config(self) -> OpenAIConfig:
        from app.config.settings import settings
        return OpenAIConfig(api_key=settings.openai_api_key)

    def complete(self, prompt: str, config: OpenAIConfig) -> str:
        if not config.api_key:
            raise Exception("OpenAI API key is not configured — set OPENAI_API_KEY or pass api_key in provider_config")
        try:
            response = requests.post(
                config.base_url,
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                },
                timeout=config.timeout,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]

        except requests.exceptions.ReadTimeout:
            raise Exception("OpenAI timeout — try increasing timeout in provider_config")
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to OpenAI API — check your network")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"OpenAI HTTP error: {e}")
        except (KeyError, IndexError):
            raise Exception("Unexpected OpenAI response format")
        except Exception as e:
            raise Exception(f"Unexpected OpenAI error: {e}")
