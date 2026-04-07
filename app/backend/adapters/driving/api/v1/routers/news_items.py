"""
News Items Router - Insights for individual news items

Single endpoint for retrieving insights of a specific news item.
"""
import logging

from fastapi import APIRouter, Depends, HTTPException

import app as app_module
from middleware import CurrentUser, get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{news_item_id}/insights")
async def get_news_item_insights(
    news_item_id: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get generated insights for a specific news item."""
    insights = app_module.news_item_repository.list_insights_by_news_item_id_sync(news_item_id)

    if not insights:
        raise HTTPException(status_code=404, detail="Insights not available for this news item")

    selected = next(
        (item for item in insights if item.get("status") in ("insights_done", "done")),
        insights[0],
    )

    return {
        "news_item_id": news_item_id,
        "document_id": selected.get("document_id"),
        "title": selected.get("title") or "",
        "content": selected.get("content") or "",
    }
