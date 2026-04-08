"""
Dashboard router — summary, analysis, parallel coordinates.

Uses `import app as app_module` for caches and global helpers defined in app.py.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException

import app as app_module
from adapters.driving.api.v1.dependencies import (
    get_dashboard_metrics_service,
    get_news_item_repository,
)
from core.application.services.dashboard_metrics_service import DashboardMetricsService
from core.ports.repositories.news_item_repository import NewsItemRepository
from adapters.driving.api.v1.schemas.dashboard_schemas import (
    ParallelDocumentFlow,
    ParallelFlowResponse,
    ParallelNewsItem,
)
from middleware import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary")
async def get_dashboard_summary(
    current_user: CurrentUser = Depends(get_current_user),
    metrics_service: DashboardMetricsService = Depends(get_dashboard_metrics_service),
):
    """Get consolidated dashboard metrics (files, news items, OCR, chunking, insights, errors)."""
    cached = app_module._cache_get("dashboard_summary")
    if cached is not None:
        return cached
    try:
        result = metrics_service.get_summary()
        app_module._cache_set("dashboard_summary", result)
        return result
    except Exception as e:
        logger.error(f"Error fetching dashboard summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching summary")


@router.get("/parallel-data", response_model=ParallelFlowResponse)
async def get_parallel_coordinates_data(
    limit: int = 80,
    max_news_per_doc: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
    metrics_service: DashboardMetricsService = Depends(get_dashboard_metrics_service),
):
    """Return document + news_item slices for the Parallel Coordinates visualization."""
    limit = max(10, min(limit, 250))
    max_news_per_doc = max(1, min(max_news_per_doc, 50))

    try:
        payload = metrics_service.get_parallel_data(limit=limit, max_news_per_doc=max_news_per_doc)
        documents_payload: List[ParallelDocumentFlow] = []
        for doc in payload["documents"]:
            news_items = [ParallelNewsItem(**item) for item in doc.get("news_items", [])]
            documents_payload.append(
                ParallelDocumentFlow(
                    document_id=doc.get("document_id"),
                    filename=doc.get("filename"),
                    status=doc.get("status"),
                    processing_stage=doc.get("processing_stage"),
                    ingested_at=doc.get("ingested_at"),
                    news_items_total=doc.get("news_items_total", 0),
                    news_items=news_items,
                )
            )

        return ParallelFlowResponse(documents=documents_payload, meta=payload["meta"])
    except Exception as e:
        logger.error(f"Error building parallel dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching parallel data")


@router.get("/analysis")
async def get_dashboard_analysis(
    current_user: CurrentUser = Depends(get_current_user),
    metrics_service: DashboardMetricsService = Depends(get_dashboard_metrics_service),
):
    """
    Comprehensive dashboard analysis endpoint.
    Provides detailed analysis of errors, pipeline status, workers, and database state.
    """
    cached = app_module._cache_get("dashboard_analysis")
    if cached is not None:
        return cached
    try:
        result = metrics_service.get_analysis()
        app_module._cache_set("dashboard_analysis", result)
        return result
    except Exception as e:
        logger.error(f"Error fetching dashboard analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard analysis: {str(e)}")


@router.get("/expired-insights")
async def get_expired_insights(
    current_user: CurrentUser = Depends(get_current_user),
    news_item_repo: NewsItemRepository = Depends(get_news_item_repository),
    max_retries: int = 3
):
    """
    Get insights that exceeded max retries (permanently failed).
    Shows insights with retry_count >= max_retries along with their error messages.
    """
    try:
        expired = news_item_repo.list_expired_insights_sync(max_retries)
        return {
            "total": len(expired),
            "max_retries": max_retries,
            "insights": expired
        }
    except Exception as e:
        logger.error(f"Error fetching expired insights: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching expired insights: {str(e)}")


@router.get("/insight-detail/{news_item_id}")
async def get_insight_detail(
    news_item_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    news_item_repo: NewsItemRepository = Depends(get_news_item_repository),
):
    """
    Get complete journey of a specific insight including:
    - Original news text
    - OCR validation result (if applicable)
    - Retry history
    - Error messages
    - Generated insights (if any)
    - Stage timestamps
    """
    try:
        # Get news item basic info
        news_item = news_item_repo.get_by_id_sync(news_item_id)
        if not news_item:
            raise HTTPException(status_code=404, detail="News item not found")
        
        # Get insight record
        insight = news_item_repo.get_insight_by_news_item_id_sync(news_item_id)
        
        # Get retry history from logs (if exists)
        # TODO: Implement retry history tracking
        
        result = {
            "news_item_id": news_item_id,
            "document_id": news_item.get("document_id"),
            "title": news_item.get("title"),
            "content": news_item.get("content"),
            "content_length": len(news_item.get("content", "")),
            "item_index": news_item.get("item_index"),
            "created_at": news_item.get("created_at"),
            "insight": {
                "status": insight.get("status") if insight else None,
                "retry_count": insight.get("retry_count", 0) if insight else 0,
                "error_message": insight.get("error_message") if insight else None,
                "content": insight.get("content") if insight else None,
                "llm_source": insight.get("llm_source") if insight else None,
                "created_at": insight.get("created_at") if insight else None,
                "updated_at": insight.get("updated_at") if insight else None,
            } if insight else None,
            "ocr_validation": {
                "validated": bool(insight and "OCR validation" in (insight.get("error_message") or "")),
                "reason": insight.get("error_message") if insight and "OCR validation" in (insight.get("error_message") or "") else None
            },
            "pipeline_stage": "insights",
            "is_short_content": len(news_item.get("content", "")) < 500
        }
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching insight detail for {news_item_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching insight detail: {str(e)}")

