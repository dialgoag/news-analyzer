"""
Admin data integrity service.

Builds the payload consumed by /api/admin/data-integrity without exposing the
routers to legacy stores or raw SQL queries.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Dict, Optional, Set, Tuple

from core.ports.repositories.document_repository import DocumentRepository
from core.ports.repositories.news_item_repository import NewsItemRepository


class AdminDataIntegrityService:
    """Aggregates filesystem/DB checks for the admin data-integrity endpoint."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        news_item_repository: NewsItemRepository,
        uploads_dir: Optional[str] = None,
    ) -> None:
        self._documents = document_repository
        self._news_items = news_item_repository
        self._uploads_dir = uploads_dir or os.getenv("UPLOAD_DIR", "/app/uploads")

    def get_data_integrity(self) -> dict:
        """Return the same structure previously assembled in admin.py."""
        documents = self._documents.list_all_sync(limit=None)
        doc_ids = {doc["document_id"] for doc in documents}
        total_db = len(documents)
        with_hash = sum(1 for doc in documents if doc.get("file_hash"))
        chunks_total = sum(int(doc.get("num_chunks") or 0) for doc in documents)

        disk_files = self._list_pdf_files(self._uploads_dir)
        orphaned_disk = disk_files - doc_ids
        orphaned_db = doc_ids - disk_files
        match_pct = self._compute_match_percentage(disk_files, doc_ids, total_db)

        files_section = {
            "total_disk": len(disk_files),
            "total_db": total_db,
            "with_hash": with_hash,
            "match": match_pct,
            "orphaned_count": len(orphaned_db),
        }

        total_insights, linked_insights = self._count_insights(doc_ids)
        orphaned_insights = total_insights - linked_insights
        insights_section = {
            "total": total_insights,
            "linked": linked_insights,
            "link_percentage": round((linked_insights / (total_insights or 1)) * 100, 1),
            "orphaned_count": orphaned_insights,
        }

        news_total = self._count_news_items()

        data_loss_percentage = (
            round(len(orphaned_db) / total_db * 100, 1) if total_db > 0 and orphaned_db else 0.0
        )

        schema_section = {"join_valid": True, "fk_active": False}
        recommendations = self._build_recommendations(match_pct, orphaned_db, orphaned_insights)

        overall = self._compute_overall_status(match_pct, orphaned_insights)

        return {
            "overall_status": overall,
            "timestamp": datetime.utcnow().isoformat(),
            "files": files_section,
            "insights": insights_section,
            "news_items": {"total": news_total},
            "chunks": {"total": int(chunks_total)},
            "data_loss_percentage": data_loss_percentage,
            "schema": schema_section,
            "recommendations": recommendations,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _list_pdf_files(self, uploads_dir: str) -> Set[str]:
        if not os.path.isdir(uploads_dir):
            return set()
        return {name for name in os.listdir(uploads_dir) if name.endswith(".pdf")}

    def _compute_match_percentage(self, disk_files: Set[str], doc_ids: Set[str], total_db: int) -> float:
        if not disk_files and not doc_ids:
            return 100.0
        intersection = len(disk_files & doc_ids)
        denominator = max(len(disk_files), total_db) or 1
        return round(intersection / denominator * 100, 1)

    def _count_insights(self, doc_ids: Set[str]) -> Tuple[int, int]:
        total, linked = self._news_items.count_insights_linkage_sync(list(doc_ids))
        return total, linked

    def _count_news_items(self) -> int:
        return self._news_items.count_all_sync()

    def _build_recommendations(
        self,
        match_pct: float,
        orphaned_db: Set[str],
        orphaned_insights: int,
    ) -> list:
        recommendations = []
        if match_pct < 100:
            recommendations.append(
                {
                    "priority": "high",
                    "message": f"{len(orphaned_db)} registros en BD sin archivo físico",
                }
            )
        if orphaned_insights > 0:
            recommendations.append(
                {
                    "priority": "medium",
                    "message": f"{orphaned_insights} insights con documento inexistente",
                }
            )
        return recommendations

    def _compute_overall_status(self, match_pct: float, orphaned_insights: int) -> str:
        if match_pct >= 99 and orphaned_insights == 0:
            return "healthy"
        if match_pct >= 95:
            return "warning"
        return "error"
