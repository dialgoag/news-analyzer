"""
Worker Repository Port - Interface for worker task persistence.

This is a Hexagonal Architecture port (interface).
Adapters implement this interface for different persistence mechanisms.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime

from core.domain.entities.worker import Worker
from core.domain.value_objects.pipeline_status import PipelineStatus


class WorkerRepository(ABC):
    """
    Port (interface) for worker task persistence.
    
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
