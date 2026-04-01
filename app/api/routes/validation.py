from fastapi import APIRouter, HTTPException, Request

from app.api.schemas.requests import ValidateRequest

router = APIRouter(tags=["Validation"])


@router.post("/validate", summary="Validate Response from /generateAndRun")
def validate(request: ValidateRequest, req: Request):
    provider_registry = req.app.state.provider_registry
    validator = req.app.state.validator

    try:
        provider = provider_registry.get(request.provider.lower())
    except KeyError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        merged = {**provider.default_config().model_dump(), **(request.provider_config or {})}
        provider_config = provider.config_class(**merged)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid provider_config: {e}")

    try:
        result = validator.validate(
            test=request.test,
            response=request.response,
            meta=request.meta or {},
            provider=provider,
            provider_config=provider_config,
        )
        return {"validation": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")
