"""
Stage Timing Repository Port - Persistence interface for stage timing records.
"""

from abc import ABC, abstractmethod
from typing import List, Optional
from core.domain.entities.stage_timing import StageTimingRecord


class StageTimingRepository(ABC):
    """
    Port for persisting stage timing records.
    
    Tracks when each pipeline stage starts/ends for each document.
    """
    
    # ========================================
    # ASYNC methods (primary interface)
    # ========================================
    
    @abstractmethod
    async def record_stage_start(
        self, 
        document_id: str, 
        stage: str,
        news_item_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> StageTimingRecord:
        """
        Record that a stage has STARTED.
        
        Creates a new timing record with status='processing'.
        Uses INSERT ... ON CONFLICT to handle retries/restarts.
        
        Args:
            document_id: Document being processed
            stage: Pipeline stage name
            news_item_id: Optional news_item_id (for news-level stages like insights)
            metadata: Optional metadata (worker_id, etc.)
        
        Returns:
            Created StageTimingRecord
        """
        pass
    
    @abstractmethod
    async def record_stage_end(
        self,
        document_id: str,
        stage: str,
        status: str,  # 'done' or 'error'
        news_item_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        Record that a stage has ENDED.
        
        Updates existing record with final status and updated_at.
        
        Args:
            document_id: Document being processed
            stage: Pipeline stage name
            status: Final status ('done' or 'error')
            news_item_id: Optional news_item_id (must match record)
            error_message: Error message if status='error'
        """
        pass
    
    @abstractmethod
    async def get_stage_timing(
        self,
        document_id: str,
        stage: str,
        news_item_id: Optional[str] = None
    ) -> Optional[StageTimingRecord]:
        """
        Get timing record for specific document/news_item and stage.
        
        Args:
            document_id: Document ID
            stage: Pipeline stage name
            news_item_id: Optional news_item_id
        
        Returns:
            StageTimingRecord or None if not found
        """
        pass
    
    @abstractmethod
    async def get_all_timings(
        self,
        document_id: str
    ) -> List[StageTimingRecord]:
        """
        Get ALL timing records for a document (full pipeline timeline).
        
        Args:
            document_id: Document ID
        
        Returns:
            List of StageTimingRecords ordered by created_at
        """
        pass
    
    @abstractmethod
    async def get_stage_statistics(
        self,
        stage: str,
        news_item_level: bool = False,
        limit: int = 100
    ) -> dict:
        """
        Get performance statistics for a stage.
        
        Calculates average, min, max duration for completed stages.
        
        Args:
            stage: Pipeline stage name
            news_item_level: If True, include news-level records; if False, only document-level
            limit: Max records to analyze
        
        Returns:
            Dict with avg_seconds, min_seconds, max_seconds, count
        """
        pass
    
    # ========================================
    # SYNC methods (for legacy scheduler compatibility)
    # ========================================
    
    def record_stage_start_sync(
        self,
        document_id: str,
        stage: str,
        news_item_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> StageTimingRecord:
        """SYNC version - Record stage start."""
        pass
    
    def record_stage_end_sync(
        self,
        document_id: str,
        stage: str,
        status: str,
        news_item_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """SYNC version - Record stage end."""
        pass

    @abstractmethod
    async def delete_for_document(self, document_id: str) -> None:
        """Delete all timing records for a document."""
        pass

    def delete_for_document_sync(self, document_id: str) -> None:
        """SYNC version - Delete timing records for a document."""
        pass
