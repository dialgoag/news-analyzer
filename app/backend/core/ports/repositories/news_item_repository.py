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

    @abstractmethod
    async def count_insights_by_status(self) -> dict:
        """Return counts of news_item_insights grouped by status."""
        pass
