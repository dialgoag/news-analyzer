"""
Base Domain Event class.
All domain events inherit from this.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass
class DomainEvent:
    """
    Base class for all domain events.
    
    Domain events represent something that happened in the business domain.
    They are immutable and carry all the information needed to process them.
    """
    
    event_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=datetime.now)
    aggregate_id: Optional[str] = None  # ID of the aggregate that emitted the event
    
    def __post_init__(self):
        """Validate event after initialization."""
        if not self.event_id:
            raise ValueError("event_id cannot be empty")
        if not self.occurred_at:
            raise ValueError("occurred_at cannot be empty")
