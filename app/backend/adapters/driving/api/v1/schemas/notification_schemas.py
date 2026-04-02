"""Pydantic models for /api/notifications endpoints."""
from typing import List, Optional

from pydantic import BaseModel

__all__ = [
    "NotificationItem",
    "NotificationsListResponse",
    "MarkNotificationReadResponse",
    "MarkAllNotificationsReadResponse",
]


class NotificationItem(BaseModel):
    id: int
    report_kind: str
    report_date: str
    message: Optional[str] = None
    created_at: str
    read: bool


class NotificationsListResponse(BaseModel):
    notifications: List[NotificationItem]
    unread_count: int


class MarkNotificationReadResponse(BaseModel):
    ok: bool


class MarkAllNotificationsReadResponse(BaseModel):
    ok: bool
    marked: int
