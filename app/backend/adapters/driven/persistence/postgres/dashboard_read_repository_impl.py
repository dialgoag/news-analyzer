"""
PostgreSQL implementation of DashboardReadRepository.

Executes the raw SQL needed for dashboard analysis endpoints.
"""

from datetime import datetime
from typing import Dict, List

from core.ports.repositories.dashboard_read_repository import DashboardReadRepository
from pipeline_states import DocStatus, QueueStatus, Stage, TaskType, WorkerStatus

from .base import BasePostgresRepository


class PostgresDashboardReadRepository(BasePostgresRepository, DashboardReadRepository):
    """Runs the SQL aggregation queries for dashboard analysis."""

    def build_analysis_snapshot(self, *, inbox_count: int) -> dict:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()

            error_groups, real_errors_count, shutdown_errors_count = self._collect_document_errors(cursor)
            insight_groups, insight_real_errors = self._collect_insight_errors(cursor)
            error_groups.extend(insight_groups)
            real_errors_count += insight_real_errors

            stages_analysis = self._build_stage_analysis(cursor, inbox_count)
            chunks_total, news_count = self._fetch_chunk_and_news_counts(cursor)

            workers = self._build_workers_section(cursor)
            queue_summary = self._build_queue_summary(cursor)
            worker_tasks_summary = self._build_worker_tasks_summary(cursor)
            inconsistencies = self._detect_inconsistencies(cursor)

            return {
                "timestamp": self._now_iso(),
                "errors": {
                    "groups": error_groups,
                    "real_errors": real_errors_count,
                    "shutdown_errors": shutdown_errors_count,
                    "total_errors": real_errors_count + shutdown_errors_count,
                },
                "pipeline": {
                    "stages": self._inject_chunk_news_counts(stages_analysis, chunks_total, news_count),
                    "total_blockers": sum(len(stage.get("blockers", [])) for stage in stages_analysis),
                },
                "workers": workers,
                "database": {
                    "processing_queue": queue_summary,
                    "worker_tasks": worker_tasks_summary,
                    "inconsistencies": inconsistencies,
                },
            }
        finally:
            self.release_connection(conn)

    def fetch_news_overview(self) -> Dict[str, object]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(DISTINCT ni.news_item_id) as total_current,
                    SUM(CASE WHEN nii.status = 'done' THEN 1 ELSE 0 END) as done,
                    SUM(CASE WHEN nii.status IN ('pending', 'queued', 'generating') THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN nii.status = 'error' THEN 1 ELSE 0 END) as errors,
                    MIN(ni.created_at) as date_first,
                    MAX(ni.created_at) as date_last
                FROM news_items ni
                LEFT JOIN news_item_insights nii ON ni.news_item_id = nii.news_item_id
                """
            )
            row = cursor.fetchone() or {}
            return dict(row)
        finally:
            self.release_connection(conn)

    def fetch_insights_overview(self) -> Dict[str, object]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(DISTINCT nii.news_item_id) as total_current,
                    SUM(CASE WHEN nii.status = 'done' THEN 1 ELSE 0 END) as done,
                    SUM(CASE WHEN nii.status IN ('pending', 'queued', 'generating') THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN nii.status = 'error' THEN 1 ELSE 0 END) as errors
                FROM news_item_insights nii
                INNER JOIN news_items ni ON ni.news_item_id = nii.news_item_id
                """
            )
            row = cursor.fetchone() or {}
            return dict(row)
        finally:
            self.release_connection(conn)

    def count_news_items(self) -> int:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as count FROM news_items")
            row = cursor.fetchone() or {}
            return int(row.get("count") or 0)
        finally:
            self.release_connection(conn)

    def fetch_queue_counts(self, task_type: str) -> Dict[str, int]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            return self._fetch_queue_counts(cursor, task_type)
        finally:
            self.release_connection(conn)

    def count_news_by_document_ids(self, document_ids: List[str]) -> Dict[str, int]:
        if not document_ids:
            return {}
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            placeholders = ",".join(["%s"] * len(document_ids))
            cursor.execute(
                f"""
                SELECT document_id, COUNT(*) as count
                FROM news_items
                WHERE document_id IN ({placeholders})
                GROUP BY document_id
                """,
                tuple(document_ids),
            )
            rows = cursor.fetchall()
            return {row["document_id"]: int(row["count"] or 0) for row in rows}
        finally:
            self.release_connection(conn)

    def fetch_parallel_news_items(
        self, document_ids: List[str], max_news_per_doc: int
    ) -> Dict[str, List[Dict[str, object]]]:
        if not document_ids or max_news_per_doc <= 0:
            return {}

        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            placeholders = ",".join(["%s"] * len(document_ids))
            cursor.execute(
                f"""
                SELECT *
                FROM (
                    SELECT
                        ni.news_item_id,
                        ni.document_id,
                        ni.item_index,
                        ni.title,
                        ni.status AS news_status,
                        nii.status AS insight_status,
                        nii.error_message,
                        nii.indexed_in_qdrant_at,
                        ROW_NUMBER() OVER (
                            PARTITION BY ni.document_id
                            ORDER BY ni.item_index ASC
                        ) AS rn
                    FROM news_items ni
                    LEFT JOIN news_item_insights nii ON ni.news_item_id = nii.news_item_id
                    WHERE ni.document_id IN ({placeholders})
                ) sub
                WHERE rn <= %s
                ORDER BY document_id, item_index
                """,
                tuple(document_ids + [max_news_per_doc]),
            )
            rows = cursor.fetchall()
        finally:
            self.release_connection(conn)

        result: Dict[str, List[Dict[str, object]]] = {doc_id: [] for doc_id in document_ids}
        for row in rows:
            doc_id = row["document_id"]
            indexed_at = row.get("indexed_in_qdrant_at")
            if isinstance(indexed_at, datetime):
                indexed_at = indexed_at.isoformat()
            insight_status = row.get("insight_status") or None
            if indexed_at:
                index_status = "indexed"
            elif insight_status == "indexing":
                index_status = "indexing"
            elif insight_status == "done":
                index_status = "ready"
            else:
                index_status = "pending"

            result.setdefault(doc_id, []).append(
                {
                    "news_item_id": row["news_item_id"],
                    "document_id": doc_id,
                    "title": row.get("title"),
                    "item_index": int(row.get("item_index") or 0),
                    "news_status": row.get("news_status"),
                    "insight_status": insight_status,
                    "index_status": index_status,
                    "error_message": row.get("error_message"),
                }
            )
        return result

    # ------------------------------------------------------------------
    # Internal helpers (mostly copied from legacy logic)
    # ------------------------------------------------------------------

    def _collect_document_errors(self, cursor):
        cursor.execute(
            """
            SELECT
                error_message,
                processing_stage,
                COUNT(*) as count,
                ARRAY_AGG(document_id ORDER BY document_id) as document_ids,
                ARRAY_AGG(filename ORDER BY document_id) as filenames
            FROM document_status
            WHERE status = %s
            GROUP BY error_message, processing_stage
            ORDER BY count DESC
            """,
            (DocStatus.ERROR,),
        )
        rows = cursor.fetchall()
        groups = []
        real_errors = 0
        shutdown_errors = 0
        for row in rows:
            error_msg = row["error_message"] or "Sin mensaje de error"
            is_shutdown = "Shutdown ordenado" in error_msg
            if is_shutdown:
                shutdown_errors += row["count"]
            else:
                real_errors += row["count"]
            groups.append(
                {
                    "error_message": error_msg,
                    "stage": row["processing_stage"] or "unknown",
                    "count": row["count"],
                    "cause": self._infer_error_cause(error_msg),
                    "can_auto_fix": self._can_auto_fix(error_msg),
                    "document_ids": row["document_ids"] or [],
                    "filenames": row["filenames"] or [],
                }
            )
        return groups, real_errors, shutdown_errors

    def _collect_insight_errors(self, cursor):
        cursor.execute(
            """
            SELECT
                error_message,
                COUNT(*) as count,
                ARRAY_AGG('insight_' || news_item_id ORDER BY news_item_id) as document_ids,
                ARRAY_AGG(filename ORDER BY news_item_id) as filenames
            FROM news_item_insights
            WHERE status = 'error'
            GROUP BY error_message
            ORDER BY count DESC
            """
        )
        rows = cursor.fetchall()
        groups = []
        real_errors = 0
        for row in rows:
            error_msg = row["error_message"] or "Sin mensaje de error"
            real_errors += row["count"]
            groups.append(
                {
                    "error_message": error_msg,
                    "stage": "insights",
                    "count": row["count"],
                    "cause": self._infer_insight_error_cause(error_msg),
                    "can_auto_fix": self._can_auto_fix_insight(error_msg),
                    "document_ids": row["document_ids"] or [],
                    "filenames": row["filenames"] or [],
                }
            )
        return groups, real_errors

    def _build_stage_analysis(self, cursor, inbox_count: int) -> List[dict]:
        stages: List[dict] = []

        upload_counts = self._fetch_upload_stage_counts(cursor)
        ocr_errors = self._count_stage_errors(cursor, Stage.OCR)
        chunk_errors = self._count_stage_errors(cursor, Stage.CHUNKING)
        indexing_errors = self._count_stage_errors(cursor, Stage.INDEXING)

        upload_pending = upload_counts["pending"] or 0
        upload_processing = upload_counts["processing"] or 0
        upload_completed = upload_counts["completed"] or 0
        upload_paused = upload_counts["paused"] or 0
        upload_total = upload_pending + upload_processing + upload_completed + upload_paused + ocr_errors
        upload_pending += max(0, inbox_count - upload_total)

        stages.append(
            {
                "name": "Upload",
                "total_documents": upload_pending + upload_processing + upload_completed + upload_paused + ocr_errors,
                "pending_tasks": upload_pending,
                "processing_tasks": upload_processing,
                "completed_tasks": upload_completed,
                "error_tasks": ocr_errors,
                "paused_tasks": upload_paused,
                "ready_for_next": upload_completed,
                "inbox_documents": inbox_count,
                "blockers": [],
            }
        )

        # OCR stage
        ocr_queue = self._fetch_queue_counts(cursor, TaskType.OCR)
        ocr_done_from_docs = self._count_docs_in_statuses(
            cursor,
            [
                DocStatus.OCR_DONE,
                DocStatus.CHUNKING_PENDING,
                DocStatus.CHUNKING_PROCESSING,
                DocStatus.CHUNKING_DONE,
                DocStatus.INDEXING_PENDING,
                DocStatus.INDEXING_PROCESSING,
                DocStatus.INDEXING_DONE,
                DocStatus.INSIGHTS_PENDING,
                DocStatus.INSIGHTS_PROCESSING,
                DocStatus.INSIGHTS_DONE,
                DocStatus.COMPLETED,
            ],
        )
        ocr_ready_for_chunking = self._count_ready_for_chunking(cursor)
        chunk_queue_needs_input = self._queue_has_pending(cursor, TaskType.CHUNKING)
        ocr_blockers = []
        if chunk_queue_needs_input and ocr_ready_for_chunking == 0:
            ocr_blockers.append(
                {
                    "reason": "No hay documentos con status='ocr_done' y texto OCR válido",
                    "count": 0,
                    "solution": "Esperando que documentos completen OCR correctamente",
                }
            )
        stages.append(
            {
                "name": "OCR",
                "total_documents": (ocr_queue["pending"] or 0)
                + (ocr_queue["processing"] or 0)
                + max(ocr_queue["completed"] or 0, ocr_done_from_docs)
                + ocr_errors,
                "pending_tasks": ocr_queue["pending"] or 0,
                "processing_tasks": ocr_queue["processing"] or 0,
                "completed_tasks": max(ocr_queue["completed"] or 0, ocr_done_from_docs),
                "error_tasks": ocr_errors,
                "ready_for_next": ocr_ready_for_chunking,
                "blockers": ocr_blockers,
            }
        )

        # Chunking stage
        chunk_queue = self._fetch_queue_counts(cursor, TaskType.CHUNKING)
        chunk_done_from_docs = self._count_docs_in_statuses(
            cursor,
            [
                DocStatus.CHUNKING_DONE,
                DocStatus.INDEXING_PENDING,
                DocStatus.INDEXING_PROCESSING,
                DocStatus.INDEXING_DONE,
                DocStatus.INSIGHTS_PENDING,
                DocStatus.INSIGHTS_PROCESSING,
                DocStatus.INSIGHTS_DONE,
                DocStatus.COMPLETED,
            ],
        )
        chunk_ready_for_indexing = self._count_ready_for_indexing(cursor)
        indexing_needs_input = self._queue_has_pending(cursor, TaskType.INDEXING)
        chunk_blockers = []
        if indexing_needs_input and chunk_ready_for_indexing == 0:
            chunk_blockers.append(
                {
                    "reason": "No hay documentos con chunking_done",
                    "count": 0,
                    "solution": "Esperando que documentos completen chunking",
                }
            )
        stages.append(
            {
                "name": "Chunking",
                "granularity": "document",
                "total_documents": (chunk_queue["pending"] or 0)
                + (chunk_queue["processing"] or 0)
                + max(chunk_queue["completed"] or 0, chunk_done_from_docs)
                + chunk_errors,
                "pending_tasks": chunk_queue["pending"] or 0,
                "processing_tasks": chunk_queue["processing"] or 0,
                "completed_tasks": max(chunk_queue["completed"] or 0, chunk_done_from_docs),
                "error_tasks": chunk_errors,
                "ready_for_next": chunk_ready_for_indexing,
                "blockers": chunk_blockers,
            }
        )

        # Indexing stage
        indexing_queue = self._fetch_queue_counts(cursor, TaskType.INDEXING)
        indexing_done_from_docs = self._count_docs_in_statuses(
            cursor,
            [
                DocStatus.INDEXING_DONE,
                DocStatus.INSIGHTS_PENDING,
                DocStatus.INSIGHTS_PROCESSING,
                DocStatus.INSIGHTS_DONE,
                DocStatus.COMPLETED,
            ],
        )
        stages.append(
            {
                "name": "Indexing",
                "granularity": "document",
                "total_documents": (indexing_queue["pending"] or 0)
                + (indexing_queue["processing"] or 0)
                + max(indexing_queue["completed"] or 0, indexing_done_from_docs)
                + indexing_errors,
                "pending_tasks": indexing_queue["pending"] or 0,
                "processing_tasks": indexing_queue["processing"] or 0,
                "completed_tasks": max(indexing_queue["completed"] or 0, indexing_done_from_docs),
                "error_tasks": indexing_errors,
                "ready_for_next": 0,
                "blockers": [],
            }
        )

        # Insights stages
        insights_stage = self._fetch_insights_stage(cursor)
        indexing_ins_stage = self._fetch_indexing_insights_stage(cursor)
        insights_stage["ready_for_next"] = indexing_ins_stage["pending_tasks"]
        stages.append(insights_stage)
        stages.append(indexing_ins_stage)
        return stages

    def _fetch_chunk_and_news_counts(self, cursor):
        cursor.execute("SELECT COALESCE(SUM(num_chunks), 0) as n FROM document_status WHERE num_chunks > 0")
        chunks_total = int(cursor.fetchone()["n"] or 0)
        cursor.execute("SELECT COUNT(*) as n FROM news_items")
        news_count = int(cursor.fetchone()["n"] or 0)
        return chunks_total, news_count

    def _build_workers_section(self, cursor) -> dict:
        cursor.execute(
            """
            SELECT
                wt.worker_id,
                wt.worker_type,
                wt.task_type,
                wt.document_id,
                wt.status,
                wt.started_at,
                EXTRACT(EPOCH FROM (NOW() - wt.started_at)) / 60 as minutes_running,
                COALESCE(ds.filename,
                    CASE WHEN wt.task_type IN ('insights', 'indexing_insights') THEN
                        (SELECT COALESCE(nii.filename, nii.title) FROM news_item_insights nii
                         WHERE nii.news_item_id = REPLACE(wt.document_id, 'insight_', '') LIMIT 1)
                    END
                ) as filename
            FROM worker_tasks wt
            LEFT JOIN document_status ds ON ds.document_id = wt.document_id
            WHERE wt.status IN ('assigned', 'started')
            ORDER BY wt.started_at ASC
            """
        )
        rows = cursor.fetchall()
        active_workers = []
        stuck_workers = []
        for row in rows:
            minutes = row["minutes_running"] or 0
            is_stuck = minutes > 20
            filename = row.get("filename") or row.get("document_id")
            data = {
                "worker_id": row["worker_id"],
                "worker_type": row["worker_type"],
                "task_type": row["task_type"],
                "document_id": row["document_id"],
                "filename": filename,
                "status": row["status"],
                "started_at": row["started_at"].isoformat() if row["started_at"] else None,
                "execution_time_minutes": round(minutes, 1),
                "is_stuck": is_stuck,
                "timeout_limit": 25 if row["task_type"] == TaskType.OCR else 10,
                "progress_percent": self._compute_progress(row["task_type"], minutes),
            }
            active_workers.append(data)
            if is_stuck:
                stuck_workers.append(data)

        cursor.execute(
            """
            SELECT
                worker_type,
                task_type,
                status,
                COUNT(*) as count
            FROM worker_tasks
            WHERE completed_at > NOW() - INTERVAL '24 hours'
            GROUP BY worker_type, task_type, status
            ORDER BY worker_type, task_type, status
            """
        )
        rows = cursor.fetchall()
        workers_by_type = {}
        for row in rows:
            key = f"{row['worker_type']}/{row['task_type']}"
            workers_by_type.setdefault(key, {})[row["status"]] = row["count"]

        return {
            "active": len(active_workers),
            "stuck": len(stuck_workers),
            "stuck_list": stuck_workers,
            "active_list": active_workers,
            "by_type": workers_by_type,
            "summary": self._build_worker_tasks_summary(cursor),
        }

    def _build_queue_summary(self, cursor) -> dict:
        cursor.execute(
            """
            SELECT
                task_type,
                status,
                COUNT(*) as count
            FROM processing_queue
            GROUP BY task_type, status
            ORDER BY task_type, status
            """
        )
        rows = cursor.fetchall()
        summary = {}
        for row in rows:
            summary.setdefault(row["task_type"], {})[row["status"]] = row["count"]
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM processing_queue pq
            WHERE pq.status = 'processing'
            AND NOT EXISTS (
                SELECT 1 FROM worker_tasks wt
                WHERE wt.document_id = pq.document_id
                AND wt.task_type = pq.task_type
                AND wt.status IN ('assigned', 'started')
            )
            """
        )
        orphaned = cursor.fetchone()["count"]
        return {"by_type": summary, "orphaned_tasks": orphaned}

    def _build_worker_tasks_summary(self, cursor) -> dict:
        cursor.execute(
            """
            SELECT
                status,
                COUNT(*) as count
            FROM worker_tasks
            GROUP BY status
            """
        )
        rows = cursor.fetchall()
        return {row["status"]: row["count"] for row in rows}

    def _detect_inconsistencies(self, cursor) -> List[dict]:
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM document_status ds
            INNER JOIN worker_tasks wt ON wt.document_id = ds.document_id AND wt.task_type = 'ocr'
            WHERE ds.status = %s
            AND wt.status IN (%s, %s)
            """,
            (DocStatus.OCR_DONE, WorkerStatus.ASSIGNED, WorkerStatus.STARTED),
        )
        count = cursor.fetchone()["count"]
        if count > 0:
            return [
                {
                    "type": "doc_ocr_done_but_worker_active",
                    "description": "Documentos con status='ocr_done' pero worker aún activo",
                    "count": count,
                    "severity": "low",
                    "can_auto_fix": False,
                }
            ]
        return []

    # ------------------------------------------------------------------
    # SQL helper functions
    # ------------------------------------------------------------------

    def _fetch_upload_stage_counts(self, cursor):
        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = %s) as pending,
                COUNT(*) FILTER (WHERE status = %s) as processing,
                COUNT(*) FILTER (WHERE status = %s) as completed,
                COUNT(*) FILTER (WHERE status = %s) as paused
            FROM document_status
            """,
            (
                DocStatus.UPLOAD_PENDING,
                DocStatus.UPLOAD_PROCESSING,
                DocStatus.UPLOAD_DONE,
                DocStatus.PAUSED,
            ),
        )
        return cursor.fetchone()

    def _count_stage_errors(self, cursor, stage: str) -> int:
        cursor.execute(
            """
            SELECT COUNT(*) as c FROM document_status
            WHERE status = %s AND (processing_stage IS NULL OR processing_stage = %s)
            """,
            (DocStatus.ERROR, stage),
        )
        return cursor.fetchone()["c"] or 0

    def _fetch_queue_counts(self, cursor, task_type: str):
        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'completed') as completed
            FROM processing_queue
            WHERE task_type = %s
            """,
            (task_type,),
        )
        row = cursor.fetchone()
        return {
            "pending": row["pending"] or 0,
            "processing": row["processing"] or 0,
            "completed": row["completed"] or 0,
        }

    def _count_docs_in_statuses(self, cursor, statuses: List[str]) -> int:
        placeholders = ",".join(["%s"] * len(statuses))
        cursor.execute(
            f"SELECT COUNT(*) as n FROM document_status WHERE status IN ({placeholders})",
            tuple(statuses),
        )
        return cursor.fetchone()["n"] or 0

    def _count_ready_for_chunking(self, cursor) -> int:
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM document_status
            WHERE status = %s
            AND ocr_text IS NOT NULL
            AND LENGTH(ocr_text) > 0
            AND NOT EXISTS (
                SELECT 1 FROM processing_queue pq
                WHERE pq.document_id = document_status.document_id
                AND pq.task_type = 'chunking'
                AND pq.status IN (%s, %s)
            )
            """,
            (DocStatus.OCR_DONE, QueueStatus.PENDING, QueueStatus.PROCESSING),
        )
        return cursor.fetchone()["count"] or 0

    def _count_ready_for_indexing(self, cursor) -> int:
        cursor.execute(
            """
            SELECT COUNT(*) as count
            FROM document_status
            WHERE status = %s
            AND NOT EXISTS (
                SELECT 1 FROM processing_queue pq
                WHERE pq.document_id = document_status.document_id
                AND pq.task_type = 'indexing'
                AND pq.status IN (%s, %s)
            )
            """,
            (DocStatus.CHUNKING_DONE, QueueStatus.PENDING, QueueStatus.PROCESSING),
        )
        return cursor.fetchone()["count"] or 0

    def _queue_has_pending(self, cursor, task_type: str) -> bool:
        cursor.execute(
            """
            SELECT COUNT(*) FILTER (WHERE status IN ('pending','processing')) as n
            FROM processing_queue
            WHERE task_type = %s
            """,
            (task_type,),
        )
        return (cursor.fetchone()["n"] or 0) > 0

    def _fetch_insights_stage(self, cursor) -> dict:
        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE nii.status IN ('pending', 'queued')) as pending,
                COUNT(*) FILTER (WHERE nii.status = 'generating') as processing,
                COUNT(*) FILTER (WHERE nii.status = 'done') as completed,
                COUNT(*) FILTER (WHERE nii.status = 'error') as errors
            FROM news_item_insights nii
            INNER JOIN news_items ni ON ni.news_item_id = nii.news_item_id
            """
        )
        data = cursor.fetchone()
        cursor.execute(
            """
            SELECT
                COUNT(DISTINCT nii.document_id) FILTER (
                    WHERE NOT EXISTS (
                        SELECT 1 FROM news_item_insights n2
                        WHERE n2.document_id = nii.document_id
                        AND n2.status NOT IN ('done', 'error')
                    )
                ) as docs_all_done,
                COUNT(DISTINCT nii.document_id) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM news_item_insights n2
                        WHERE n2.document_id = nii.document_id
                        AND n2.status IN ('pending', 'queued', 'generating')
                    )
                ) as docs_with_pending
            FROM news_item_insights nii
            INNER JOIN news_items ni ON ni.news_item_id = nii.news_item_id
            """
        )
        docs = cursor.fetchone()
        return {
            "name": "Insights",
            "granularity": "news_item",
            "total_documents": (data["pending"] or 0) + (data["processing"] or 0) + (data["completed"] or 0) + (data["errors"] or 0),
            "pending_tasks": data["pending"] or 0,
            "processing_tasks": data["processing"] or 0,
            "completed_tasks": data["completed"] or 0,
            "error_tasks": data["errors"] or 0,
            "ready_for_next": 0,
            "docs_with_all_insights_done": docs["docs_all_done"] or 0,
            "docs_with_pending_insights": docs["docs_with_pending"] or 0,
            "blockers": [],
        }

    def _fetch_indexing_insights_stage(self, cursor) -> dict:
        cursor.execute(
            """
            SELECT
                COUNT(*) FILTER (WHERE nii.status = 'done' AND nii.indexed_in_qdrant_at IS NULL) as pending,
                COUNT(*) FILTER (WHERE nii.status = 'indexing') as processing,
                COUNT(*) FILTER (WHERE nii.indexed_in_qdrant_at IS NOT NULL) as completed
            FROM news_item_insights nii
            INNER JOIN news_items ni ON ni.news_item_id = nii.news_item_id
            WHERE nii.content IS NOT NULL AND nii.status IN ('done', 'indexing')
            """
        )
        data = cursor.fetchone()
        pending = data["pending"] or 0
        processing = data["processing"] or 0
        completed = data["completed"] or 0
        return {
            "name": "Indexing Insights",
            "granularity": "news_item",
            "total_documents": pending + processing + completed,
            "pending_tasks": pending,
            "processing_tasks": processing,
            "completed_tasks": completed,
            "error_tasks": 0,
            "ready_for_next": 0,
            "blockers": [],
        }

    def _compute_progress(self, task_type: str, minutes_running: float) -> float:
        limit = 25 if task_type == TaskType.OCR else 10
        return min(100, round((minutes_running / (limit or 1)) * 100, 1))

    def _infer_error_cause(self, error_message: str) -> str:
        if "No OCR text found for chunking" in error_message:
            return "Documentos procesados antes del fix de guardado de OCR text"
        if "Shutdown ordenado" in error_message:
            return "Shutdown ordenado ejecutado - esperado"
        if "Only PDF files are supported" in error_message:
            return "Archivo no es PDF válido - reintentar no ayudará"
        if "OCR returned empty text" in error_message or "OCRmyPDF failed" in error_message:
            return "OCR falló, timeout o error de servicio"
        if "Server disconnected" in error_message or "Connection" in error_message:
            return "Conexión interrumpida"
        if "chunk_count" in error_message:
            return "Bug corregido: acceso a columna incorrecta"
        if "timeout" in error_message.lower():
            return "Timeout durante procesamiento"
        return "Desconocido"

    def _can_auto_fix(self, error_message: str) -> bool:
        if "Shutdown ordenado" in error_message:
            return False
        if "Only PDF files are supported" in error_message:
            return False
        return True

    def _infer_insight_error_cause(self, error_message: str) -> str:
        if "429" in error_message:
            return "Rate limit LLM"
        if "timeout" in error_message.lower():
            return "Timeout durante generación de insight"
        if "Server disconnected" in error_message or "Connection" in error_message:
            return "Conexión interrumpida"
        if "No chunks" in error_message:
            return "Sin chunks para generar insight"
        return "Error en generación LLM"

    def _can_auto_fix_insight(self, error_message: str) -> bool:
        if "No chunks" in error_message:
            return False
        return True

    def _inject_chunk_news_counts(self, stages: List[dict], chunks_total: int, news_count: int) -> List[dict]:
        for stage in stages:
            if stage.get("granularity") == "document":
                stage["total_chunks"] = chunks_total
                stage["news_items_count"] = news_count
        return stages

    def _now_iso(self) -> str:
        from datetime import datetime

        return datetime.utcnow().isoformat()
