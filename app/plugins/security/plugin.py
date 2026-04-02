import json
from app.plugins.llm_plugin import LLMBasePlugin


class SecurityPlugin(LLMBasePlugin):
    name = "security"

    def _is_valid_case(self, case):
        return (
            isinstance(case, dict)
            and "description" in case
            and "headers" in case
            and "payload" in case
            and case["payload"] != {}
        )

    def _build_system_prompt(self) -> str:
        return """You are a senior QA engineer specialized in API security testing.

STRICT OUTPUT RULES:
- Return ONLY a valid JSON array
- No extra text
- Output must start with [ and end with ]
- Use only valid JSON types
- Do NOT include real exploits, hacking instructions, or attack payloads
- Focus on misconfigurations, invalid inputs, and edge cases

IMPORTANT:
- Do NOT repeat previous cases
- DO NOT modify payload — ALWAYS reuse the original payload exactly as provided
- ONLY modify headers
- Keep cases diverse

FORMAT:
[
  {
    "description": "...",
    "headers": {},
    "payload": <same as input payload>
  }
]

GUIDELINES:
- Focus on Authorization header issues
- Include missing, malformed, or incorrect tokens
- Simulate expired or invalid tokens
- Include edge cases"""

    def _build_user_prompt(self, example, previous_cases_summary: list[str], batch_size: int, meta=None) -> str:
        return f"""TASK: Generate EXACTLY {batch_size} security-focused test cases for authentication and authorization validation. No more, no fewer.

INPUT:
{json.dumps(example, indent=2)}

UNIQUENESS RULE:
If any field in the payload mentions "unique", "random", or "generate random" in the
meta constraints, produce a different realistic value for it in every test case.

ALREADY GENERATED (descriptions only — do NOT duplicate these scenarios):
{json.dumps(previous_cases_summary, indent=2)}

Output the JSON array now."""
