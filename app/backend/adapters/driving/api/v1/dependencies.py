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
    PostgresDashboardReadRepository,
    PostgresDocumentRepository,
    PostgresNewsItemRepository,
    PostgresWorkerRepository,
)
from adapters.driven.persistence.postgres.stage_timing_repository_impl import (
    PostgresStageTimingRepository,
)
from core.application.services.admin_data_integrity_service import AdminDataIntegrityService
from core.application.services.dashboard_metrics_service import DashboardMetricsService
from core.ports.repositories.document_repository import DocumentRepository
from core.ports.repositories.news_item_repository import NewsItemRepository
from core.ports.repositories.worker_repository import WorkerRepository
from core.ports.repositories.stage_timing_repository import StageTimingRepository
from core.ports.repositories.dashboard_read_repository import DashboardReadRepository

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


@lru_cache()
def get_dashboard_metrics_service() -> DashboardMetricsService:
    """Singleton DashboardMetricsService."""
    return DashboardMetricsService(
        document_repository=get_document_repository(),
        dashboard_read_repository=get_dashboard_read_repository(),
    )


@lru_cache()
def get_admin_data_integrity_service() -> AdminDataIntegrityService:
    """Singleton AdminDataIntegrityService."""
    return AdminDataIntegrityService(
        document_repository=get_document_repository(),
        news_item_repository=get_news_item_repository(),
    )


@lru_cache()
def get_dashboard_read_repository() -> DashboardReadRepository:
    return PostgresDashboardReadRepository()


# Type aliases for dependency injection
DocumentRepositoryDep = Annotated[DocumentRepository, Depends(get_document_repository)]
NewsItemRepositoryDep = Annotated[NewsItemRepository, Depends(get_news_item_repository)]
WorkerRepositoryDep = Annotated[WorkerRepository, Depends(get_worker_repository)]
StageTimingRepositoryDep = Annotated[StageTimingRepository, Depends(get_stage_timing_repository)]
DashboardMetricsServiceDep = Annotated[DashboardMetricsService, Depends(get_dashboard_metrics_service)]
AdminDataIntegrityServiceDep = Annotated[
    AdminDataIntegrityService, Depends(get_admin_data_integrity_service)
]
DashboardReadRepositoryDep = Annotated[DashboardReadRepository, Depends(get_dashboard_read_repository)]

# Auth dependencies (re-export for convenience)
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin)]
