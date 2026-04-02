import hashlib
import json
import logging
import threading
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.api.schemas.requests import TestRequest
from app.engine.orchestrator import Orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Execution"])

# ── Simple in-process result cache ────────────────────────────────────────────
# Keyed on (plugin_type, payload, meta, max_cases).  TTL = 5 minutes.
# Prevents redundant LLM calls when the same schema is submitted repeatedly
# during development or CI runs.
_CACHE_TTL = 300  # seconds
_CACHE_MAX = 200  # max entries before oldest are evicted

_cache: dict[str, tuple[list, float]] = {}
_cache_lock = threading.Lock()


def _cache_key(plugin_type: str, payload: dict, meta: dict, max_cases: int) -> str:
    data = json.dumps(
        {"type": plugin_type, "payload": payload, "meta": meta, "max": max_cases},
        sort_keys=True,
    )
    return hashlib.sha256(data.encode()).hexdigest()


def _cache_get(key: str) -> list | None:
    with _cache_lock:
        entry = _cache.get(key)
        if entry and (time.time() - entry[1]) < _CACHE_TTL:
            return entry[0]
        if entry:
            del _cache[key]
    return None


def _cache_set(key: str, tests: list) -> None:
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX:
            # Evict the oldest entry
            oldest = min(_cache, key=lambda k: _cache[k][1])
            del _cache[oldest]
        _cache[key] = (tests, time.time())


# ── Validation-specific model overrides ────────────────────────────────────────
# Validation requires stronger reasoning than generation, so we use Sonnet
# instead of the Haiku default that is set in each provider's config.
_VALIDATION_MODEL_OVERRIDES: dict[str, dict[str, Any]] = {
    "anthropic": {"model": "claude-sonnet-4-6", "max_tokens": 150},
    "openai": {"model": "gpt-4o", "max_tokens": 150},
    # Ollama: no override — same local model is used for both phases.
}


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

    # ── Build generation config (uses provider defaults: Haiku / gpt-4o-mini) ─
    try:
        merged = {**provider.default_config().model_dump(), **(request.provider_config or {})}
        provider_config = provider.config_class(**merged)
    except Exception as e:
        msg = f"Invalid provider_config: {e}"
        def error_stream():
            yield f"data: {json.dumps({'phase': 'error', 'message': msg})}\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # ── Build validation config (Sonnet / gpt-4o, smaller max_tokens) ─────────
    val_overrides = _VALIDATION_MODEL_OVERRIDES.get(request.provider.lower(), {})
    try:
        val_merged = {**merged, **val_overrides}
        validation_provider_config = provider.config_class(**val_merged)
    except Exception:
        # If override fails for any reason, fall back to generation config
        validation_provider_config = provider_config

    orchestrator = Orchestrator(
        plugin,
        executor,
        validator,
        provider,
        provider_config,
        validation_provider=provider,
        validation_provider_config=validation_provider_config,
    )

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
        "validate": request.run_validation,
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

        # Phase 2: Generate all test cases (check cache first)
        yield f"data: {json.dumps({'phase': 'generating'})}\n\n"

        cache_key = _cache_key(
            request.test_type.upper(),
            request.payload,
            request.payload_meta or {},
            request.max_cases,
        )
        tests = _cache_get(cache_key)

        if tests is not None:
            logger.info("generation cache hit — skipping LLM generation call")
        else:
            try:
                tests = orchestrator.generate(safe_input, request.max_cases)
                tests = tests[: request.max_cases]
                _cache_set(cache_key, tests)
            except Exception as e:
                logger.exception("Error generating test cases")
                yield f"data: {json.dumps({'phase': 'error', 'message': f'Error generating test cases: {e}'})}\n\n"
                return

        if not tests:
            yield f"data: {json.dumps({'phase': 'error', 'message': 'No test cases were generated. LLM may be unavailable or returned invalid output.'})}\n\n"
            return

        # Phase 3+4: Execute (sequential) then validate (parallel), yield results
        results = []
        try:
            for step in orchestrator.run_stream(safe_request, tests, stop_event=stop_event):
                event = step["event"]
                if event == "executing":
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
