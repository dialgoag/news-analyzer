"""
FastAPI Dependencies for Dependency Injection

Provides repository instances, services, and auth dependencies
following Hexagonal Architecture principles.
"""
import asyncpg
import os
from functools import lru_cache
from typing import Annotated, Optional
from urllib.parse import quote_plus

from fastapi import Depends

# Repository imports
from adapters.driven.persistence.postgres import (
    PostgresDashboardReadRepository,
    PostgresDocumentRepository,
    PostgresNewsItemRepository,
    PostgresNotificationRepository,
    PostgresReportRepository,
    PostgresUserRepository,
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
from core.ports.repositories.notification_repository import NotificationRepository
from core.ports.repositories.report_repository import ReportRepository
from core.ports.repositories.user_repository import UserRepository

# Auth imports
from middleware import get_current_user, require_admin, CurrentUser


# Asyncpg pool singleton for Orchestrator
_asyncpg_pool: Optional[asyncpg.Pool] = None


async def get_db_pool() -> asyncpg.Pool:
    """
    Get singleton AsyncPG connection pool for Orchestrator Agent.
    
    This pool is used by the Orchestrator Agent and its dashboard endpoints
    for async database operations.
    
    Uses same database credentials as the rest of the application (from env vars).
    """
    global _asyncpg_pool
    
    if _asyncpg_pool is None:
        import logging
        logger = logging.getLogger(__name__)
        
        # Get DATABASE_URL if exists, otherwise build from components
        db_url = os.getenv("DATABASE_URL")
        
        if not db_url:
            # Build from individual env vars (same logic as database.py)
            user = quote_plus(os.getenv("POSTGRES_USER", ""))
            password = quote_plus(os.getenv("POSTGRES_PASSWORD", ""))
            host = os.getenv("POSTGRES_HOST", "postgres")
            port = os.getenv("POSTGRES_PORT", "5432")
            db = os.getenv("POSTGRES_DB", "")
            
            if not user or not password or not db:
                raise ValueError(
                    "Missing required database credentials. "
                    "Please set POSTGRES_USER, POSTGRES_PASSWORD, and POSTGRES_DB environment variables."
                )
            
            db_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
        
        logger.info(f"[AsyncPG] Creating pool with host={os.getenv('POSTGRES_HOST')}, db={os.getenv('POSTGRES_DB')}")
        
        _asyncpg_pool = await asyncpg.create_pool(
            db_url,
            min_size=2,
            max_size=10,
            command_timeout=60
        )
        
        logger.info("[AsyncPG] Pool created successfully")
    
    return _asyncpg_pool


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


@lru_cache()
def get_report_repository() -> ReportRepository:
    return PostgresReportRepository()


@lru_cache()
def get_notification_repository() -> NotificationRepository:
    return PostgresNotificationRepository()


@lru_cache()
def get_user_repository() -> UserRepository:
    return PostgresUserRepository()


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
ReportRepositoryDep = Annotated[ReportRepository, Depends(get_report_repository)]
NotificationRepositoryDep = Annotated[
    NotificationRepository, Depends(get_notification_repository)
]
UserRepositoryDep = Annotated[UserRepository, Depends(get_user_repository)]

# Auth dependencies (re-export for convenience)
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
AdminUserDep = Annotated[CurrentUser, Depends(require_admin)]
