"""
Worker Repository Port - Interface for worker task persistence.

This is a Hexagonal Architecture port (interface).
Adapters implement this interface for different persistence mechanisms.
"""

from abc import ABC, abstractmethod
from typing import Optional, List, Dict
from datetime import datetime

from core.domain.entities.worker import Worker
from core.domain.value_objects.pipeline_status import PipelineStatus


class WorkerRepository(ABC):
    """
    Port (interface) for worker task persistence.
    
    Includes both worker_tasks and processing_queue management.
    
    Implementations:
    - PostgresWorkerRepository (adapters/driven/persistence/postgres/)
    """
    
    @abstractmethod
    async def get_by_id(self, worker_id: str) -> Optional[Worker]:
        """
        Get worker by ID.
        
        Args:
            worker_id: Worker identifier (UUID)
        
        Returns:
            Worker entity or None if not found
        """
        pass
    
    @abstractmethod
    async def get_active_by_document(
        self, 
        document_id: str,
        task_type: str
    ) -> Optional[Worker]:
        """
        Get active worker for a document and task type.
        
        Args:
            document_id: Document identifier
            task_type: Task type (ocr, chunking, indexing, insights)
        
        Returns:
            Active worker or None if not found
        """
        pass
    
    @abstractmethod
    async def create(self, worker: Worker) -> str:
        """
        Create a new worker task.
        
        Args:
            worker: Worker entity to create
        
        Returns:
            Worker ID (UUID)
        
        Raises:
            ValueError: If worker is invalid
        """
        pass
    
    @abstractmethod
    async def save(self, worker: Worker) -> None:
        """
        Save worker (update existing).
        
        Args:
            worker: Worker entity to save
        
        Raises:
            ValueError: If worker not found
        """
        pass
    
    @abstractmethod
    async def list_active(self, limit: Optional[int] = None) -> List[Worker]:
        """
        List all active workers (assigned or started).
        
        Args:
            limit: Maximum number of workers to return
        
        Returns:
            List of active workers
        """
        pass
    
    @abstractmethod
    async def list_stuck(
        self, 
        threshold_minutes: int = 5
    ) -> List[Worker]:
        """
        List stuck workers (started but not completed after threshold).
        
        Args:
            threshold_minutes: Time threshold in minutes
        
        Returns:
            List of stuck workers
        """
        pass
    
    @abstractmethod
    async def list_by_document(
        self, 
        document_id: str,
        limit: Optional[int] = None
    ) -> List[Worker]:
        """
        List all workers for a document.
        
        Args:
            document_id: Document identifier
            limit: Maximum number of workers to return
        
        Returns:
            List of workers for the document
        """
        pass
    
    @abstractmethod
    async def update_status(
        self, 
        worker_id: str, 
        status: PipelineStatus,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update worker status.
        
        Args:
            worker_id: Worker identifier
            status: New status (worker_assigned, worker_started, etc.)
            error_message: Error message if status is error
        
        Raises:
            ValueError: If worker not found
        """
        pass
    
    @abstractmethod
    async def delete(self, worker_id: str) -> None:
        """
        Delete worker task.
        
        Args:
            worker_id: Worker identifier
        
        Raises:
            ValueError: If worker not found
        """
        pass
    
    @abstractmethod
    async def delete_old_completed(
        self, 
        hours: int = 1
    ) -> int:
        """
        Delete old completed workers.
        
        Args:
            hours: Age threshold in hours
        
        Returns:
            Number of workers deleted
        """
        pass
    
    @abstractmethod
    async def count_active_by_type(self, task_type: str) -> int:
        """
        Count active workers by task type.
        
        Args:
            task_type: Task type (ocr, chunking, indexing, insights)
        
        Returns:
            Number of active workers of that type
        """
        pass
    
    # ========================================
    # PROCESSING QUEUE MANAGEMENT
    # (Migrated from ProcessingQueueStore)
    # ========================================
    
    @abstractmethod
    async def enqueue_task(
        self, 
        document_id: str, 
        filename: str, 
        task_type: str, 
        priority: int = 0
    ) -> bool:
        """
        Add a task to the processing queue.
        
        Args:
            document_id: Document identifier
            filename: Document filename
            task_type: Task type (ocr, chunking, indexing, insights)
            priority: Task priority (higher = more urgent)
        
        Returns:
            True if task was enqueued successfully
        """
        pass
    
    @abstractmethod
    async def mark_task_completed(
        self, 
        document_id: str, 
        task_type: str
    ) -> bool:
        """
        Mark a task as completed in the processing queue.
        
        Args:
            document_id: Document identifier
            task_type: Task type
        
        Returns:
            True if task was marked completed
        """
        pass
    
    @abstractmethod
    async def assign_worker_to_task(
        self, 
        worker_id: str, 
        worker_type: str, 
        document_id: str, 
        task_type: str
    ) -> bool:
        """
        Assign a task to a worker atomically.
        
        Uses database locks to prevent duplicate assignment.
        
        Args:
            worker_id: Worker identifier
            worker_type: Worker type (OCR, Chunking, Indexing, Insights)
            document_id: Document identifier
            task_type: Task type
        
        Returns:
            True if assignment succeeded, False if already assigned
        """
        pass

    # ========================================
    # DASHBOARD / MAINTENANCE HELPERS
    # ========================================

    @abstractmethod
    async def list_active_with_documents(self) -> List[Dict]:
        """Return active workers joined with document metadata (filenames)."""
        pass

    @abstractmethod
    async def list_recent_errors_with_documents(
        self,
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict]:
        """Return recent error workers (finished within timeframe) with document metadata."""
        pass

    @abstractmethod
    async def get_worker_status_summary(self) -> Dict[str, int]:
        """Return counts of worker_tasks grouped by status."""
        pass

    @abstractmethod
    async def get_pending_task_counts(self) -> Dict[str, int]:
        """Return counts of pending tasks grouped by task_type."""
        pass
    
    @abstractmethod
    async def get_processing_queue_status(self) -> Dict[str, Dict[str, int]]:
        """Return counts of processing_queue grouped by task_type/status."""
        pass

    @abstractmethod
    async def count_processing_orphans(self) -> int:
        """Return number of processing_queue rows without an active worker assigned."""
        pass

    @abstractmethod
    async def reset_processing_tasks(self) -> Dict[str, int]:
        """
        Reset processing_queue rows (status='processing') back to 'pending'.
        Returns counts per task_type prior to the reset.
        """
        pass

    @abstractmethod
    async def delete_active_worker_tasks(self) -> int:
        """Delete worker_tasks in statuses ACTIVE. Returns number deleted."""
        pass
    
    # ========================================
    # SYNC methods for legacy scheduler compatibility
    # TODO: Remove when master_pipeline_scheduler becomes async
    # ========================================
    
    def enqueue_task_sync(
        self, 
        document_id: str, 
        filename: str, 
        task_type: str, 
        priority: int = 0
    ) -> bool:
        """SYNC version - Enqueue task to processing queue."""
        pass
    
    def mark_task_completed_sync(
        self, 
        document_id: str, 
        task_type: str
    ) -> bool:
        """SYNC version - Mark task as completed."""
        pass
    
    def assign_worker_to_task_sync(
        self, 
        worker_id: str, 
        worker_type: str, 
        document_id: str, 
        task_type: str
    ) -> bool:
        """SYNC version - Assign worker to task."""
        pass
    
    def update_worker_status_sync(
        self,
        worker_id: str,
        document_id: str,
        task_type: str,
        status: str,
        error_message: Optional[str] = None
    ) -> bool:
        """SYNC version - Update worker task status."""
        pass
