"""
PostgreSQL Persistence Adapters.

Implementations of repository ports for PostgreSQL.
"""

from .base import BasePostgresRepository
from .document_repository_impl import PostgresDocumentRepository
from .news_item_repository_impl import PostgresNewsItemRepository
from .worker_repository_impl import PostgresWorkerRepository
from .stage_timing_repository_impl import PostgresStageTimingRepository

__all__ = [
    "BasePostgresRepository",
    "PostgresDocumentRepository",
    "PostgresNewsItemRepository",
    "PostgresWorkerRepository",
    "PostgresStageTimingRepository",
]
