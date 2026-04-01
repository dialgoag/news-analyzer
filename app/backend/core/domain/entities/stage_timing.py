"""
Stage Timing Entity - Tracks timing for each pipeline stage.

Represents the lifecycle of a document through one specific pipeline stage.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class StageStatus(str, Enum):
    """Status of a pipeline stage."""
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    ERROR = "error"
    SKIPPED = "skipped"


@dataclass
class StageTimingRecord:
    """
    Tracks timing and status for one pipeline stage.
    
    Unified for both:
    - Document-level stages (news_item_id=None): upload, ocr, chunking, indexing
    - News-level stages (news_item_id!=None): insights, insights_indexing, etc.
    
    Each document has multiple StageTimingRecords (one per stage).
    Each news_item has multiple StageTimingRecords (one per stage).
    
    Lifecycle:
        1. Worker starts stage → INSERT (created_at=NOW, status='processing')
        2. Worker ends stage → UPDATE (updated_at=NOW, status='done'/'error')
    
    Business rules:
    - created_at = when stage STARTED
    - updated_at = when stage ENDED (or last update)
    - Duration = updated_at - created_at (only valid when status='done')
    - Unique constraint: (document_id, news_item_id, stage)
    
    Usage:
        >>> # Document-level stage
        >>> record = StageTimingRecord.start(document_id="doc-123", stage="ocr")
        >>> record.mark_done()
        
        >>> # News-level stage
        >>> record = StageTimingRecord.start(
        ...     document_id="doc-123", 
        ...     news_item_id="news-1",
        ...     stage="insights"
        ... )
        >>> record.mark_done()
    """
    
    # Identity (composite key)
    document_id: str
    stage: str  # 'upload', 'ocr', 'chunking', 'indexing', 'insights', etc.
    
    # Optional: for news-level stages
    news_item_id: Optional[str] = None  # NULL = document-level, NOT NULL = news-level
    
    # Status
    status: StageStatus = StageStatus.PROCESSING
    
    # Timestamps (UNIVERSAL PATTERN)
    created_at: datetime = field(default_factory=datetime.utcnow)  # Stage STARTS
    updated_at: datetime = field(default_factory=datetime.utcnow)  # Stage ENDS (or last modification)
    
    # Optional fields
    id: Optional[int] = None  # DB primary key
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)  # Flexible JSON metadata
    
    @classmethod
    def start(
        cls,
        document_id: str,
        stage: str,
        news_item_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> "StageTimingRecord":
        """
        Create a new stage timing record when stage STARTS.
        
        Args:
            document_id: Document being processed
            stage: Pipeline stage name
            news_item_id: Optional news_item_id (for news-level stages like insights)
            metadata: Optional metadata (worker_id, file_info, etc.)
        
        Returns:
            New StageTimingRecord with status='processing'
        """
        now = datetime.utcnow()
        return cls(
            document_id=document_id,
            stage=stage,
            news_item_id=news_item_id,
            status=StageStatus.PROCESSING,
            created_at=now,
            updated_at=now,  # Initially same as created_at
            metadata=metadata or {}
        )
    
    def mark_done(self):
        """Mark stage as completed successfully."""
        self.status = StageStatus.DONE
        self.updated_at = datetime.utcnow()
        self.error_message = None
    
    def mark_error(self, error_message: str):
        """Mark stage as failed with error."""
        self.status = StageStatus.ERROR
        self.updated_at = datetime.utcnow()
        self.error_message = error_message[:500] if error_message else None
    
    def mark_skipped(self):
        """Mark stage as skipped (not needed)."""
        self.status = StageStatus.SKIPPED
        self.updated_at = datetime.utcnow()
        self.error_message = None
    
    def duration_seconds(self) -> Optional[float]:
        """
        Calculate duration in seconds.
        
        Returns:
            Seconds elapsed from created_at to updated_at, or None if not completed
        """
        if self.status not in (StageStatus.DONE, StageStatus.ERROR):
            return None  # Not finished yet
        
        delta = self.updated_at - self.created_at
        return delta.total_seconds()
    
    def is_completed(self) -> bool:
        """Check if stage completed successfully."""
        return self.status == StageStatus.DONE
    
    def is_error(self) -> bool:
        """Check if stage failed."""
        return self.status == StageStatus.ERROR
    
    def is_processing(self) -> bool:
        """Check if stage is currently processing."""
        return self.status == StageStatus.PROCESSING
    
    def __repr__(self) -> str:
        """Debug representation."""
        duration = f", duration={self.duration_seconds():.2f}s" if self.duration_seconds() else ""
        news_info = f", news={self.news_item_id}" if self.news_item_id else ""
        return f"StageTimingRecord(doc={self.document_id}{news_info}, stage={self.stage}, status={self.status.value}{duration})"
