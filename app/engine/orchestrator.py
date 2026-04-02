import time

from app.engine.executor import Executor
from app.validator.base import BaseValidator


class Orchestrator:

    def __init__(
        self,
        plugin,
        executor: Executor,
        validator: BaseValidator,
        provider,
        provider_config,
    ):
        self.plugin = plugin
        self.executor = executor
        self.validator = validator
        self.provider = provider
        self.provider_config = provider_config

    def generate(self, payload: dict, max_cases: int) -> list:
        return self.plugin.generate(
            example=payload,
            previous_cases=[],
            max_cases=max_cases,
            meta=payload.get("meta", {}),
            provider=self.provider,
            provider_config=self.provider_config,
        )

    def run_stream(self, request: dict, tests: list, stop_event=None):
        """Generator yielding typed step events for each test.

        Event shapes:
          {"event": "executing",  "progress": N, "total": T}
          {"event": "validating", "progress": N, "total": T}
          {"event": "result",     "progress": N, "total": T, "result": {...}}
          {"event": "cancelled",  "progress": N, "total": T}
        """
        validate_enabled = request.get("validate", True)
        meta = request.get("meta", {})
        total = len(tests)

        for idx, test in enumerate(tests, start=1):
            if stop_event and stop_event.is_set():
                yield {"event": "cancelled", "progress": idx - 1, "total": total}
                return

            payload = test.get("payload", {})
            test_headers = test.get("headers")
            effective_headers = test_headers if test_headers is not None else request.get("headers", {})

            yield {"event": "executing", "progress": idx, "total": total}

            start = time.time()
            response = self.executor.execute(request, payload, headers=effective_headers)
            duration = int((time.time() - start) * 1000)
            success = 200 <= response.get("status_code", 500) < 300

            validation_result = None
            if validate_enabled:
                yield {"event": "validating", "progress": idx, "total": total}
                validation_result = self.validator.validate(
                    test=test,
                    response=response,
                    meta=meta,
                    provider=self.provider,
                    provider_config=self.provider_config,
                )

            yield {
                "event": "result",
                "progress": idx,
                "total": total,
                "result": {
                    "id": f"tc-{idx:03}",
                    "description": test.get("description"),
                    "request": {
                        "headers": test_headers if test_headers is not None else request.get("headers", {}),
                        "body": payload,                
                    },
                    "response": response,
                    "success": success,
                    "duration_ms": duration,
                    "validation": validation_result,
                },
            }

    def run(self, request: dict, tests: list) -> dict:
        validate_enabled = request.get("validate", True)
        meta = request.get("meta", {})
        enriched_tests = []
        success_count = 0
        total_duration = 0

        for idx, test in enumerate(tests, start=1):
            payload = test.get("payload", {})
            test_headers = test.get("headers")
            effective_headers = test_headers if test_headers is not None else request.get("headers", {})

            start = time.time()
            response = self.executor.execute(request, payload, headers=effective_headers)
            duration = int((time.time() - start) * 1000)
            total_duration += duration

            success = 200 <= response.get("status_code", 500) < 300
            if success:
                success_count += 1

            validation_result = None
            if validate_enabled:
                validation_result = self.validator.validate(
                    test=test,
                    response=response,
                    meta=meta,
                    provider=self.provider,
                    provider_config=self.provider_config,
                )

            enriched_tests.append({
                "id": f"tc-{idx:03}",
                "description": test.get("description"),
                "request": {
                    "headers": test_headers if test_headers is not None else request.get("headers", {}),
                    "body": payload,
                },
                "response": response,
                "success": success,
                "duration_ms": duration,
                "validation": validation_result,
            })

        return {
            "tests": enriched_tests,
            "summary": {
                "total": len(enriched_tests),
                "success": success_count,
                "failed": len(enriched_tests) - success_count,
                "total_duration_ms": total_duration,
            },
        }
