"""
Notification repository port for user inbox operations.
"""

from abc import ABC, abstractmethod
from typing import Dict, List


class NotificationRepository(ABC):
    """Port for notification list/read persistence."""

    @abstractmethod
    def create_sync(self, report_kind: str, report_date: str, message: str | None = None) -> bool:
        """Create one notification entry."""
        pass

    @abstractmethod
    def list_for_user_sync(self, user_id: int, limit: int = 50) -> List[Dict]:
        """Return notifications for a user with read flag."""
        pass

    @abstractmethod
    def count_unread_for_user_sync(self, user_id: int) -> int:
        """Return unread notifications count for a user."""
        pass

    @abstractmethod
    def mark_read_sync(self, notification_id: int, user_id: int) -> bool:
        """Mark one notification as read for a user."""
        pass

    @abstractmethod
    def mark_all_read_sync(self, user_id: int) -> int:
        """Mark all notifications as read for a user."""
        pass
