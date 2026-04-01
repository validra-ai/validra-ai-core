from pydantic import BaseModel
from typing import Any, Dict, List, Optional


class ValidationResult(BaseModel):
    dstatus: str
    reason: str
    confidence: float


class TestResult(BaseModel):
    id: str
    description: Optional[str]
    request: Dict[str, Any]
    response: Dict[str, Any]
    success: bool
    duration_ms: int
    validation: Optional[ValidationResult]


class Summary(BaseModel):
    total: int
    success: int
    failed: int
    total_duration_ms: int


class GenerationResponse(BaseModel):
    tests: List[TestResult]
    summary: Summary
