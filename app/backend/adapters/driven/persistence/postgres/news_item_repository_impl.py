"""
PostgreSQL NewsItem Repository Implementation.

Maps between database rows and Domain entities.
"""

from typing import Optional, List, Dict, Sequence, Tuple
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
                WHERE status IN ('insights_pending', 'insights_queued')
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
                    status = 'insights_done', updated_at = %s
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

    async def count_insights_by_status(self) -> dict:
        """Return counts of news_item_insights grouped by status."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT status, COUNT(*) AS count FROM news_item_insights GROUP BY status"
            )
            rows = cursor.fetchall()
            return {
                row["status"]: int(row["count"])
                for row in (self.map_row_to_dict(cursor, row) for row in rows)
            }
        finally:
            self.release_connection(conn)

    def count_all_sync(self) -> int:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS count FROM news_items")
            row = cursor.fetchone()
            return int(row[0] if isinstance(row, tuple) else row.get("count", 0))
        finally:
            self.get_connection_pool().putconn(conn)

    def count_insights_linkage_sync(self, document_ids: Sequence[str]) -> Tuple[int, int]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) AS count FROM news_item_insights")
            total_row = cursor.fetchone()
            total = int(total_row[0] if isinstance(total_row, tuple) else total_row.get("count", 0))
            if not document_ids:
                return total, 0
            cursor.execute(
                """
                SELECT COUNT(*) AS count
                FROM news_item_insights
                WHERE document_id = ANY(%s)
                """,
                (list(document_ids),),
            )
            linked_row = cursor.fetchone()
            linked = int(linked_row[0] if isinstance(linked_row, tuple) else linked_row.get("count", 0))
            return total, linked
        finally:
            self.get_connection_pool().putconn(conn)

    def get_counts_by_document_ids_sync(self, document_ids: Sequence[str]) -> dict:
        if not document_ids:
            return {}
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT document_id, COUNT(*) AS cnt
                FROM news_items
                WHERE document_id = ANY(%s)
                GROUP BY document_id
                """,
                (list(document_ids),),
            )
            rows = cursor.fetchall()
            return {
                row["document_id"] if isinstance(row, dict) else row[0]:
                int((row["cnt"] if isinstance(row, dict) else row[1]) or 0)
                for row in rows
            }
        finally:
            self.get_connection_pool().putconn(conn)

    def get_progress_by_document_ids_sync(self, document_ids: Sequence[str]) -> dict:
        if not document_ids:
            return {}
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT
                    document_id,
                    COUNT(*) FILTER (WHERE status = 'insights_pending') AS pending,
                    COUNT(*) FILTER (WHERE status = 'insights_queued') AS queued,
                    COUNT(*) FILTER (WHERE status = 'insights_generating') AS generating,
                    COUNT(*) FILTER (WHERE status = 'insights_indexing') AS indexing,
                    COUNT(*) FILTER (WHERE status = 'insights_done') AS done,
                    COUNT(*) FILTER (WHERE status = 'insights_error') AS error,
                    COUNT(*) AS total
                FROM news_item_insights
                WHERE document_id = ANY(%s)
                GROUP BY document_id
                """,
                (list(document_ids),),
            )
            rows = cursor.fetchall()
            result = {}
            for row in (self.map_row_to_dict(cursor, r) if isinstance(r, tuple) else r for r in rows):
                result[row["document_id"]] = {
                    "pending": int(row.get("pending") or 0),
                    "queued": int(row.get("queued") or 0),
                    "generating": int(row.get("generating") or 0),
                    "indexing": int(row.get("indexing") or 0),
                    "done": int(row.get("done") or 0),
                    "error": int(row.get("error") or 0),
                    "total": int(row.get("total") or 0),
                }
            return result
        finally:
            self.get_connection_pool().putconn(conn)

    def list_by_document_id_sync(self, document_id: str) -> List[dict]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT news_item_id, document_id, filename, item_index, title, status, text_hash, created_at, updated_at
                FROM news_items
                WHERE document_id = %s
                ORDER BY item_index ASC
                """,
                (document_id,),
            )
            rows = cursor.fetchall()
            return [self.map_row_to_dict(cursor, r) if isinstance(r, tuple) else dict(r) for r in rows]
        finally:
            self.get_connection_pool().putconn(conn)

    def upsert_items_sync(self, document_id: str, filename: str, items: Sequence[dict]) -> int:
        if not items:
            return 0
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            rows = 0
            now = datetime.utcnow().isoformat()
            for it in items:
                cursor.execute(
                    """
                    INSERT INTO news_items (news_item_id, document_id, filename, item_index, title, status, text_hash, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT(news_item_id) DO UPDATE SET
                        title = excluded.title,
                        status = excluded.status,
                        text_hash = excluded.text_hash,
                        updated_at = excluded.updated_at
                    """,
                    (
                        it["news_item_id"],
                        document_id,
                        filename,
                        int(it.get("item_index", 0)),
                        it.get("title") or None,
                        it.get("status") or "pending",
                        it.get("text_hash") or None,
                        now,
                        now,
                    ),
                )
                rows += 1
            conn.commit()
            return rows
        finally:
            self.get_connection_pool().putconn(conn)

    def list_insights_by_document_id_sync(self, document_id: str) -> List[dict]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT news_item_id, document_id, filename, item_index, title, status, content, error_message,
                       text_hash, llm_source, indexed_in_qdrant_at, created_at, updated_at
                FROM news_item_insights
                WHERE document_id = %s
                ORDER BY item_index ASC
                """,
                (document_id,),
            )
            rows = cursor.fetchall()
            return [self.map_row_to_dict(cursor, r) if isinstance(r, tuple) else dict(r) for r in rows]
        finally:
            self.get_connection_pool().putconn(conn)

    def get_insight_by_id_sync(self, news_item_id: str) -> Optional[dict]:
        """Get single news_item_insight by news_item_id."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT news_item_id, document_id, filename, item_index, title, status, content, error_message,
                       text_hash, llm_source, indexed_in_qdrant_at, retry_count, created_at, updated_at
                FROM news_item_insights
                WHERE news_item_id = %s
                """,
                (news_item_id,),
            )
            row = cursor.fetchone()
            return self.map_row_to_dict(cursor, row) if row else None
        finally:
            self.get_connection_pool().putconn(conn)

    def list_insights_by_news_item_id_sync(self, news_item_id: str) -> List[dict]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT news_item_id, document_id, filename, item_index, title, status, content, error_message,
                       text_hash, llm_source, indexed_in_qdrant_at, created_at, updated_at
                FROM news_item_insights
                WHERE news_item_id = %s
                ORDER BY created_at DESC
                """,
                (news_item_id,),
            )
            rows = cursor.fetchall()
            return [self.map_row_to_dict(cursor, r) if isinstance(r, tuple) else dict(r) for r in rows]
        finally:
            self.get_connection_pool().putconn(conn)

    def get_document_insight_summary_sync(self, document_id: str) -> Optional[dict]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT news_item_id, content
                FROM news_item_insights
                WHERE document_id = %s AND status = 'insights_done' AND content IS NOT NULL
                ORDER BY item_index ASC
                """,
                (document_id,),
            )
            rows = cursor.fetchall()
            if not rows:
                return None
            contents = []
            for row in (self.map_row_to_dict(cursor, r) if isinstance(r, tuple) else r for r in rows):
                c = (row.get("content") or "").strip()
                if c:
                    contents.append(c)
            if not contents:
                return None
            return {
                "document_id": document_id,
                "status": "insights_done",
                "content": "\n\n".join(contents),
            }
        finally:
            self.get_connection_pool().putconn(conn)

    def list_active_insight_tasks_sync(self) -> List[dict]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT news_item_id, document_id, filename, title
                FROM news_item_insights
                WHERE status IN ('insights_generating', 'insights_indexing')
                ORDER BY news_item_id
                """
            )
            rows = cursor.fetchall()
            return [self.map_row_to_dict(cursor, r) if isinstance(r, tuple) else dict(r) for r in rows]
        finally:
            self.get_connection_pool().putconn(conn)

    def count_pending_or_queued_insights_sync(self) -> int:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM news_item_insights
                WHERE status IN ('insights_pending', 'insights_queued')
                """
            )
            row = cursor.fetchone()
            value = row["cnt"] if isinstance(row, dict) else row[0]
            return int(value or 0)
        finally:
            self.get_connection_pool().putconn(conn)

    def count_ready_for_indexing_insights_sync(self) -> int:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM news_item_insights
                WHERE status = 'insights_done'
                  AND indexed_in_qdrant_at IS NULL
                  AND content IS NOT NULL
                """
            )
            row = cursor.fetchone()
            value = row["cnt"] if isinstance(row, dict) else row[0]
            return int(value or 0)
        finally:
            self.get_connection_pool().putconn(conn)

    def list_insights_pending_indexing_sync(self, document_id: str, limit: Optional[int] = None) -> List[dict]:
        """List insights with status=DONE and indexed_in_qdrant_at IS NULL for a document."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            query = """
                SELECT news_item_id, document_id, filename, title, content, status
                FROM news_item_insights
                WHERE document_id = %s
                  AND status = 'insights_done'
                  AND indexed_in_qdrant_at IS NULL
                  AND content IS NOT NULL
                ORDER BY created_at
            """
            params = [document_id]
            if limit:
                query += " LIMIT %s"
                params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [
                {
                    "news_item_id": row["news_item_id"] if isinstance(row, dict) else row[0],
                    "document_id": row["document_id"] if isinstance(row, dict) else row[1],
                    "filename": row["filename"] if isinstance(row, dict) else row[2],
                    "title": row["title"] if isinstance(row, dict) else row[3],
                    "content": row["content"] if isinstance(row, dict) else row[4],
                    "status": row["status"] if isinstance(row, dict) else row[5],
                }
                for row in rows
            ]
        finally:
            self.get_connection_pool().putconn(conn)

    def list_insight_errors_sync(self, news_item_ids: Optional[Sequence[str]] = None) -> List[dict]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            if news_item_ids:
                cursor.execute(
                    """
                    SELECT news_item_id, document_id, filename, title, error_message
                    FROM news_item_insights
                    WHERE status = 'insights_error'
                      AND news_item_id = ANY(%s)
                    ORDER BY news_item_id
                    """,
                    (list(news_item_ids),),
                )
            else:
                cursor.execute(
                    """
                    SELECT news_item_id, document_id, filename, title, error_message
                    FROM news_item_insights
                    WHERE status = 'insights_error'
                    ORDER BY news_item_id
                    """
                )
            rows = cursor.fetchall()
            return [self.map_row_to_dict(cursor, r) if isinstance(r, tuple) else dict(r) for r in rows]
        finally:
            self.get_connection_pool().putconn(conn)

    def set_insight_status_sync(
        self,
        news_item_id: str,
        status: str,
        content: Optional[str] = None,
        error_message: Optional[str] = None,
        llm_source: Optional[str] = None,
    ) -> bool:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            updates = ["status = %s", "updated_at = NOW()"]
            args: List[object] = [status]
            if content is not None:
                updates.append("content = %s")
                args.append(content)
            if error_message is not None:
                updates.append("error_message = %s")
                args.append(error_message)
            if llm_source is not None:
                updates.append("llm_source = %s")
                args.append(llm_source)
            args.append(news_item_id)
            cursor.execute(
                f"UPDATE news_item_insights SET {', '.join(updates)} WHERE news_item_id = %s",
                tuple(args),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.get_connection_pool().putconn(conn)

    def set_insight_status_with_retry_sync(
        self,
        news_item_id: str,
        status: str,
        error_message: Optional[str] = None,
        retry_count: int = 0,
    ) -> bool:
        """Update insight status, error message, and retry_count."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            updates = ["status = %s", "retry_count = %s", "updated_at = NOW()"]
            args: List[object] = [status, retry_count]
            if error_message is not None:
                updates.append("error_message = %s")
                args.append(error_message)
            args.append(news_item_id)
            cursor.execute(
                f"UPDATE news_item_insights SET {', '.join(updates)} WHERE news_item_id = %s",
                tuple(args),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.get_connection_pool().putconn(conn)

    def delete_by_document_id_sync(self, document_id: str) -> int:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM news_items WHERE document_id = %s", (document_id,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            self.get_connection_pool().putconn(conn)

    def delete_insights_by_document_id_sync(self, document_id: str) -> int:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM news_item_insights WHERE document_id = %s", (document_id,))
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            self.get_connection_pool().putconn(conn)

    def enqueue_insight_sync(
        self,
        news_item_id: str,
        document_id: str,
        filename: str,
        item_index: int,
        title: Optional[str] = None,
        text_hash: Optional[str] = None,
    ) -> bool:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO news_item_insights
                    (news_item_id, document_id, filename, item_index, title, status, text_hash, created_at)
                VALUES
                    (%s, %s, %s, %s, %s, 'insights_pending', %s, NOW())
                ON CONFLICT (news_item_id) DO NOTHING
                """,
                (
                    news_item_id,
                    document_id,
                    filename,
                    int(item_index),
                    title or None,
                    text_hash or None,
                ),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.get_connection_pool().putconn(conn)

    def set_insight_indexed_in_qdrant_sync(self, news_item_id: str) -> bool:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE news_item_insights
                SET indexed_in_qdrant_at = NOW(), status = 'insights_done', updated_at = NOW()
                WHERE news_item_id = %s
                """,
                (news_item_id,),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            self.get_connection_pool().putconn(conn)

    def set_insights_pending_for_document_sync(self, document_id: str, from_status: str) -> int:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE news_item_insights
                SET status = 'insights_pending', error_message = NULL, updated_at = NOW()
                WHERE document_id = %s
                  AND status = %s
                """,
                (document_id, from_status),
            )
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            self.get_connection_pool().putconn(conn)

    def set_insight_status_if_current_sync(
        self,
        news_item_id: str,
        from_status: str,
        to_status: str,
        clear_error: bool = False,
    ) -> int:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            if clear_error:
                cursor.execute(
                    """
                    UPDATE news_item_insights
                    SET status = %s, error_message = NULL, updated_at = NOW()
                    WHERE news_item_id = %s AND status = %s
                    """,
                    (to_status, news_item_id, from_status),
                )
            else:
                cursor.execute(
                    """
                    UPDATE news_item_insights
                    SET status = %s, updated_at = NOW()
                    WHERE news_item_id = %s AND status = %s
                    """,
                    (to_status, news_item_id, from_status),
                )
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            self.get_connection_pool().putconn(conn)

    def reset_orphaned_indexing_insights_sync(self) -> int:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE news_item_insights nii
                SET status = 'insights_done', updated_at = NOW()
                WHERE nii.status = 'insights_indexing'
                  AND NOT EXISTS (
                    SELECT 1 FROM worker_tasks wt
                    WHERE wt.document_id = 'insight_' || nii.news_item_id
                      AND wt.task_type = 'indexing_insights'
                      AND wt.status IN ('assigned', 'started')
                  )
                """
            )
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            self.get_connection_pool().putconn(conn)

    def get_next_pending_insight_for_document_sync(self, document_id: str) -> Optional[dict]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT news_item_id, title
                FROM news_item_insights
                WHERE document_id = %s
                  AND status IN ('insights_pending', 'insights_queued')
                ORDER BY item_index ASC, news_item_id ASC
                LIMIT 1
                """,
                (document_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self.map_row_to_dict(cursor, row)
        finally:
            self.get_connection_pool().putconn(conn)

    def get_next_pending_insight_sync(self) -> Optional[dict]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT news_item_id, document_id, filename, title
                FROM news_item_insights
                WHERE status IN ('insights_pending', 'insights_queued')
                ORDER BY updated_at ASC NULLS LAST, created_at ASC, news_item_id ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self.map_row_to_dict(cursor, row)
        finally:
            self.get_connection_pool().putconn(conn)

    def reset_generating_insights_sync(self) -> int:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE news_item_insights
                SET status = 'insights_pending', error_message = NULL, updated_at = NOW()
                WHERE status = 'insights_generating'
                """
            )
            count = cursor.rowcount
            conn.commit()
            return count
        finally:
            self.get_connection_pool().putconn(conn)

    def get_text_hash_for_news_item_sync(self, news_item_id: str) -> Optional[str]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT text_hash FROM news_item_insights WHERE news_item_id = %s",
                (news_item_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            row_dict = self.map_row_to_dict(cursor, row)
            return row_dict.get("text_hash")
        finally:
            self.get_connection_pool().putconn(conn)

    def get_done_insight_by_text_hash_sync(self, text_hash: str) -> Optional[dict]:
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT news_item_id, document_id, filename, title, status, content, llm_source, text_hash
                FROM news_item_insights
                WHERE text_hash = %s
                  AND status = 'insights_done'
                  AND content IS NOT NULL
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (text_hash,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return self.map_row_to_dict(cursor, row)
        finally:
            self.get_connection_pool().putconn(conn)
    
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
