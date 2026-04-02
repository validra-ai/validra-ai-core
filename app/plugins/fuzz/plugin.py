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

    def _build_prompt(self, example, previous_cases, batch_size, meta):
        return f"""
You are a senior QA engineer specialized in API testing.

TASK:
Generate up to {batch_size} diverse NEGATIVE and edge test cases.

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
META USAGE
====================================================

META describes constraints for each field in the payload.

{json.dumps(meta, indent=2)}

Use META to generate invalid and edge cases such as:
- Required fields -> missing, null, empty
- Numeric ranges -> below min, above max
- String constraints -> too short, too long
- Type mismatches

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
  {{
    "description": "Body missing",
    "payload": {{
      "body": null,
      "title": "Validra Test",
      "userId": 30
    }}
  }},
  {{
    "description": "Title too short",
    "payload": {{
      "body": "Testing",
      "title": "",
      "userId": 30
    }}
  }},
  {{
    "description": "Title too long",
    "payload": {{
      "body": "Testing",
      "title": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "userId": 30
    }}
  }}
]

====================================================
STRICT RULES
====================================================

- Do NOT repeat previous cases
- Generate only negative and edge cases
- Do NOT include headers
- Do NOT include any fields outside payload
- Do NOT include code or explanations
- Keep outputs diverse

====================================================
INPUT PAYLOAD
====================================================

{json.dumps(example, indent=2)}

====================================================
PREVIOUS CASES (DO NOT DUPLICATE)
====================================================

{json.dumps(previous_cases, indent=2)}

====================================================
END OF INSTRUCTIONS
====================================================
"""
