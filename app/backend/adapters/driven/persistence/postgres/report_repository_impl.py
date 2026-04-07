"""
PostgreSQL implementation of ReportRepository.
"""

from datetime import datetime
from typing import Dict, List, Optional

from core.ports.repositories.report_repository import ReportRepository
from .base import BasePostgresRepository


class PostgresReportRepository(BasePostgresRepository, ReportRepository):
    """Read adapter for daily/weekly reports."""

    def upsert_daily_sync(self, report_date: str, content: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """
                INSERT INTO daily_reports (report_date, content, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(report_date) DO UPDATE SET
                    content = excluded.content,
                    updated_at = excluded.updated_at
                """,
                (report_date, content, now, now),
            )
            conn.commit()
            return True
        finally:
            self.release_connection(conn)

    def upsert_weekly_sync(self, week_start: str, content: str) -> bool:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()
            cursor.execute(
                """
                INSERT INTO weekly_reports (week_start, content, created_at, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT(week_start) DO UPDATE SET
                    content = excluded.content,
                    updated_at = excluded.updated_at
                """,
                (week_start, content, now, now),
            )
            conn.commit()
            return True
        finally:
            self.release_connection(conn)

    def list_daily_sync(self, limit: int = 100) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT report_date, content, created_at, updated_at
                FROM daily_reports
                ORDER BY report_date DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [self._map_report_row(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)

    def get_daily_by_date_sync(self, report_date: str) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT report_date, content, created_at, updated_at
                FROM daily_reports
                WHERE report_date = %s
                """,
                (report_date,),
            )
            row = cursor.fetchone()
            return self._map_report_row(cursor, row)
        finally:
            self.release_connection(conn)

    def list_weekly_sync(self, limit: int = 52) -> List[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT week_start, content, created_at, updated_at
                FROM weekly_reports
                ORDER BY week_start DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            return [self._map_report_row(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)

    def get_weekly_by_start_sync(self, week_start: str) -> Optional[Dict]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT week_start, content, created_at, updated_at
                FROM weekly_reports
                WHERE week_start = %s
                """,
                (week_start,),
            )
            row = cursor.fetchone()
            return self._map_report_row(cursor, row)
        finally:
            self.release_connection(conn)

    @staticmethod
    def _to_iso(value):
        if isinstance(value, datetime):
            return value.isoformat()
        return value

    def _map_report_row(self, cursor, row) -> Optional[Dict]:
        data = self.map_row_to_dict(cursor, row)
        if not data:
            return None
        for key in ("report_date", "week_start", "created_at", "updated_at"):
            if key in data:
                data[key] = self._to_iso(data[key])
        return data
