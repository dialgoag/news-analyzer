"""
Document Entity - Core domain entity representing an uploaded document.

Entities have identity and lifecycle. Two documents with the same ID are
the same document, even if their attributes differ.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from enum import Enum

from core.domain.value_objects.document_id import DocumentId
from core.domain.value_objects.text_hash import TextHash
from core.domain.value_objects.pipeline_status import (
    PipelineStatus, StageEnum, StateEnum, TerminalStateEnum
)


class DocumentType(str, Enum):
    """Supported document types."""
    PDF = "pdf"
    TEXT = "txt"
    DOCX = "docx"
    CONTRACT = "CONTRACT"  # Legacy value from production data
    GENERIC_DOCUMENT = "GENERIC_DOCUMENT"  # Legacy value from production data
    UNKNOWN = "unknown"


@dataclass
class Document:
    """
    Document aggregate root.
    
    Represents a document in the system with its lifecycle through stages:
    upload → ocr → chunking → indexing → insights → completed
    
    Each stage has states: pending → processing → done
    
    Business rules:
    - SHA256 is computed on upload (content-based deduplication)
    - Status transitions must be valid (stage → state)
    - Cannot advance to next stage without completing current stage
    - Document aggregates its NewsItems
    
    Usage:
        >>> doc = Document.create(filename="report.pdf", sha256="abc...", file_size=1024000)
        >>> doc.advance_to(StageEnum.OCR, StateEnum.PENDING)
        >>> doc.advance_to(StageEnum.OCR, StateEnum.PROCESSING)
        >>> doc.advance_to(StageEnum.OCR, StateEnum.DONE)
        >>> doc.advance_to(StageEnum.CHUNKING, StateEnum.PENDING)
        >>> # ... process through all stages ...
        >>> doc.mark_terminal(TerminalStateEnum.COMPLETED)
    """
    
    # ========================================
    # REQUIRED FIELDS (no defaults) - MUST BE FIRST
    # ========================================
    
    # Identity
    id: DocumentId
    
    # Attributes (required)
    filename: str
    original_filename: str
    sha256: str
    file_size: int  # bytes
    document_type: DocumentType
    
    # Status (required - composable)
    status: PipelineStatus
    
    # ========================================
    # OPTIONAL FIELDS (with defaults)
    # ========================================
    
    # Metadata (from DB)
    source: str = "web"  # Document source (web, upload, api, etc.)
    news_date: Optional[datetime] = None  # Date of the news content
    processing_stage: Optional[str] = None  # Current pipeline stage
    
    # OCR results
    total_pages: Optional[int] = None
    total_news_items: Optional[int] = None
    ocr_text: Optional[str] = None  # Full OCR text
    ocr_text_length: Optional[int] = None
    
    # Indexing
    num_chunks: int = 0  # Number of chunks/news items
    indexed_at: Optional[datetime] = None  # LEGACY: Use document_stage_timing table instead
    
    # Reprocessing
    reprocess_requested: bool = False  # Flag for manual reprocessing
    
    # Content hash (for deduplication)
    content_hash: Optional[TextHash] = None  # SHA256 of file content
    
    # Error handling
    error_message: Optional[str] = None
    
    # ========================================
    # TIMESTAMPS: Document-level (applies to entire entity)
    # ========================================
    created_at: datetime = field(default_factory=datetime.utcnow)  # Document first entered system
    updated_at: datetime = field(default_factory=datetime.utcnow)  # Last modification (auto-trigger)
    
    # ========================================
    # LEGACY COMPATIBILITY (deprecated - use document_stage_timing table)
    # ========================================
    ingested_at: datetime = field(default_factory=datetime.utcnow)  # LEGACY: = upload completion time
    uploaded_at: datetime = field(default_factory=datetime.utcnow)  # LEGACY: = created_at (for backward compat)
    
    @classmethod
    def create(
        cls,
        filename: str,
        sha256: str,
        file_size: int,
        document_id: Optional[DocumentId] = None,
        document_type: Optional[DocumentType] = None
    ) -> "Document":
        """
        Create a new document.
        
        Factory method for creating documents with proper initialization.
        Initial state: upload_pending
        
        Args:
            filename: Original filename
            sha256: SHA256 hash of file content
            file_size: File size in bytes
            document_id: Optional custom ID (generated if not provided)
            document_type: Document type (inferred from filename if not provided)
        
        Returns:
            New Document instance
        """
        # Generate ID if not provided
        if document_id is None:
            document_id = DocumentId.generate(prefix="doc")
        
        # Infer document type from filename
        if document_type is None:
            document_type = cls._infer_document_type(filename)
        
        # Initial status: upload_pending
        initial_status = PipelineStatus.create(StageEnum.UPLOAD, StateEnum.PENDING)
        
        return cls(
            id=document_id,
            filename=filename,
            original_filename=filename,
            sha256=sha256,
            file_size=file_size,
            document_type=document_type,
            status=initial_status
        )
    
    @staticmethod
    def _infer_document_type(filename: str) -> DocumentType:
        """Infer document type from filename extension."""
        filename_lower = filename.lower()
        if filename_lower.endswith('.pdf'):
            return DocumentType.PDF
        elif filename_lower.endswith('.txt'):
            return DocumentType.TEXT
        elif filename_lower.endswith('.docx'):
            return DocumentType.DOCX
        else:
            return DocumentType.UNKNOWN
    
    # === Status Transitions (Business Logic) ===
    
    def advance_to(self, stage: StageEnum, state: StateEnum):
        """
        Advance document to a specific stage and state.
        
        Validates:
        - If advancing to new stage, current stage must be DONE
        - If advancing state within stage, transition must be valid
        
        Args:
            stage: Target stage
            state: Target state
        
        Raises:
            ValueError: If transition is invalid
        """
        current_stage = self.status.current_stage()
        current_state = self.status.current_state()
        
        # If terminal, can't advance
        if self.status.is_terminal():
            raise ValueError(f"Cannot advance from terminal status {self.status}")
        
        # Check if advancing to new stage
        if current_stage != stage:
            # Must be DONE in current stage before advancing
            if current_state != StateEnum.DONE:
                raise ValueError(
                    f"Must complete current stage ({current_stage.value}) "
                    f"before advancing to {stage.value}"
                )
            
            # Validate stage transition
            if not self.status.can_transition_to_stage(stage):
                raise ValueError(
                    f"Invalid stage transition: {current_stage.value} → {stage.value}"
                )
            
            # New stage must start at PENDING
            if state != StateEnum.PENDING:
                raise ValueError(
                    f"New stage {stage.value} must start at PENDING, got {state.value}"
                )
        else:
            # Same stage - validate state transition
            if not self.status.can_transition_to_state(state):
                raise ValueError(
                    f"Invalid state transition in {stage.value}: "
                    f"{current_state.value} → {state.value}"
                )
        
        # Update status
        self.status = PipelineStatus.create(stage, state)
        self.updated_at = datetime.utcnow()
    
    def mark_terminal(self, terminal_state: TerminalStateEnum, error_message: Optional[str] = None):
        """
        Mark document with terminal status (completed, error, paused).
        
        Args:
            terminal_state: Terminal status to set
            error_message: Error message (required if ERROR)
        
        Raises:
            ValueError: If transition to terminal state is invalid
        """
        # Validate terminal transition
        if not self.status.can_transition_to_terminal(terminal_state):
            raise ValueError(
                f"Cannot transition to {terminal_state.value} from {self.status}"
            )
        
        # Set terminal status
        self.status = PipelineStatus.terminal(terminal_state)
        self.updated_at = datetime.utcnow()
        
        # Handle error message
        if terminal_state == TerminalStateEnum.ERROR:
            if not error_message:
                raise ValueError("error_message required for ERROR terminal state")
            self.error_message = error_message[:500]
        else:
            self.error_message = None
    
    def update_ocr_results(self, total_pages: int, total_news_items: int, ocr_text_length: int):
        """
        Update OCR results metadata.
        
        Should be called when OCR stage completes (ocr_done).
        
        Args:
            total_pages: Number of pages processed
            total_news_items: Number of news items extracted
            ocr_text_length: Length of OCR text
        """
        self.total_pages = total_pages
        self.total_news_items = total_news_items
        self.ocr_text_length = ocr_text_length
        self.updated_at = datetime.utcnow()
    
    # === Queries (Read-only) ===
    
    def is_completed(self) -> bool:
        """Check if document processing is completed."""
        return self.status.full_status() == TerminalStateEnum.COMPLETED.value
    
    def is_error(self) -> bool:
        """Check if document has error."""
        return self.status.is_error()
    
    def is_processing(self) -> bool:
        """Check if document is being processed."""
        return self.status.is_processing()
    
    def current_stage(self) -> Optional[StageEnum]:
        """Get current processing stage."""
        return self.status.current_stage()
    
    def current_state(self) -> Optional[StateEnum]:
        """Get current state within stage."""
        return self.status.current_state()
    
    def can_retry(self) -> bool:
        """Check if document can be retried (must be in error state)."""
        return self.status.full_status() == TerminalStateEnum.ERROR.value
    
    def get_id_string(self) -> str:
        """Get document ID as string."""
        return str(self.id)
    
    def get_production_status(self) -> str:
        """Get production-ready status string (e.g., 'ocr_processing')."""
        return self.status.full_status()
    
    def __eq__(self, other) -> bool:
        """
        Equality based on identity (ID), not attributes.
        
        Two documents with same ID are the same document.
        """
        if not isinstance(other, Document):
            return False
        return self.id == other.id
    
    def __hash__(self) -> int:
        """Hash based on ID."""
        return hash(self.id)
    
    def __repr__(self) -> str:
        """Debug representation."""
        return f"Document(id={self.id}, filename='{self.filename}', status={self.status})"
