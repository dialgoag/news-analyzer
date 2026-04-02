"""
Document schemas - Pydantic models for document endpoints

These models are currently defined in app.py.
Re-exported here for modular organization.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Dict

__all__ = [
    "DocumentMetadata",
    "DocumentsListResponse",
    "DocumentStatusItem",
]


class DocumentMetadata(BaseModel):
    filename: str
    upload_date: str
    document_id: str
    num_chunks: int
    status: str
    source: Optional[str] = None
    indexed_at: Optional[str] = None
    error_message: Optional[str] = None
    news_date: Optional[str] = None
    processing_stage: Optional[str] = None
    insights_status: Optional[str] = None
    insights_progress: Optional[str] = None


class DocumentsListResponse(BaseModel):
    documents: List[DocumentMetadata]
    total: int
    insights_summary: Optional[dict] = None


class DocumentStatusItem(BaseModel):
    """Modelo para el endpoint /api/documents/status usado por DocumentsTable.jsx"""
    document_id: str
    filename: str
    status: str
    uploaded_at: str
    news_items_count: int = 0
    insights_done: int = 0
    insights_total: int = 0
