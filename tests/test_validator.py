from unittest.mock import MagicMock

import pytest

from app.validator.llm_validator import LLMValidator


validator = LLMValidator()


def test_extract_clean_json():
    raw = '{"dstatus": "PASS", "reason": "ok", "confidence": 0.9}'
    result = validator._extract_json(raw)
    assert result["dstatus"] == "PASS"
    assert result["confidence"] == 0.9


def test_extract_passes_through_dict():
    data = {"dstatus": "FAIL", "reason": "bad", "confidence": 0.1}
    assert validator._extract_json(data) == data


def test_extract_strips_markdown_code_block():
    raw = '```json\n{"dstatus": "WARN", "reason": "unclear", "confidence": 0.5}\n```'
    result = validator._extract_json(raw)
    assert result["dstatus"] == "WARN"


def test_extract_with_preamble_text():
    raw = 'My analysis: {"dstatus": "PASS", "reason": "correct", "confidence": 1.0}'
    result = validator._extract_json(raw)
    assert result["dstatus"] == "PASS"


def test_extract_raises_on_empty():
    with pytest.raises(ValueError, match="Empty LLM response"):
        validator._extract_json("")


def test_extract_raises_on_no_object():
    with pytest.raises(ValueError, match="No JSON object found"):
        validator._extract_json("no object here")


def test_extract_raises_on_invalid_json():
    with pytest.raises(ValueError, match="Invalid JSON"):
        validator._extract_json('{"broken": }')


def test_validate_returns_warn_when_provider_raises():
    provider = MagicMock()
    provider.complete.side_effect = Exception("LLM unavailable")
    config = MagicMock()

    result = validator.validate(
        test={"description": "test", "payload": {}},
        response={"status_code": 200, "body": {}},
        provider=provider,
        provider_config=config,
    )

    assert result["dstatus"] == "WARN"
    assert result["confidence"] == 0.0


def test_validate_raises_without_provider():
    with pytest.raises(ValueError, match="provider must be supplied"):
        validator.validate(test={}, response={}, provider=None, provider_config=object())


def test_validate_raises_without_provider_config():
    with pytest.raises(ValueError, match="provider_config must be supplied"):
        validator.validate(test={}, response={}, provider=object(), provider_config=None)
