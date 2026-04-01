"""
PipelineStatus Value Object - Composable status system.

Uses a composable approach: Stage + State = Full Status
This matches the production system design where statuses are formed as:
    {stage}_{state}  (e.g., "ocr_processing", "chunking_done")

Benefits:
- Reusable: Same states work for any stage
- Extensible: Add new stages without changing state logic
- Type-safe: Both stage and state are enums
- Aligned with production: Direct mapping to pipeline_states.py
- Clean validation: Transitions are state-based, stages are context

Example:
    >>> status = PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING)
    >>> status.full_status()  # "ocr_processing"
    >>> status.can_transition_to(StateEnum.DONE)  # True
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


# ============================================================================
# Stage Enums - Define pipeline stages
# ============================================================================

class StageEnum(str, Enum):
    """
    Pipeline stages for document processing.
    
    These match production (pipeline_states.py Stage class).
    Documents flow through stages sequentially.
    """
    UPLOAD = "upload"
    OCR = "ocr"
    CHUNKING = "chunking"
    INDEXING = "indexing"
    INSIGHTS = "insights"
    
    # Special stages (no composite status)
    COMPLETED = "completed"  # Final stage, no state suffix


# ============================================================================
# State Enums - Define generic states within stages
# ============================================================================

class StateEnum(str, Enum):
    """
    Generic states within a pipeline stage.
    
    These compose with stages to form full statuses:
    - {stage}_pending    (e.g., "ocr_pending")
    - {stage}_processing (e.g., "ocr_processing")
    - {stage}_done       (e.g., "ocr_done")
    
    Reusable across all stages.
    """
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"


class TerminalStateEnum(str, Enum):
    """
    Terminal states (no stage prefix).
    
    These are final states that don't belong to a specific stage.
    """
    COMPLETED = "completed"  # All stages complete
    ERROR = "error"          # Failed at some stage
    PAUSED = "paused"        # Manually paused


# ============================================================================
# Insight-specific states (no stage composition)
# ============================================================================

class InsightStatusEnum(str, Enum):
    """
    Insight generation statuses (per news item).
    
    These match production (pipeline_states.py InsightStatus).
    No stage prefixes - insights are a single-stage process.
    """
    PENDING = "pending"
    QUEUED = "queued"
    GENERATING = "generating"
    INDEXING = "indexing"  # Indexing insights in Qdrant
    DONE = "done"
    ERROR = "error"


# ============================================================================
# Worker-specific states
# ============================================================================

class WorkerStatusEnum(str, Enum):
    """
    Worker task statuses.
    
    These match production (pipeline_states.py WorkerStatus).
    """
    IDLE = "idle"
    ASSIGNED = "assigned"
    STARTED = "started"
    COMPLETED = "completed"
    ERROR = "error"


# ============================================================================
# PipelineStatus Value Object - Composable Status
# ============================================================================

@dataclass(frozen=True)
class PipelineStatus:
    """
    Composable pipeline status: Stage + State = Full Status.
    
    Immutable value object that combines a stage with a state to form
    production-ready status strings like "ocr_processing", "chunking_done".
    
    For terminal states (completed, error, paused), stage is None.
    For insights/worker, use type-specific factory methods.
    
    Usage:
        # Document status (composable)
        >>> status = PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING)
        >>> status.full_status()  # "ocr_processing"
        >>> status.can_transition_to_state(StateEnum.DONE)  # True
        
        # Terminal status
        >>> status = PipelineStatus.terminal(TerminalStateEnum.COMPLETED)
        >>> status.full_status()  # "completed"
        >>> status.is_terminal()  # True
        
        # Insight status (no stage composition)
        >>> status = PipelineStatus.for_insight(InsightStatusEnum.GENERATING)
        >>> status.full_status()  # "generating"
    """
    
    # Core attributes
    stage: Optional[StageEnum] = field(default=None)
    state: Optional[StateEnum] = field(default=None)
    terminal_state: Optional[TerminalStateEnum] = field(default=None)
    
    # Type markers (for validation)
    status_type: str = field(default="document")
    
    # Raw status (for insights/worker which don't use composition)
    _raw_status: Optional[str] = field(default=None)
    
    def __post_init__(self):
        """Validate status composition."""
        # Must have either (stage + state), terminal_state, or raw_status
        has_composite = self.stage is not None and self.state is not None
        has_terminal = self.terminal_state is not None
        has_raw = self._raw_status is not None
        
        valid_combinations = sum([has_composite, has_terminal, has_raw])
        
        if valid_combinations != 1:
            raise ValueError(
                f"PipelineStatus must have exactly one of: (stage + state), terminal_state, or _raw_status. "
                f"Got: stage={self.stage}, state={self.state}, terminal={self.terminal_state}, raw={self._raw_status}"
            )
        
        # Validate enum types
        if self.stage is not None and not isinstance(self.stage, StageEnum):
            raise ValueError(f"Invalid stage type: {type(self.stage)}")
        if self.state is not None and not isinstance(self.state, StateEnum):
            raise ValueError(f"Invalid state type: {type(self.state)}")
        if self.terminal_state is not None and not isinstance(self.terminal_state, TerminalStateEnum):
            raise ValueError(f"Invalid terminal type: {type(self.terminal_state)}")
    
    # === Factory Methods ===
    
    @classmethod
    def create(cls, stage: StageEnum, state: StateEnum) -> "PipelineStatus":
        """
        Create composable status (stage + state).
        
        Args:
            stage: Pipeline stage
            state: State within stage
        
        Returns:
            PipelineStatus instance
        
        Example:
            >>> PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING)
            PipelineStatus(stage=OCR, state=processing) → "ocr_processing"
        """
        return cls(stage=stage, state=state, status_type="document")
    
    @classmethod
    def terminal(cls, terminal_state: TerminalStateEnum) -> "PipelineStatus":
        """
        Create terminal status (completed, error, paused).
        
        Args:
            terminal_state: Terminal state enum
        
        Returns:
            PipelineStatus instance
        """
        return cls(terminal_state=terminal_state, status_type="document")
    
    @classmethod
    def for_insight(cls, insight_status: InsightStatusEnum) -> "PipelineStatus":
        """
        Create insight status (no stage composition).
        
        Args:
            insight_status: Insight status enum
        
        Returns:
            PipelineStatus instance
        """
        return cls(_raw_status=insight_status.value, status_type="insight")
    
    @classmethod
    def for_worker(cls, worker_status: WorkerStatusEnum) -> "PipelineStatus":
        """
        Create worker status.
        
        Args:
            worker_status: Worker status enum
        
        Returns:
            PipelineStatus instance
        """
        return cls(_raw_status=worker_status.value, status_type="worker")
    
    @classmethod
    def from_string(cls, status_str: str, status_type: str = "document") -> "PipelineStatus":
        """
        Parse status string into PipelineStatus.
        
        Args:
            status_str: Status string (e.g., "ocr_processing", "completed", "generating")
            status_type: Type of status ("document", "insight", "worker")
        
        Returns:
            PipelineStatus instance
        
        Raises:
            ValueError: If status string is invalid
        """
        # Terminal states (no decomposition)
        try:
            terminal = TerminalStateEnum(status_str)
            return cls.terminal(terminal)
        except ValueError:
            pass
        
        # Insight/Worker (no decomposition)
        if status_type == "insight":
            try:
                insight_status = InsightStatusEnum(status_str)
                return cls.for_insight(insight_status)
            except ValueError:
                raise ValueError(f"Invalid insight status: {status_str}")
        
        if status_type == "worker":
            try:
                worker_status = WorkerStatusEnum(status_str)
                return cls.for_worker(worker_status)
            except ValueError:
                raise ValueError(f"Invalid worker status: {status_str}")
        
        # Document status - decompose {stage}_{state}
        parts = status_str.split("_", 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid document status format: {status_str}")
        
        stage_str, state_str = parts
        
        try:
            stage = StageEnum(stage_str)
            state = StateEnum(state_str)
            return cls.create(stage, state)
        except ValueError as e:
            raise ValueError(f"Invalid document status '{status_str}': {e}")
    
    # === Status Queries ===
    
    def full_status(self) -> str:
        """
        Get full status string for production use.
        
        Returns:
            Status string (e.g., "ocr_processing", "completed", "generating")
        """
        if self.terminal_state:
            return self.terminal_state.value
        elif self._raw_status:
            return self._raw_status
        elif self.stage and self.state:
            return f"{self.stage.value}_{self.state.value}"
        else:
            raise ValueError("Invalid PipelineStatus state")
    
    def is_terminal(self) -> bool:
        """
        Check if this is a terminal status (no further transitions).
        
        Returns:
            True if status is terminal
        """
        if self.terminal_state:
            return True
        if self._raw_status:
            # Insights and workers have their own terminal states
            return self._raw_status in ("done", "completed", "error")
        return False
    
    def is_error(self) -> bool:
        """Check if status represents an error."""
        full = self.full_status()
        return full == "error"
    
    def is_processing(self) -> bool:
        """Check if status represents active processing."""
        if self.state == StateEnum.PROCESSING:
            return True
        if self._raw_status in ("generating", "started", "assigned"):
            return True
        return False
    
    def current_stage(self) -> Optional[StageEnum]:
        """Get current stage (if applicable)."""
        return self.stage
    
    def current_state(self) -> Optional[StateEnum]:
        """Get current state (if applicable)."""
        return self.state
    
    # === Transition Validation ===
    
    def can_transition_to_state(self, new_state: StateEnum) -> bool:
        """
        Check if can transition to new state within same stage.
        
        Args:
            new_state: Target state
        
        Returns:
            True if transition is valid
        """
        if not self.state:
            return False  # Can't transition states if not in a stage
        
        # State transition rules (generic across all stages)
        valid_state_transitions = {
            StateEnum.PENDING: {StateEnum.PROCESSING},
            StateEnum.PROCESSING: {StateEnum.DONE},
            StateEnum.DONE: set(),  # Terminal within stage
        }
        
        return new_state in valid_state_transitions.get(self.state, set())
    
    def can_transition_to_stage(self, new_stage: StageEnum) -> bool:
        """
        Check if can transition to new stage.
        
        Requires current state to be DONE before moving to next stage.
        
        Args:
            new_stage: Target stage
        
        Returns:
            True if transition is valid
        """
        if not self.stage or not self.state:
            return False
        
        # Must be DONE in current stage
        if self.state != StateEnum.DONE:
            return False
        
        # Define stage order
        stage_order = {
            StageEnum.UPLOAD: StageEnum.OCR,
            StageEnum.OCR: StageEnum.CHUNKING,
            StageEnum.CHUNKING: StageEnum.INDEXING,
            StageEnum.INDEXING: StageEnum.INSIGHTS,
            # INSIGHTS can go to COMPLETED (terminal)
        }
        
        next_stage = stage_order.get(self.stage)
        return new_stage == next_stage
    
    def can_transition_to_terminal(self, terminal_state: TerminalStateEnum) -> bool:
        """
        Check if can transition to terminal state.
        
        Args:
            terminal_state: Target terminal state
        
        Returns:
            True if transition is valid
        """
        # Can always error from any state
        if terminal_state == TerminalStateEnum.ERROR:
            return True
        
        # Can always pause (if not already terminal)
        if terminal_state == TerminalStateEnum.PAUSED and not self.is_terminal():
            return True
        
        # Can complete only from insights_done or indexing_done
        if terminal_state == TerminalStateEnum.COMPLETED:
            if self.stage == StageEnum.INSIGHTS and self.state == StateEnum.DONE:
                return True
            if self.stage == StageEnum.INDEXING and self.state == StateEnum.DONE:
                return True  # If insights disabled
        
        return False
    
    # === String Representations ===
    
    def __str__(self) -> str:
        """String representation (full status)."""
        return self.full_status()
    
    def __repr__(self) -> str:
        """Debug representation."""
        if self.terminal_state:
            return f"PipelineStatus(terminal={self.terminal_state.value})"
        elif self._raw_status:
            return f"PipelineStatus({self.status_type}={self._raw_status})"
        else:
            return f"PipelineStatus(stage={self.stage.value}, state={self.state.value})"
    
    def __eq__(self, other) -> bool:
        """Equality comparison."""
        if isinstance(other, PipelineStatus):
            return self.full_status() == other.full_status()
        if isinstance(other, str):
            return self.full_status() == other
        return False
    
    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash(self.full_status())
