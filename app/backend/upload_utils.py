"""
Upload utilities for file naming and state management.

File naming convention:
- pending_{hash}_{original}.pdf      → Uploaded, awaiting validation
- processing_{hash}_{original}.pdf   → Worker is validating
- {hash}_{original}.pdf              → Validated and ready for OCR
- error_{hash}_{original}.pdf        → Validation failed (kept for debug)

All files live in the same uploads directory.
"""

import os
import re
from pathlib import Path
from typing import Optional, Tuple


class UploadFileState:
    """File state prefixes."""
    PENDING = "pending_"
    PROCESSING = "processing_"
    ERROR = "error_"
    VALIDATED = ""  # No prefix = validated


def build_upload_filename(state: str, file_hash: str, original_name: str) -> str:
    """
    Build filename with state prefix.
    
    Args:
        state: One of UploadFileState constants
        file_hash: SHA256 hash (full or truncated)
        original_name: Original filename
    
    Returns:
        Filename with prefix: "pending_{hash}_{original}.pdf"
    
    Example:
        >>> build_upload_filename(UploadFileState.PENDING, "a7f2b3...", "doc.pdf")
        'pending_a7f2b3..._doc.pdf'
    """
    # Extract extension
    ext = Path(original_name).suffix
    name_without_ext = Path(original_name).stem
    
    # Build: {prefix}{hash}_{name}.{ext}
    return f"{state}{file_hash}_{name_without_ext}{ext}"


def parse_upload_filename(filename: str) -> Tuple[str, str, str]:
    """
    Parse filename to extract state, hash, and original name.
    
    Returns:
        (state, file_hash, original_name)
    
    Example:
        >>> parse_upload_filename("pending_a7f2b3abc_documento.pdf")
        ('pending_', 'a7f2b3abc', 'documento.pdf')
        
        >>> parse_upload_filename("a7f2b3abc_documento.pdf")
        ('', 'a7f2b3abc', 'documento.pdf')
    """
    # Pattern: (prefix?)(hash)_(original_name.ext)
    pattern = r'^(pending_|processing_|error_)?([a-f0-9]+)_(.+)$'
    match = re.match(pattern, filename)
    
    if not match:
        raise ValueError(f"Invalid upload filename format: {filename}")
    
    prefix = match.group(1) or ""  # Empty string if no prefix
    file_hash = match.group(2)
    original_name = match.group(3)
    
    return (prefix, file_hash, original_name)


def get_file_state(filename: str) -> str:
    """
    Get file state from filename.
    
    Returns:
        One of UploadFileState constants
    
    Example:
        >>> get_file_state("pending_a7f2b3_doc.pdf")
        'pending_'
        >>> get_file_state("a7f2b3_doc.pdf")
        ''
    """
    prefix, _, _ = parse_upload_filename(filename)
    return prefix


def transition_file_state(
    upload_dir: str,
    filename: str,
    new_state: str
) -> str:
    """
    Transition file to new state (atomic rename).
    
    Args:
        upload_dir: Upload directory path
        filename: Current filename
        new_state: New state (UploadFileState constant)
    
    Returns:
        New filename
    
    Raises:
        FileNotFoundError: If file doesn't exist
        OSError: If rename fails
    
    Example:
        >>> transition_file_state("/uploads", "pending_abc_doc.pdf", UploadFileState.PROCESSING)
        'processing_abc_doc.pdf'
    """
    old_path = Path(upload_dir) / filename
    
    if not old_path.exists():
        raise FileNotFoundError(f"File not found: {old_path}")
    
    # Parse current filename
    _, file_hash, original_name = parse_upload_filename(filename)
    
    # Build new filename
    new_filename = build_upload_filename(new_state, file_hash, original_name)
    new_path = Path(upload_dir) / new_filename
    
    # Atomic rename
    old_path.rename(new_path)
    
    return new_filename


def list_files_by_state(upload_dir: str, state: str) -> list[str]:
    """
    List all files in a given state.
    
    Args:
        upload_dir: Upload directory path
        state: State to filter (UploadFileState constant)
    
    Returns:
        List of filenames
    
    Example:
        >>> list_files_by_state("/uploads", UploadFileState.PENDING)
        ['pending_abc123_doc1.pdf', 'pending_def456_doc2.pdf']
    """
    upload_path = Path(upload_dir)
    
    if not upload_path.exists():
        return []
    
    all_files = [f.name for f in upload_path.iterdir() if f.is_file()]
    
    # Filter by state
    if state == UploadFileState.VALIDATED:
        # Validated = no prefix
        return [f for f in all_files if not f.startswith(('pending_', 'processing_', 'error_'))]
    else:
        # Has prefix
        return [f for f in all_files if f.startswith(state)]


def cleanup_error_files(upload_dir: str, max_age_hours: int = 24) -> int:
    """
    Delete error files older than max_age_hours.
    
    Args:
        upload_dir: Upload directory path
        max_age_hours: Maximum age in hours
    
    Returns:
        Number of files deleted
    """
    import time
    
    upload_path = Path(upload_dir)
    deleted = 0
    cutoff_time = time.time() - (max_age_hours * 3600)
    
    for filepath in upload_path.glob("error_*"):
        if filepath.is_file() and filepath.stat().st_mtime < cutoff_time:
            filepath.unlink()
            deleted += 1
    
    return deleted


def get_validated_path(upload_dir: str, file_hash: str, original_name: str) -> Optional[Path]:
    """
    Get path to validated file (without prefix).
    
    Args:
        upload_dir: Upload directory path
        file_hash: SHA256 hash
        original_name: Original filename
    
    Returns:
        Path if file exists and is validated, None otherwise
    
    Example:
        >>> get_validated_path("/uploads", "abc123", "doc.pdf")
        Path('/uploads/abc123_doc.pdf')  # if exists and validated
    """
    validated_filename = build_upload_filename(UploadFileState.VALIDATED, file_hash, original_name)
    validated_path = Path(upload_dir) / validated_filename
    
    return validated_path if validated_path.exists() else None
