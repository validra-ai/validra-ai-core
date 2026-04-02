import json
import re
from abc import abstractmethod
from typing import Optional

from app.plugins.base import BasePlugin


class LLMBasePlugin(BasePlugin):

    def _extract_json(self, response: str) -> list:
        if isinstance(response, list):
            return response

        if not isinstance(response, str):
            raise ValueError(f"Unexpected LLM response type: {type(response)}")

        response = re.sub(r"(?i)final text:\s*", "", response)

        start = response.find("[")
        end = response.rfind("]")

        if start == -1 or end == -1:
            raise ValueError("No JSON array found in LLM response")

        json_str = response[start : end + 1]

        # Sanitize JS expressions LLMs sometimes emit instead of literal values

        # "prefix" + new Array(N).join("sep")  →  expand to a literal string
        def _expand_concat(m):
            prefix, n, sep = m.group(1), int(m.group(2)), m.group(3)
            return json.dumps(prefix + sep * max(n - 1, 0))

        json_str = re.sub(
            r'"([^"]*)"\s*\+\s*new\s+Array\((\d+)\)\.join\("([^"]*)"\)',
            _expand_concat,
            json_str,
        )
        # new Array(N).join("sep")  →  expand to a literal string
        def _expand_array_join(m):
            n, sep = int(m.group(1)), m.group(2)
            return json.dumps(sep * max(n - 1, 0))

        json_str = re.sub(
            r'new\s+Array\((\d+)\)\.join\("([^"]*)"\)',
            _expand_array_join,
            json_str,
        )
        json_str = re.sub(
            r"new\s+Array\(\d+\)\.fill\([^\)]*\)\.join\([^\)]*\)",
            '"INVALID_STRING"',
            json_str,
        )
        json_str = re.sub(r"new\s+\w+\(.*?\)", '"INVALID_STRING"', json_str)
        json_str = re.sub(r"\.repeat\(\d+\)", "", json_str)
        json_str = re.sub(r"\bundefined\b", "null", json_str)

        return json.loads(json_str)

    @abstractmethod
    def _build_prompt(self, example, previous_cases, batch_size, meta=None) -> str:
        raise NotImplementedError

    @abstractmethod
    def _is_valid_case(self, case: dict) -> bool:
        raise NotImplementedError

    def generate(
        self,
        example,
        previous_cases=None,
        max_cases=10,
        meta=None,
        provider=None,
        provider_config=None,
    ):
        if provider is None:
            raise ValueError("A provider must be supplied to generate()")
        if provider_config is None:
            raise ValueError("A provider_config must be supplied to generate()")

        if previous_cases is None:
            previous_cases = []

        all_cases = previous_cases.copy()

        while len(all_cases) < max_cases:
            remaining = max_cases - len(all_cases)
            batch_size = min(3, remaining)
            prompt = self._build_prompt(example, all_cases, batch_size, meta)

            try:
                raw = provider.complete(prompt, provider_config)
                print("RAW LLM OUTPUT:\n", raw)

                new_cases = self._extract_json(raw)
                print("PARSED CASES:\n", new_cases)

                if isinstance(new_cases, list):
                    added_any = False
                    for case in new_cases:
                        if len(all_cases) >= max_cases:
                            break
                        if not isinstance(case, dict):
                            continue
                        if not self._is_valid_case(case):
                            continue
                        if case not in all_cases:
                            all_cases.append(case)
                            added_any = True

                    if not added_any:
                        break
                else:
                    print("Unexpected format from LLM:", new_cases)

            except Exception as e:
                raise RuntimeError(str(e))

        return all_cases[:max_cases]
