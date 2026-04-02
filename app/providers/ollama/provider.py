import json
import logging

import httpx

from app.providers.base import BaseLLMProvider
from app.providers.ollama.config import OllamaConfig

logger = logging.getLogger(__name__)


class OllamaProvider(BaseLLMProvider):
    name = "ollama"
    config_class = OllamaConfig

    def default_config(self) -> OllamaConfig:
        from app.config.settings import settings
        return OllamaConfig(url=settings.ollama_url)

    def complete(self, prompt: str, config: OllamaConfig, system: str | None = None) -> str:
        try:
            body: dict = {
                "model": config.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": config.temperature,
                    "num_predict": config.max_tokens,
                    "top_p": config.top_p,
                },
            }
            if system:
                body["system"] = system

            response = httpx.post(
                config.url,
                json=body,
                timeout=config.timeout,
            )
            response.raise_for_status()

            final_text = ""
            for line in response.text.splitlines():
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    if "response" in data:
                        final_text += data["response"]
                    if data.get("done"):
                        break
                except json.JSONDecodeError:
                    continue

            return final_text

        except httpx.TimeoutException:
            raise Exception("Ollama timeout — model too slow or prompt too large")
        except httpx.ConnectError:
            raise Exception(
                "Cannot connect to Ollama — is Ollama running? Check OLLAMA_URL in settings or url in provider_config"
            )
        except httpx.HTTPStatusError as e:
            raise Exception(f"Ollama HTTP error: {e}")
        except Exception as e:
            raise Exception(f"Unexpected Ollama error: {e}")
