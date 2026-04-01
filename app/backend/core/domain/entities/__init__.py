"""
Domain Entities - Objects with identity and lifecycle.

Entities are defined by their identity (ID), not their attributes.
Two entities with the same ID are the same entity, even if attributes differ.

They are mutable and have business logic for state transitions.
"""

from .document import Document, DocumentType
from .news_item import NewsItem
from .worker import Worker, WorkerType

__all__ = [
    "Document",
    "DocumentType",
    "NewsItem",
    "Worker",
    "WorkerType",
]
