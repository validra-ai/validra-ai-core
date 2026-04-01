import requests

from app.providers.base import BaseLLMProvider
from app.providers.anthropic.config import AnthropicConfig


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"
    config_class = AnthropicConfig

    def default_config(self) -> AnthropicConfig:
        from app.config.settings import settings
        return AnthropicConfig(api_key=settings.anthropic_api_key)

    def complete(self, prompt: str, config: AnthropicConfig) -> str:
        if not config.api_key:
            raise Exception("Anthropic API key is not configured — set ANTHROPIC_API_KEY in environment or pass api_key in provider_config")
        try:
            response = requests.post(
                config.base_url,
                headers={
                    "x-api-key": config.api_key,
                    "anthropic-version": config.anthropic_version,
                    "Content-Type": "application/json",
                },
                json={
                    "model": config.model,
                    "max_tokens": config.max_tokens,
                    "temperature": config.temperature,
                    "messages": [{"role": "user", "content": prompt}],
                },
                timeout=config.timeout,
            )
            response.raise_for_status()
            return response.json()["content"][0]["text"]

        except requests.exceptions.ReadTimeout:
            raise Exception("Anthropic timeout — try increasing timeout in provider_config")
        except requests.exceptions.ConnectionError:
            raise Exception("Cannot connect to Anthropic API — check your network")
        except requests.exceptions.HTTPError as e:
            raise Exception(f"Anthropic HTTP error: {e}")
        except (KeyError, IndexError):
            raise Exception("Unexpected Anthropic response format")
        except Exception as e:
            raise Exception(f"Unexpected Anthropic error: {e}")
