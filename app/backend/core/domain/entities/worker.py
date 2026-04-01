"""
Worker Entity - Background worker processing tasks.

Represents a worker in the distributed processing system.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum

from core.domain.value_objects.pipeline_status import PipelineStatus, WorkerStatusEnum


class WorkerType(str, Enum):
    """Types of workers in the system."""
    OCR = "OCR"
    CHUNKING = "Chunking"
    INDEXING = "Indexing"
    INSIGHTS = "Insights"
    INDEXING_INSIGHTS = "IndexingInsights"


@dataclass
class Worker:
    """
    Worker entity.
    
    Represents a background worker processing a task.
    Workers have a lifecycle: idle → assigned → started → completed/error
    
    Business rules:
    - Each worker has unique worker_id
    - Worker can only process one task at a time
    - Must transition through states sequentially
    - Completion or error marks worker as available
    
    Usage:
        >>> worker = Worker.create(
        ...     worker_type=WorkerType.INSIGHTS,
        ...     task_id="insight_123",
        ...     document_id="doc_456"
        ... )
        >>> worker.start()
        >>> worker.complete()
    """
    
    # Identity
    worker_id: str
    
    # Attributes
    worker_type: WorkerType
    task_id: str  # Task being processed
    document_id: str  # Document being processed
    
    # Status
    status: PipelineStatus
    
    # Timestamps
    assigned_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Error handling
    error_message: Optional[str] = None
    
    @classmethod
    def create(
        cls,
        worker_type: WorkerType,
        task_id: str,
        document_id: str,
        worker_id: Optional[str] = None
    ) -> "Worker":
        """
        Create a new worker.
        
        Args:
            worker_type: Type of worker (OCR, Insights, etc.)
            task_id: Task identifier
            document_id: Document being processed
            worker_id: Optional custom worker ID
        
        Returns:
            New Worker instance
        """
        import uuid
        
        # Generate worker_id if not provided
        if worker_id is None:
            worker_id = f"{worker_type.value.lower()}_{uuid.uuid4().hex[:8]}"
        
        # Initial status
        initial_status = PipelineStatus.for_worker(WorkerStatusEnum.ASSIGNED)
        
        return cls(
            worker_id=worker_id,
            worker_type=worker_type,
            task_id=task_id,
            document_id=document_id,
            status=initial_status
        )
    
    # === Status Transitions ===
    
    def start(self):
        """Mark worker as started."""
        self.status = PipelineStatus.for_worker(WorkerStatusEnum.STARTED)
        self.started_at = datetime.utcnow()
    
    def complete(self):
        """Mark worker as completed."""
        self.status = PipelineStatus.for_worker(WorkerStatusEnum.COMPLETED)
        self.completed_at = datetime.utcnow()
        self.error_message = None
    
    def mark_error(self, error_message: str):
        """
        Mark worker as failed.
        
        Args:
            error_message: Error description
        """
        self.status = PipelineStatus.for_worker(WorkerStatusEnum.ERROR)
        self.error_message = error_message[:500]
        self.completed_at = datetime.utcnow()
    
    # === Queries ===
    
    def is_active(self) -> bool:
        """Check if worker is actively processing."""
        return self.status.full_status() in [
            WorkerStatusEnum.ASSIGNED.value,
            WorkerStatusEnum.STARTED.value
        ]
    
    def is_completed(self) -> bool:
        """Check if worker completed successfully."""
        return self.status.full_status() == WorkerStatusEnum.COMPLETED.value
    
    def is_error(self) -> bool:
        """Check if worker failed."""
        return self.status.is_error()
    
    def duration_seconds(self) -> Optional[float]:
        """
        Calculate worker execution duration.
        
        Returns:
            Duration in seconds, or None if not started/completed
        """
        if not self.started_at or not self.completed_at:
            return None
        
        delta = self.completed_at - self.started_at
        return delta.total_seconds()
    
    def __eq__(self, other) -> bool:
        """Equality based on worker_id."""
        if not isinstance(other, Worker):
            return False
        return self.worker_id == other.worker_id
    
    def __hash__(self) -> int:
        """Hash based on worker_id."""
        return hash(self.worker_id)
    
    def __repr__(self) -> str:
        """Debug representation."""
        return (
            f"Worker(id={self.worker_id}, type={self.worker_type}, "
            f"task={self.task_id}, status={self.status})"
        )
