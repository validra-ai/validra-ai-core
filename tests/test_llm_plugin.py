import pytest

from app.plugins.llm_plugin import LLMBasePlugin


class _Plugin(LLMBasePlugin):
    name = "test"

    def _build_prompt(self, example, previous_cases, batch_size, meta=None):
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
