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
    "validate": False,
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
