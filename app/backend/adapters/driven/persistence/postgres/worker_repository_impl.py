"""
PostgreSQL Worker Repository Implementation.

Maps between database rows and Domain entities.
"""

from typing import Optional, List
from datetime import datetime, timedelta
import uuid

from core.domain.entities.worker import Worker
from core.domain.value_objects.pipeline_status import PipelineStatus
from core.ports.repositories.worker_repository import WorkerRepository
from .base import BasePostgresRepository


class PostgresWorkerRepository(BasePostgresRepository, WorkerRepository):
    """
    PostgreSQL implementation of WorkerRepository.
    
    Maps between:
    - Database: worker_tasks table (status as string)
    - Domain: Worker entity (status as PipelineStatus)
    """
    
    async def get_by_id(self, worker_id: str) -> Optional[Worker]:
        """Get worker by ID."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT worker_id, document_id, task_type, status,
                       started_at, completed_at, error_message,
                       created_at, updated_at
                FROM worker_tasks
                WHERE worker_id = %s
                """,
                (worker_id,)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._map_row_to_entity(cursor, row)
        finally:
            self.release_connection(conn)
    
    async def get_active_by_document(
        self, 
        document_id: str,
        task_type: str
    ) -> Optional[Worker]:
        """Get active worker for a document and task type."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT worker_id, document_id, task_type, status,
                       started_at, completed_at, error_message,
                       created_at, updated_at
                FROM worker_tasks
                WHERE document_id = %s 
                  AND task_type = %s
                  AND status IN ('worker_assigned', 'worker_started')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (document_id, task_type)
            )
            row = cursor.fetchone()
            
            if not row:
                return None
            
            return self._map_row_to_entity(cursor, row)
        finally:
            self.release_connection(conn)
    
    async def create(self, worker: Worker) -> str:
        """Create a new worker task."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Generate worker_id if not provided
            worker_id = worker.id or str(uuid.uuid4())
            status_str = self.map_status_from_domain(worker.status)
            
            cursor.execute(
                """
                INSERT INTO worker_tasks
                (worker_id, document_id, task_type, status, started_at, 
                 completed_at, error_message, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING worker_id
                """,
                (
                    worker_id,
                    worker.document_id,
                    worker.task_type,
                    status_str,
                    worker.started_at,
                    worker.completed_at,
                    worker.error_message,
                    worker.created_at,
                    worker.updated_at
                )
            )
            
            result = cursor.fetchone()
            conn.commit()
            
            return result[0] if result else worker_id
        finally:
            self.release_connection(conn)
    
    async def save(self, worker: Worker) -> None:
        """Save worker (update existing)."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            status_str = self.map_status_from_domain(worker.status)
            
            cursor.execute(
                """
                UPDATE worker_tasks
                SET document_id = %s, task_type = %s, status = %s,
                    started_at = %s, completed_at = %s, error_message = %s,
                    updated_at = %s
                WHERE worker_id = %s
                """,
                (
                    worker.document_id,
                    worker.task_type,
                    status_str,
                    worker.started_at,
                    worker.completed_at,
                    worker.error_message,
                    datetime.now(),
                    worker.id
                )
            )
            
            if cursor.rowcount == 0:
                raise ValueError(f"Worker not found: {worker.id}")
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    async def list_active(self, limit: Optional[int] = None) -> List[Worker]:
        """List all active workers."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT worker_id, document_id, task_type, status,
                       started_at, completed_at, error_message,
                       created_at, updated_at
                FROM worker_tasks
                WHERE status IN ('worker_assigned', 'worker_started')
                ORDER BY created_at DESC
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
    
    async def list_stuck(
        self, 
        threshold_minutes: int = 5
    ) -> List[Worker]:
        """List stuck workers."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            threshold = datetime.now() - timedelta(minutes=threshold_minutes)
            
            cursor.execute(
                """
                SELECT worker_id, document_id, task_type, status,
                       started_at, completed_at, error_message,
                       created_at, updated_at
                FROM worker_tasks
                WHERE status = 'worker_started'
                  AND started_at < %s
                ORDER BY started_at ASC
                """,
                (threshold,)
            )
            rows = cursor.fetchall()
            
            return [self._map_row_to_entity(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)
    
    async def list_by_document(
        self, 
        document_id: str,
        limit: Optional[int] = None
    ) -> List[Worker]:
        """List all workers for a document."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            query = """
                SELECT worker_id, document_id, task_type, status,
                       started_at, completed_at, error_message,
                       created_at, updated_at
                FROM worker_tasks
                WHERE document_id = %s
                ORDER BY created_at DESC
            """
            
            params = [document_id]
            
            if limit:
                query += " LIMIT %s"
                params.append(limit)
            
            cursor.execute(query, tuple(params))
            rows = cursor.fetchall()
            
            return [self._map_row_to_entity(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)
    
    async def update_status(
        self, 
        worker_id: str, 
        status: PipelineStatus,
        error_message: Optional[str] = None
    ) -> None:
        """Update worker status."""
        status_str = self.map_status_from_domain(status)
        
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE worker_tasks
                SET status = %s, error_message = %s, updated_at = %s
                WHERE worker_id = %s
                """,
                (status_str, error_message, datetime.now(), worker_id)
            )
            
            if cursor.rowcount == 0:
                raise ValueError(f"Worker not found: {worker_id}")
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    async def delete(self, worker_id: str) -> None:
        """Delete worker task."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM worker_tasks WHERE worker_id = %s",
                (worker_id,)
            )
            
            if cursor.rowcount == 0:
                raise ValueError(f"Worker not found: {worker_id}")
            
            conn.commit()
        finally:
            self.release_connection(conn)
    
    async def delete_old_completed(
        self, 
        hours: int = 1
    ) -> int:
        """Delete old completed workers."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            threshold = datetime.now() - timedelta(hours=hours)
            
            cursor.execute(
                """
                DELETE FROM worker_tasks
                WHERE status IN ('worker_completed', 'worker_error')
                  AND completed_at < %s
                """,
                (threshold,)
            )
            
            deleted_count = cursor.rowcount
            conn.commit()
            
            return deleted_count
        finally:
            self.release_connection(conn)
    
    async def count_active_by_type(self, task_type: str) -> int:
        """Count active workers by task type."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) 
                FROM worker_tasks 
                WHERE task_type = %s 
                  AND status IN ('worker_assigned', 'worker_started')
                """,
                (task_type,)
            )
            row = cursor.fetchone()
            return row[0] if row else 0
        finally:
            self.release_connection(conn)
    
    # ========================================
    # PRIVATE: Mapping helpers
    # ========================================
    
    def _map_row_to_entity(self, cursor, row) -> Worker:
        """
        Map database row to Worker entity.
        
        Args:
            cursor: Database cursor (has column names)
            row: Database row tuple
        
        Returns:
            Worker entity
        """
        row_dict = self.map_row_to_dict(cursor, row)
        
        # Map status string to PipelineStatus
        status = self.map_status_to_domain(
            row_dict["status"], 
            status_type="worker"
        )
        
        # Create Worker entity
        return Worker(
            id=row_dict["worker_id"],
            document_id=row_dict["document_id"],
            task_type=row_dict["task_type"],
            status=status,
            started_at=row_dict.get("started_at"),
            completed_at=row_dict.get("completed_at"),
            error_message=row_dict.get("error_message"),
            created_at=row_dict.get("created_at") or datetime.now(),
            updated_at=row_dict.get("updated_at") or datetime.now()
        )
