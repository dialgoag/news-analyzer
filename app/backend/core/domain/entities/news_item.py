"""
NewsItem Entity - Individual news item within a document.

Represents a single news article extracted from a document.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.domain.value_objects.document_id import DocumentId, NewsItemId
from core.domain.value_objects.text_hash import TextHash
from core.domain.value_objects.pipeline_status import PipelineStatus, InsightStatusEnum


@dataclass
class NewsItem:
    """
    NewsItem entity.
    
    Represents a single news article extracted from a document.
    Each news item has its own insights generation lifecycle.
    
    Business rules:
    - Must belong to a parent Document
    - Text hash computed from content (for deduplication)
    - Cannot generate insights without content
    - Status transitions follow insight pipeline
    
    Usage:
        >>> item = NewsItem.create(
        ...     document_id=DocumentId.from_string("doc_123"),
        ...     item_index=0,
        ...     title="Breaking News",
        ...     content="Article content..."
        ... )
        >>> item.start_generating_insights()
        >>> item.mark_insights_done(insight_content="...", provider="openai")
    """
    
    # Identity
    id: NewsItemId
    document_id: DocumentId
    
    # Attributes
    item_index: int  # Position within document (0-based)
    title: Optional[str] = None
    content: Optional[str] = None  # Full text content
    
    # Deduplication
    text_hash: Optional[TextHash] = None
    
    # Insights
    insight_status: PipelineStatus = field(
        default_factory=lambda: PipelineStatus.for_insight(InsightStatusEnum.PENDING)
    )
    insight_content: Optional[str] = None
    llm_source: Optional[str] = None  # Provider used (openai, ollama, etc.)
    
    # Metadata
    filename: Optional[str] = None  # For display/logging
    
    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    indexed_in_qdrant_at: Optional[datetime] = None
    
    # Error handling
    error_message: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        document_id: DocumentId,
        item_index: int,
        title: Optional[str] = None,
        content: Optional[str] = None,
        filename: Optional[str] = None,
        news_item_id: Optional[NewsItemId] = None
    ) -> "NewsItem":
        """
        Create a new news item.
        
        Args:
            document_id: Parent document ID
            item_index: Position within document
            title: Article title
            content: Article content
            filename: Filename (for display)
            news_item_id: Optional custom ID
        
        Returns:
            New NewsItem instance
        """
        # Generate ID if not provided
        if news_item_id is None:
            news_item_id = NewsItemId.generate(
                document_id=str(document_id),
                index=item_index
            )
        
        # Compute text hash from content (for deduplication)
        text_hash = None
        if content:
            text_hash = TextHash.compute(content)
        
        return cls(
            id=news_item_id,
            document_id=document_id,
            item_index=item_index,
            title=title,
            content=content,
            filename=filename,
            text_hash=text_hash
        )
    
    # === Insights Status Transitions ===
    
    def queue_for_insights(self):
        """Queue item for insights generation."""
        self.insight_status = PipelineStatus.for_insight(InsightStatusEnum.QUEUED)
        self.updated_at = datetime.utcnow()
    
    def start_generating_insights(self):
        """Mark insights generation as started."""
        self.insight_status = PipelineStatus.for_insight(InsightStatusEnum.GENERATING)
        self.updated_at = datetime.utcnow()
    
    def mark_insights_done(self, insight_content: str, llm_source: str):
        """
        Mark insights as completed.
        
        Args:
            insight_content: Generated insights text
            llm_source: Provider used (e.g., "openai/gpt-4o-mini")
        """
        if not insight_content:
            raise ValueError("Insight content cannot be empty")
        
        self.insight_status = PipelineStatus.for_insight(InsightStatusEnum.DONE)
        self.insight_content = insight_content
        self.llm_source = llm_source
        self.error_message = None
        self.updated_at = datetime.utcnow()
    
    def start_indexing(self):
        """Mark as being indexed in Qdrant."""
        self.insight_status = PipelineStatus.for_insight(InsightStatusEnum.INDEXING)
        self.updated_at = datetime.utcnow()
    
    def mark_indexed(self):
        """Mark as indexed in Qdrant."""
        self.indexed_in_qdrant_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def mark_insights_error(self, error_message: str):
        """
        Mark insights generation as failed.
        
        Args:
            error_message: Error description
        """
        self.insight_status = PipelineStatus.for_insight(InsightStatusEnum.ERROR)
        self.error_message = error_message[:500]
        self.updated_at = datetime.utcnow()
    
    # === Queries ===
    
    def has_insights(self) -> bool:
        """Check if insights have been generated."""
        return (
            self.insight_content is not None 
            and self.insight_status.full_status() == InsightStatusEnum.DONE.value
        )
    
    def is_indexed(self) -> bool:
        """Check if indexed in Qdrant."""
        return self.indexed_in_qdrant_at is not None
    
    def needs_insights(self) -> bool:
        """Check if item needs insights generation."""
        return self.insight_status.full_status() in [
            InsightStatusEnum.PENDING.value,
            InsightStatusEnum.QUEUED.value
        ]
    
    def can_retry_insights(self) -> bool:
        """Check if insights can be retried."""
        return self.insight_status.full_status() == InsightStatusEnum.ERROR.value
    
    def get_id_string(self) -> str:
        """Get news item ID as string."""
        return str(self.id)
    
    def __eq__(self, other) -> bool:
        """Equality based on identity (ID)."""
        if not isinstance(other, NewsItem):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash based on ID."""
        return hash(self.id)
    
    def __repr__(self) -> str:
        """Debug representation."""
        return (
            f"NewsItem(id={self.id}, document={self.document_id}, "
            f"title='{self.title[:30] if self.title else 'N/A'}...', "
            f"status={self.insight_status})"
        )
