import json
import re
from typing import Optional

from app.validator.base import BaseValidator

_VALIDATOR_SYSTEM = """You are an expert API test validator.

Your job is to determine if the API response satisfies the intent of the test case.

EVALUATION INSTRUCTIONS:
- Use the test description as the primary source of intent.
- Evaluate whether the API behaved correctly.
- Consider:
  - Whether invalid inputs were rejected
  - Whether valid inputs were accepted
  - Whether the response matches expected behavior
  - Whether errors are appropriate or unexpected
- Meta constraints are additional context to guide your reasoning.

OUTPUT FORMAT (STRICT JSON ONLY):
- Output MUST be a single JSON object
- No explanations outside JSON
- No markdown or code blocks
- The response must start with { and end with }
- Keep the "reason" field concise (1-3 sentences)

Return:

{
  "dstatus": "PASS | FAIL | WARN",
  "reason": "Brief explanation",
  "confidence": 0.0
}"""


class LLMValidator(BaseValidator):

    def validate(
        self,
        test: dict,
        response: dict,
        meta: Optional[dict] = None,
        provider=None,
        provider_config=None,
    ) -> dict:
        if provider is None:
            raise ValueError("A provider must be supplied to validate()")
        if provider_config is None:
            raise ValueError("A provider_config must be supplied to validate()")

        meta = meta or {}

        prompt = f"""TEST DESCRIPTION:
{test.get("description")}

TEST PAYLOAD:
{json.dumps(test.get("payload", {}), indent=2)}

META CONSTRAINTS (for context only):
{json.dumps(meta, indent=2)}

API RESPONSE:
{json.dumps(response, indent=2)}

Evaluate and return the JSON object."""

        try:
            raw = provider.complete(prompt, provider_config, system=_VALIDATOR_SYSTEM)
            return self._extract_json(raw)
        except Exception as e:
            return {
                "dstatus": "WARN",
                "reason": f"LLM validation failed: {str(e)}",
                "confidence": 0.0,
            }

    def _extract_json(self, raw: str) -> dict:
        if not raw:
            raise ValueError("Empty LLM response")

        if isinstance(raw, dict):
            return raw

        if not isinstance(raw, str):
            raise ValueError(f"Unsupported LLM output type: {type(raw)}")

        raw = raw.strip()

        # Strip markdown code blocks if present
        if "```" in raw:
            parts = raw.split("```")
            for part in parts:
                part = part.strip()
                if part.startswith("json"):
                    part = part[4:].strip()
                if part.startswith("{"):
                    raw = part
                    break

        start = raw.find("{")
        end = raw.rfind("}")

        if start == -1 or end == -1:
            raise ValueError(f"No JSON object found in LLM output: {raw}")

        json_str = raw[start : end + 1]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON from LLM: {e}")
