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
