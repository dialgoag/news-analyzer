"""
PostgreSQL implementation of Stage Timing Repository.

Persists stage timing records to document_stage_timing table.
"""

from typing import List, Optional
from datetime import datetime
import json

from core.ports.repositories.stage_timing_repository import StageTimingRepository
from core.domain.entities.stage_timing import StageTimingRecord, StageStatus
from adapters.driven.persistence.postgres.base import BasePostgresRepository


class PostgresStageTimingRepository(BasePostgresRepository, StageTimingRepository):
    """PostgreSQL implementation of StageTimingRepository."""
    
    # ========================================
    # ASYNC methods (primary interface)
    # ========================================
    
    async def record_stage_start(
        self,
        document_id: str,
        stage: str,
        news_item_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> StageTimingRecord:
        """
        Record stage start.
        
        Uses INSERT ... ON CONFLICT to handle retries:
        - If stage never started → INSERT new record
        - If stage was restarted → UPDATE created_at (restart timing)
        
        UNIQUE constraint: (document_id, COALESCE(news_item_id, ''), stage)
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            now = datetime.utcnow()
            metadata_json = json.dumps(metadata or {})
            
            cursor.execute(
                """
                INSERT INTO document_stage_timing 
                (document_id, news_item_id, stage, status, created_at, updated_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (document_id, COALESCE(news_item_id, ''), stage) 
                DO UPDATE SET 
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at,
                    error_message = NULL,
                    metadata = EXCLUDED.metadata
                RETURNING id
                """,
                (document_id, news_item_id, stage, StageStatus.PROCESSING.value, now, now, metadata_json)
            )
            
            row = cursor.fetchone()
            record_id = row[0] if row else None
            
            conn.commit()
            
            return StageTimingRecord(
                id=record_id,
                document_id=document_id,
                news_item_id=news_item_id,
                stage=stage,
                status=StageStatus.PROCESSING,
                created_at=now,
                updated_at=now,
                metadata=metadata or {}
            )
        finally:
            self.release_connection(conn)
    
    async def record_stage_end(
        self,
        document_id: str,
        stage: str,
        status: str,
        news_item_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """Record stage end (done or error)."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Validate status
            stage_status = StageStatus(status)
            
            cursor.execute(
                """
                UPDATE document_stage_timing
                SET status = %s,
                    error_message = %s
                WHERE document_id = %s 
                  AND stage = %s
                  AND (news_item_id = %s OR (news_item_id IS NULL AND %s IS NULL))
                """,
                (stage_status.value, error_message, document_id, stage, news_item_id, news_item_id)
            )
            
            if cursor.rowcount == 0:
                raise ValueError(f"Stage timing not found: {document_id}/{stage}/{news_item_id}")
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    async def get_stage_timing(
        self,
        document_id: str,
        stage: str,
        news_item_id: Optional[str] = None
    ) -> Optional[StageTimingRecord]:
        """Get timing for specific document/news_item and stage."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, document_id, news_item_id, stage, status, created_at, updated_at, 
                       error_message, metadata
                FROM document_stage_timing
                WHERE document_id = %s 
                  AND stage = %s
                  AND (news_item_id = %s OR (news_item_id IS NULL AND %s IS NULL))
                """,
                (document_id, stage, news_item_id, news_item_id)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._map_row_to_entity(cursor, row)
        finally:
            self.release_connection(conn)
    
    async def get_all_timings(
        self,
        document_id: str
    ) -> List[StageTimingRecord]:
        """Get all timing records for a document (full timeline)."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, document_id, stage, status, created_at, updated_at,
                       error_message, metadata
                FROM document_stage_timing
                WHERE document_id = %s
                ORDER BY created_at ASC
                """,
                (document_id,)
            )
            rows = cursor.fetchall()
            
            return [self._map_row_to_entity(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)
    
    async def get_stage_statistics(
        self,
        stage: str,
        news_item_level: bool = False,
        limit: int = 100
    ) -> dict:
        """Get performance statistics for a stage."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Filter by level (document-level vs news-level)
            news_filter = "news_item_id IS NOT NULL" if news_item_level else "news_item_id IS NULL"
            
            cursor.execute(
                f"""
                SELECT 
                    COUNT(*) as count,
                    AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_seconds,
                    MIN(EXTRACT(EPOCH FROM (updated_at - created_at))) as min_seconds,
                    MAX(EXTRACT(EPOCH FROM (updated_at - created_at))) as max_seconds
                FROM document_stage_timing
                WHERE stage = %s 
                  AND status = 'done'
                  AND {news_filter}
                LIMIT %s
                """,
                (stage, limit)
            )
            row = cursor.fetchone()
            
            if not row or row[0] == 0:
                return {
                    "count": 0,
                    "avg_seconds": None,
                    "min_seconds": None,
                    "max_seconds": None
                }
            
            return {
                "count": row[0],
                "avg_seconds": float(row[1]) if row[1] else None,
                "min_seconds": float(row[2]) if row[2] else None,
                "max_seconds": float(row[3]) if row[3] else None
            }
        finally:
            self.release_connection(conn)
    
    # ========================================
    # SYNC methods (for legacy compatibility)
    # ========================================
    
    def record_stage_start_sync(
        self,
        document_id: str,
        stage: str,
        news_item_id: Optional[str] = None,
        metadata: Optional[dict] = None
    ) -> StageTimingRecord:
        """SYNC version - Record stage start."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            now = datetime.utcnow()
            metadata_json = json.dumps(metadata or {})
            
            cursor.execute(
                """
                INSERT INTO document_stage_timing 
                (document_id, news_item_id, stage, status, created_at, updated_at, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
                ON CONFLICT (document_id, COALESCE(news_item_id, ''), stage) 
                DO UPDATE SET 
                    status = EXCLUDED.status,
                    created_at = EXCLUDED.created_at,
                    updated_at = EXCLUDED.updated_at,
                    error_message = NULL,
                    metadata = EXCLUDED.metadata
                RETURNING id
                """,
                (document_id, news_item_id, stage, StageStatus.PROCESSING.value, now, now, metadata_json)
            )
            
            row = cursor.fetchone()
            record_id = row[0] if row else None
            
            conn.commit()
            
            return StageTimingRecord(
                id=record_id,
                document_id=document_id,
                news_item_id=news_item_id,
                stage=stage,
                status=StageStatus.PROCESSING,
                created_at=now,
                updated_at=now,
                metadata=metadata or {}
            )
        finally:
            self.release_connection(conn)
    
    def record_stage_end_sync(
        self,
        document_id: str,
        stage: str,
        status: str,
        news_item_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """SYNC version - Record stage end."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Validate status
            stage_status = StageStatus(status)
            
            cursor.execute(
                """
                UPDATE document_stage_timing
                SET status = %s,
                    error_message = %s
                WHERE document_id = %s 
                  AND stage = %s
                  AND (news_item_id = %s OR (news_item_id IS NULL AND %s IS NULL))
                """,
                (stage_status.value, error_message, document_id, stage, news_item_id, news_item_id)
            )
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    # ========================================
    # PRIVATE: Mapping helpers
    # ========================================
    
    def _map_row_to_entity(self, cursor, row) -> StageTimingRecord:
        """Map database row to StageTimingRecord entity."""
        row_dict = self.map_row_to_dict(cursor, row)
        
        # Parse metadata JSON
        metadata = row_dict.get("metadata", {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)
        
        return StageTimingRecord(
            id=row_dict.get("id"),
            document_id=row_dict["document_id"],
            news_item_id=row_dict.get("news_item_id"),  # NULL for document-level
            stage=row_dict["stage"],
            status=StageStatus(row_dict["status"]),
            created_at=row_dict["created_at"],
            updated_at=row_dict["updated_at"],
            error_message=row_dict.get("error_message"),
            metadata=metadata
        )
