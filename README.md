# Validra Core

AI-powered API test generation and validation engine. Validra uses Large Language Models to automatically generate test cases — fuzzing, security, and penetration tests — and executes them against live APIs, validating responses intelligently.

---

## Features

- **3 test plugins**: Fuzz (edge-case inputs), Auth (header mutations), Pen (injection & privilege escalation)
- **3 LLM providers**: Ollama (local), OpenAI, Anthropic — switchable per-request
- **End-to-end pipeline**: Generate → Execute → Validate, all in one request
- **LLM-powered validation**: Responses are assessed by the LLM with PASS/FAIL/WARN + confidence score
- **Stateless API**: No database, minimal dependencies — install via `pip install validra`

---

## Quick Start

**Prerequisites**: Python 3.11+

```bash
pip install validra
validra
```

The API will be available at `http://localhost:8000`.  
Swagger UI: `http://localhost:8000/docs`

Validra works out of the box with Ollama as the default provider. To use OpenAI or Anthropic instead, set your key before starting:

```bash
OPENAI_API_KEY=sk-... validra
# or
ANTHROPIC_API_KEY=sk-ant-... validra
```

Or create a `.env` file in the directory where you run `validra`:

```bash
cp .env.example .env
# edit .env, then:
validra
```

> **Using Ollama?** Install it from [ollama.ai](https://ollama.ai) and run `ollama serve`. Validra connects to it automatically — no extra configuration needed.

---

## Configuration

Validra has sensible defaults built in. Most users don't need any configuration to get started — just run it and go.

There are two ways to configure behaviour, each suited to different needs:

### 1. Environment variables (`.env`) — persistent, server-level config

Use a `.env` file (or real environment variables) for things that are fixed for your setup:

| Variable | Default | When to set |
|---|---|---|
| `DEFAULT_PROVIDER` | `ollama` | Change if you always want OpenAI or Anthropic |
| `OLLAMA_URL` | `http://localhost:11434/api/generate` | Only if Ollama runs on a non-default address |
| `OPENAI_API_KEY` | — | Required to use the OpenAI provider |
| `ANTHROPIC_API_KEY` | — | Required to use the Anthropic provider |
| `EXECUTOR_TIMEOUT` | `60` | Increase if your target API is slow |

```env
# Minimal .env for OpenAI users
DEFAULT_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

`.env` is completely optional. If you pass `api_key` directly in `provider_config` on each request, you don't need a `.env` file at all.

---

### 2. `provider_config` in the request — per-request overrides

Use `provider_config` when you want to change provider behaviour for a specific call without touching server config:

```json
{
  "provider": "openai",
  "provider_config": {
    "api_key": "sk-...",
    "model": "gpt-4o-mini",
    "temperature": 0.9,
    "max_tokens": 1000,
    "timeout": 30
  }
}
```

Unknown fields in `provider_config` are rejected with a `400` error.

---

### Provider defaults (built into code)

If neither `.env` nor `provider_config` sets a value, these defaults apply. All fields are overridable via `provider_config` in the request.

> **Automatic model routing** — Validra uses a cheaper/faster model for *generation* and automatically upgrades to a stronger model for *validation*, where reasoning quality matters more. The `model` field in `provider_config` overrides the **generation** model only; the validation model is set independently by the server.

**Ollama**

| Field | Default | Description |
|---|---|---|
| `model` | `llama3:8b-instruct-q4_0` | Model identifier |
| `temperature` | `0.3` | Sampling temperature (lower = more reliable JSON output) |
| `max_tokens` | `700` | Max output tokens for generation (validation auto-uses 150) |
| `top_p` | `0.9` | Top-p sampling |
| `url` | `http://localhost:11434/api/generate` | Ollama API endpoint |
| `timeout` | `600` | Request timeout in seconds |

**OpenAI**

| Field | Default | Description |
|---|---|---|
| `model` | `gpt-4o-mini` | Generation model (validation auto-upgrades to `gpt-4o`) |
| `temperature` | `0.3` | Sampling temperature |
| `max_tokens` | `750` | Max output tokens for generation (validation auto-uses 150) |
| `timeout` | `60` | Request timeout in seconds |
| `api_key` | — | Required (env or per-request) |
| `base_url` | `https://api.openai.com/v1/chat/completions` | API endpoint |

**Anthropic**

| Field | Default | Description |
|---|---|---|
| `model` | `claude-haiku-4-5-20251001` | Generation model (validation auto-upgrades to `claude-sonnet-4-6`) |
| `temperature` | `0.3` | Sampling temperature |
| `max_tokens` | `750` | Max output tokens for generation (validation auto-uses 150) |
| `timeout` | `60` | Request timeout in seconds |
| `api_key` | — | Required (env or per-request) |
| `base_url` | `https://api.anthropic.com/v1/messages` | API endpoint |
| `anthropic_version` | `2023-06-01` | Anthropic API version header |

**Anthropic — prompt caching**

Static prompt sections (role, rules, output format) are automatically sent with `cache_control: ephemeral`. After the first call for a given schema, subsequent generation batches hit the cache at ~10% of normal input-token cost. No configuration needed.

**Result caching**

Generated test cases are cached in-process for 5 minutes, keyed on `(test_type, payload, payload_meta, max_cases)`. Resubmitting the same schema during development or CI skips the LLM generation call entirely.

---

## API Reference

### `POST /generateAndRun`

Generates test cases and executes them against a target API endpoint.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `endpoint` | string | yes | Target API URL |
| `method` | string | yes | `POST` or `GET` |
| `headers` | object | no | HTTP headers to send (default: `{}`) |
| `payload` | object | yes | Request body or query params |
| `payload_meta` | object | no | Field constraints for smarter test generation (see [Payload Meta guide](#payload_meta)) |
| `test_type` | string | yes | Plugin to use: `FUZZ`, `AUTH`, or `PEN` |
| `max_cases` | integer | no | Number of test cases to generate (3–100, default: 10) |
| `run_validation` | boolean | no | Run LLM validation on responses (default: `true`) |
| `provider` | string | no | LLM provider: `ollama`, `openai`, `anthropic` (default: `ollama`) |
| `provider_config` | object | no | Override provider settings for this request only |

**Example — Fuzz test:**

```json
{
  "endpoint": "https://your-api.com/users",
  "method": "POST",
  "headers": { "Content-Type": "application/json" },
  "payload": {
    "username": "john",
    "age": 25,
    "email": "john@example.com"
  },
  "payload_meta": {
    "username": "required, alphanumeric, [3-20] chars",
    "age": "required, numeric, [0-120]",
    "email": "required, valid email format"
  },
  "test_type": "FUZZ",
  "max_cases": 10,
  "provider": "ollama"
}
```

**Example — Auth test:**

```json
{
  "endpoint": "https://your-api.com/protected",
  "method": "GET",
  "headers": { "Authorization": "Bearer valid-token-here" },
  "payload": {},
  "test_type": "AUTH",
  "max_cases": 8
}
```

**Example — Penetration test:**

```json
{
  "endpoint": "https://your-api.com/items",
  "method": "POST",
  "payload": {
    "item_id": 1,
    "name": "widget",
    "role": "user"
  },
  "test_type": "PEN",
  "max_cases": 15,
  "provider": "openai",
  "provider_config": { "model": "gpt-4o-mini", "temperature": 0.3 }
}
```

**Response:**

```json
{
  "tests": [
    {
      "id": "tc-001",
      "description": "Missing required field: username",
      "request": {
        "payload": { "username": null, "age": 25, "email": "john@example.com" },
        "headers": { "Content-Type": "application/json" }
      },
      "response": {
        "status_code": 422,
        "body": { "error": "username is required" }
      },
      "success": false,
      "duration_ms": 134,
      "validation": {
        "dstatus": "PASS",
        "reason": "API correctly rejected missing required field with 422",
        "confidence": 0.97
      }
    }
  ],
  "summary": {
    "total": 10,
    "success": 3,
    "failed": 7,
    "total_duration_ms": 1842
  }
}
```

---

### `POST /validate`

Validates a single test result using the LLM. Useful when you want to validate a test you already ran manually.

**Request body:**

| Field | Type | Required | Description |
|---|---|---|---|
| `test` | object | yes | The test case object |
| `response` | object | yes | The API response object |
| `meta` | object | no | Payload constraints (optional context) |
| `provider` | string | no | LLM provider to use |
| `provider_config` | object | no | Provider overrides |

**Response:**

```json
{
  "validation": {
    "dstatus": "PASS",
    "reason": "The API returned 401 as expected for a missing Authorization header.",
    "confidence": 0.95
  }
}
```

`dstatus` values:
- `PASS` — response matches expected behavior
- `FAIL` — response does not match expected behavior
- `WARN` — ambiguous or partially correct

---

## Test Plugins

### FUZZ

Generates edge-case and invalid payloads to test input validation. Uses `payload_meta` constraints to craft meaningful boundary violations:

- Missing required fields (`null` values)
- Out-of-range values (below min, above max)
- Type mismatches (string where integer expected, etc.)
- String violations (too short, too long, empty)

Best used to verify your API's input validation and error handling.

---

---

## `payload_meta`

`payload_meta` is a plain string-per-field map that tells the LLM what each field means, what values are valid, and how to generate meaningful edge cases. The more precise your meta, the better the generated tests.

Each value is a free-form string — there is no rigid schema. The LLM reads it as natural language. The hints below are the patterns that produce the most reliable results.

---

### Constraint hints

| Pattern | Example | What the LLM does |
|---|---|---|
| `required` | `"required"` | Generates a case where the field is `null` or missing |
| `optional` | `"optional"` | Generates a case where the field is omitted entirely |
| `alphanumeric` | `"alphanumeric"` | Injects special characters, spaces, symbols |
| `numeric` | `"numeric"` | Injects strings, booleans, floats when int expected |
| `[min-max]` | `"[3-20]"` | Generates values below min and above max |
| `[min-max] chars` | `"[3-20] chars"` | Generates strings shorter and longer than the range |
| `>= N` / `<= N` | `">= 0"` | Generates boundary values and violations |
| `enum: A/B/C` | `"Active/Inactive"` | Generates a value outside the allowed set |
| `valid email format` | `"valid email format"` | Generates malformed emails (missing `@`, no domain, etc.) |
| `valid url` | `"valid url"` | Generates malformed URLs |
| `ISO 8601` / `date` | `"ISO 8601 date"` | Generates invalid date strings |
| `boolean` | `"boolean"` | Injects strings and numbers where bool expected |
| `unique` | `"unique"` | Uses a different value in every test case |
| `generate random` | `"generate random for valid"` | Generates a fresh realistic value each time (e.g. random email) |

---

### Combining hints

Multiple hints on one field work together:

```json
"payload_meta": {
  "username": "required, alphanumeric, [3-20] chars",
  "age":      "required, numeric, >= 0, <= 120",
  "status":   "optional, enum: Active/Inactive",
  "email":    "required, valid email format, unique, generate random for valid"
}
```

This instructs the LLM to:
- Test `username` with null, too-short, too-long, and special-character values
- Test `age` with strings, negatives, and values above 120
- Test `status` with values outside `Active/Inactive`, and omit it entirely in some cases
- Generate a fresh unique valid email in every test case, plus invalid-format variants

---

### Uniqueness and randomness

Some APIs (e.g. user-creation endpoints) reject duplicate values. Use `unique` and/or `generate random` to ensure valid fields vary across test cases:

```json
"email": "required, valid email format, unique, generate random for valid"
```

Without this hint, the LLM may reuse values like `test1@example.com` across cases, causing the API to return `409 Conflict` instead of the error you are testing for.

---

### Full example

```json
{
  "endpoint": "https://api.example.com/users",
  "method": "POST",
  "payload": {
    "name": "Alice",
    "age": 30,
    "status": "Active",
    "role": "user",
    "email": "alice@example.com"
  },
  "payload_meta": {
    "name":   "required, alphanumeric, [3-50] chars",
    "age":    "required, numeric, [0-120]",
    "status": "optional, enum: Active/Inactive",
    "role":   "optional, enum: user/admin/moderator",
    "email":  "required, valid email format, unique, generate random for valid"
  },
  "test_type": "FUZZ",
  "max_cases": 10
}
```

---

### AUTH

Mutates HTTP headers to test authentication and authorization edge cases. Payload is unchanged — only headers are modified:

- Missing `Authorization` header
- Expired or malformed tokens
- Wrong token format (Basic vs Bearer)
- Empty or invalid credentials

Best used to verify your API enforces authentication correctly.

---

### PEN

Generates penetration test-style payloads to probe for common vulnerabilities:

- Injection probes (SQL-like, NoSQL-like, template injection)
- Privilege escalation attempts (role manipulation, `isAdmin` flags)
- Parameter pollution (duplicate or conflicting fields)
- ID tampering (large numbers, negatives, other users' IDs)
- Encoding tricks (Unicode, escaped characters)
- Structural manipulation (arrays, nested objects, nulls)
- Boundary abuse (very long strings, extremely large numbers)

Best used to find security weaknesses in your API's logic.

---

## Project Structure

```
validra-ai-core/
├── app/
│   ├── api/
│   │   ├── routes/
│   │   │   ├── generation.py      # POST /generateAndRun
│   │   │   └── validation.py      # POST /validate
│   │   └── schemas/
│   │       ├── requests.py        # Request models
│   │       └── responses.py       # Response models
│   ├── config/
│   │   └── settings.py            # Pydantic settings
│   ├── engine/
│   │   ├── executor.py            # HTTP request executor
│   │   └── orchestrator.py        # Generation + execution pipeline
│   ├── plugins/
│   │   ├── fuzz/plugin.py         # Fuzz plugin
│   │   ├── security/plugin.py     # Auth plugin
│   │   └── pen/plugin.py          # Penetration test plugin
│   ├── providers/
│   │   ├── ollama/                # Ollama provider
│   │   ├── openai/                # OpenAI provider
│   │   └── anthropic/             # Anthropic provider
│   ├── validator/
│   │   └── llm_validator.py       # LLM-based response validator
│   └── main.py                    # App factory & startup
├── tests/                         # Test suite
├── .github/workflows/             # CI + PyPI publish
├── requirements.txt
└── .env.example
```
