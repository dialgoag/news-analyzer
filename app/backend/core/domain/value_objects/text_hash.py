"""
TextHash Value Object - SHA256 hash for content deduplication.

Encapsulates hash computation and validation.
"""

from dataclasses import dataclass
import hashlib
import re


@dataclass(frozen=True)
class TextHash:
    """
    SHA256 hash value object for text deduplication.
    
    Immutable value object that encapsulates hash computation and validation.
    Ensures consistent hashing across the system.
    
    Usage:
        >>> text_hash = TextHash.compute("Some text content")
        >>> str(text_hash)  # "a3b5c7..."
        >>> text_hash.is_valid()  # True
    """
    
    value: str
    
    def __post_init__(self):
        """Validate hash format."""
        if not self.value:
            raise ValueError("TextHash cannot be empty")
        if not isinstance(self.value, str):
            raise ValueError(f"TextHash must be string, got {type(self.value)}")
        if not self._is_valid_sha256(self.value):
            raise ValueError(f"Invalid SHA256 hash format: {self.value}")
    
    @staticmethod
    def _is_valid_sha256(value: str) -> bool:
        """Check if string is valid SHA256 hex."""
        return bool(re.match(r'^[a-f0-9]{64}$', value.lower()))
    
    @classmethod
    def compute(cls, text: str) -> "TextHash":
        """
        Compute SHA256 hash of text.
        
        Normalizes text before hashing:
        - Strips whitespace
        - Converts to lowercase
        - Removes extra spaces
        
        Args:
            text: Text to hash
        
        Returns:
            TextHash instance
        """
        # Normalize text
        normalized = cls._normalize_text(text)
        
        # Compute SHA256
        hash_value = hashlib.sha256(normalized.encode('utf-8')).hexdigest()
        
        return cls(value=hash_value)
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """
        Normalize text for consistent hashing.
        
        - Strip leading/trailing whitespace
        - Lowercase
        - Collapse multiple spaces into one
        - Remove newlines (replace with space)
        
        Args:
            text: Raw text
        
        Returns:
            Normalized text
        """
        # Remove extra whitespace
        normalized = ' '.join(text.split())
        
        # Lowercase for case-insensitive matching
        normalized = normalized.lower()
        
        return normalized.strip()
    
    @classmethod
    def from_string(cls, value: str) -> "TextHash":
        """
        Create TextHash from existing hash string.
        
        Args:
            value: SHA256 hash string (64 hex chars)
        
        Returns:
            TextHash instance
        
        Raises:
            ValueError: If hash format is invalid
        """
        return cls(value=value.lower())
    
    def is_valid(self) -> bool:
        """Check if hash is valid SHA256."""
        return self._is_valid_sha256(self.value)
    
    def short_form(self, length: int = 8) -> str:
        """
        Get shortened version of hash (for logging/display).
        
        Args:
            length: Number of characters to return
        
        Returns:
            Shortened hash (e.g., "a3b5c7d9")
        """
        return self.value[:length]
    
    def __str__(self) -> str:
        """String representation (full hash)."""
        return self.value
    
    def __repr__(self) -> str:
        """Debug representation."""
        return f"TextHash('{self.short_form()}...')"
    
    def __eq__(self, other) -> bool:
        """Equality comparison."""
        if isinstance(other, TextHash):
            return self.value == other.value
        if isinstance(other, str):
            return self.value == other.lower()
        return False
    
    def __hash__(self) -> int:
        """Hash for use in sets/dicts."""
        return hash(self.value)
