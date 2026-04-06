"""
Dashboard router — summary, analysis, parallel coordinates.

Uses `import app as app_module` for caches and global helpers defined in app.py.
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException

import app as app_module
from adapters.driving.api.v1.dependencies import DashboardMetricsServiceDep
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
    metrics_service: DashboardMetricsServiceDep = Depends(),
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
    metrics_service: DashboardMetricsServiceDep = Depends(),
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
    metrics_service: DashboardMetricsServiceDep = Depends(),
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
