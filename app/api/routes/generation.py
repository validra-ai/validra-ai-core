from fastapi import APIRouter, HTTPException, Request

from app.api.schemas.requests import TestRequest
from app.engine.orchestrator import Orchestrator

router = APIRouter(tags=["Execution"])


@router.post("/generateAndRun", summary="Generates Test Cases and Run")
def generate_and_run(request: TestRequest, req: Request):
    """
    Generate and execute automated API tests.

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
        raise HTTPException(status_code=400, detail=str(e))

    try:
        provider = provider_registry.get(request.provider.lower())
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Merge user overrides on top of settings-based defaults, then validate
    # via the provider's own config class — unknown keys raise 400 (extra="forbid")
    try:
        merged = {**provider.default_config().model_dump(), **(request.provider_config or {})}
        provider_config = provider.config_class(**merged)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid provider_config: {e}")

    orchestrator = Orchestrator(plugin, executor, validator, provider, provider_config)

    safe_input = {
        "payload": request.payload,
        "headers": request.headers,
        "meta": request.payload_meta or {},
    }

    try:
        tests = orchestrator.generate(safe_input, request.max_cases)
        tests = tests[: request.max_cases]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generating test cases: {str(e)}")

    if not tests:
        raise HTTPException(
            status_code=500,
            detail="No test cases were generated. LLM may be unavailable or returned invalid output.",
        )

    try:
        safe_request = {
            "endpoint": request.endpoint,
            "method": request.method,
            "headers": request.headers,
            "validate": request.validate,
            "meta": request.payload_meta or {},  # FIX #1: pass meta so validator receives constraints
        }
        results = orchestrator.run(safe_request, tests)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing test cases: {str(e)}")

    return results
