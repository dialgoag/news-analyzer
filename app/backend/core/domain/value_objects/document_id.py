"""
DocumentId Value Object - Unique identifier for documents.

Value objects are immutable and defined by their attributes, not identity.
"""

from dataclasses import dataclass
from typing import Optional
import uuid


@dataclass(frozen=True)
class DocumentId:
    """
    Unique identifier for a document.
    
    Immutable value object that encapsulates document ID validation and behavior.
    
    Usage:
        >>> doc_id = DocumentId.generate()
        >>> doc_id = DocumentId.from_string("doc_123")
        >>> str(doc_id)  # "doc_123"
    """
    
    value: str
    
    def __post_init__(self):
        """Validate document ID."""
        if not self.value:
            raise ValueError("DocumentId cannot be empty")
        if not isinstance(self.value, str):
            raise ValueError(f"DocumentId must be string, got {type(self.value)}")
    
    @classmethod
    def generate(cls, prefix: str = "doc") -> "DocumentId":
        """
        Generate a new unique document ID.
        
        Args:
            prefix: Prefix for the ID (default: "doc")
        
        Returns:
            New DocumentId instance
        """
        unique_id = str(uuid.uuid4())
        return cls(value=f"{prefix}_{unique_id}")
    
    @classmethod
    def from_string(cls, value: str) -> "DocumentId":
        """
        Create DocumentId from string.
        
        Args:
            value: Document ID string
        
        Returns:
            DocumentId instance
        
        Raises:
            ValueError: If value is invalid
        """
        return cls(value=value)
    
    def __str__(self) -> str:
        """String representation."""
        return self.value
    
    def __repr__(self) -> str:
        """Debug representation."""
        return f"DocumentId('{self.value}')"
    
    def __eq__(self, other) -> bool:
        """Equality comparison."""
        if isinstance(other, DocumentId):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False
    
    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash(self.value)


@dataclass(frozen=True)
class NewsItemId:
    """
    Unique identifier for a news item.
    
    Similar to DocumentId but for individual news items within a document.
    """
    
    value: str
    
    def __post_init__(self):
        """Validate news item ID."""
        if not self.value:
            raise ValueError("NewsItemId cannot be empty")
        if not isinstance(self.value, str):
            raise ValueError(f"NewsItemId must be string, got {type(self.value)}")
    
    @classmethod
    def generate(cls, document_id: str, index: int) -> "NewsItemId":
        """
        Generate news item ID from document ID and index.
        
        Args:
            document_id: Parent document ID
            index: Item index (0-based)
        
        Returns:
            NewsItemId instance
        """
        return cls(value=f"{document_id}_item_{index}")
    
    @classmethod
    def from_string(cls, value: str) -> "NewsItemId":
        """Create NewsItemId from string."""
        return cls(value=value)
    
    def __str__(self) -> str:
        return self.value
    
    def __repr__(self) -> str:
        return f"NewsItemId('{self.value}')"
    
    def __eq__(self, other) -> bool:
        if isinstance(other, NewsItemId):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other
        return False
    
    def __hash__(self) -> int:
        return hash(self.value)
