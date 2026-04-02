"""
FastAPI Dependencies for Dependency Injection

Provides repository instances, services, and auth dependencies
following Hexagonal Architecture principles.
"""
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

# Repository imports
from adapters.driven.persistence.postgres import (
    PostgresDocumentRepository,
    PostgresNewsItemRepository,
    PostgresWorkerRepository,
)
from adapters.driven.persistence.postgres.stage_timing_repository_impl import (
    PostgresStageTimingRepository,
)
from core.ports.repositories.document_repository import DocumentRepository
from core.ports.repositories.news_item_repository import NewsItemRepository
from core.ports.repositories.worker_repository import WorkerRepository
from core.ports.repositories.stage_timing_repository import StageTimingRepository

# Auth imports
from middleware import get_current_user, require_admin, CurrentUser


# Repository factory functions (singleton pattern)
@lru_cache()
def get_document_repository() -> DocumentRepository:
    """Get singleton DocumentRepository instance"""
    return PostgresDocumentRepository()


@lru_cache()
def get_news_item_repository() -> NewsItemRepository:
    """Get singleton NewsItemRepository instance"""
    return PostgresNewsItemRepository()


@lru_cache()
def get_worker_repository() -> WorkerRepository:
    """Get singleton WorkerRepository instance"""
    return PostgresWorkerRepository()


@lru_cache()
def get_stage_timing_repository() -> StageTimingRepository:
    """Get singleton StageTimingRepository instance"""
    return PostgresStageTimingRepository()


# Type aliases for dependency injection
DocumentRepositoryDep = Annotated[DocumentRepository, Depends(get_document_repository)]
NewsItemRepositoryDep = Annotated[NewsItemRepository, Depends(get_news_item_repository)]
WorkerRepositoryDep = Annotated[WorkerRepository, Depends(get_worker_repository)]
StageTimingRepositoryDep = Annotated[StageTimingRepository, Depends(get_stage_timing_repository)]

# Auth dependencies (re-export for convenience)
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin)]
