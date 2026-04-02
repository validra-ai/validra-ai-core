import logging

import httpx

from app.providers.base import BaseLLMProvider
from app.providers.anthropic.config import AnthropicConfig

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    name = "anthropic"
    config_class = AnthropicConfig

    def default_config(self) -> AnthropicConfig:
        from app.config.settings import settings
        return AnthropicConfig(api_key=settings.anthropic_api_key)

    def complete(self, prompt: str, config: AnthropicConfig, system: str | None = None) -> str:
        if not config.api_key:
            raise Exception(
                "Anthropic API key is not configured — set ANTHROPIC_API_KEY in environment or pass api_key in provider_config"
            )
        try:
            body: dict = {
                "model": config.model,
                "max_tokens": config.max_tokens,
                "temperature": config.temperature,
                "messages": [{"role": "user", "content": prompt}],
            }

            # Send static instructions as a cached system prompt.
            # Anthropic charges only for cache writes on first call; subsequent
            # calls with the same prefix are served from cache at ~10% of the
            # input-token cost.
            if system:
                body["system"] = [
                    {
                        "type": "text",
                        "text": system,
                        "cache_control": {"type": "ephemeral"},
                    }
                ]

            response = httpx.post(
                config.base_url,
                headers={
                    "x-api-key": config.api_key,
                    "anthropic-version": config.anthropic_version,
                    "anthropic-beta": "prompt-caching-2024-07-31",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=config.timeout,
            )
            response.raise_for_status()
            data = response.json()

            # Log token usage so costs are visible in server logs.
            usage = data.get("usage", {})
            logger.info(
                "anthropic tokens — model=%s input=%s output=%s cache_read=%s cache_write=%s",
                config.model,
                usage.get("input_tokens", "?"),
                usage.get("output_tokens", "?"),
                usage.get("cache_read_input_tokens", 0),
                usage.get("cache_creation_input_tokens", 0),
            )

            return data["content"][0]["text"]

        except httpx.TimeoutException:
            raise Exception("Anthropic timeout — try increasing timeout in provider_config")
        except httpx.ConnectError:
            raise Exception("Cannot connect to Anthropic API — check your network")
        except httpx.HTTPStatusError as e:
            raise Exception(f"Anthropic HTTP error: {e}")
        except (KeyError, IndexError):
            raise Exception("Unexpected Anthropic response format")
        except Exception as e:
            raise Exception(f"Unexpected Anthropic error: {e}")
