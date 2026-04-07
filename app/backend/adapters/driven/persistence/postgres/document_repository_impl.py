"""
PostgreSQL Document Repository Implementation.

Maps between database rows and Domain entities.
"""

from typing import Optional, List, Tuple
from datetime import datetime

from core.domain.entities.document import Document, DocumentType
from core.domain.value_objects.document_id import DocumentId
from core.domain.value_objects.text_hash import TextHash
from core.domain.value_objects.pipeline_status import PipelineStatus, StageEnum, StateEnum
from core.ports.repositories.document_repository import DocumentRepository
from .base import BasePostgresRepository


class PostgresDocumentRepository(BasePostgresRepository, DocumentRepository):
    """
    PostgreSQL implementation of DocumentRepository.
    
    Maps between:
    - Database: document_status table (status as string)
    - Domain: Document entity (status as PipelineStatus)
    """

    REPORT_ELIGIBLE_STATUSES: Tuple[str, ...] = (
        "indexing_done",
        "insights_pending",
        "insights_processing",
        "insights_done",
        "completed",
    )
    
    async def get_by_id(self, document_id: DocumentId) -> Optional[Document]:
        """Get document by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT document_id, filename, source, status, ingested_at, 
                       news_date, file_hash, ocr_text, doc_type, error_message,
                       processing_stage, num_chunks, indexed_at, reprocess_requested,
                       created_at, updated_at
                FROM document_status
                WHERE document_id = %s
                """,
                (document_id.value,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._map_row_to_entity(cursor, row)
        finally:
            self.release_connection(conn)
    
    async def get_by_sha256(self, sha256: str) -> Optional[Document]:
        """Get document by SHA256 hash."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            return self._fetch_document_by_hash(cursor, sha256)
        finally:
            self.release_connection(conn)
    
    def get_by_sha256_sync(self, sha256: str) -> Optional[Document]:
        """SYNC version - Get document by SHA256 hash."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            return self._fetch_document_by_hash(cursor, sha256)
        finally:
            self.release_connection(conn)
    
    async def save(self, document: Document) -> None:
        """Save document (insert or update)."""
        conn = self.get_connection()
        try:
            self._save_document(conn, document)
        finally:
            self.release_connection(conn)
    
    def save_sync(self, document: Document) -> None:
        """SYNC version - Save document."""
        conn = self.get_connection()
        try:
            self._save_document(conn, document)
        finally:
            self.release_connection(conn)
    
    def _save_document(self, conn, document: Document) -> None:
        cursor = conn.cursor()
        
        # Check if exists
        cursor.execute(
            "SELECT document_id FROM document_status WHERE document_id = %s",
            (document.id.value,)
        )
        exists = cursor.fetchone()
        
        status_str = self.map_status_from_domain(document.status)
        
        if exists:
            # Update existing
            cursor.execute(
                """
                UPDATE document_status
                SET filename = %s, source = %s, status = %s, 
                    news_date = %s, file_hash = %s, ocr_text = %s,
                    doc_type = %s, error_message = %s, processing_stage = %s,
                    num_chunks = %s, indexed_at = %s, reprocess_requested = %s
                WHERE document_id = %s
                """,
                (
                    document.filename,
                    document.source,
                    status_str,
                    document.news_date,
                    document.content_hash.value if document.content_hash else document.sha256,
                    document.ocr_text,
                    document.document_type.value,
                    document.error_message,
                    document.processing_stage,
                    document.num_chunks,
                    document.indexed_at,
                    1 if document.reprocess_requested else 0,
                    document.id.value
                )
            )
        else:
            cursor.execute(
                """
                INSERT INTO document_status
                (document_id, filename, source, status, ingested_at, news_date, 
                 file_hash, ocr_text, doc_type, error_message, processing_stage, 
                 num_chunks, indexed_at, reprocess_requested, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    document.id.value,
                    document.filename,
                    document.source,
                    status_str,
                    document.ingested_at,
                    document.news_date,
                    document.content_hash.value if document.content_hash else document.sha256,
                    document.ocr_text,
                    document.document_type.value,
                    document.error_message,
                    document.processing_stage,
                    document.num_chunks,
                    document.indexed_at,
                    1 if document.reprocess_requested else 0,
                    document.created_at,
                    document.updated_at
                )
            )
        
        conn.commit()
    
    def _fetch_document_by_hash(self, cursor, sha256: str) -> Optional[Document]:
        cursor.execute(
            """
            SELECT document_id, filename, source, status, ingested_at, 
                   news_date, file_hash, ocr_text, doc_type, error_message,
                   processing_stage, num_chunks, indexed_at, reprocess_requested,
                   created_at, updated_at
            FROM document_status
            WHERE file_hash = %s
            """,
            (sha256,)
        )
        row = cursor.fetchone()
        if not row:
            return None
        return self._map_row_to_entity(cursor, row)
    
    async def list_by_status(
        self, 
        status: PipelineStatus,
        limit: Optional[int] = None
    ) -> List[Document]:
        """List documents by status."""
        status_str = self.map_status_from_domain(status)
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT document_id, filename, source, status, ingested_at, 
                       news_date, file_hash, ocr_text, doc_type, error_message,
                       processing_stage, num_chunks, indexed_at, reprocess_requested,
                       created_at, updated_at
                FROM document_status
                WHERE status = %s
                ORDER BY ingested_at DESC
            """
            
            params = [status_str]
            
            if limit:
                query += " LIMIT %s"
                params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            return [self._map_row_to_entity(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)
    
    async def list_pending(self, limit: Optional[int] = None) -> List[Document]:
        """List documents pending processing."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Pending = any stage with pending/processing state, or paused
            query = """
                SELECT document_id, filename, source, status, ingested_at, 
                       news_date, file_hash, ocr_text, doc_type, error_message,
                       processing_stage, num_chunks, indexed_at, reprocess_requested,
                       created_at, updated_at
                FROM document_status
                WHERE status LIKE '%_pending' 
                   OR status LIKE '%_processing'
                   OR status = 'paused'
                   OR status = 'upload_pending'
                ORDER BY ingested_at ASC
            """
            
            params = []
            
            if limit:
                query += " LIMIT %s"
                params.append(limit)
            
            cursor.execute(query, tuple(params) if params else None)
            rows = cursor.fetchall()
            
            return [self._map_row_to_entity(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)
    
    async def list_all(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Document]:
        """List all documents with pagination."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT document_id, filename, source, status, ingested_at, 
                       news_date, file_hash, ocr_text, doc_type, error_message,
                       processing_stage, num_chunks, indexed_at, reprocess_requested,
                       created_at, updated_at
                FROM document_status
                ORDER BY ingested_at DESC
                LIMIT %s OFFSET %s
                """,
                (limit, skip)
            )
            rows = cursor.fetchall()
            
            return [self._map_row_to_entity(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)
    
    async def update_status(
        self, 
        document_id: DocumentId, 
        status: PipelineStatus,
        *,
        indexed_at: Optional[str] = None,
        error_message: Optional[str] = None,
        num_chunks: Optional[int] = None,
        doc_type: Optional[str] = None,
        news_date: Optional[str] = None,
        processing_stage: Optional[str] = None,
        clear_indexed_at: bool = False,
        clear_error_message: bool = False,
    ) -> None:
        """Update document status and optional metadata."""
        status_str = self.map_status_from_domain(status)
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            updates = ["status = %s"]
            params = [status_str]
            
            if clear_indexed_at:
                updates.append("indexed_at = NULL")
            elif indexed_at is not None:
                updates.append("indexed_at = %s")
                params.append(indexed_at)
            
            if clear_error_message:
                updates.append("error_message = NULL")
            elif error_message is not None:
                updates.append("error_message = %s")
                params.append(error_message)
            
            if num_chunks is not None:
                updates.append("num_chunks = %s")
                params.append(num_chunks)

            if doc_type is not None:
                updates.append("doc_type = %s")
                params.append(doc_type)
            
            if news_date is not None:
                updates.append("news_date = %s")
                params.append(news_date)
            
            if processing_stage is not None:
                updates.append("processing_stage = %s")
                params.append(processing_stage)
            
            params.append(document_id.value)
            query = f"""
                UPDATE document_status
                SET {', '.join(updates)}
                WHERE document_id = %s
            """
            cursor.execute(query, tuple(params))
            
            if cursor.rowcount == 0:
                raise ValueError(f"Document not found: {document_id.value}")
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    async def count_by_status(self, status: PipelineStatus) -> int:
        """Count documents by status."""
        status_str = self.map_status_from_domain(status)
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM document_status WHERE status = %s",
                (status_str,)
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            self.release_connection(conn)
    
    async def exists(self, document_id: DocumentId) -> bool:
        """Check if document exists."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM document_status WHERE document_id = %s",
                (document_id.value,)
            )
            return cursor.fetchone() is not None
        finally:
            self.release_connection(conn)
    
    # ========================================
    # PRIVATE: Mapping helpers
    # ========================================
    
    def _map_row_to_entity(self, cursor, row) -> Document:
        """
        Map database row to Document entity.
        
        Args:
            cursor: Database cursor (has column names)
            row: Database row tuple
        
        Returns:
            Document entity
        """
        row_dict = self.map_row_to_dict(cursor, row)
        
        # Map status string to PipelineStatus
        status = self.map_status_to_domain(
            row_dict["status"], 
            status_type="document"
        )
        
        # Create Document entity
        # NOTE: Complete mapping of ALL document_status fields
        # Stage timing (upload_created_at, ocr_updated_at, etc.) is now in separate table
        # Use StageTimingRepository to query stage-level timestamps
        return Document(
            # REQUIRED FIELDS
            id=DocumentId(row_dict["document_id"]),
            filename=row_dict["filename"],
            original_filename=row_dict["filename"],
            sha256=row_dict.get("file_hash", ""),
            file_size=0,  # Not stored in document_status yet (TODO: add if needed)
            document_type=DocumentType(row_dict.get("doc_type", "unknown")),
            status=status,
            
            # OPTIONAL FIELDS
            source=row_dict.get("source", "web"),
            news_date=row_dict.get("news_date"),
            processing_stage=row_dict.get("processing_stage"),
            total_pages=None,  # Not in document_status
            total_news_items=row_dict.get("num_chunks"),
            ocr_text=row_dict.get("ocr_text"),
            ocr_text_length=len(row_dict.get("ocr_text") or ""),
            num_chunks=row_dict.get("num_chunks", 0),
            indexed_at=row_dict.get("indexed_at"),  # LEGACY
            reprocess_requested=bool(row_dict.get("reprocess_requested", 0)),
            content_hash=TextHash(row_dict["file_hash"]) if row_dict.get("file_hash") else None,
            
            # DOCUMENT-LEVEL TIMESTAMPS
            created_at=row_dict.get("created_at") or datetime.now(),
            updated_at=row_dict.get("updated_at") or datetime.now(),
            
            # LEGACY COMPATIBILITY
            ingested_at=row_dict.get("ingested_at") or datetime.now(),
            uploaded_at=row_dict.get("created_at") or datetime.now(),
            
            # ERROR HANDLING
            error_message=row_dict.get("error_message")
        )
    
    async def list_pending_reprocess(self) -> List[Document]:
        """List documents marked for reprocessing."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM document_status
                WHERE reprocess_requested = 1
                ORDER BY ingested_at ASC
            """)
            rows = cursor.fetchall()
            return [self._map_row_to_entity(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)
    
    async def mark_for_reprocessing(
        self,
        document_id: DocumentId,
        requested: bool = True
    ) -> None:
        """Mark document for reprocessing."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE document_status
                SET reprocess_requested = %s
                WHERE document_id = %s
            """, (1 if requested else 0, str(document_id)))
            conn.commit()
        finally:
            self.release_connection(conn)
    
    async def store_ocr_text(
        self,
        document_id: DocumentId,
        ocr_text: Optional[str]
    ) -> None:
        """Store OCR text for document."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE document_status
                SET ocr_text = %s
                WHERE document_id = %s
            """, (ocr_text, str(document_id)))
            conn.commit()
        finally:
            self.release_connection(conn)
    
    # ========================================
    # SYNC methods for legacy scheduler compatibility
    # TODO: Remove when master_pipeline_scheduler becomes async
    # ========================================
    
    def list_pending_reprocess_sync(self) -> List[dict]:
        """SYNC version - List documents pending reprocessing."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM document_status
                WHERE reprocess_requested = 1
                ORDER BY ingested_at ASC
            """)
            rows = cursor.fetchall()
            return [self.map_row_to_dict(cursor, row) for row in rows]
        finally:
            self.get_connection_pool().putconn(conn)
    
    def mark_for_reprocessing_sync(
        self,
        document_id: str,
        requested: bool = True
    ) -> None:
        """SYNC version - Mark document for reprocessing."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE document_status
                SET reprocess_requested = %s
                WHERE document_id = %s
            """, (1 if requested else 0, document_id))
            conn.commit()
        finally:
            self.get_connection_pool().putconn(conn)
    
    def store_ocr_text_sync(
        self,
        document_id: str,
        ocr_text: Optional[str]
    ) -> None:
        """SYNC version - Store OCR text."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE document_status
                SET ocr_text = %s
                WHERE document_id = %s
            """, (ocr_text, document_id))
            conn.commit()
        finally:
            self.get_connection_pool().putconn(conn)
    
    def get_by_id_sync(self, document_id: str) -> Optional[dict]:
        """SYNC version - Get document by ID (returns dict for legacy compat)."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM document_status WHERE document_id = %s", (document_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self.map_row_to_dict(cursor, row)
        finally:
            self.get_connection_pool().putconn(conn)

    def update_status_sync(
        self,
        document_id: str,
        status: PipelineStatus,
        *,
        indexed_at: Optional[str] = None,
        error_message: Optional[str] = None,
        num_chunks: Optional[int] = None,
        doc_type: Optional[str] = None,
        news_date: Optional[str] = None,
        processing_stage: Optional[str] = None,
        clear_indexed_at: bool = False,
        clear_error_message: bool = False,
    ) -> None:
        """SYNC version - Update document status and metadata."""
        status_str = self.map_status_from_domain(status)
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            updates = ["status = %s"]
            params = [status_str]
            
            if clear_indexed_at:
                updates.append("indexed_at = NULL")
            elif indexed_at is not None:
                updates.append("indexed_at = %s")
                params.append(indexed_at)
            
            if clear_error_message:
                updates.append("error_message = NULL")
            elif error_message is not None:
                updates.append("error_message = %s")
                params.append(error_message)
            
            if num_chunks is not None:
                updates.append("num_chunks = %s")
                params.append(num_chunks)

            if doc_type is not None:
                updates.append("doc_type = %s")
                params.append(doc_type)
            
            if news_date is not None:
                updates.append("news_date = %s")
                params.append(news_date)
            
            if processing_stage is not None:
                updates.append("processing_stage = %s")
                params.append(processing_stage)
            
            params.append(document_id)
            query = f"""
                UPDATE document_status
                SET {', '.join(updates)}
                WHERE document_id = %s
            """
            cursor.execute(query, tuple(params))
            conn.commit()
        finally:
            self.get_connection_pool().putconn(conn)
    
    def list_all_sync(
        self,
        skip: int = 0,
        limit: Optional[int] = None,
        *,
        status: Optional[str] = None,
        source: Optional[str] = None,
    ) -> List[dict]:
        """SYNC version - List documents (returns dicts)."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            where_clauses = []
            params: list = []
            if status:
                where_clauses.append("status = %s")
                params.append(status)
            if source:
                where_clauses.append("source = %s")
                params.append(source)
            where_sql = ""
            if where_clauses:
                where_sql = "WHERE " + " AND ".join(where_clauses)
            order_clause = "ORDER BY COALESCE(created_at, ingested_at, NOW()) DESC"
            limit_clause = ""
            offset_clause = ""
            if limit is not None:
                limit_clause = "LIMIT %s"
                params.append(limit)
            if skip:
                offset_clause = "OFFSET %s"
                params.append(skip)
            query = f"""
                SELECT * FROM document_status
                {where_sql}
                {order_clause}
                {limit_clause}
                {offset_clause}
            """
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            return [self.map_row_to_dict(cursor, row) for row in rows]
        finally:
            self.get_connection_pool().putconn(conn)

    def get_files_overview_sync(self) -> dict:
        """Return aggregated counts used by dashboard summary."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            completed_placeholders = ",".join(["%s"] * len(self.REPORT_ELIGIBLE_STATUSES))
            cursor.execute(
                f"""
                SELECT
                    COUNT(*) AS total_documents,
                    COUNT(*) FILTER (WHERE status IN ({completed_placeholders})) AS completed_documents,
                    COUNT(*) FILTER (WHERE status LIKE %s) AS processing_documents,
                    COUNT(*) FILTER (WHERE status = 'error') AS error_documents,
                    MIN(ingested_at) AS date_first,
                    MAX(ingested_at) AS date_last,
                    COALESCE(SUM(num_chunks), 0) AS chunks_total
                FROM document_status
                """,
                (*self.REPORT_ELIGIBLE_STATUSES, "%_processing"),
            )
            overview = self.map_row_to_dict(cursor, cursor.fetchone())
            if not overview:
                overview = {}
            # Default values if table is empty
            overview.setdefault("total_documents", 0)
            overview.setdefault("completed_documents", 0)
            overview.setdefault("processing_documents", 0)
            overview.setdefault("error_documents", 0)
            overview.setdefault("date_first", None)
            overview.setdefault("date_last", None)
            overview.setdefault("chunks_total", 0)

            cursor.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM document_status
                GROUP BY status
                """
            )
            status_counts = {}
            for row in cursor.fetchall():
                row_dict = self.map_row_to_dict(cursor, row)
                status_counts[row_dict["status"]] = row_dict["count"]
            overview["status_counts"] = status_counts
            return overview
        finally:
            self.get_connection_pool().putconn(conn)

    def list_ids_by_news_date_sync(self, report_date: str) -> List[str]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            placeholders = ",".join(["%s"] * len(self.REPORT_ELIGIBLE_STATUSES))
            cursor.execute(
                f"""
                SELECT document_id
                FROM document_status
                WHERE news_date = %s
                  AND status IN ({placeholders})
                ORDER BY document_id
                """,
                (report_date, *self.REPORT_ELIGIBLE_STATUSES),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            self.get_connection_pool().putconn(conn)

    def list_ids_by_news_date_range_sync(self, start_date: str, end_date: str) -> List[str]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            placeholders = ",".join(["%s"] * len(self.REPORT_ELIGIBLE_STATUSES))
            cursor.execute(
                f"""
                SELECT document_id
                FROM document_status
                WHERE news_date BETWEEN %s AND %s
                  AND status IN ({placeholders})
                ORDER BY news_date, document_id
                """,
                (start_date, end_date, *self.REPORT_ELIGIBLE_STATUSES),
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            self.get_connection_pool().putconn(conn)

    def delete_sync(self, document_id: str) -> None:
        """SYNC version - Delete document by ID."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM document_status WHERE document_id = %s",
                (document_id,),
            )
            conn.commit()
        finally:
            self.get_connection_pool().putconn(conn)

    async def get_status_summary(self) -> dict:
        """Return aggregated counts of documents by status/stage."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    COUNT(*) AS total,
                    COUNT(*) FILTER (
                        WHERE status IN (
                            'indexing_done','insights_pending','insights_processing',
                            'insights_done','completed'
                        )
                    ) AS completed,
                    COUNT(*) FILTER (WHERE status LIKE '%_processing') AS processing,
                    COUNT(*) FILTER (WHERE status = 'error') AS errors
                FROM document_status
                """
            )
            totals = self.map_row_to_dict(cursor, cursor.fetchone())

            cursor.execute(
                """
                SELECT processing_stage, COUNT(*) AS count
                FROM document_status
                WHERE status = 'error'
                GROUP BY processing_stage
                """
            )
            error_breakdown = {
                (row["processing_stage"] or "unknown"): row["count"]
                for row in (self.map_row_to_dict(cursor, row) for row in cursor.fetchall())
            }

            cursor.execute("SELECT COALESCE(SUM(num_chunks), 0) AS total_chunks FROM document_status")
            chunk_row = self.map_row_to_dict(cursor, cursor.fetchone())

            return {
                "documents": totals,
                "error_breakdown": error_breakdown,
                "chunks_total": int(chunk_row["total_chunks"]) if chunk_row and chunk_row["total_chunks"] is not None else 0,
            }
        finally:
            self.release_connection(conn)
