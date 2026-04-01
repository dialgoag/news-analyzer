"""
Value Objects - Immutable objects defined by their attributes.

Value objects have no identity - two value objects with the same attributes
are considered equal. They are immutable and should be used for simple
domain concepts like IDs, hashes, statuses, etc.
"""

from .document_id import DocumentId, NewsItemId
from .text_hash import TextHash
from .pipeline_status import (
    PipelineStatus,
    StageEnum,
    StateEnum,
    TerminalStateEnum,
    InsightStatusEnum,
    WorkerStatusEnum,
)

__all__ = [
    # IDs
    "DocumentId",
    "NewsItemId",
    # Hashes
    "TextHash",
    # Status - Main class
    "PipelineStatus",
    # Status - Enums
    "StageEnum",
    "StateEnum",
    "TerminalStateEnum",
    "InsightStatusEnum",
    "WorkerStatusEnum",
]
