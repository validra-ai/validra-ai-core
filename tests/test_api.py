import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client():
    app = create_app()
    with TestClient(app) as c:
        yield c


def _parse_sse(text: str) -> list[dict]:
    events = []
    for line in text.splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events


# ── /generateAndRun ──────────────────────────────────────────────────────────

BASE_GENERATE_PAYLOAD = {
    "endpoint": "http://example.com/api",
    "method": "POST",
    "payload": {"username": "test", "age": 25},
    "test_type": "FUZZ",
    "max_cases": 3,
    "run_validation": False,
    "provider": "ollama",
}


def test_generate_invalid_plugin_returns_error_event(client):
    response = client.post(
        "/generateAndRun",
        json={**BASE_GENERATE_PAYLOAD, "test_type": "INVALID_PLUGIN"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert any(e.get("phase") == "error" for e in events)


def test_generate_invalid_provider_returns_error_event(client):
    response = client.post(
        "/generateAndRun",
        json={**BASE_GENERATE_PAYLOAD, "provider": "nonexistent_provider"},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert any(e.get("phase") == "error" for e in events)


def test_generate_invalid_provider_config_returns_error_event(client):
    response = client.post(
        "/generateAndRun",
        json={**BASE_GENERATE_PAYLOAD, "provider_config": {"unknown_field": "bad"}},
    )
    assert response.status_code == 200
    events = _parse_sse(response.text)
    assert any(e.get("phase") == "error" for e in events)


def test_generate_happy_path_emits_done_event(client):
    fake_cases = json.dumps([
        {"description": "missing username", "payload": {"username": None, "age": 25}},
        {"description": "negative age", "payload": {"username": "test", "age": -1}},
        {"description": "empty string", "payload": {"username": "", "age": 25}},
    ])
    fake_response = {"status_code": 422, "body": {"error": "invalid"}}

    provider = client.app.state.provider_registry.get("ollama")
    executor = client.app.state.executor

    with (
        patch.object(provider, "complete", return_value=fake_cases),
        patch.object(executor, "execute", return_value=fake_response),
    ):
        response = client.post("/generateAndRun", json=BASE_GENERATE_PAYLOAD)

    assert response.status_code == 200
    events = _parse_sse(response.text)
    phases = [e.get("phase") for e in events]
    assert "done" in phases
    assert "error" not in phases

    done_event = next(e for e in events if e.get("phase") == "done")
    assert done_event["summary"]["total"] == 3


# ── /validate ────────────────────────────────────────────────────────────────

BASE_VALIDATE_PAYLOAD = {
    "test": {"description": "missing auth", "payload": {}},
    "response": {"status_code": 401, "body": {"error": "unauthorized"}},
    "provider": "ollama",
}


def test_validate_invalid_provider_returns_400(client):
    response = client.post(
        "/validate",
        json={**BASE_VALIDATE_PAYLOAD, "provider": "nonexistent"},
    )
    assert response.status_code == 400


def test_validate_invalid_provider_config_returns_400(client):
    response = client.post(
        "/validate",
        json={**BASE_VALIDATE_PAYLOAD, "provider_config": {"bogus_key": "value"}},
    )
    assert response.status_code == 400


def test_validate_happy_path(client):
    fake_result = '{"dstatus": "PASS", "reason": "correct 401", "confidence": 0.95}'

    provider = client.app.state.provider_registry.get("ollama")

    with patch.object(provider, "complete", return_value=fake_result):
        response = client.post("/validate", json=BASE_VALIDATE_PAYLOAD)

    assert response.status_code == 200
    body = response.json()
    assert body["validation"]["dstatus"] == "PASS"
    assert body["validation"]["confidence"] == 0.95


# ── Generation result cache ──────────────────────────────────────────────────

def test_generate_cache_hit_skips_llm_on_second_identical_request(client):
    """Submitting the same (plugin, payload, meta, max_cases) twice must only
    call provider.complete for generation on the first request; the second
    request is served from the in-process cache."""
    import app.api.routes.generation as gen_module

    fake_cases = json.dumps([
        {"description": "missing field", "payload": {"username": None, "age": 25}},
        {"description": "negative age",  "payload": {"username": "test", "age": -1}},
        {"description": "empty string",  "payload": {"username": "", "age": 25}},
    ])
    fake_response = {"status_code": 422, "body": {"error": "invalid"}}

    provider = client.app.state.provider_registry.get("ollama")
    executor = client.app.state.executor

    # Clear the cache so this test is independent of run order
    with gen_module._cache_lock:
        gen_module._cache.clear()

    with (
        patch.object(provider, "complete", return_value=fake_cases) as mock_complete,
        patch.object(executor, "execute", return_value=fake_response),
    ):
        client.post("/generateAndRun", json={**BASE_GENERATE_PAYLOAD, "run_validation": False})
        first_call_count = mock_complete.call_count

        client.post("/generateAndRun", json={**BASE_GENERATE_PAYLOAD, "run_validation": False})
        second_call_count = mock_complete.call_count

    assert first_call_count > 0, "First request must call the LLM"
    assert second_call_count == first_call_count, "Second identical request must be served from cache"


def test_generate_cache_miss_on_different_payload(client):
    """Changing any part of the payload must produce a cache miss."""
    import app.api.routes.generation as gen_module

    fake_cases = json.dumps([
        {"description": "missing field", "payload": {"username": None, "age": 25}},
        {"description": "negative age",  "payload": {"username": "test", "age": -1}},
        {"description": "empty string",  "payload": {"username": "", "age": 25}},
    ])
    fake_response = {"status_code": 422, "body": {"error": "invalid"}}

    provider = client.app.state.provider_registry.get("ollama")
    executor = client.app.state.executor

    with gen_module._cache_lock:
        gen_module._cache.clear()

    payload_a = {**BASE_GENERATE_PAYLOAD, "payload": {"username": "a", "age": 1}, "run_validation": False}
    payload_b = {**BASE_GENERATE_PAYLOAD, "payload": {"username": "b", "age": 2}, "run_validation": False}

    with (
        patch.object(provider, "complete", return_value=fake_cases) as mock_complete,
        patch.object(executor, "execute", return_value=fake_response),
    ):
        client.post("/generateAndRun", json=payload_a)
        after_first = mock_complete.call_count

        client.post("/generateAndRun", json=payload_b)
        after_second = mock_complete.call_count

    assert after_second > after_first, "Different payload must trigger a new LLM call"
