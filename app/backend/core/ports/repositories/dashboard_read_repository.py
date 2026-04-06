"""
Dashboard Read Repository Port.

Centralizes read-heavy queries used by dashboard/admin services so routers and
services depend on hexagonal ports instead of legacy stores.
"""

from abc import ABC, abstractmethod
from typing import Dict, List


class DashboardReadRepository(ABC):
    """Port for specialized dashboard read models."""

    @abstractmethod
    def build_analysis_snapshot(self, *, inbox_count: int) -> dict:
        """
        Return the analysis payload (errors, stages, workers, queues, inconsistencies).

        Args:
            inbox_count: Number of files detected in the inbox directory (used for upload stage).
        """
        raise NotImplementedError

    @abstractmethod
    def fetch_news_overview(self) -> Dict[str, object]:
        """Return aggregated counts for news items vs. insights linkage."""
        raise NotImplementedError

    @abstractmethod
    def fetch_insights_overview(self) -> Dict[str, object]:
        """Return aggregated counts for insights (pending/done/errors)."""
        raise NotImplementedError

    @abstractmethod
    def count_news_items(self) -> int:
        """Return total news items ingested."""
        raise NotImplementedError

    @abstractmethod
    def fetch_queue_counts(self, task_type: str) -> Dict[str, int]:
        """Return pending/processing/completed counts for the given queue task."""
        raise NotImplementedError

    @abstractmethod
    def count_news_by_document_ids(self, document_ids: List[str]) -> Dict[str, int]:
        """Return news-item totals grouped by document_id."""
        raise NotImplementedError

    @abstractmethod
    def fetch_parallel_news_items(
        self, document_ids: List[str], max_news_per_doc: int
    ) -> Dict[str, List[Dict[str, object]]]:
        """Return per-document slices used by the parallel coordinates visualization."""
        raise NotImplementedError
