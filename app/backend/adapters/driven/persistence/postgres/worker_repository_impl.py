"""
PostgreSQL Worker Repository Implementation.

Maps between database rows and Domain entities.
"""

from typing import Optional, List, Dict
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
    
    # ========================================
    # PROCESSING QUEUE MANAGEMENT
    # (Migrated from ProcessingQueueStore - Fase 5F)
    # ========================================
    
    async def enqueue_task(
        self, 
        document_id: str, 
        filename: str, 
        task_type: str, 
        priority: int = 0
    ) -> bool:
        """Add a task to the processing queue."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO processing_queue 
                (document_id, filename, task_type, priority, created_at, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, task_type) 
                DO UPDATE SET priority = EXCLUDED.priority, status = EXCLUDED.status
            """, (document_id, filename, task_type, priority, datetime.utcnow().isoformat(), 'pending'))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            import logging
            logging.getLogger(__name__).error(f"Error enqueueing task: {e}")
            return False
        finally:
            self.release_connection(conn)
    
    async def mark_task_completed(
        self, 
        document_id: str, 
        task_type: str
    ) -> bool:
        """Mark a task as completed in the processing queue."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE processing_queue
                SET status = 'completed', processed_at = %s
                WHERE document_id = %s AND task_type = %s
            """, (datetime.utcnow().isoformat(), document_id, task_type))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            import logging
            logging.getLogger(__name__).error(f"Error marking task completed: {e}")
            return False
        finally:
            self.release_connection(conn)
    
    async def assign_worker_to_task(
        self, 
        worker_id: str, 
        worker_type: str, 
        document_id: str, 
        task_type: str
    ) -> bool:
        """
        Assign a task to a worker atomically.
        
        Uses pg_advisory_xact_lock and SELECT FOR UPDATE to prevent race conditions.
        Returns True if assignment succeeded, False if already assigned.
        """
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            
            # Advisory lock to serialize assignment
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s::text), hashtext(%s::text))",
                (document_id, task_type),
            )
            
            # Check if already assigned
            cursor.execute("""
                SELECT worker_id FROM worker_tasks
                WHERE document_id = %s AND task_type = %s AND status IN ('assigned', 'started')
                FOR UPDATE
                LIMIT 1
            """, (document_id, task_type))
            
            existing_worker = cursor.fetchone()
            if existing_worker:
                conn.rollback()
                return False
            
            # Assign worker
            now_iso = datetime.utcnow().isoformat()
            cursor.execute("""
                INSERT INTO worker_tasks
                (worker_id, worker_type, document_id, task_type, status, assigned_at, error_message, completed_at)
                VALUES (%s, %s, %s, %s, 'assigned', %s, NULL, NULL)
                ON CONFLICT (worker_id, document_id, task_type) DO UPDATE SET
                    status = 'assigned', assigned_at = EXCLUDED.assigned_at,
                    error_message = NULL, completed_at = NULL, started_at = NULL
            """, (worker_id, worker_type, document_id, task_type, now_iso))
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            import logging
            logging.getLogger(__name__).error(f"Error assigning worker: {e}")
            return False
        finally:
            self.release_connection(conn)

    async def list_active_with_documents(self) -> List[dict]:
        """Return active workers joined with document metadata."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT wt.worker_id, wt.task_type, wt.document_id, wt.status,
                       wt.started_at, wt.error_message, wt.completed_at,
                       ds.filename
                FROM worker_tasks wt
                LEFT JOIN document_status ds ON wt.document_id = ds.document_id
                WHERE wt.status IN ('assigned', 'started')
                ORDER BY wt.task_type, wt.document_id
                """
            )
            rows = cursor.fetchall()
            return [self.map_row_to_dict(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)

    async def list_recent_errors_with_documents(
        self,
        hours: int = 24,
        limit: int = 50
    ) -> List[dict]:
        """Return recent error workers with document metadata."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT wt.worker_id, wt.task_type, wt.document_id, wt.status,
                       wt.started_at, wt.error_message, wt.completed_at,
                       ds.filename
                FROM worker_tasks wt
                LEFT JOIN document_status ds ON wt.document_id = ds.document_id
                WHERE wt.status = 'error'
                  AND wt.completed_at > NOW() - (%s * INTERVAL '1 hour')
                ORDER BY wt.completed_at DESC
                LIMIT %s
                """,
                (hours, limit)
            )
            rows = cursor.fetchall()
            return [self.map_row_to_dict(cursor, row) for row in rows]
        finally:
            self.release_connection(conn)

    async def get_worker_status_summary(self) -> Dict[str, int]:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT status, COUNT(*) AS count
                FROM worker_tasks
                GROUP BY status
                ORDER BY status
                """
            )
            rows = cursor.fetchall()
            return {
                row["status"]: int(row["count"])
                for row in (self.map_row_to_dict(cursor, row) for row in rows)
            }
        finally:
            self.release_connection(conn)

    async def get_pending_task_counts(self) -> dict:
        """Return counts of pending processing_queue tasks grouped by task_type."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT task_type, COUNT(*) AS count
                FROM processing_queue
                WHERE status = 'pending'
                GROUP BY task_type
                """
            )
            rows = cursor.fetchall()
            dict_rows = [self.map_row_to_dict(cursor, row) for row in rows]
            return {row["task_type"]: int(row["count"]) for row in dict_rows}
        finally:
            self.release_connection(conn)

    async def reset_processing_tasks(self) -> dict:
        """Reset processing_queue tasks back to pending and return counts by task_type."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT task_type, COUNT(*) AS count
                FROM processing_queue
                WHERE status = 'processing'
                GROUP BY task_type
                """
            )
            rows = cursor.fetchall()
            stats_rows = [self.map_row_to_dict(cursor, row) for row in rows]
            stats = {row["task_type"]: int(row["count"]) for row in stats_rows}
            cursor.execute(
                """
                UPDATE processing_queue
                SET status = 'pending'
                WHERE status = 'processing'
                """
            )
            conn.commit()
            return stats
        finally:
            self.release_connection(conn)

    async def delete_active_worker_tasks(self) -> int:
        """Delete worker_tasks currently assigned or started."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                DELETE FROM worker_tasks
                WHERE status IN ('assigned', 'started')
                """
            )
            deleted = cursor.rowcount
            conn.commit()
            return deleted
        finally:
            self.release_connection(conn)

    async def get_processing_queue_status(self) -> dict:
        """Return counts of processing_queue grouped by task_type and status."""
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT task_type, status, COUNT(*) AS count
                FROM processing_queue
                GROUP BY task_type, status
                """
            )
            rows = cursor.fetchall()
            result: Dict[str, Dict[str, int]] = {}
            for row in (self.map_row_to_dict(cursor, row) for row in rows):
                task_type = row["task_type"]
                status = row["status"]
                result.setdefault(task_type, {})[status] = int(row["count"])
            return result
        finally:
            self.release_connection(conn)

    async def count_processing_orphans(self) -> int:
        conn = self.get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT COUNT(*) AS count
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
            row = cursor.fetchone() or {"count": 0}
            return int(row.get("count") or 0)
        finally:
            self.release_connection(conn)
    
    # ========================================
    # SYNC methods for legacy scheduler compatibility
    # ========================================
    
    def enqueue_task_sync(
        self, 
        document_id: str, 
        filename: str, 
        task_type: str, 
        priority: int = 0
    ) -> bool:
        """SYNC version - Enqueue task to processing queue."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO processing_queue 
                (document_id, filename, task_type, priority, created_at, status)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (document_id, task_type) 
                DO UPDATE SET priority = EXCLUDED.priority, status = EXCLUDED.status
            """, (document_id, filename, task_type, priority, datetime.utcnow().isoformat(), 'pending'))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            import logging
            logging.getLogger(__name__).error(f"Error enqueueing task (sync): {e}")
            return False
        finally:
            self.get_connection_pool().putconn(conn)
    
    def mark_task_completed_sync(
        self, 
        document_id: str, 
        task_type: str
    ) -> bool:
        """SYNC version - Mark task as completed."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE processing_queue
                SET status = 'completed', processed_at = %s
                WHERE document_id = %s AND task_type = %s
            """, (datetime.utcnow().isoformat(), document_id, task_type))
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            import logging
            logging.getLogger(__name__).error(f"Error marking task completed (sync): {e}")
            return False
        finally:
            self.get_connection_pool().putconn(conn)
    
    def assign_worker_to_task_sync(
        self, 
        worker_id: str, 
        worker_type: str, 
        document_id: str, 
        task_type: str
    ) -> bool:
        """SYNC version - Assign worker to task."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            
            # Advisory lock
            cursor.execute(
                "SELECT pg_advisory_xact_lock(hashtext(%s::text), hashtext(%s::text))",
                (document_id, task_type),
            )
            
            # Check if already assigned
            cursor.execute("""
                SELECT worker_id FROM worker_tasks
                WHERE document_id = %s AND task_type = %s AND status IN ('assigned', 'started')
                FOR UPDATE
                LIMIT 1
            """, (document_id, task_type))
            
            existing_worker = cursor.fetchone()
            if existing_worker:
                conn.rollback()
                return False
            
            # Assign worker
            now_iso = datetime.utcnow().isoformat()
            cursor.execute("""
                INSERT INTO worker_tasks
                (worker_id, worker_type, document_id, task_type, status, assigned_at, error_message, completed_at)
                VALUES (%s, %s, %s, %s, 'assigned', %s, NULL, NULL)
                ON CONFLICT (worker_id, document_id, task_type) DO UPDATE SET
                    status = 'assigned', assigned_at = EXCLUDED.assigned_at,
                    error_message = NULL, completed_at = NULL, started_at = NULL
            """, (worker_id, worker_type, document_id, task_type, now_iso))
            conn.commit()
            return True
            
        except Exception as e:
            conn.rollback()
            import logging
            logging.getLogger(__name__).error(f"Error assigning worker (sync): {e}")
            return False
        finally:
            self.get_connection_pool().putconn(conn)
    
    def update_worker_status_sync(
        self,
        worker_id: str,
        document_id: str,
        task_type: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """SYNC version - Update worker task status."""
        conn = self.get_connection_pool().getconn()
        try:
            cursor = conn.cursor()
            now = datetime.utcnow().isoformat()
            
            if status == 'started':
                cursor.execute("""
                    UPDATE worker_tasks
                    SET status = %s, started_at = %s
                    WHERE worker_id = %s AND document_id = %s AND task_type = %s
                """, (status, now, worker_id, document_id, task_type))
            elif status == 'completed':
                cursor.execute("""
                    UPDATE worker_tasks
                    SET status = %s, completed_at = %s
                    WHERE worker_id = %s AND document_id = %s AND task_type = %s
                """, (status, now, worker_id, document_id, task_type))
            elif status == 'error':
                cursor.execute("""
                    UPDATE worker_tasks
                    SET status = %s, completed_at = %s, error_message = %s
                    WHERE worker_id = %s AND document_id = %s AND task_type = %s
                """, (status, now, error_message, worker_id, document_id, task_type))
            else:
                cursor.execute("""
                    UPDATE worker_tasks
                    SET status = %s
                    WHERE worker_id = %s AND document_id = %s AND task_type = %s
                """, (status, worker_id, document_id, task_type))
            
            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            import logging
            logging.getLogger(__name__).error(f"Error updating worker status (sync): {e}")
            return False
        finally:
            self.get_connection_pool().putconn(conn)
