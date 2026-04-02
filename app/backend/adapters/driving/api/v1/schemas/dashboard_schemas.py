"""
Pydantic models for dashboard endpoints (summary, analysis, parallel coordinates).
"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional


class ParallelNewsItem(BaseModel):
    news_item_id: str
    document_id: str
    title: Optional[str] = None
    item_index: int = 0
    news_status: Optional[str] = None
    insight_status: Optional[str] = None
    index_status: Optional[str] = None
    error_message: Optional[str] = None


class ParallelDocumentFlow(BaseModel):
    document_id: str
    filename: str
    status: str
    processing_stage: Optional[str] = None
    ingested_at: Optional[str] = None
    news_items_total: int = 0
    news_items: List[ParallelNewsItem] = Field(default_factory=list)


class ParallelFlowResponse(BaseModel):
    documents: List[ParallelDocumentFlow]
    meta: Dict[str, int]
