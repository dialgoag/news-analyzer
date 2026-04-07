"""
Centralized pipeline state definitions.

Single source of truth for all status strings, processing stages,
task types, and state transitions used across the pipeline.

Naming convention:
    document_status.status = "{stage}_{state}"
    where state is one of: pending, processing, done
    Terminal states: completed, error, paused

Flow:
    upload_pending -> upload_processing -> upload_done
    -> ocr_pending -> ocr_processing -> ocr_done
    -> chunking_pending -> chunking_processing -> chunking_done
    -> indexing_pending -> indexing_processing -> indexing_done
    -> insights_pending -> insights_processing -> insights_done
    -> completed

Usage:
    from pipeline_states import DocStatus, Stage, TaskType, QueueStatus, WorkerStatus

    cursor.execute("... WHERE status = %s", (DocStatus.OCR_PENDING,))
    if doc['status'] == DocStatus.OCR_DONE: ...
    next_status = PipelineTransitions.done_status(Stage.OCR)  # -> "ocr_done"
"""


class DocStatus:
    """document_status.status — lifecycle of a document through the pipeline."""

    # Upload stage
    UPLOAD_PENDING = "upload_pending"
    UPLOAD_PROCESSING = "upload_processing"
    UPLOAD_DONE = "upload_done"

    # OCR stage
    OCR_PENDING = "ocr_pending"
    OCR_PROCESSING = "ocr_processing"
    OCR_DONE = "ocr_done"

    # Chunking stage
    CHUNKING_PENDING = "chunking_pending"
    CHUNKING_PROCESSING = "chunking_processing"
    CHUNKING_DONE = "chunking_done"

    # Indexing stage
    INDEXING_PENDING = "indexing_pending"
    INDEXING_PROCESSING = "indexing_processing"
    INDEXING_DONE = "indexing_done"

    # Insights stage
    INSIGHTS_PENDING = "insights_pending"
    INSIGHTS_PROCESSING = "insights_processing"
    INSIGHTS_DONE = "insights_done"

    # Terminal states
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"

    ACTIVE_STATES = {
        UPLOAD_PENDING, UPLOAD_PROCESSING, UPLOAD_DONE,
        OCR_PENDING, OCR_PROCESSING, OCR_DONE,
        CHUNKING_PENDING, CHUNKING_PROCESSING, CHUNKING_DONE,
        INDEXING_PENDING, INDEXING_PROCESSING, INDEXING_DONE,
        INSIGHTS_PENDING, INSIGHTS_PROCESSING, INSIGHTS_DONE,
    }
    TERMINAL_STATES = {COMPLETED, ERROR, PAUSED}

    PENDING_STATES = {
        UPLOAD_PENDING, OCR_PENDING, CHUNKING_PENDING,
        INDEXING_PENDING, INSIGHTS_PENDING,
    }
    PROCESSING_STATES = {
        UPLOAD_PROCESSING, OCR_PROCESSING, CHUNKING_PROCESSING,
        INDEXING_PROCESSING, INSIGHTS_PROCESSING,
    }
    DONE_STATES = {
        UPLOAD_DONE, OCR_DONE, CHUNKING_DONE,
        INDEXING_DONE, INSIGHTS_DONE, COMPLETED,
    }

    @classmethod
    def is_processable(cls, status: str) -> bool:
        return status in cls.ACTIVE_STATES

    # Deprecated: migration 012 normalizes DB. Single schema only. Not used at runtime.
    MIGRATION_MAP = {
        "pending": "upload_pending",
        "queued": "upload_pending",
        "processing": "ocr_processing",
        "chunked": "chunking_done",
        "indexed": "indexing_done",
    }


class Stage:
    """document_status.processing_stage — which pipeline step the doc is in."""
    UPLOAD = "upload"
    OCR = "ocr"
    CHUNKING = "chunking"
    INDEXING = "indexing"
    INSIGHTS = "insights"
    COMPLETED = "completed"

    ORDERED = [UPLOAD, OCR, CHUNKING, INDEXING, INSIGHTS, COMPLETED]


class TaskType:
    """processing_queue.task_type / worker_tasks.task_type."""
    OCR = "ocr"
    CHUNKING = "chunking"
    INDEXING = "indexing"
    INSIGHTS = "insights"
    INDEXING_INSIGHTS = "indexing_insights"

    ALL = [OCR, CHUNKING, INDEXING, INSIGHTS, INDEXING_INSIGHTS]


class QueueStatus:
    """processing_queue.status."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"

    IN_PROGRESS = {PENDING, PROCESSING}


class WorkerStatus:
    """worker_tasks.status."""
    ASSIGNED = "assigned"
    STARTED = "started"
    COMPLETED = "completed"
    ERROR = "error"

    ACTIVE = {ASSIGNED, STARTED}


class InsightStatus:
    """news_item_insights.status / document_insights.status."""
    PENDING = "insights_pending"
    QUEUED = "insights_queued"
    GENERATING = "insights_generating"
    INDEXING = "insights_indexing"  # Being indexed in Qdrant (after LLM done)
    DONE = "insights_done"
    ERROR = "insights_error"

    IN_PROGRESS = {PENDING, QUEUED, GENERATING, INDEXING}


class PipelineTransitions:
    """
    Defines the valid state machine for the pipeline.

    Each stage has three states: {stage}_pending -> {stage}_processing -> {stage}_done
    When a stage completes ({stage}_done), the next stage starts ({next_stage}_pending).
    """

    _STAGE_ORDER = {
        Stage.UPLOAD: Stage.OCR,
        Stage.OCR: Stage.CHUNKING,
        Stage.CHUNKING: Stage.INDEXING,
        Stage.INDEXING: Stage.INSIGHTS,
        Stage.INSIGHTS: Stage.COMPLETED,
    }

    _STAGE_PENDING = {
        Stage.UPLOAD: DocStatus.UPLOAD_PENDING,
        Stage.OCR: DocStatus.OCR_PENDING,
        Stage.CHUNKING: DocStatus.CHUNKING_PENDING,
        Stage.INDEXING: DocStatus.INDEXING_PENDING,
        Stage.INSIGHTS: DocStatus.INSIGHTS_PENDING,
    }

    _STAGE_PROCESSING = {
        Stage.UPLOAD: DocStatus.UPLOAD_PROCESSING,
        Stage.OCR: DocStatus.OCR_PROCESSING,
        Stage.CHUNKING: DocStatus.CHUNKING_PROCESSING,
        Stage.INDEXING: DocStatus.INDEXING_PROCESSING,
        Stage.INSIGHTS: DocStatus.INSIGHTS_PROCESSING,
    }

    _STAGE_DONE = {
        Stage.UPLOAD: DocStatus.UPLOAD_DONE,
        Stage.OCR: DocStatus.OCR_DONE,
        Stage.CHUNKING: DocStatus.CHUNKING_DONE,
        Stage.INDEXING: DocStatus.INDEXING_DONE,
        Stage.INSIGHTS: DocStatus.INSIGHTS_DONE,
    }

    _STAGE_TASK_TYPE = {
        Stage.OCR: TaskType.OCR,
        Stage.CHUNKING: TaskType.CHUNKING,
        Stage.INDEXING: TaskType.INDEXING,
        Stage.INSIGHTS: TaskType.INSIGHTS,
    }

    @classmethod
    def next_stage(cls, current: str) -> str | None:
        return cls._STAGE_ORDER.get(current)

    @classmethod
    def pending_status(cls, stage: str) -> str | None:
        return cls._STAGE_PENDING.get(stage)

    @classmethod
    def processing_status(cls, stage: str) -> str | None:
        return cls._STAGE_PROCESSING.get(stage)

    @classmethod
    def done_status(cls, stage: str) -> str | None:
        return cls._STAGE_DONE.get(stage)

    @classmethod
    def entry_status(cls, stage: str) -> str | None:
        """Doc status required to enter this stage (= previous stage's done_status)."""
        for prev_stage, next_stage in cls._STAGE_ORDER.items():
            if next_stage == stage:
                return cls._STAGE_DONE.get(prev_stage)
        return cls._STAGE_PENDING.get(Stage.UPLOAD) if stage == Stage.UPLOAD else None

    @classmethod
    def task_type_for(cls, stage: str) -> str | None:
        return cls._STAGE_TASK_TYPE.get(stage)

    @classmethod
    def stage_for_task(cls, task_type: str) -> str | None:
        for stage, tt in cls._STAGE_TASK_TYPE.items():
            if tt == task_type:
                return stage
        return None
