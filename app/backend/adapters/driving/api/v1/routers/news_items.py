"""
News Items Router - Insights for individual news items

Single endpoint for retrieving insights of a specific news item.
"""
from typing import List
import logging

from fastapi import APIRouter, HTTPException

from database import news_item_insights_store

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{news_item_id}/insights")
async def get_news_item_insights(news_item_id: str):
    """Get insights for a specific news item"""
    insights = news_item_insights_store.list_by_news_item_id(news_item_id)
    
    return {
        "news_item_id": news_item_id,
        "insights": insights,
        "total": len(insights)
    }
