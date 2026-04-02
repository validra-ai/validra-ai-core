import logging

import httpx

from app.providers.base import BaseLLMProvider
from app.providers.openai.config import OpenAIConfig

logger = logging.getLogger(__name__)


class OpenAIProvider(BaseLLMProvider):
    name = "openai"
    config_class = OpenAIConfig

    def default_config(self) -> OpenAIConfig:
        from app.config.settings import settings
        return OpenAIConfig(api_key=settings.openai_api_key)

    def complete(self, prompt: str, config: OpenAIConfig, system: str | None = None) -> str:
        if not config.api_key:
            raise Exception(
                "OpenAI API key is not configured — set OPENAI_API_KEY or pass api_key in provider_config"
            )
        try:
            messages = []
            if system:
                messages.append({"role": "system", "content": system})
            messages.append({"role": "user", "content": prompt})

            response = httpx.post(
                config.base_url,
                headers={
                    "Authorization": f"Bearer {config.api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.model,
                    "messages": messages,
                    "temperature": config.temperature,
                    "max_tokens": config.max_tokens,
                },
                timeout=config.timeout,
            )
            response.raise_for_status()
            data = response.json()

            usage = data.get("usage", {})
            logger.info(
                "openai tokens — model=%s prompt=%s completion=%s",
                config.model,
                usage.get("prompt_tokens", "?"),
                usage.get("completion_tokens", "?"),
            )

            return data["choices"][0]["message"]["content"]

        except httpx.TimeoutException:
            raise Exception("OpenAI timeout — try increasing timeout in provider_config")
        except httpx.ConnectError:
            raise Exception("Cannot connect to OpenAI API — check your network")
        except httpx.HTTPStatusError as e:
            raise Exception(f"OpenAI HTTP error: {e}")
        except (KeyError, IndexError):
            raise Exception("Unexpected OpenAI response format")
        except Exception as e:
            raise Exception(f"Unexpected OpenAI error: {e}")
