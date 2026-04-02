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


def test_run_stream_validation_uses_validation_provider_config():
    """When a separate validation_provider_config is supplied, validate() must
    receive it — not the generation provider_config."""
    plugin = MagicMock()
    executor = MagicMock()
    validator = MagicMock()
    provider = MagicMock()
    gen_config = MagicMock(name="gen_config")
    val_config = MagicMock(name="val_config")

    executor.execute.return_value = {"status_code": 200, "body": {}}
    validator.validate.return_value = {"dstatus": "PASS", "reason": "ok", "confidence": 0.9}

    orch = Orchestrator(
        plugin, executor, validator, provider, gen_config,
        validation_provider=provider,
        validation_provider_config=val_config,
    )

    list(orch.run_stream(_req(validate=True), _tests(1)))

    call_kwargs = validator.validate.call_args.kwargs
    assert call_kwargs["provider_config"] is val_config
    assert call_kwargs["provider_config"] is not gen_config


def test_run_stream_validates_all_tests_in_parallel():
    """validator.validate must be called once per test (parallel execution)."""
    orch = _make_orch()
    n = 5

    list(orch.run_stream(_req(validate=True), _tests(n)))

    assert orch.validator.validate.call_count == n


def test_run_stream_results_ordered_after_parallel_validation():
    """Results must be yielded in the original test order even though
    validation runs in parallel."""
    orch = _make_orch()
    tests = _tests(3)

    events = list(orch.run_stream(_req(validate=True), tests))
    result_events = [e for e in events if e["event"] == "result"]

    descriptions = [e["result"]["description"] for e in result_events]
    expected = [t["description"] for t in tests]
    assert descriptions == expected
