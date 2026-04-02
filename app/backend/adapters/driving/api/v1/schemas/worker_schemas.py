"""
Pydantic models for workers endpoints (status, start, shutdown, retry-errors).
"""
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional


class RetryErrorsRequest(BaseModel):
    """Optional body for POST /retry-errors."""

    document_ids: Optional[List[str]] = Field(
        default=None,
        description='Document IDs or "insight_<news_item_id>" for insights; omit or empty to retry all errors.',
    )


class RetryErrorsResponse(BaseModel):
    message: str
    retried_count: int
    retried_documents: List[Dict[str, Any]] = Field(default_factory=list)
    errors: Optional[List[str]] = None


class WorkerStartResponse(BaseModel):
    status: str
    message: str
    architecture: str
    pool_active: bool
    supported_tasks: List[str]
    note: str


class WorkerShutdownResponse(BaseModel):
    status: str
    message: str
    actions_taken: List[str]
    note: str
