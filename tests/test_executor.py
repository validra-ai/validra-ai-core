from unittest.mock import MagicMock, patch

import requests as req_lib

from app.engine.executor import Executor


def _req(method="POST"):
    return {"endpoint": "http://example.com/api", "method": method}


def test_post_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"result": "ok"}

    with patch("app.engine.executor.requests.post", return_value=mock_resp):
        result = Executor().execute(_req("POST"), {"key": "value"})

    assert result["status_code"] == 200
    assert result["body"] == {"result": "ok"}


def test_get_success():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"items": []}

    with patch("app.engine.executor.requests.get", return_value=mock_resp):
        result = Executor().execute(_req("GET"), {"q": "test"})

    assert result["status_code"] == 200
    assert result["body"] == {"items": []}


def test_timeout_returns_408():
    with patch("app.engine.executor.requests.post", side_effect=req_lib.exceptions.Timeout):
        result = Executor().execute(_req(), {})

    assert result["status_code"] == 408
    assert result["error"] == "timeout"


def test_connection_error_returns_503():
    with patch("app.engine.executor.requests.post", side_effect=req_lib.exceptions.ConnectionError):
        result = Executor().execute(_req(), {})

    assert result["status_code"] == 503
    assert result["error"] == "connection_error"


def test_unsupported_method_returns_500():
    result = Executor().execute(_req("DELETE"), {})

    assert result["status_code"] == 500
    assert "error" in result


def test_non_json_response_uses_text():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.side_effect = ValueError("not json")
    mock_resp.text = "plain text response"

    with patch("app.engine.executor.requests.post", return_value=mock_resp):
        result = Executor().execute(_req(), {})

    assert result["body"] == "plain text response"


def test_custom_headers_forwarded():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}

    with patch("app.engine.executor.requests.post", return_value=mock_resp) as mock_post:
        Executor().execute(_req(), {}, headers={"Authorization": "Bearer token"})

    _, kwargs = mock_post.call_args
    assert kwargs["headers"] == {"Authorization": "Bearer token"}
