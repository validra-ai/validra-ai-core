import json
from app.plugins.llm_plugin import LLMBasePlugin


class PenTestPlugin(LLMBasePlugin):
    name = "pen"

    def _is_valid_case(self, case):
        return (
            isinstance(case, dict)
            and "description" in case
            and "payload" in case
            and isinstance(case["payload"], dict)
            and len(case["payload"]) > 0
        )

    def _build_prompt(self, example, previous_cases, batch_size, meta=None):
        return f"""
You are a senior penetration tester specializing in API security.

TASK:
Generate up to {batch_size} realistic penetration test cases to identify API vulnerabilities.

STRICT OUTPUT RULES:
- Return ONLY a valid JSON array
- No extra text
- Output must start with [ and end with ]
- Use only valid JSON types
- Do NOT include real exploits or harmful payloads
- Use SAFE test patterns only

IMPORTANT:
- Do NOT repeat previous cases
- MODIFY ONLY the payload
- Keep structure similar to original payload
- Each test must simulate a realistic attack scenario

FORMAT:
[
  {{
    "description": "...",
    "payload": {{}}
  }}
]

TEST STRATEGIES:

1. Injection Probes (SAFE)
- SQL-like: "' OR '1'='1"
- NoSQL-like: {{ "$ne": null }}
- Template-like: "{{{{7*7}}}}"

2. Privilege Escalation Attempts
- "role": "admin", "isAdmin": true, "permissions": ["*"]

3. Parameter Pollution
- Duplicate or conflicting fields, unexpected extra fields

4. ID Tampering
- userId: very large number, negative number, another user's ID

5. Encoding Tricks
- Unicode encoding, escaped characters, mixed encodings

6. Structure Manipulation
- Replace values with arrays, nested objects, nulls in critical fields

7. Boundary Abuse
- Extremely long strings, very large numbers

GUIDELINES:
- Keep payload realistic (similar structure)
- Do NOT break JSON validity
- Each case should represent a clear attack idea

Previous cases:
{json.dumps(previous_cases, indent=2)}

INPUT:
{json.dumps(example["payload"], indent=2)}
"""
