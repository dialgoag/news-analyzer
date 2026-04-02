"""
Notifications router — in-app notification inbox (report updates).

Uses notification_store from database (same as app.py).
"""
import logging

from fastapi import APIRouter, Depends

from database import notification_store
from middleware import CurrentUser, get_current_user

from adapters.driving.api.v1.schemas.notification_schemas import (
    MarkAllNotificationsReadResponse,
    MarkNotificationReadResponse,
    NotificationsListResponse,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("", response_model=NotificationsListResponse)
async def list_notifications(
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List notifications for current user (report updates). All authenticated users."""
    items = notification_store.get_all_for_user(current_user.user_id, limit=limit)
    unread_count = notification_store.get_unread_count(current_user.user_id)
    return {"notifications": items, "unread_count": unread_count}


@router.patch("/{notification_id}/read", response_model=MarkNotificationReadResponse)
async def mark_notification_read(
    notification_id: int,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Mark one notification as read."""
    notification_store.mark_read(notification_id, current_user.user_id)
    return {"ok": True}


@router.post("/read-all", response_model=MarkAllNotificationsReadResponse)
async def mark_all_notifications_read(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Mark all notifications as read for current user."""
    count = notification_store.mark_all_read(current_user.user_id)
    return {"ok": True, "marked": count}
