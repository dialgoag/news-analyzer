"""
Insights-related domain events.
"""

from dataclasses import dataclass
from typing import Optional
from .base import DomainEvent


@dataclass
class InsightGenerationRequested(DomainEvent):
    """Event emitted when insight generation is requested."""
    news_item_id: str
    document_id: str
    title: str
    text_hash: str


@dataclass
class InsightGenerated(DomainEvent):
    """Event emitted when an insight is successfully generated."""
    news_item_id: str
    document_id: str
    insight_text: str
    llm_provider: str  # openai, perplexity, ollama
    llm_model: str
    processing_time_seconds: float
    tokens_used: Optional[int] = None


@dataclass
class InsightGenerationFailed(DomainEvent):
    """Event emitted when insight generation fails."""
    news_item_id: str
    document_id: str
    error_message: str
    error_type: str  # rate_limit, timeout, invalid_response, etc.
    retry_count: int


@dataclass
class InsightIndexed(DomainEvent):
    """Event emitted when an insight is indexed in vector store."""
    news_item_id: str
    document_id: str
    vector_id: str
    processing_time_seconds: float
