"""
PostgreSQL NewsItem Repository Implementation.

Maps between database rows and Domain entities.
"""

from typing import Optional, List
from datetime import datetime

from core.domain.entities.news_item import NewsItem
from core.domain.value_objects.document_id import DocumentId
from core.domain.value_objects.text_hash import TextHash
from core.domain.value_objects.pipeline_status import PipelineStatus
from core.ports.repositories.news_item_repository import NewsItemRepository
from .base import BasePostgresRepository


class PostgresNewsItemRepository(BasePostgresRepository, NewsItemRepository):
    """
    PostgreSQL implementation of NewsItemRepository.
    
    Maps between:
    - Database: news_item_insights table (status as string)
    - Domain: NewsItem entity (status as PipelineStatus)
    """
    
    async def get_by_id(self, news_item_id: str) -> Optional[NewsItem]:
        """Get news item by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, document_id, title, content, summary, analysis, 
                       status, text_hash, llm_source, error_message,
                       created_at, updated_at
                FROM news_item_insights
                WHERE id = %s
                """,
                (news_item_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._map_row_to_entity(cursor, row)
        finally:
            self.release_connection(conn)
    
    async def get_by_document_id(
        self, 
        document_id: DocumentId,
        limit: Optional[int] = None
    ) -> List[NewsItem]:
        """Get all news items for a document."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT id, document_id, title, content, summary, analysis, 
                       status, text_hash, llm_source, error_message,
                       created_at, updated_at
                FROM news_item_insights
                WHERE document_id = %s
                ORDER BY created_at ASC
            """
            
            params = [document_id.value]
            
            if limit:
                query += " LIMIT %s"
                params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            return [self._map_row_to_entity(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)
    
    async def save(self, news_item: NewsItem) -> None:
        """Save news item (insert or update)."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Check if exists
            cursor.execute(
                "SELECT id FROM news_item_insights WHERE id = %s",
                (news_item.id,)
            )
            exists = cursor.fetchone()
            
            status_str = self.map_status_from_domain(news_item.status)
            
            if exists:
                # Update existing
                cursor.execute(
                    """
                    UPDATE news_item_insights
                    SET document_id = %s, title = %s, content = %s,
                        summary = %s, analysis = %s, status = %s,
                        text_hash = %s, llm_source = %s, error_message = %s,
                        updated_at = %s
                    WHERE id = %s
                    """,
                    (
                        news_item.document_id.value,
                        news_item.title,
                        news_item.content,
                        news_item.summary,
                        news_item.analysis,
                        status_str,
                        news_item.text_hash.value if news_item.text_hash else None,
                        news_item.llm_source,
                        news_item.error_message,
                        datetime.now(),
                        news_item.id
                    )
                )
            else:
                # Insert new
                cursor.execute(
                    """
                    INSERT INTO news_item_insights
                    (id, document_id, title, content, summary, analysis,
                     status, text_hash, llm_source, error_message, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        news_item.id,
                        news_item.document_id.value,
                        news_item.title,
                        news_item.content,
                        news_item.summary,
                        news_item.analysis,
                        status_str,
                        news_item.text_hash.value if news_item.text_hash else None,
                        news_item.llm_source,
                        news_item.error_message,
                        news_item.created_at,
                        news_item.updated_at
                    )
                )
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    async def list_by_status(
        self, 
        status: PipelineStatus,
        limit: Optional[int] = None
    ) -> List[NewsItem]:
        """List news items by insight status."""
        status_str = self.map_status_from_domain(status)
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT id, document_id, title, content, summary, analysis, 
                       status, text_hash, llm_source, error_message,
                       created_at, updated_at
                FROM news_item_insights
                WHERE status = %s
                ORDER BY created_at ASC
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
    
    async def list_pending_insights(
        self, 
        limit: Optional[int] = None
    ) -> List[NewsItem]:
        """List news items pending insight generation."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT id, document_id, title, content, summary, analysis, 
                       status, text_hash, llm_source, error_message,
                       created_at, updated_at
                FROM news_item_insights
                WHERE status IN ('insight_pending', 'insight_queued')
                ORDER BY created_at ASC
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
    
    async def update_status(
        self, 
        news_item_id: str, 
        status: PipelineStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Update news item insight status."""
        status_str = self.map_status_from_domain(status)
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE news_item_insights
                SET status = %s, error_message = %s, updated_at = %s
                WHERE id = %s
                """,
                (status_str, error_message, datetime.now(), news_item_id)
            )
            
            if cursor.rowcount == 0:
                raise ValueError(f"News item not found: {news_item_id}")
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    async def update_insights(
        self,
        news_item_id: str,
        summary: str,
        analysis: str,
        llm_source: str
    ) -> None:
        """Update news item with generated insights."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE news_item_insights
                SET summary = %s, analysis = %s, llm_source = %s, 
                    status = 'insight_done', updated_at = %s
                WHERE id = %s
                """,
                (summary, analysis, llm_source, datetime.now(), news_item_id)
            )
            
            if cursor.rowcount == 0:
                raise ValueError(f"News item not found: {news_item_id}")
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    async def count_by_document(self, document_id: DocumentId) -> int:
        """Count news items for a document."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT COUNT(*) FROM news_item_insights WHERE document_id = %s",
                (document_id.value,)
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            self.release_connection(conn)
    
    async def exists(self, news_item_id: str) -> bool:
        """Check if news item exists."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT 1 FROM news_item_insights WHERE id = %s",
                (news_item_id,)
            )
            return cursor.fetchone() is not None
        finally:
            self.release_connection(conn)
    
    # ========================================
    # PRIVATE: Mapping helpers
    # ========================================
    
    def _map_row_to_entity(self, cursor, row) -> NewsItem:
        """
        Map database row to NewsItem entity.
        
        Args:
            cursor: Database cursor (has column names)
            row: Database row tuple
        
        Returns:
            NewsItem entity
        """
        row_dict = self.map_row_to_dict(cursor, row)
        
        # Map status string to PipelineStatus
        status = self.map_status_to_domain(
            row_dict["status"], 
            status_type="insight"
        )
        
        # Create NewsItem entity
        return NewsItem(
            id=row_dict["id"],
            document_id=DocumentId(row_dict["document_id"]),
            title=row_dict["title"],
            content=row_dict["content"],
            summary=row_dict.get("summary"),
            analysis=row_dict.get("analysis"),
            status=status,
            text_hash=TextHash(row_dict["text_hash"]) if row_dict.get("text_hash") else None,
            llm_source=row_dict.get("llm_source"),
            error_message=row_dict.get("error_message"),
            created_at=row_dict.get("created_at") or datetime.now(),
            updated_at=row_dict.get("updated_at") or datetime.now()
        )
