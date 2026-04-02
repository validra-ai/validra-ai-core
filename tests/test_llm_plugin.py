import pytest

from app.plugins.llm_plugin import LLMBasePlugin


class _Plugin(LLMBasePlugin):
    name = "test"

    def _build_system_prompt(self) -> str:
        return ""

    def _build_user_prompt(self, example, previous_cases_summary, batch_size, meta=None) -> str:
        return ""

    def _is_valid_case(self, case):
        return isinstance(case, dict) and "description" in case and "payload" in case


plugin = _Plugin()


def test_extract_clean_array():
    raw = '[{"description": "test", "payload": {}}]'
    result = plugin._extract_json(raw)
    assert isinstance(result, list)
    assert len(result) == 1


def test_extract_passes_through_list():
    data = [{"description": "t", "payload": {}}]
    assert plugin._extract_json(data) == data


def test_extract_strips_preamble():
    raw = 'Here are the cases:\n[{"description": "t", "payload": {}}]'
    result = plugin._extract_json(raw)
    assert len(result) == 1


def test_extract_expands_str_repeat():
    raw = '[{"description": "t", "payload": {"field": "a".repeat(5)}}]'
    result = plugin._extract_json(raw)
    assert result[0]["payload"]["field"] == "aaaaa"


def test_extract_expands_prefix_plus_repeat():
    raw = '[{"description": "t", "payload": {"field": "x" + "a".repeat(3)}}]'
    result = plugin._extract_json(raw)
    assert result[0]["payload"]["field"] == "xaaa"


def test_extract_replaces_undefined_with_null():
    raw = '[{"description": "t", "payload": {"field": undefined}}]'
    result = plugin._extract_json(raw)
    assert result[0]["payload"]["field"] is None


def test_extract_expands_new_array_join():
    raw = '[{"description": "t", "payload": {"f": new Array(4).join("x")}}]'
    result = plugin._extract_json(raw)
    assert result[0]["payload"]["f"] == "xxx"


def test_extract_expands_prefix_plus_new_array_join():
    raw = '[{"description": "t", "payload": {"f": "pre" + new Array(3).join("-")}}]'
    result = plugin._extract_json(raw)
    assert result[0]["payload"]["f"] == "pre--"


def test_extract_raises_on_no_array():
    with pytest.raises(ValueError, match="No JSON array found"):
        plugin._extract_json("no array here")


def test_extract_raises_on_wrong_type():
    with pytest.raises(ValueError, match="Unexpected LLM response type"):
        plugin._extract_json(42)


def test_generate_raises_without_provider():
    with pytest.raises(ValueError, match="provider must be supplied"):
        plugin.generate(example={}, provider=None, provider_config=object())


def test_generate_raises_without_provider_config():
    with pytest.raises(ValueError, match="provider_config must be supplied"):
        plugin.generate(example={}, provider=object(), provider_config=None)


def test_generate_passes_system_prompt_to_provider():
    """generate() must forward the static system prompt as a kwarg to provider.complete."""
    from unittest.mock import MagicMock
    provider = MagicMock()
    config = MagicMock()
    provider.complete.return_value = '[{"description": "t", "payload": {"x": 1}}]'

    plugin.generate(example={"x": 0}, max_cases=1, provider=provider, provider_config=config)

    _, kwargs = provider.complete.call_args
    assert "system" in kwargs


def test_generate_sends_descriptions_not_full_cases_to_second_batch(monkeypatch):
    """Previous cases are passed as description strings only, not full objects.
    This keeps context size flat instead of growing O(N) per batch.
    """
    from unittest.mock import MagicMock
    captured_summaries: list = []

    original_build = _Plugin._build_user_prompt

    def spy_build(self, example, previous_cases_summary, batch_size, meta=None):
        captured_summaries.append(list(previous_cases_summary))
        return original_build(self, example, previous_cases_summary, batch_size, meta)

    monkeypatch.setattr(_Plugin, "_build_user_prompt", spy_build)

    provider = MagicMock()
    config = MagicMock()
    provider.complete.side_effect = [
        '[{"description": "first case", "payload": {"x": 1}}]',
        '[{"description": "second case", "payload": {"x": 2}}]',
    ]

    plugin.generate(example={"x": 0}, max_cases=2, provider=provider, provider_config=config)

    # Second batch call must receive the description string of the first case,
    # not the full {"description": ..., "payload": ...} object.
    assert len(captured_summaries) >= 2
    assert captured_summaries[1] == ["first case"]
