import json
from app.plugins.llm_plugin import LLMBasePlugin


class FuzzPlugin(LLMBasePlugin):
    name = "fuzz"

    def _is_valid_case(self, case):
        return (
            isinstance(case, dict)
            and "description" in case
            and "payload" in case
            and isinstance(case["payload"], dict)
        )

    def _build_system_prompt(self) -> str:
        return """You are a senior QA engineer specialized in API testing.

====================================================
CRITICAL INSTRUCTIONS (MUST FOLLOW STRICTLY)
====================================================

- You MUST return ONLY valid JSON
- Output MUST be a JSON array
- Do NOT include any explanations, markdown, comments, or extra text
- Output must start with [ and end with ]
- The response will be parsed programmatically — invalid JSON will be rejected

====================================================
STRICT OUTPUT CONSTRAINTS
====================================================

- Do NOT use:
  - JavaScript expressions (e.g. "a".repeat(10))
  - Any programming syntax or code
  - Functions, methods, or constructors (e.g. new String, repeat, fill)
  - Pseudo-code
  - Computations or expressions of any kind
- All values MUST be literal JSON values only:
  - string, number, boolean (true/false), null, object, array

====================================================
STRING RULES (VERY IMPORTANT)
====================================================

- If a field requires a long string, you MUST write the full string explicitly
- DO NOT generate strings using any expression or shorthand

BAD:  "title": "a".repeat(51)
GOOD: "title": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"

====================================================
TEST CASE REQUIREMENTS
====================================================

Each test case MUST include:
- "description": short explanation of the scenario
- "payload": object with mutated input values

====================================================
OUTPUT FORMAT EXAMPLE
REMEMBER: All string values must be written out fully as literals.
NEVER write: "a" + "a".repeat(21) or "a".repeat(21) — write the actual characters.

[
  {
    "description": "Body missing",
    "payload": {
      "body": null,
      "title": "Validra Test",
      "userId": 30
    }
  },
  {
    "description": "Title too short",
    "payload": {
      "body": "Testing",
      "title": "",
      "userId": 30
    }
  },
  {
    "description": "Title too long",
    "payload": {
      "body": "Testing",
      "title": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "userId": 30
    }
  }
]

====================================================
STRICT RULES
====================================================

- Generate EXACTLY the number of cases requested — not more, not fewer
- Do NOT repeat previous cases
- Generate only negative and edge cases
- Do NOT include headers
- Do NOT include any fields outside payload
- Do NOT include code or explanations
- Keep outputs diverse"""

    def _build_user_prompt(self, example, previous_cases_summary: list[str], batch_size: int, meta=None) -> str:
        return f"""TASK: Generate EXACTLY {batch_size} diverse NEGATIVE and edge test cases. No more, no fewer.

META CONSTRAINTS (use to drive invalid/edge values):
{json.dumps(meta or {}, indent=2)}

UNIQUENESS RULE:
If a META field mentions "unique", "random", or "generate random", you MUST produce a
different realistic value for that field in every test case. Never reuse values like
test1@, test2@. Use realistic-looking random values (e.g. "alice.morgan42@example.com",
"dev.user_9x@mail.co").

INPUT PAYLOAD:
{json.dumps(example, indent=2)}

ALREADY GENERATED (descriptions only — do NOT duplicate these scenarios):
{json.dumps(previous_cases_summary, indent=2)}

Output the JSON array now."""
