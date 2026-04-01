"""
Document Repository Port - Interface for document persistence.

This is a Hexagonal Architecture port (interface).
Adapters implement this interface for different persistence mechanisms.
"""

from abc import ABC, abstractmethod
from typing import Optional, List
from datetime import datetime

from core.domain.entities.document import Document
from core.domain.value_objects.document_id import DocumentId
from core.domain.value_objects.pipeline_status import PipelineStatus


class DocumentRepository(ABC):
    """
    Port (interface) for document persistence.
    
    Implementations:
    - PostgresDocumentRepository (adapters/driven/persistence/postgres/)
    """
    
    @abstractmethod
    async def get_by_id(self, document_id: DocumentId) -> Optional[Document]:
        """
        Get document by ID.
        
        Args:
            document_id: Document identifier
        
        Returns:
            Document entity or None if not found
        """
        pass
    
    @abstractmethod
    async def get_by_sha256(self, sha256: str) -> Optional[Document]:
        """
        Get document by SHA256 hash (deduplication).
        
        Args:
            sha256: SHA256 hash of document content
        
        Returns:
            Document entity or None if not found
        """
        pass
    
    @abstractmethod
    async def save(self, document: Document) -> None:
        """
        Save document (insert or update).
        
        Args:
            document: Document entity to save
        
        Raises:
            ValueError: If document is invalid
        """
        pass
    
    @abstractmethod
    async def list_by_status(
        self, 
        status: PipelineStatus,
        limit: Optional[int] = None
    ) -> List[Document]:
        """
        List documents by status.
        
        Args:
            status: Pipeline status to filter by
            limit: Maximum number of documents to return
        
        Returns:
            List of documents matching the status
        """
        pass
    
    @abstractmethod
    async def list_pending(self, limit: Optional[int] = None) -> List[Document]:
        """
        List documents pending processing (any stage).
        
        Args:
            limit: Maximum number of documents to return
        
        Returns:
            List of documents in pending/processing states
        """
        pass
    
    @abstractmethod
    async def list_all(
        self, 
        skip: int = 0, 
        limit: int = 100
    ) -> List[Document]:
        """
        List all documents with pagination.
        
        Args:
            skip: Number of documents to skip
            limit: Maximum number of documents to return
        
        Returns:
            List of documents
        """
        pass
    
    @abstractmethod
    async def update_status(
        self, 
        document_id: DocumentId, 
        status: PipelineStatus,
        error_message: Optional[str] = None
    ) -> None:
        """
        Update document status.
        
        Args:
            document_id: Document identifier
            status: New status
            error_message: Error message if status is error
        
        Raises:
            ValueError: If document not found
        """
        pass
    
    @abstractmethod
    async def count_by_status(self, status: PipelineStatus) -> int:
        """
        Count documents by status.
        
        Args:
            status: Pipeline status to filter by
        
        Returns:
            Number of documents with that status
        """
        pass
    
    @abstractmethod
    async def exists(self, document_id: DocumentId) -> bool:
        """
        Check if document exists.
        
        Args:
            document_id: Document identifier
        
        Returns:
            True if document exists, False otherwise
        """
        pass
    
    @abstractmethod
    async def list_pending_reprocess(self) -> List[Document]:
        """
        List documents marked for reprocessing.
        
        Returns:
            List of documents pending reprocessing
        """
        pass
    
    @abstractmethod
    async def mark_for_reprocessing(
        self,
        document_id: DocumentId,
        requested: bool = True
    ) -> None:
        """
        Mark document for reprocessing.
        
        Args:
            document_id: Document identifier
            requested: Whether reprocessing was manually requested
        """
        pass
    
    @abstractmethod
    async def store_ocr_text(
        self,
        document_id: DocumentId,
        ocr_text: Optional[str]
    ) -> None:
        """
        Store OCR text for document.
        
        Args:
            document_id: Document identifier
            ocr_text: OCR extracted text (None to clear)
        """
        pass
    
    # ========================================
    # SYNC methods for legacy scheduler compatibility
    # TODO: Remove when master_pipeline_scheduler is async
    # ========================================
    
    def list_pending_reprocess_sync(self) -> List[dict]:
        """SYNC version - List documents pending reprocessing (returns dicts)."""
        pass
    
    def mark_for_reprocessing_sync(
        self,
        document_id: str,
        requested: bool = True
    ) -> None:
        """SYNC version - Mark document for reprocessing."""
        pass
    
    def store_ocr_text_sync(
        self,
        document_id: str,
        ocr_text: Optional[str]
    ) -> None:
        """SYNC version - Store OCR text."""
        pass
