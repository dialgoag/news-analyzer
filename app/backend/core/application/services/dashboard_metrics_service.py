"""
Dashboard metrics service.

Centralizes the data aggregation logic that previously lived inside the
dashboard/admin routers so they can depend on hexagonal services instead of
querying the legacy document_status_store directly.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.ports.repositories.dashboard_read_repository import DashboardReadRepository
from core.ports.repositories.document_repository import DocumentRepository
from pipeline_states import DocStatus, TaskType


class DashboardMetricsService:
    """Aggregates pipeline metrics for dashboard endpoints."""

    COMPLETED_STATUSES = {
        DocStatus.INDEXING_DONE,
        DocStatus.INSIGHTS_PENDING,
        DocStatus.INSIGHTS_PROCESSING,
        DocStatus.INSIGHTS_DONE,
        DocStatus.COMPLETED,
    }

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        dashboard_read_repository: DashboardReadRepository,
    ) -> None:
        self._documents = document_repository
        self._dashboard_reads = dashboard_read_repository

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_summary(self, *, inbox_dir: Optional[str] = None) -> dict:
        """
        Build the data payload required by GET /api/dashboard/summary.

        Args:
            inbox_dir: Optional override for the inbox directory. Defaults to
                       env INBOX_DIR or /app/inbox.
        """
        overview = self._documents.get_files_overview_sync()
        inbox_count = self._count_inbox_files(inbox_dir or os.getenv("INBOX_DIR", "/app/inbox"))

        (
            files_section,
            total_docs,
            completed_files,
            processing_files,
            error_files,
        ) = self._build_files_section(overview, inbox_count)

        news_section = self._build_news_section(
            completed_files=completed_files,
            total_files=files_section["total"],
        )
        insights_section = self._build_insights_section(expected_total_news=news_section["total"])

        chunking_section, indexing_section = self._build_chunking_and_indexing_sections(
            total_docs=total_docs,
            chunks_total=int(overview.get("chunks_total") or 0),
        )

        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "files": files_section,
            "news_items": news_section,
            "ocr": self._build_ocr_section(
                total_files=files_section["total"],
                completed_files=completed_files,
                processing_files=processing_files,
                error_files=error_files,
            ),
            "chunking": chunking_section,
            "indexing": indexing_section,
            "insights": insights_section,
            "errors": {
                "documents_with_errors": error_files,
                "ocr_errors": 0,
                "chunking_errors": 0,
                "indexing_errors": 0,
            },
        }
        return summary

    def get_parallel_data(self, *, limit: int, max_news_per_doc: int) -> Dict[str, Any]:
        rows = self._documents.list_all_sync()
        selected_docs = rows[:limit]
        doc_ids = [row["document_id"] for row in selected_docs]
        news_totals = self._dashboard_reads.count_news_by_document_ids(doc_ids)
        news_map = self._fetch_parallel_news_items(doc_ids, max_news_per_doc)

        documents_payload: List[Dict[str, Any]] = []
        for row in selected_docs:
            doc_id = row["document_id"]
            ingested_at = row.get("ingested_at")
            if isinstance(ingested_at, datetime):
                ingested_at = ingested_at.isoformat()

            documents_payload.append(
                {
                    "document_id": doc_id,
                    "filename": row.get("filename"),
                    "status": row.get("status"),
                    "processing_stage": row.get("processing_stage"),
                    "ingested_at": ingested_at,
                    "news_items_total": int(news_totals.get(doc_id, 0) or 0),
                    "news_items": news_map.get(doc_id, []),
                }
            )

        return {
            "documents": documents_payload,
            "meta": {
                "limit": limit,
                "max_news_per_doc": max_news_per_doc,
                "total_documents": len(documents_payload),
            },
        }

    def get_analysis(self, *, inbox_dir: Optional[str] = None) -> dict:
        inbox_count = self._count_inbox_files(inbox_dir or os.getenv("INBOX_DIR", "/app/inbox"))
        return self._dashboard_reads.build_analysis_snapshot(inbox_count=inbox_count)

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _build_files_section(
        self,
        overview: dict,
        inbox_count: int,
    ) -> Tuple[dict, int, int, int, int]:
        total_docs = int(overview.get("total_documents") or 0)
        completed_files = int(overview.get("completed_documents") or 0)
        processing_files = int(overview.get("processing_documents") or 0)
        error_files = int(overview.get("error_documents") or 0)

        date_first_raw = overview.get("date_first")
        date_last_raw = overview.get("date_last")
        date_first = (
            self._coerce_datetime(date_first_raw).isoformat() if date_first_raw else None
        )
        date_last = (
            self._coerce_datetime(date_last_raw).isoformat() if date_last_raw else None
        )

        total_files = max(inbox_count, total_docs)
        pending_files = max(0, total_files - completed_files - error_files)

        files_section = {
            "total": total_files,
            "completed": completed_files,
            "processing": processing_files,
            "errors": error_files,
            "pending": pending_files,
            "percentage_done": round((completed_files or 0) / (total_files or 1) * 100, 2),
            "date_first": date_first,
            "date_last": date_last,
            "inbox_count": inbox_count,
        }
        return files_section, total_docs, completed_files, processing_files, error_files

    def _build_news_section(self, *, completed_files: int, total_files: int) -> dict:
        row = self._dashboard_reads.fetch_news_overview()
        current_news = int(row.get("total_current") or 0)
        done = int(row.get("done") or 0)
        pending = int(row.get("pending") or 0)
        errors = int(row.get("errors") or 0)

        pending_files = max(0, total_files - completed_files)
        news_per_file = current_news / completed_files if completed_files > 0 else 0
        expected_total = int(current_news + (pending_files * news_per_file))

        return {
            "total": expected_total,
            "done": done,
            "pending": pending,
            "errors": errors,
            "percentage_done": round((done or 0) / (expected_total or 1) * 100, 2),
            "date_first": row.get("date_first"),
            "date_last": row.get("date_last"),
        }

    def _build_insights_section(self, *, expected_total_news: int) -> dict:
        row = self._dashboard_reads.fetch_insights_overview()
        done = int(row.get("done") or 0)
        pending = int(row.get("pending") or 0)
        errors = int(row.get("errors") or 0)

        parallel_workers = 4
        pending_batches = pending / parallel_workers if parallel_workers else 0
        eta_seconds = int(pending_batches * 15)

        return {
            "total": expected_total_news,
            "done": done,
            "pending": pending,
            "errors": errors,
            "percentage_done": round((done or 0) / (expected_total_news or 1) * 100, 2),
            "parallel_workers": parallel_workers,
            "eta_seconds": eta_seconds,
        }

    def _build_chunking_and_indexing_sections(
        self,
        *,
        total_docs: int,
        chunks_total: int,
    ) -> Tuple[dict, dict]:
        chunk_counts = self._dashboard_reads.fetch_queue_counts(TaskType.CHUNKING)
        indexing_counts = self._dashboard_reads.fetch_queue_counts(TaskType.INDEXING)

        news_items_total = self._dashboard_reads.count_news_items()

        chunk_completed = chunk_counts["completed"]
        chunk_processing = chunk_counts["processing"]
        chunk_pending = max(0, total_docs - chunk_completed - chunk_processing)

        chunking_section = {
            "granularity": "document",
            "total": total_docs,
            "total_chunks": total_docs,
            "indexed": chunk_completed,
            "completed": chunk_completed,
            "pending": chunk_pending,
            "processing": chunk_processing,
            "errors": 0,
            "percentage_indexed": round((chunk_completed or 0) / (total_docs or 1) * 100, 2),
            "chunks_total": chunks_total,
            "news_items_count": news_items_total,
        }

        indexing_completed = indexing_counts["completed"]
        indexing_processing = indexing_counts["processing"]
        indexing_pending = max(0, total_docs - indexing_completed - indexing_processing)

        indexing_section = {
            "granularity": "document",
            "total": total_docs,
            "active": indexing_completed,
            "completed": indexing_completed,
            "pending": indexing_pending,
            "errors": 0,
            "percentage_indexed": round((indexing_completed or 0) / (total_docs or 1) * 100, 2),
            "total_chunks": chunks_total,
            "news_items_count": news_items_total,
        }

        return chunking_section, indexing_section

    def _build_ocr_section(
        self,
        *,
        total_files: int,
        completed_files: int,
        processing_files: int,
        error_files: int,
    ) -> dict:
        return {
            "total": total_files,
            "successful": completed_files,
            "processing": processing_files,
            "errors": error_files,
            "percentage_success": round((completed_files or 0) / (total_files or 1) * 100, 2),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _count_inbox_files(self, inbox_dir: str) -> int:
        if not os.path.isdir(inbox_dir):
            return 0
        files = [
            name
            for name in os.listdir(inbox_dir)
            if name != "processed" and os.path.isfile(os.path.join(inbox_dir, name))
        ]
        return len(files)

    def _coerce_datetime(self, value) -> datetime:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.min

    def _fetch_parallel_news_items(self, doc_ids: List[str], max_news_per_doc: int) -> Dict[str, List[Dict[str, Any]]]:
        return self._dashboard_reads.fetch_parallel_news_items(doc_ids, max_news_per_doc)
