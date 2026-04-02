from pydantic import BaseModel, Field
from typing import Optional, Dict, Any


_PROVIDER_CONFIG_DESCRIPTION = """
Per-request provider overrides. Fields depend on the selected provider:

**ollama**
- `model` (str) — default: `llama3:8b-instruct-q4_0`
- `temperature` (float) — default: `0.7`
- `max_tokens` (int) — default: `700`
- `top_p` (float) — default: `0.9`
- `url` (str) — default: `http://localhost:11434/api/generate`
- `timeout` (int, seconds) — default: `300`

**openai**
- `model` (str) — default: `gpt-4o`
- `temperature` (float) — default: `0.7`
- `max_tokens` (int) — default: `700`
- `timeout` (int, seconds) — default: `60`
- `api_key` (str) — required
- `base_url` (str) — default: `https://api.openai.com/v1/chat/completions`

**anthropic**
- `model` (str) — default: `claude-sonnet-4-6`
- `temperature` (float) — default: `0.7`
- `max_tokens` (int) — default: `700`
- `timeout` (int, seconds) — default: `60`
- `api_key` (str) — required
- `base_url` (str) — default: `https://api.anthropic.com/v1/messages`
- `anthropic_version` (str) — default: `2023-06-01`
""".strip()


class TestRequest(BaseModel):
    endpoint: str
    method: str
    headers: dict = {}
    payload: dict
    payload_meta: Optional[Dict[str, Any]] = None
    test_type: str
    max_cases: int = Field(
        default=10,
        ge=3,
        le=100,
        description="Maximum number of test cases to generate (3-100)",
    )
    validate: bool = True
    provider: str = Field(
        default="ollama",
        description="LLM provider: ollama | openai | anthropic",
    )
    provider_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description=_PROVIDER_CONFIG_DESCRIPTION,
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "endpoint": "https://jsonplaceholder.typicode.com/posts",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "payload": {"title": "Validra Test", "body": "Testing fuzzy payload generation", "userId": 30},
                    "payload_meta": {
                        "body": "required, alphanumeric [1-50]",
                        "title": "optional, alphanumeric [1-50]",
                        "userId": "numeric [1-999]",
                    },
                    "test_type": "FUZZ",
                    "max_cases": 10,
                    "validate": True,
                    "provider": "ollama",
                    "provider_config": {
                        "model": "llama3:8b-instruct-q4_0",
                        "temperature": 0.5,
                        "top_p": 0.9,
                        "max_tokens": 700,
                        "timeout": 300,
                        "url": "http://localhost:11434/api/generate",
                    },
                },
                {
                    "endpoint": "https://jsonplaceholder.typicode.com/posts",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "payload": {"title": "Validra Test", "body": "Testing fuzzy payload generation", "userId": 30},
                    "test_type": "FUZZ",
                    "max_cases": 10,
                    "validate": True,
                    "provider": "openai",
                    "provider_config": {
                        "api_key": "sk-...",
                        "model": "gpt-4o",
                        "temperature": 0.7,
                        "max_tokens": 700,
                        "timeout": 60,
                    },
                },
                {
                    "endpoint": "https://jsonplaceholder.typicode.com/posts",
                    "method": "POST",
                    "headers": {"Content-Type": "application/json"},
                    "payload": {"title": "Validra Test", "body": "Testing fuzzy payload generation", "userId": 30},
                    "test_type": "FUZZ",
                    "max_cases": 10,
                    "validate": True,
                    "provider": "anthropic",
                    "provider_config": {
                        "api_key": "sk-ant-...",
                        "model": "claude-sonnet-4-6",
                        "temperature": 0.7,
                        "max_tokens": 700,
                        "timeout": 60,
                    },
                },
            ]
        }
    }


class ValidateRequest(BaseModel):
    test: Dict[str, Any]
    response: Dict[str, Any]
    meta: Optional[Dict[str, Any]] = None
    provider: str = Field(
        default="ollama",
        description="LLM provider: ollama | openai | anthropic",
    )
    provider_config: Optional[Dict[str, Any]] = Field(
        default=None,
        description=_PROVIDER_CONFIG_DESCRIPTION,
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "test": {
                        "id": "tc-001",
                        "description": "Body too long",
                        "payload": {
                            "title": "Validra Test",
                            "body": "Testing fuzzy payload generation",
                            "userId": 30,
                        },
                    },
                    "response": {"status_code": 201, "body": {"id": 101}},
                    "meta": {
                        "body": "required, alphanumeric [1-50]",
                        "title": "optional, alphanumeric [1-50]",
                        "userId": "numeric [1-999]",
                    },
                    "provider": "ollama",
                }
            ]
        }
    }
