import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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
        validation_provider=None,
        validation_provider_config=None,
    ):
        self.plugin = plugin
        self.executor = executor
        self.validator = validator
        self.provider = provider
        self.provider_config = provider_config
        # Validation can use a different (larger) model than generation.
        # Falls back to the generation provider/config when not specified.
        self.validation_provider = validation_provider or provider
        self.validation_provider_config = validation_provider_config or provider_config

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

        Execution is sequential (to avoid hammering the target API).
        Validation calls are parallelised with a thread pool so total
        validation time ≈ max(single call) instead of sum(all calls).

        Event shapes:
          {"event": "executing",  "progress": N, "total": T}
          {"event": "result",     "progress": N, "total": T, "result": {...}}
          {"event": "cancelled",  "progress": N, "total": T}
        """
        validate_enabled = request.get("validate", True)
        meta = request.get("meta", {})
        total = len(tests)

        # ── Phase 1: execute all tests sequentially ────────────────────────
        execution_data = []
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

            execution_data.append({
                "test": test,
                "payload": payload,
                "test_headers": test_headers,
                "effective_headers": effective_headers,
                "response": response,
                "duration_ms": duration,
                "success": 200 <= response.get("status_code", 500) < 300,
            })

        # ── Phase 2: validate all in parallel ──────────────────────────────
        validations: list = [None] * total
        if validate_enabled:
            with ThreadPoolExecutor(max_workers=min(8, total)) as pool:
                future_to_idx = {
                    pool.submit(
                        self.validator.validate,
                        test=data["test"],
                        response=data["response"],
                        meta=meta,
                        provider=self.validation_provider,
                        provider_config=self.validation_provider_config,
                    ): i
                    for i, data in enumerate(execution_data)
                }
                for future in as_completed(future_to_idx):
                    i = future_to_idx[future]
                    try:
                        validations[i] = future.result()
                    except Exception as e:
                        validations[i] = {
                            "dstatus": "WARN",
                            "reason": f"LLM validation failed: {e}",
                            "confidence": 0.0,
                        }

        # ── Phase 3: yield results in original order ───────────────────────
        for idx, (data, validation) in enumerate(zip(execution_data, validations), start=1):
            yield {
                "event": "result",
                "progress": idx,
                "total": total,
                "result": {
                    "id": f"tc-{idx:03}",
                    "description": data["test"].get("description"),
                    "request": {
                        "headers": data["test_headers"] if data["test_headers"] is not None else request.get("headers", {}),
                        "body": data["payload"],
                    },
                    "response": data["response"],
                    "success": data["success"],
                    "duration_ms": data["duration_ms"],
                    "validation": validation,
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
                    provider=self.validation_provider,
                    provider_config=self.validation_provider_config,
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
