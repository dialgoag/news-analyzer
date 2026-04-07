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
import json
import logging
import os
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict

from database import ProcessingQueueStore
from pipeline_states import DocStatus, TaskType, Stage
from adapters.driven.persistence.postgres import PostgresDocumentRepository
from adapters.driven.persistence.postgres.stage_timing_repository_impl import PostgresStageTimingRepository
from core.domain.entities.document import Document
from core.domain.value_objects.document_id import DocumentId
from core.domain.value_objects.pipeline_status import PipelineStatus, StageEnum, StateEnum
from core.domain.value_objects.text_hash import TextHash

logger = logging.getLogger("file_ingestion_service")

ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
    '.odt', '.rtf', '.html', '.xml', '.json', '.csv', '.md',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp'
}

processing_queue_store = ProcessingQueueStore()
document_repository = PostgresDocumentRepository()
stage_timing_repository = PostgresStageTimingRepository()


def _generate_document_id(filename: str, file_hash: str) -> str:
    """document_id por hash: evita colisión cuando dos archivos tienen el mismo nombre."""
    return file_hash


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
    existing = document_repository.get_by_sha256_sync(file_hash)
    if not existing:
        return None
    return {
        "document_id": existing.id.value,
        "filename": existing.filename,
        "source": existing.source,
    }


def _has_hash_prefix(basename: str) -> bool:
    """True if basename looks like {8 hex}_{rest} (Fix #95 / migrate_file_naming)."""
    parts = basename.split("_", 1)
    if len(parts) < 2:
        return False
    prefix = parts[0]
    return len(prefix) == 8 and all(c in "0123456789abcdef" for c in prefix)


def _processed_basename(original_filename: str, short_hash: str) -> str:
    """
    Target name under processed/: add short_hash_ unless the file already has that prefix.
    Avoids abcdef12_abcdef12_report.pdf when inbox files were pre-prefixed.
    """
    if _has_hash_prefix(original_filename):
        return original_filename
    return f"{short_hash}_{original_filename}"


def _map_initial_status(initial_status: str) -> PipelineStatus:
    if initial_status == DocStatus.UPLOAD_DONE:
        return PipelineStatus.create(StageEnum.UPLOAD, StateEnum.DONE)
    if initial_status == DocStatus.UPLOAD_PROCESSING:
        return PipelineStatus.create(StageEnum.UPLOAD, StateEnum.PROCESSING)
    return PipelineStatus.create(StageEnum.UPLOAD, StateEnum.PENDING)


def _news_date_to_datetime(news_date_str: Optional[str]) -> Optional[datetime]:
    if not news_date_str:
        return None
    try:
        return datetime.fromisoformat(news_date_str)
    except ValueError:
        return None


def _register_and_enqueue(
    document_id: str,
    filename: str,
    source: str,
    file_hash: str,
    file_size: int,
    initial_status: str = DocStatus.UPLOAD_DONE,
    enqueue_ocr: bool = True,
    priority: int = 1,
) -> bool:
    """Register document via DocumentRepository and optionally enqueue OCR task."""
    news_date_str = _parse_news_date(filename)
    news_date = _news_date_to_datetime(news_date_str)
    status = _map_initial_status(initial_status)
    now = datetime.utcnow()
    
    document = Document.create(
        filename=filename,
        sha256=file_hash,
        file_size=file_size,
        document_id=DocumentId(document_id)
    )
    document.status = status
    document.source = source
    document.news_date = news_date
    document.processing_stage = Stage.UPLOAD
    document.content_hash = TextHash(file_hash)
    document.ingested_at = now
    document.uploaded_at = now
    document.updated_at = now
    document.num_chunks = 0
    document.reprocess_requested = False
    document.error_message = None
    
    document_repository.save_sync(document)
    stage_timing_repository.record_stage_start_sync(
        document_id=document_id,
        stage='upload',
        metadata={'source': source, 'filename': filename, 'ingestion_channel': source}
    )

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


def _ensure_upload_audit_trail(
    *,
    document_id: str,
    filename: str,
    upload_dir: str,
    file_ext: str,
    file_path: str,
    source: str,
) -> None:
    """Create processed symlink + append audit event for uploads."""
    processed_dir = os.path.join(upload_dir, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    short_hash = document_id[:8]
    processed_name = _processed_basename(filename, short_hash)
    processed_path = os.path.join(processed_dir, processed_name)
    if not os.path.exists(processed_path):
        try:
            os.symlink(file_path, processed_path)
        except FileExistsError:
            pass
    audit_dir = os.path.join(upload_dir, "audit")
    os.makedirs(audit_dir, exist_ok=True)
    audit_path = os.path.join(audit_dir, "ingestion_events.jsonl")
    event = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event": "upload_ingest",
        "document_id": document_id,
        "filename": filename,
        "storage_path": file_path,
        "processed_entry": processed_path,
        "source": source,
    }
    with open(audit_path, "a", encoding="utf-8") as audit_file:
        audit_file.write(json.dumps(event, ensure_ascii=False) + "\n")


def ingest_from_upload(
    content: bytes,
    filename: str,
    upload_dir: str,
) -> Tuple[str, str]:
    """
    Ingest a file uploaded via the API.

    Writes content directly to uploads/{document_id}.pdf.
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

    document_id = _generate_document_id(filename, file_hash)
    
    # Add .pdf extension to symlink (Fix #95)
    file_ext = Path(filename).suffix or '.pdf'
    file_path = os.path.join(upload_dir, f"{document_id}{file_ext}")

    with open(file_path, "wb") as f:
        f.write(content)

    _ensure_upload_audit_trail(
        document_id=document_id,
        filename=filename,
        upload_dir=upload_dir,
        file_ext=file_ext,
        file_path=file_path,
        source="upload",
    )

    _register_and_enqueue(
        document_id=document_id,
        filename=filename,
        source="upload",
        file_hash=file_hash,
        file_size=len(content),
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

    Moves original to processed/{short_hash}_{filename} (or keeps name if it already has an 8-char hex prefix),
    creates symlink in uploads/{document_id}{ext}.
    Returns document_id on success, None if duplicate or error.

    Fix #95: Prevents overwriting files with same name but different content.
    """
    file_hash = compute_sha256(file_path=inbox_path)
    file_size = os.path.getsize(inbox_path)
    short_hash = file_hash[:8]  # First 8 chars for identification

    existing = check_duplicate(file_hash)
    if existing:
        os.makedirs(processed_dir, exist_ok=True)
        dup_name = _processed_basename(filename, short_hash)
        dest = os.path.join(processed_dir, dup_name)
        try:
            shutil.move(inbox_path, dest)
        except OSError as e:
            logger.warning(f"Could not move duplicate {filename}: {e}")
        logger.info(
            f"📦 Inbox: Duplicate {filename} → processed/{dup_name} "
            f"(matches {existing['filename']})"
        )
        return None

    document_id = _generate_document_id(filename, file_hash)

    os.makedirs(processed_dir, exist_ok=True)

    proc_name = _processed_basename(filename, short_hash)
    processed_path = os.path.join(processed_dir, proc_name)
    shutil.move(inbox_path, processed_path)

    # Create symlink with .pdf extension (Fix #95)
    file_ext = Path(filename).suffix or '.pdf'
    symlink_path = os.path.join(upload_dir, f"{document_id}{file_ext}")
    os.symlink(os.path.abspath(processed_path), symlink_path)

    _register_and_enqueue(
        document_id=document_id,
        filename=filename,
        source="inbox",
        file_hash=file_hash,
        file_size=file_size,
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
    
    Fix #95: Tries with extension first (new format), falls back to without extension (legacy).
    """
    # Try with .pdf extension first (new format, Fix #95)
    path_with_ext = os.path.join(upload_dir, f"{document_id}.pdf")
    if os.path.exists(path_with_ext):
        real = os.path.realpath(path_with_ext)
        if os.path.exists(real):
            return real
    
    # Fall back to legacy format (without extension)
    path_legacy = os.path.join(upload_dir, document_id)
    real_legacy = os.path.realpath(path_legacy)
    if os.path.exists(real_legacy):
        return real_legacy
    
    # Neither found
    raise FileNotFoundError(
        f"File not found: {path_with_ext} or {path_legacy}"
    )
