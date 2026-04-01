"""
Repository Ports - Interfaces for persistence layer.

These are Hexagonal Architecture ports (interfaces).
Implementations live in adapters/driven/persistence/.
"""

from .document_repository import DocumentRepository
from .news_item_repository import NewsItemRepository
from .worker_repository import WorkerRepository

__all__ = [
    "DocumentRepository",
    "NewsItemRepository",
    "WorkerRepository",
]
