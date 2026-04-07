"""
Report generation service (daily/weekly).

Encapsula la lógica de selección de documentos, extracción de chunks y
generación de reportes para que los jobs no dependan de document_status_store.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Optional, Sequence, TYPE_CHECKING
import logging

from core.ports.repositories.document_repository import DocumentRepository
from core.ports.repositories.report_repository import ReportRepository
from core.ports.repositories.notification_repository import NotificationRepository

if TYPE_CHECKING:
    from qdrant_connector import QdrantConnector
    from rag_pipeline import RAGPipeline


logger = logging.getLogger(__name__)


class ReportService:
    """Genera reportes diarios y semanales usando los puertos hexagonales disponibles."""

    def __init__(
        self,
        *,
        document_repository: DocumentRepository,
        qdrant_connector: "QdrantConnector",
        rag_pipeline: "RAGPipeline",
        report_repository: ReportRepository,
        notification_repository: NotificationRepository,
        max_daily_context_len: int = 120_000,
        max_weekly_context_len: int = 150_000,
    ) -> None:
        self._documents = document_repository
        self._qdrant = qdrant_connector
        self._rag = rag_pipeline
        self._reports = report_repository
        self._notifications = notification_repository
        self._max_daily_context_len = max_daily_context_len
        self._max_weekly_context_len = max_weekly_context_len

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def generate_daily_report(self, report_date: str) -> bool:
        """Genera o regenera el reporte diario para una fecha específica."""
        if not self._is_ready():
            logger.warning("Daily report skipped: service not fully initialized")
            return False

        doc_ids = self._documents.list_ids_by_news_date_sync(report_date)
        if not doc_ids:
            logger.info("Daily report: no indexed documents for news_date=%s", report_date)
            return False

        logger.info("Daily report: building context for %s (%d document_ids)", report_date, len(doc_ids))
        context = self._build_context_from_documents(doc_ids, max_chunks=2000, max_chars=self._max_daily_context_len)
        if not context:
            logger.warning("Daily report: no chunks retrieved for %s", report_date)
            return False

        try:
            content = self._rag.generate_report_from_context(context, report_date)
            self._reports.upsert_daily_sync(report_date, content)
            self._notifications.create_sync("daily", report_date, message=f"Reporte del {report_date} actualizado")
            logger.info("Daily report generated for %s", report_date)
            return True
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Daily report generation failed for %s: %s", report_date, exc, exc_info=True)
            return False

    def generate_weekly_report(self, week_start: str) -> bool:
        """Genera o regenera el reporte semanal para la semana que inicia en week_start."""
        if not self._is_ready():
            logger.warning("Weekly report skipped: service not fully initialized")
            return False

        try:
            start = datetime.strptime(week_start, "%Y-%m-%d").date()
        except ValueError:
            logger.warning("Weekly report: invalid week_start %s", week_start)
            return False
        end = start + timedelta(days=6)
        week_end = end.isoformat()

        doc_ids = self._documents.list_ids_by_news_date_range_sync(start.isoformat(), week_end)
        if not doc_ids:
            logger.info("Weekly report: no documents for week %s-%s", week_start, week_end)
            return False

        logger.info(
            "Weekly report: building context for range %s-%s (%d document_ids)",
            week_start,
            week_end,
            len(doc_ids),
        )
        context = self._build_context_from_documents(doc_ids, max_chunks=3000, max_chars=self._max_weekly_context_len)
        if not context:
            logger.warning("Weekly report: no chunks retrieved for %s-%s", week_start, week_end)
            return False

        try:
            content = self._rag.generate_weekly_report_from_context(context, week_start, week_end)
            self._reports.upsert_weekly_sync(week_start, content)
            self._notifications.create_sync("weekly", week_start, message=f"Reporte semanal {week_start} listo")
            logger.info("Weekly report generated for range %s-%s", week_start, week_end)
            return True
        except Exception as exc:  # pragma: no cover
            logger.error("Weekly report generation failed for %s-%s: %s", week_start, week_end, exc, exc_info=True)
            return False

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _is_ready(self) -> bool:
        return self._qdrant is not None and self._rag is not None

    def _build_context_from_documents(
        self,
        document_ids: Sequence[str],
        *,
        max_chunks: int,
        max_chars: int,
    ) -> Optional[str]:
        if not document_ids:
            return None

        chunks = self._qdrant.get_chunks_by_document_ids(list(document_ids), max_chunks=max_chunks)
        if not chunks:
            return None

        grouped = {}
        for chunk in chunks:
            doc_id = chunk.get("document_id") or "unknown"
            entry = grouped.setdefault(doc_id, {"filename": chunk.get("filename", "unknown"), "texts": []})
            entry["texts"].append(chunk.get("text") or "")

        parts: List[str] = []
        for data in grouped.values():
            filename = data["filename"]
            parts.append(f"[{filename}]\n" + "\n".join(filter(None, data["texts"])))

        context = "\n\n---\n\n".join(parts)
        if len(context) > max_chars:
            context = context[:max_chars] + "\n\n[... texto recortado por límite ...]"
        return context
