"""
Centralized file ingestion service.

Single source of truth for: generating document_id, storing files,
registering in DB, and enqueuing OCR tasks.

Used by: Upload API, inbox scheduler (PASO 1), run_inbox_scan().

Fix #56 (REQ-016): Eliminates 3 inconsistent ingestion paths that caused
"File not found" errors when inbox scanner stored files with original
filename but registered UUID as document_id.
"""

import hashlib
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict

from database import document_status_store, ProcessingQueueStore
from pipeline_states import DocStatus, TaskType

logger = logging.getLogger("file_ingestion_service")

ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
    '.odt', '.rtf', '.html', '.xml', '.json', '.csv', '.md',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp'
}

processing_queue_store = ProcessingQueueStore()


def _generate_document_id(filename: str) -> str:
    return f"{datetime.now().timestamp()}_{filename}"


def _parse_news_date(filename: str) -> Optional[str]:
    base = os.path.basename(filename)
    m = re.match(r"^(\d{2})-(\d{2})-(\d{2})", base)
    if not m:
        return None
    d, month, y = m.group(1), m.group(2), m.group(3)
    year = int(y)
    if year < 100:
        year += 2000 if year < 50 else 1900
    try:
        return f"{year:04d}-{int(month):02d}-{int(d):02d}"
    except ValueError:
        return None


def compute_sha256(data: bytes = None, *, file_path: str = None) -> str:
    """Compute SHA256 from bytes or by streaming a file."""
    if data is not None:
        return hashlib.sha256(data).hexdigest()
    if file_path is None:
        raise ValueError("Either data or file_path must be provided")
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def check_duplicate(file_hash: str) -> Optional[Dict]:
    """Return existing document dict if hash already registered, else None."""
    return document_status_store.find_by_hash(file_hash)


def _register_and_enqueue(
    document_id: str,
    filename: str,
    source: str,
    file_hash: str,
    initial_status: str = DocStatus.UPLOAD_DONE,
    enqueue_ocr: bool = True,
    priority: int = 1,
) -> bool:
    """Register document in DB and optionally enqueue OCR task."""
    news_date = _parse_news_date(filename)
    ok = document_status_store.insert(
        document_id=document_id,
        filename=filename,
        source=source,
        status=initial_status,
        news_date=news_date,
        file_hash=file_hash,
    )
    if not ok:
        logger.warning(f"Document already registered: {document_id}")
        return False

    if enqueue_ocr:
        processing_queue_store.enqueue_task(
            document_id=document_id,
            filename=filename,
            task_type=TaskType.OCR,
            priority=priority,
        )

    logger.info(
        f"✅ Ingested: {filename} → {document_id} "
        f"(source={source}, hash={file_hash[:12]}...)"
    )
    return True


def ingest_from_upload(
    content: bytes,
    filename: str,
    upload_dir: str,
) -> Tuple[str, str]:
    """
    Ingest a file uploaded via the API.

    Writes content directly to uploads/{document_id}.
    Returns (document_id, file_hash).
    Raises ValueError on duplicate.
    """
    file_hash = compute_sha256(data=content)

    existing = check_duplicate(file_hash)
    if existing:
        raise ValueError(
            f"Duplicate: '{filename}' matches '{existing['filename']}' "
            f"(doc_id={existing['document_id']})"
        )

    document_id = _generate_document_id(filename)
    file_path = os.path.join(upload_dir, document_id)

    with open(file_path, "wb") as f:
        f.write(content)

    _register_and_enqueue(
        document_id=document_id,
        filename=filename,
        source="upload",
        file_hash=file_hash,
        initial_status=DocStatus.UPLOAD_PROCESSING,
        enqueue_ocr=False,  # Upload API uses background_tasks instead
    )

    return document_id, file_hash


def ingest_from_inbox(
    inbox_path: str,
    filename: str,
    upload_dir: str,
    processed_dir: str,
) -> Optional[str]:
    """
    Ingest a file from the inbox folder.

    Moves original to processed/, creates symlink in uploads/{document_id}.
    Returns document_id on success, None if duplicate or error.
    """
    file_hash = compute_sha256(file_path=inbox_path)

    existing = check_duplicate(file_hash)
    if existing:
        os.makedirs(processed_dir, exist_ok=True)
        dest = os.path.join(processed_dir, filename)
        try:
            shutil.move(inbox_path, dest)
        except OSError as e:
            logger.warning(f"Could not move duplicate {filename}: {e}")
        logger.info(
            f"📦 Inbox: Duplicate {filename} → processed/ "
            f"(matches {existing['filename']})"
        )
        return None

    document_id = _generate_document_id(filename)

    os.makedirs(processed_dir, exist_ok=True)
    processed_path = os.path.join(processed_dir, filename)
    shutil.move(inbox_path, processed_path)

    symlink_path = os.path.join(upload_dir, document_id)
    os.symlink(os.path.abspath(processed_path), symlink_path)

    _register_and_enqueue(
        document_id=document_id,
        filename=filename,
        source="inbox",
        file_hash=file_hash,
        initial_status=DocStatus.UPLOAD_DONE,
        enqueue_ocr=True,
        priority=1,
    )

    return document_id


def resolve_file_path(document_id: str, upload_dir: str) -> str:
    """
    Resolve the real file path for a document_id.
    Works for both direct files and symlinks.
    Returns the path (following symlinks) or raises FileNotFoundError.
    """
    path = os.path.join(upload_dir, document_id)
    real = os.path.realpath(path)
    if not os.path.exists(real):
        raise FileNotFoundError(f"File not found: {path} (resolved: {real})")
    return real
