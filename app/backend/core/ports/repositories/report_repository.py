"""
Report repository port for daily/weekly report reads.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional


class ReportRepository(ABC):
    """Port for reading generated reports from persistence."""

    @abstractmethod
    def list_daily_sync(self, limit: int = 100) -> List[Dict]:
        """Return daily reports sorted by report_date desc."""
        pass

    @abstractmethod
    def get_daily_by_date_sync(self, report_date: str) -> Optional[Dict]:
        """Return a daily report by date (YYYY-MM-DD)."""
        pass

    @abstractmethod
    def list_weekly_sync(self, limit: int = 52) -> List[Dict]:
        """Return weekly reports sorted by week_start desc."""
        pass

    @abstractmethod
    def get_weekly_by_start_sync(self, week_start: str) -> Optional[Dict]:
        """Return a weekly report by week_start (YYYY-MM-DD)."""
        pass
