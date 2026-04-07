"""
NewsItem Repository Port - Interface for news item persistence.

This is a Hexagonal Architecture port (interface).
Adapters implement this interface for different persistence mechanisms.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Sequence, Tuple
from datetime import datetime

from core.domain.entities.news_item import NewsItem
from core.domain.value_objects.document_id import DocumentId
from core.domain.value_objects.pipeline_status import PipelineStatus


class NewsItemRepository(ABC):
    """
    Port (interface) for news item persistence.
    
    Implementations:
    - PostgresNewsItemRepository (adapters/driven/persistence/postgres/)
    """
    
    @abstractmethod
    async def get_by_id(self, news_item_id: str) -> Optional[NewsItem]:
        """
        Get news item by ID.
        
        Args:
            news_item_id: News item identifier (UUID or insight_UUID)
        
        Returns:
            NewsItem entity or None if not found
        """
        pass
    
    @abstractmethod
    async def get_by_document_id(
        self, 
        document_id: DocumentId,
        limit: Optional[int] = None
    ) -> List[NewsItem]:
        """
        Get all news items for a document.
        
        Args:
            document_id: Document identifier
            limit: Maximum number of items to return
        
        Returns:
            List of news items for the document
        """
        pass
    
    @abstractmethod
    async def save(self, news_item: NewsItem) -> None:
        """
        Save news item (insert or update).
        
        Args:
            news_item: NewsItem entity to save
        
        Raises:
            ValueError: If news item is invalid
        """
        pass
    
    @abstractmethod
    async def list_by_status(
        self, 
        status: PipelineStatus,
        limit: Optional[int] = None
    ) -> List[NewsItem]:
        """
        List news items by insight status.
        
        Args:
            status: Pipeline status to filter by (insight_pending, etc.)
            limit: Maximum number of items to return
        
        Returns:
            List of news items matching the status
        """
        pass
    
    @abstractmethod
    async def list_pending_insights(
        self, 
        limit: Optional[int] = None
    ) -> List[NewsItem]:
        """
        List news items pending insight generation.
        
        Args:
            limit: Maximum number of items to return
        
        Returns:
            List of news items with status insight_pending or insight_queued
        """
        pass
    
    @abstractmethod
    async def update_status(
        self, 
        news_item_id: str, 
        status: PipelineStatus,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update news item insight status.
        
        Args:
            news_item_id: News item identifier
            status: New status (insight_*)
            error_message: Error message if status is error
        
        Raises:
            ValueError: If news item not found
        """
        pass
    
    @abstractmethod
    async def update_insights(
        self,
        news_item_id: str,
        summary: str,
        analysis: str,
        llm_source: str
    ) -> None:
        """
        Update news item with generated insights.
        
        Args:
            news_item_id: News item identifier
            summary: Generated summary
            analysis: Generated analysis
            llm_source: LLM provider used (openai, ollama, etc.)
        
        Raises:
            ValueError: If news item not found
        """
        pass
    
    @abstractmethod
    async def count_by_document(self, document_id: DocumentId) -> int:
        """
        Count news items for a document.
        
        Args:
            document_id: Document identifier
        
        Returns:
            Number of news items for the document
        """
        pass
    
    @abstractmethod
    async def exists(self, news_item_id: str) -> bool:
        """
        Check if news item exists.
        
        Args:
            news_item_id: News item identifier
        
        Returns:
            True if news item exists, False otherwise
        """
        pass

    def count_all_sync(self) -> int:
        """SYNC version - Count total news items."""
        pass

    def count_insights_linkage_sync(self, document_ids: Sequence[str]) -> Tuple[int, int]:
        """
        SYNC version - Return (total_insights, linked_insights) for given document IDs.

        Args:
            document_ids: Iterable of document IDs to check linkage.
        """
        pass

    def get_counts_by_document_ids_sync(self, document_ids: Sequence[str]) -> dict:
        """SYNC: return {document_id: news_items_count}."""
        pass

    def get_progress_by_document_ids_sync(self, document_ids: Sequence[str]) -> dict:
        """
        SYNC: return per-document insights progress counters.
        Expected shape:
        {document_id: {"pending":int,"queued":int,"generating":int,"indexing":int,"done":int,"error":int,"total":int}}
        """
        pass

    def list_by_document_id_sync(self, document_id: str) -> List[dict]:
        """SYNC: list news_items rows for a document."""
        pass

    def list_insights_by_document_id_sync(self, document_id: str) -> List[dict]:
        """SYNC: list news_item_insights rows for a document."""
        pass

    def list_insights_by_news_item_id_sync(self, news_item_id: str) -> List[dict]:
        """SYNC: list news_item_insights rows for a news_item_id."""
        pass

    def get_document_insight_summary_sync(self, document_id: str) -> Optional[dict]:
        """
        SYNC: aggregate done insights for a document.
        Returns {"document_id","content","status"} or None.
        """
        pass

    def list_active_insight_tasks_sync(self) -> List[dict]:
        """SYNC: list insight tasks currently generating or indexing."""
        pass

    def count_pending_or_queued_insights_sync(self) -> int:
        """SYNC: count insights in pending/queued."""
        pass

    def count_ready_for_indexing_insights_sync(self) -> int:
        """SYNC: count done insights pending indexing in Qdrant."""
        pass

    def list_insight_errors_sync(self, news_item_ids: Optional[Sequence[str]] = None) -> List[dict]:
        """SYNC: list insight rows in error, optionally filtered by IDs."""
        pass

    def set_insight_status_sync(
        self,
        news_item_id: str,
        status: str,
        content: Optional[str] = None,
        error_message: Optional[str] = None,
        llm_source: Optional[str] = None,
    ) -> bool:
        """SYNC: update status/content/error for a news_item_insights row."""
        pass

    def delete_by_document_id_sync(self, document_id: str) -> int:
        """SYNC: delete news_items rows for a document."""
        pass

    def delete_insights_by_document_id_sync(self, document_id: str) -> int:
        """SYNC: delete news_item_insights rows for a document."""
        pass

    def set_insights_pending_for_document_sync(self, document_id: str, from_status: str) -> int:
        """SYNC: set document insights to pending from a specific status."""
        pass

    def set_insight_status_if_current_sync(
        self,
        news_item_id: str,
        from_status: str,
        to_status: str,
        clear_error: bool = False,
    ) -> int:
        """SYNC: conditional status transition for one insight row."""
        pass

    def reset_orphaned_indexing_insights_sync(self) -> int:
        """SYNC: set insights_indexing rows without active workers back to insights_done."""
        pass

    def get_next_pending_insight_for_document_sync(self, document_id: str) -> Optional[dict]:
        """SYNC: first pending/queued insight row for a document."""
        pass

    def reset_generating_insights_sync(self) -> int:
        """SYNC: set insights_generating rows back to insights_pending."""
        pass

    @abstractmethod
    async def count_insights_by_status(self) -> dict:
        """Return counts of news_item_insights grouped by status."""
        pass
