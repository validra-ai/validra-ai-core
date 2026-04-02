import json
import logging
import threading
import uuid

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.schemas.requests import TestRequest
from app.engine.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Execution"])


@router.post("/generateAndRun", summary="Generates Test Cases and Run")
def generate_and_run(request: TestRequest, req: Request):
    """
    Generate and execute automated API tests, streaming results via SSE.

    Events emitted:
    - `{"phase": "generating"}` — LLM is generating test cases
    - `{"phase": "running", "progress": N, "total": T, "result": {...}}` — one test completed
    - `{"phase": "done", "summary": {...}}` — all tests finished
    - `{"phase": "error", "message": "..."}` — unrecoverable failure

    ## Test Types

    ### FUZZ
    Generates invalid, unexpected, or edge-case payloads to test input validation.

    ### AUTH
    Mutates headers to test authentication and authorization scenarios
    (missing tokens, expired credentials, malformed values).

    ### PEN
    Simulates penetration test payloads: injection, privilege escalation,
    parameter pollution, ID tampering, encoding tricks.

    ## Provider Config
    Pass `provider` and optionally `provider_config` to select and configure
    the LLM backend per request. Unset fields fall back to environment defaults.
    Unknown keys in `provider_config` are rejected with a 400 error.
    """
    plugin_registry = req.app.state.plugin_registry
    provider_registry = req.app.state.provider_registry
    executor = req.app.state.executor
    validator = req.app.state.validator

    try:
        plugin = plugin_registry.get(request.test_type.upper())
    except KeyError as e:
        msg = str(e)
        def error_stream():
            yield f"data: {json.dumps({'phase': 'error', 'message': msg})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    try:
        provider = provider_registry.get(request.provider.lower())
    except KeyError as e:
        msg = str(e)
        def error_stream():
            yield f"data: {json.dumps({'phase': 'error', 'message': msg})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    try:
        merged = {**provider.default_config().model_dump(), **(request.provider_config or {})}
        provider_config = provider.config_class(**merged)
    except Exception as e:
        msg = f"Invalid provider_config: {e}"
        def error_stream():
            yield f"data: {json.dumps({'phase': 'error', 'message': msg})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    orchestrator = Orchestrator(plugin, executor, validator, provider, provider_config)

    run_id = str(uuid.uuid4())
    stop_event = threading.Event()
    req.app.state.active_runs[run_id] = stop_event

    safe_input = {
        "payload": request.payload,
        "headers": request.headers,
        "meta": request.payload_meta or {},
    }

    safe_request = {
        "endpoint": request.endpoint,
        "method": request.method,
        "headers": request.headers,
        "validate": request.validate,
        "meta": request.payload_meta or {},
    }

    def event_stream():
        try:
            yield from _event_stream()
        finally:
            req.app.state.active_runs.pop(run_id, None)

    def _event_stream():
        # Phase 1: Warming up (instant feedback to the client)
        yield f"data: {json.dumps({'phase': 'warming_up', 'run_id': run_id})}\n\n"

        # Phase 2: Generate all test cases (single LLM call)
        yield f"data: {json.dumps({'phase': 'generating'})}\n\n"

        try:
            tests = orchestrator.generate(safe_input, request.max_cases)
            tests = tests[: request.max_cases]
        except Exception as e:
            logger.exception("Error generating test cases")
            yield f"data: {json.dumps({'phase': 'error', 'message': f'Error generating test cases: {e}'})}\n\n"
            return

        if not tests:
            yield f"data: {json.dumps({'phase': 'error', 'message': 'No test cases were generated. LLM may be unavailable or returned invalid output.'})}\n\n"
            return

        # Phase 3+4: Execute and validate each test, yielding granular step events
        results = []
        try:
            for step in orchestrator.run_stream(safe_request, tests, stop_event=stop_event):
                event = step["event"]
                if event in ("executing", "validating"):
                    yield f"data: {json.dumps({'phase': event, 'progress': step['progress'], 'total': step['total']})}\n\n"
                elif event == "result":
                    results.append(step["result"])
                    yield f"data: {json.dumps({'phase': 'result', 'progress': step['progress'], 'total': step['total'], 'result': step['result']}, default=str)}\n\n"
                elif event == "cancelled":
                    yield f"data: {json.dumps({'phase': 'cancelled', 'progress': step['progress'], 'total': step['total']})}\n\n"
                    return
        except Exception as e:
            logger.exception("Error executing test cases")
            yield f"data: {json.dumps({'phase': 'error', 'message': f'Error executing test cases: {e}'})}\n\n"
            return

        # Phase 5: Final summary
        success_count = sum(1 for r in results if r["success"])
        total_duration = sum(r["duration_ms"] for r in results)
        summary = {
            "total": len(results),
            "success": success_count,
            "failed": len(results) - success_count,
            "total_duration_ms": total_duration,
        }
        yield f"data: {json.dumps({'phase': 'done', 'summary': summary})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
