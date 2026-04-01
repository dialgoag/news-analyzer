"""
PostgreSQL Document Repository Implementation.

Maps between database rows and Domain entities.
"""

from typing import Optional, List
from datetime import datetime

from core.domain.entities.document import Document
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
    
    async def get_by_id(self, document_id: DocumentId) -> Optional[Document]:
        """Get document by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT document_id, filename, source, status, ingested_at, 
                       news_date, file_hash, ocr_text, doc_type, error_message,
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
            cursor.execute(
                """
                SELECT document_id, filename, source, status, ingested_at, 
                       news_date, file_hash, ocr_text, doc_type, error_message,
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
        finally:
            self.release_connection(conn)
    
    async def save(self, document: Document) -> None:
        """Save document (insert or update)."""
        conn = self.get_connection()
        try:
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
                        doc_type = %s, error_message = %s, updated_at = %s
                    WHERE document_id = %s
                    """,
                    (
                        document.filename,
                        document.source,
                        status_str,
                        document.news_date,
                        document.content_hash.value if document.content_hash else None,
                        document.ocr_text,
                        document.doc_type,
                        document.error_message,
                        datetime.now(),
                        document.id.value
                    )
                )
            else:
                # Insert new
                cursor.execute(
                    """
                    INSERT INTO document_status
                    (document_id, filename, source, status, ingested_at, news_date, 
                     file_hash, ocr_text, doc_type, error_message, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        document.id.value,
                        document.filename,
                        document.source,
                        status_str,
                        document.ingested_at,
                        document.news_date,
                        document.content_hash.value if document.content_hash else None,
                        document.ocr_text,
                        document.doc_type,
                        document.error_message,
                        document.created_at,
                        document.updated_at
                    )
                )
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
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
        error_message: Optional[str] = None
    ) -> None:
        """Update document status."""
        status_str = self.map_status_from_domain(status)
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE document_status
                SET status = %s, error_message = %s, updated_at = %s
                WHERE document_id = %s
                """,
                (status_str, error_message, datetime.now(), document_id.value)
            )
            
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
        return Document(
            id=DocumentId(row_dict["document_id"]),
            filename=row_dict["filename"],
            source=row_dict["source"],
            status=status,
            ingested_at=row_dict["ingested_at"],
            news_date=row_dict.get("news_date"),
            content_hash=TextHash(row_dict["file_hash"]) if row_dict.get("file_hash") else None,
            ocr_text=row_dict.get("ocr_text"),
            doc_type=row_dict.get("doc_type"),
            error_message=row_dict.get("error_message"),
            created_at=row_dict.get("created_at") or row_dict["ingested_at"],
            updated_at=row_dict.get("updated_at") or row_dict["ingested_at"]
        )
