"""
PostgreSQL implementation of NotificationRepository.
"""

from datetime import datetime
from typing import Dict, List

from core.ports.repositories.notification_repository import NotificationRepository
from .base import BasePostgresRepository


class PostgresNotificationRepository(BasePostgresRepository, NotificationRepository):
    """Read/write adapter for in-app notifications."""

    def list_for_user_sync(self, user_id: int, limit: int = 50) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT n.id, n.report_kind, n.report_date, n.message, n.created_at,
                       nr.read_at IS NOT NULL AS read
                FROM notifications n
                LEFT JOIN notification_reads nr
                    ON nr.notification_id = n.id AND nr.user_id = %s
                ORDER BY n.created_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            rows = cursor.fetchall()
            return [self._map_notification_row(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)

    def count_unread_for_user_sync(self, user_id: int) -> int:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM notifications n
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM notification_reads nr
                    WHERE nr.notification_id = n.id AND nr.user_id = %s
                )
                """,
                (user_id,),
            )
            row = cursor.fetchone()
            count = self.map_row_to_dict(cursor, row)
            return int(count["count"]) if count else 0
        finally:
            self.release_connection(conn)

    def mark_read_sync(self, notification_id: int, user_id: int) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO notification_reads (notification_id, user_id, read_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (notification_id, user_id) DO NOTHING
                """,
                (notification_id, user_id, datetime.utcnow().isoformat()),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.release_connection(conn)

    def mark_all_read_sync(self, user_id: int) -> int:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """
                INSERT INTO notification_reads (notification_id, user_id, read_at)
                SELECT n.id, %s, %s
                FROM notifications n
                WHERE NOT EXISTS (
                    SELECT 1
                    FROM notification_reads nr
                    WHERE nr.notification_id = n.id AND nr.user_id = %s
                )
                ON CONFLICT (notification_id, user_id) DO NOTHING
                """,
                (user_id, now, user_id),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            self.release_connection(conn)

    @staticmethod
    def _to_iso(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _map_notification_row(self, cursor, row) -> Dict:
        data = self.map_row_to_dict(cursor, row) or {}
        data["report_date"] = self._to_iso(data.get("report_date"))
        data["created_at"] = self._to_iso(data.get("created_at"))
        data["read"] = bool(data.get("read"))
        if data.get("message") == "":
            data["message"] = None
        return data
