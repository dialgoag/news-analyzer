"""
Document-related domain events.
"""

from dataclasses import dataclass
from typing import Optional
from .base import DomainEvent


@dataclass
class DocumentUploaded(DomainEvent):
    """Event emitted when a document is uploaded."""
    document_id: str
    filename: str
    sha256: str
    file_size: int
    uploaded_by: Optional[str] = None


@dataclass
class OCRCompleted(DomainEvent):
    """Event emitted when OCR processing completes successfully."""
    document_id: str
    text_length: int
    news_items_count: int
    processing_time_seconds: float


@dataclass
class OCRFailed(DomainEvent):
    """Event emitted when OCR processing fails."""
    document_id: str
    error_message: str
    retry_count: int


@dataclass
class ChunkingCompleted(DomainEvent):
    """Event emitted when document chunking completes."""
    document_id: str
    chunks_count: int
    processing_time_seconds: float


@dataclass
class IndexingCompleted(DomainEvent):
    """Event emitted when document indexing completes."""
    document_id: str
    vectors_indexed: int
    processing_time_seconds: float
