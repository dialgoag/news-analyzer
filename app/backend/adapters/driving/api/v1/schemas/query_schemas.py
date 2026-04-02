"""Pydantic models for POST /api/query (RAG)."""
from typing import List, Optional

from pydantic import BaseModel

__all__ = [
    "QueryRequest",
    "QueryResponse",
    "SourceInfo",
]


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    temperature: float = 0.0


class SourceInfo(BaseModel):
    filename: str
    document_id: str
    similarity_score: float
    chunk_index: Optional[int] = None
    text: Optional[str] = None


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]
    processing_time: float
    num_sources: int
