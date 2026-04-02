from unittest.mock import MagicMock

from app.engine.orchestrator import Orchestrator


def _make_orch():
    plugin = MagicMock()
    executor = MagicMock()
    validator = MagicMock()
    provider = MagicMock()
    provider_config = MagicMock()

    executor.execute.return_value = {"status_code": 200, "body": {"ok": True}}
    validator.validate.return_value = {"dstatus": "PASS", "reason": "ok", "confidence": 0.9}

    return Orchestrator(plugin, executor, validator, provider, provider_config)


def _req(validate=True):
    return {
        "endpoint": "http://example.com",
        "method": "POST",
        "headers": {},
        "validate": validate,
        "meta": {},
    }


def _tests(n=2):
    return [{"description": f"test {i}", "payload": {"i": i}} for i in range(n)]


def test_run_counts_successes_and_failures():
    orch = _make_orch()
    orch.executor.execute.side_effect = [
        {"status_code": 200, "body": {}},
        {"status_code": 422, "body": {"error": "bad"}},
    ]

    result = orch.run(_req(), _tests(2))

    assert result["summary"]["total"] == 2
    assert result["summary"]["success"] == 1
    assert result["summary"]["failed"] == 1


def test_run_skips_validation_when_disabled():
    orch = _make_orch()

    orch.run(_req(validate=False), _tests(1))

    orch.validator.validate.assert_not_called()


def test_run_calls_validation_when_enabled():
    orch = _make_orch()

    result = orch.run(_req(validate=True), _tests(1))

    orch.validator.validate.assert_called_once()
    assert result["tests"][0]["validation"] is not None


def test_run_assigns_sequential_ids():
    orch = _make_orch()

    result = orch.run(_req(), _tests(3))

    ids = [t["id"] for t in result["tests"]]
    assert ids == ["tc-001", "tc-002", "tc-003"]


def test_run_tracks_total_duration():
    orch = _make_orch()

    result = orch.run(_req(), _tests(2))

    assert result["summary"]["total_duration_ms"] >= 0


def test_run_stream_yields_executing_validating_result_events():
    orch = _make_orch()

    events = list(orch.run_stream(_req(), _tests(1)))

    event_types = [e["event"] for e in events]
    assert "executing" in event_types
    assert "validating" in event_types
    assert "result" in event_types


def test_run_stream_skips_validating_event_when_disabled():
    orch = _make_orch()

    events = list(orch.run_stream(_req(validate=False), _tests(1)))

    event_types = [e["event"] for e in events]
    assert "validating" not in event_types


def test_run_stream_result_has_expected_fields():
    orch = _make_orch()

    events = list(orch.run_stream(_req(), _tests(1)))
    result_event = next(e for e in events if e["event"] == "result")

    assert "id" in result_event["result"]
    assert "description" in result_event["result"]
    assert "response" in result_event["result"]
    assert "success" in result_event["result"]
    assert "duration_ms" in result_event["result"]
