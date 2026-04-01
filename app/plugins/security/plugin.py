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

    def _build_prompt(self, example, previous_cases, batch_size, meta=None):
        return f"""
You are a senior QA engineer specialized in API security testing.

TASK:
Generate up to {batch_size} security-focused test cases for authentication and authorization validation.

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
  {{
    "description": "...",
    "headers": {{}},
    "payload": <same as input payload>
  }}
]

GUIDELINES:
- Focus on Authorization header issues
- Include missing, malformed, or incorrect tokens
- Simulate expired or invalid tokens
- Include edge cases

Previous cases:
{json.dumps(previous_cases, indent=2)}

INPUT:
{json.dumps(example, indent=2)}
"""
