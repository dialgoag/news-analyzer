"""
RAG Enterprise Backend - FastAPI Application
Manages: OCR, Embedding, RAG Pipeline, Qdrant Integration
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import hashlib
import shutil
import asyncio
import logging
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import traceback
import gc
import torch
import requests
from pathlib import Path

from rag_pipeline import RAGPipeline, wait_for_ollama, ensure_model
from ocr_service import get_ocr_service, OCRService
from embeddings_service import EmbeddingsService
from qdrant_connector import QdrantConnector
import re
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ocr_service import OCRService

# Authentication imports
from auth import create_user_token
from database import (
    db,
    document_status_store,
    daily_report_store,
    weekly_report_store,
    notification_store,
    document_insights_store,
    news_item_store,
    news_item_insights_store,
    ProcessingQueueStore,
    UserRole,
)
from auth_models import (
    LoginRequest, LoginResponse, UserInfo, UserCreate, UserUpdate,
    PasswordChange, UserListResponse, MessageResponse
)
from pipeline_states import (
    DocStatus, Stage, TaskType, QueueStatus, WorkerStatus,
    InsightStatus, PipelineTransitions,
)
from middleware import (
    get_current_user, require_admin, require_upload_permission,
    require_delete_permission, CurrentUser
)

# Backup imports
from backup_service import backup_service
from backup_scheduler import BackupScheduler
from backup_models import (
    BackupProviderCreate, BackupRunRequest, BackupScheduleRequest,
    BackupRestoreRequest
)

def parse_news_date_from_filename(filename: str) -> Optional[str]:
    """Infer news date from filename. Convention: DD-MM-YY at start (e.g. 02-03-26-ABC.pdf) -> YYYY-MM-DD."""
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


def _normalize_text_for_hash(text: str) -> str:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    # Collapse whitespace but keep newlines as weak separators
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def segment_news_items_from_text(text: str, max_items: int = 200) -> List[Dict[str, str]]:
    """
    Segmenta un PDF (texto OCR) en múltiples noticias usando heurística de títulos.

    Retorna lista de items: {title, text}.
    Si no detecta títulos, cae a segmentación por páginas (\\f) o un solo item.
    """
    raw = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    raw = raw.strip()
    if not raw:
        return []

    # Page breaks (a veces OCR/Tika usa \f)
    pages = [p.strip() for p in raw.split("\f") if p.strip()]
    if len(pages) > 1:
        # Intentar títulos dentro de páginas igualmente, pero como fallback una noticia por página
        raw_for_titles = "\n\n".join(pages)
    else:
        raw_for_titles = raw

    lines = raw_for_titles.split("\n")

    def is_title_line(s: str) -> bool:
        s = (s or "").strip()
        if len(s) < 12 or len(s) > 140:
            return False
        # Must contain letters
        if not re.search(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", s):
            return False
        # Heuristic: mostly uppercase letters OR title-like (many words start uppercase)
        letters = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", s)
        if not letters:
            return False
        upper = sum(1 for ch in letters if ch.isupper())
        upper_ratio = upper / max(1, len(letters))
        words = [w for w in re.split(r"\s+", s) if w]
        titlecase_ratio = sum(1 for w in words if w[:1].isupper()) / max(1, len(words))
        if upper_ratio >= 0.75:
            return True
        if len(words) >= 3 and titlecase_ratio >= 0.7:
            return True
        return False

    # Find candidate titles with some spacing context
    title_idxs: List[int] = []
    for i, ln in enumerate(lines):
        if not is_title_line(ln):
            continue
        prev = lines[i - 1].strip() if i > 0 else ""
        # Find next non-empty line as body hint
        nxt_nonempty = ""
        for j in range(i + 1, min(len(lines), i + 8)):
            cand = lines[j].strip()
            if cand:
                nxt_nonempty = cand
                break
        # Prefer titles separated by blank lines (or start) and followed by non-trivial body
        if prev == "" and len(nxt_nonempty) > 30:
            title_idxs.append(i)

    # Build sections by title indices
    items: List[Dict[str, str]] = []
    if title_idxs:
        title_idxs = sorted(set(title_idxs))[:max_items]
        for idx, start in enumerate(title_idxs):
            end = title_idxs[idx + 1] if idx + 1 < len(title_idxs) else len(lines)
            title = lines[start].strip()
            body_lines = [l for l in lines[start + 1:end] if l.strip() != ""]
            body = "\n".join(body_lines).strip()
            # Filter very small bodies
            if len(body) < 200:
                continue
            items.append({"title": title, "text": body})

    if not items:
        # Fallback: one item per page if pages exist, else whole document
        if len(pages) > 1:
            for i, p in enumerate(pages[:max_items]):
                items.append({"title": f"Página {i + 1}", "text": p})
        else:
            items.append({"title": "Documento", "text": raw})

    # Hard cap
    return items[:max_items]


def detect_document_type(text: str) -> str:
    """Detects document type - with stricter checks"""
    text_upper = text.upper()

    # Order: more specific → less specific

    # 1. IDENTITY CARD (very specific)
    if 'CARTA DI IDENTITA' in text_upper or 'IDENTITY CARD' in text_upper:
        if 'REPUBBLICA ITALIANA' in text_upper:  # Extra check
            return 'IDENTITY_CARD'
    
    # 2. PASSPORT (very specific)
    if 'PASSAPORTO' in text_upper or 'PASSPORT' in text_upper:
        if 'REPUBBLICA ITALIANA' in text_upper:
            return 'PASSPORT'

    # 3. DRIVING LICENSE (very specific)
    if 'PATENTE DI GUIDA' in text_upper or 'DRIVING LICENSE' in text_upper:
        return 'DRIVING_LICENSE'

    # 4. CONTRACT
    if 'CONTRATTO' in text_upper or 'CONTRACT' in text_upper or 'AGREEMENT' in text_upper:
        return 'CONTRACT'
    
    # DEFAULT
    return 'GENERIC_DOCUMENT'


def extract_id_fields(text: str) -> Dict[str, Optional[str]]:
    """Extracts fields from Identity Card - vertical layout"""
    fields = {}
    
    # Tax Code (Codice Fiscale): after "CODICE FISCALE" or "FISCAL CODE", on the next line
    # Pattern: exactly 16 characters (6 letters + 2 digits + 1 letter + 2 digits + 1 letter + 3 digits + 1 letter)
    cf_pattern = r'(?:CODICE\s+FISCALE|FISCAL\s+CODE)\s*\n\s*([A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z])'
    cf_match = re.search(cf_pattern, text, re.IGNORECASE | re.MULTILINE)
    
    if cf_match:
        fields['codice_fiscale'] = cf_match.group(1)
    
    # Address
    addr_pattern = r'(VIA|VIALE|PIAZZA|CORSO|STRADA)\s+([A-Z\s,\'-]+?),\s+N\.\s+(\d+)\s+([A-Z\s\(\)]+)'
    addr_match = re.search(addr_pattern, text)
    if addr_match:
        fields['address'] = f"{addr_match.group(1)} {addr_match.group(2)}, N. {addr_match.group(3)} {addr_match.group(4)}"

    # Birth date (search after "LUOGO E DATA DI NASCITA" / "PLACE AND DATE OF BIRTH")
    date_pattern = r'(?:LUOGO\s+E\s+DATA|PLACE\s+AND\s+DATE)[^\n]*\n\s*([A-Z\s]+)\s+(\d{1,2})[./](\d{1,2})[./](\d{4})'
    date_match = re.search(date_pattern, text, re.IGNORECASE | re.MULTILINE)
    if date_match:
        fields['birth_date'] = f"{date_match.group(2)}.{date_match.group(3)}.{date_match.group(4)}"
        fields['birth_place'] = date_match.group(1).strip()
    
    return fields


def extract_passport_fields(text: str) -> Dict[str, Optional[str]]:
    """Extracts fields from Passport"""
    fields = {}
    
    # Passport number (usually 9 characters)
    passport_pattern = r'[A-Z]{2}\d{7}'
    passport_match = re.search(passport_pattern, text)
    if passport_match:
        fields['passport_number'] = passport_match.group()
    
    return fields


def extract_license_fields(text: str) -> Dict[str, Optional[str]]:
    """Extracts fields from Driving License - WITH strict checks"""
    fields = {}

    # Check 1: must contain "PATENTE DI GUIDA"
    if 'PATENTE DI GUIDA' not in text.upper() and 'DRIVING LICENSE' not in text.upper():
        return fields

    # Check 2: Italian license number pattern (10 alphanumeric characters)
    # But ONLY if preceded by specific keywords
    license_pattern = r'(?:Numero|Number|N\.|Nr\.)\s*[:\s]*([A-Z0-9]{10})'
    license_match = re.search(license_pattern, text)
    if license_match:
        fields['license_number'] = license_match.group(1)
    
    return fields


def extract_structured_fields(text: str, doc_type: str) -> Dict[str, Optional[str]]:
    """Extracts structured fields based on document type"""

    if doc_type == 'IDENTITY_CARD':
        return extract_id_fields(text)
    elif doc_type == 'PASSPORT':
        return extract_passport_fields(text)
 #   elif doc_type == 'DRIVING_LICENSE':
 #       return extract_license_fields(text)
    else:
        return {}

# Logging setup - DYNAMIC LEVEL CONTROL
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Dynamic logging control - can be changed at runtime
_log_level_override = None

def get_effective_log_level():
    """Get current effective log level (override or default)"""
    if _log_level_override:
        return _log_level_override
    return LOG_LEVEL

def set_log_level(level: str):
    """Change log level at runtime for all loggers"""
    global _log_level_override
    level = level.upper()
    if level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        raise ValueError(f"Invalid log level: {level}")
    
    _log_level_override = level
    numeric_level = getattr(logging, level)
    
    # Update root logger
    logging.getLogger().setLevel(numeric_level)
    
    # Update all existing loggers
    for logger_name in logging.Logger.manager.loggerDict:
        logger_obj = logging.getLogger(logger_name)
        if isinstance(logger_obj, logging.Logger):
            logger_obj.setLevel(numeric_level)
    
    logger.info(f"✅ Log level changed to {level} for all loggers")

# Initialize processing queue store for event-driven task management
processing_queue_store = ProcessingQueueStore()

# Cache for Tika health status (avoid blocking on health checks)
_tika_health_cache = {
    "status": "checking",
    "last_check": 0,
    "cache_ttl": 3  # Cache TTL: 3 seconds
}

# Environment variables
QDRANT_HOST = os.getenv("QDRANT_HOST", "qdrant")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", 6333))
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_openai_model = os.getenv("OPENAI_MODEL", "gpt-4o")
_ollama_model = os.getenv("LLM_MODEL", "mistral")
LLM_MODEL = os.getenv("LLM_MODEL", "") or (_openai_model if LLM_PROVIDER == "openai" else _ollama_model)
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "ollama")
OLLAMA_PORT = os.getenv("OLLAMA_PORT", "11434")
OLLAMA_BASE_URL = f"http://{OLLAMA_HOST}:{OLLAMA_PORT}"
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
UPLOAD_DIR = os.getenv("UPLOAD_DIR", "./uploads")
CUDA_VISIBLE_DEVICES = os.getenv("CUDA_VISIBLE_DEVICES", "0")
RELEVANCE_THRESHOLD = float(os.getenv("RELEVANCE_THRESHOLD", "0.3"))
MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "100"))
BACKUP_DIR = os.getenv("BACKUP_DIR", "/app/backups")
INBOX_DIR = os.getenv("INBOX_DIR", "").strip()


def _get_ram_gb() -> Optional[float]:
    try:
        import psutil
        return psutil.virtual_memory().total / (1024 ** 3)
    except ImportError:
        pass
    if os.path.exists("/proc/meminfo"):
        try:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        return kb / (1024 ** 2)
        except Exception:
            pass
    return None


def _suggest_ingest_workers_heuristic() -> int:
    """Recomendación por heurística (CPU/RAM) para INGEST_PARALLEL_WORKERS."""
    cpu = os.cpu_count() or 4
    ram_gb = _get_ram_gb()
    by_cpu = min(4, max(1, cpu - 1)) if cpu > 1 else 1
    if ram_gb is not None:
        if ram_gb < 4:
            return 1
        if ram_gb < 8:
            return min(2, by_cpu)
    return by_cpu


def _update_env_file_key(key: str, value: str) -> bool:
    """Actualiza o añade key=value en .env del directorio actual o en ENV_FILE_PATH. Devuelve True si se escribió."""
    env_path = os.getenv("ENV_FILE_PATH", "").strip() or os.path.join(os.getcwd(), ".env")
    if not os.path.isfile(env_path):
        return False
    try:
        with open(env_path, "r") as f:
            lines = f.readlines()
        new_line = f"{key}={value}\n"
        found = False
        for i, line in enumerate(lines):
            if line.strip().startswith(f"{key}="):
                lines[i] = new_line
                found = True
                break
        if not found:
            lines.append(f"\n# Auto-tune (INGEST_AUTO_TUNE_ON_START)\n{new_line}")
        with open(env_path, "w") as f:
            f.writelines(lines)
        return True
    except Exception as e:
        logging.warning(f"Could not update {env_path}: {e}")
        return False


# Resolver INGEST_PARALLEL_WORKERS: auto-tune opcional y valor "auto"
_ingest_auto_tune = os.getenv("INGEST_AUTO_TUNE_ON_START", "").strip().lower() in ("1", "true", "yes")
if _ingest_auto_tune:
    _suggested = _suggest_ingest_workers_heuristic()
    os.environ["INGEST_PARALLEL_WORKERS"] = str(_suggested)
    if _update_env_file_key("INGEST_PARALLEL_WORKERS", str(_suggested)):
        logging.info(f"INGEST_AUTO_TUNE_ON_START: wrote INGEST_PARALLEL_WORKERS={_suggested} to .env")
    logging.info(f"INGEST_AUTO_TUNE_ON_START: using INGEST_PARALLEL_WORKERS={_suggested}")

_raw_workers = os.getenv("INGEST_PARALLEL_WORKERS", "2").strip()
if _raw_workers.lower() == "auto":
    INGEST_PARALLEL_WORKERS = max(1, _suggest_ingest_workers_heuristic())
    logging.info(f"INGEST_PARALLEL_WORKERS=auto → {INGEST_PARALLEL_WORKERS}")
else:
    try:
        INGEST_PARALLEL_WORKERS = max(1, int(_raw_workers))
    except ValueError:
        INGEST_PARALLEL_WORKERS = max(1, _suggest_ingest_workers_heuristic())
        logging.warning(f"Invalid INGEST_PARALLEL_WORKERS '{_raw_workers}', using heuristic: {INGEST_PARALLEL_WORKERS}")

# Si 1/true/yes: no generar reporte diario tras cada documento indexado (solo job 23:00); útil en ingesta masiva
INGEST_DEFER_REPORT_GENERATION = os.getenv("INGEST_DEFER_REPORT_GENERATION", "").strip().lower() in ("1", "true", "yes")
# Throttle: regenerar reporte diario de una fecha como máximo cada N minutos (0 = sin límite). Reduce llamadas al LLM en ingesta masiva.
INGEST_REPORT_THROTTLE_MINUTES = max(0, int(os.getenv("INGEST_REPORT_THROTTLE_MINUTES", "0")))
# Chunking al indexar: tamaño y solapamiento (solo lectura desde .env)
CHUNK_SIZE = max(200, int(os.getenv("CHUNK_SIZE", "1000")))
CHUNK_OVERLAP = max(0, int(os.getenv("CHUNK_OVERLAP", "100")))

# Cola de reporte por archivo (insights): throttling OpenAI
INSIGHTS_QUEUE_ENABLED = os.getenv("INSIGHTS_QUEUE_ENABLED", "true").strip().lower() in ("1", "true", "yes")
INSIGHTS_THROTTLE_SECONDS = max(10, int(os.getenv("INSIGHTS_THROTTLE_SECONDS", "60")))
INSIGHTS_MAX_RETRIES = max(1, min(10, int(os.getenv("INSIGHTS_MAX_RETRIES", "5"))))

# Create upload folder if it doesn't exist
os.makedirs(UPLOAD_DIR, exist_ok=True)

# FastAPI App
app = FastAPI(
    title="RAG Enterprise Backend",
    description="API for Distributed RAG Pipeline",
    version="1.0.0"
)

# CORS configuration
# Read ALLOWED_ORIGINS from environment variable
allowed_origins_env = os.getenv("ALLOWED_ORIGINS", "")
if allowed_origins_env:
    # Split by comma and strip whitespace
    allowed_origins = [origin.strip() for origin in allowed_origins_env.split(",")]
    logging.info(f"CORS: Restricted to specific origins: {allowed_origins}")
else:
    # Default: allow all (development mode)
    allowed_origins = ["*"]
    logging.warning("CORS: ALLOWED_ORIGINS not set - allowing all origins (*)")
    logging.warning("For production, set ALLOWED_ORIGINS in .env (e.g., https://yourdomain.com)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
ocr_service: Optional[OCRService] = None
embeddings_service: Optional[EmbeddingsService] = None
rag_pipeline: Optional[RAGPipeline] = None
qdrant_connector: Optional[QdrantConnector] = None
generic_worker_pool = None  # Unified worker pool for all pipeline tasks

# Conversational memory for users
user_conversations: dict = {}  # {user_id: [{"user": "...", "assistant": "..."}]}

# Backup scheduler
backup_scheduler = BackupScheduler(backup_service)

# Throttle de generación de reporte diario por fecha (solo si INGEST_REPORT_THROTTLE_MINUTES > 0)
_last_daily_report_by_date: Dict[str, datetime] = {}


# ============================================================================
# INITIALIZATION
# ============================================================================



def _initialize_processing_queue():
    """Seed the processing queue for documents stuck in upload_pending.

    This only handles the very first stage entry (upload_pending → OCR task).
    All other recovery is handled by detect_crashed_workers() which:
      - Rolls back *_processing → previous *_done
      - Resets orphaned processing_queue / worker_tasks / insights
    The master scheduler's normal cycle then detects *_done states and
    creates the correct next-stage tasks automatically.

    Pipeline state machine (document_status.status):
    ┌─────────────────────────────────────────────────────────────────┐
    │  upload_pending → upload_processing → upload_done              │
    │       → ocr_pending → ocr_processing → ocr_done               │
    │       → chunking_pending → chunking_processing → chunking_done│
    │       → indexing_pending → indexing_processing → indexing_done │
    │       → insights (per news_item via news_item_insights table)  │
    │       → completed                                              │
    │  Terminal: error, paused                                       │
    └─────────────────────────────────────────────────────────────────┘

    Transition rules (example: stage=indexing, prev=chunking):
      {prev_stage}_done       →  master scheduler creates {stage} task
      task pending             →  master scheduler assigns worker
      worker starts            →  sets {stage}_processing
      worker ends              →  sets {stage}_done
      crash/restart            →  rolls back {stage}_processing → {prev_stage}_done
    """
    try:
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT document_id, filename FROM document_status "
            "WHERE status = %s ORDER BY ingested_at ASC",
            (DocStatus.UPLOAD_PENDING,),
        )
        pending_docs = cursor.fetchall()
        conn.close()

        if pending_docs:
            for row in pending_docs:
                processing_queue_store.enqueue_task(
                    row['document_id'], row['filename'],
                    TaskType.OCR, priority=0,
                )
            logger.info(f"📋 Seeded {len(pending_docs)} upload_pending docs into OCR queue")
        else:
            logger.info("📋 No upload_pending documents to seed")

    except Exception as e:
        logger.warning(f"⚠️  Error initializing processing queue: {e}")


def master_pipeline_scheduler():
    """
    Master Pipeline Scheduler — runs every 10 seconds.

    Implements the pipeline state machine transitions:

        {stage}_done  ──(this scheduler)──▶  next-stage task in processing_queue
        task pending   ──(this scheduler)──▶  worker_task assigned + thread spawned
        worker thread  ──(worker code)────▶  {next_stage}_done

    Steps per cycle:
        0. Cleanup: detect workers stuck >5 min → delete worker_task,
           reset processing_queue entry to pending (runtime crash recovery).
        1. Reprocess: docs flagged for reprocessing → enqueue OCR task.
        2. Inbox:    scan inbox dir → copy new PDFs → enqueue OCR task.
        3. Transitions (the core state machine):
           upload_done / ocr_pending  → create OCR task
           ocr_done                   → create Chunking task
           chunking_done              → create Indexing task
           indexing_done (all insights done) → mark completed
        4. Reconciliation: news_items without insight records → enqueue.
        5. Dispatch: pick pending tasks from processing_queue, assign to
           worker threads up to TOTAL_WORKERS (25) with per-type limits.
    """
    import os
    import hashlib
    import shutil
    from pathlib import Path
    
    conn = None
    debug_mode = True  # Enable debug logging
    try:
        if debug_mode:
            logger.debug("🔄 [Master Pipeline] Starting cycle...")
        
        # PASO 0: Runtime crash recovery — workers stuck >5 min are dead threads.
        # Same logic as startup recovery but only for stale workers (not all).
        # Rollback: worker_task → delete, processing_queue → pending,
        #           document_status → previous *_done so scheduler re-creates task.
        _RUNTIME_ROLLBACK = {
            TaskType.OCR:      DocStatus.UPLOAD_DONE,
            TaskType.CHUNKING: DocStatus.OCR_DONE,
            TaskType.INDEXING: DocStatus.CHUNKING_DONE,
            TaskType.INSIGHTS: DocStatus.INDEXING_DONE,
        }
        try:
            conn_cleanup = document_status_store.get_connection()
            cursor_cleanup = conn_cleanup.cursor()
            
            cursor_cleanup.execute("""
                SELECT worker_id, document_id, task_type
                FROM worker_tasks
                WHERE status IN (%s, %s)
                AND started_at < NOW() - INTERVAL '5 minutes'
            """, (WorkerStatus.STARTED, WorkerStatus.ASSIGNED))
            crashed_workers = cursor_cleanup.fetchall()
            
            if crashed_workers:
                logger.warning(f"🔧 Detected {len(crashed_workers)} crashed workers, recovering...")
                
                for worker_id, doc_id, task_type in crashed_workers:
                    cursor_cleanup.execute(
                        "DELETE FROM worker_tasks WHERE worker_id = %s",
                        (worker_id,),
                    )
                    cursor_cleanup.execute(
                        "UPDATE processing_queue SET status = %s "
                        "WHERE document_id = %s AND task_type = %s AND status = %s",
                        (QueueStatus.PENDING, doc_id, task_type, QueueStatus.PROCESSING),
                    )
                    rollback_to = _RUNTIME_ROLLBACK.get(task_type)
                    if rollback_to:
                        cursor_cleanup.execute(
                            "UPDATE document_status SET status = %s, error_message = NULL "
                            "WHERE document_id = %s AND status IN (%s)",
                            (rollback_to, doc_id,
                             PipelineTransitions.processing_status(
                                 PipelineTransitions.stage_for_task(task_type))),
                        )
                    logger.info(f"   ↻ Recovered {task_type} for {doc_id[:30]}... → {rollback_to}")
                
                conn_cleanup.commit()
            
            conn_cleanup.close()
        except Exception as e:
            logger.error(f"❌ Error cleaning crashed workers: {e}")
        
        # PASO 1: Documentos marcados para reprocesamiento
        try:
            docs_to_reprocess = document_status_store.get_documents_pending_reprocess()
            if docs_to_reprocess:
                logger.info(f"🔄 Found {len(docs_to_reprocess)} documents marked for reprocessing")
                for doc in docs_to_reprocess:
                    doc_id = doc['document_id']
                    filename = doc['filename']
                    
                    # Verificar si ya está en la cola de procesamiento
                    conn_temp = processing_queue_store.get_connection()
                    cursor_temp = conn_temp.cursor()
                    cursor_temp.execute("""
                        SELECT COUNT(*) FROM processing_queue
                        WHERE document_id = %s
                        AND task_type = %s
                        AND status IN (%s, %s)
                    """, (doc_id, TaskType.OCR, QueueStatus.PENDING, QueueStatus.PROCESSING))
                    result = cursor_temp.fetchone()
                    in_queue = result[list(result.keys())[0]] if result else None
                    conn_temp.close()
                    
                    if not in_queue:
                        processing_queue_store.enqueue_task(doc_id, filename, TaskType.OCR, priority=10)
                        logger.info(f"   ✅ Enqueued {filename} for reprocessing")
                    else:
                        logger.debug(f"   ⏳ {filename} already in queue, skipping")
        except Exception as e:
            logger.error(f"❌ Error checking reprocess queue: {e}")
        
        # PASO 1: Monitorear Inbox
        inbox_dir = INBOX_DIR
        if inbox_dir and os.path.exists(inbox_dir):
            try:
                inbox_files = [f for f in os.listdir(inbox_dir) if f.endswith(('.pdf', '.PDF'))]
                
                for filename in inbox_files:
                    inbox_path = os.path.join(inbox_dir, filename)
                    
                    # Calcular SHA256 del archivo en inbox
                    sha256_hash = hashlib.sha256()
                    with open(inbox_path, "rb") as f:
                        for byte_block in iter(lambda: f.read(4096), b""):
                            sha256_hash.update(byte_block)
                    file_hash = sha256_hash.hexdigest()
                    
                    # Buscar si archivo existe en uploads (por hash)
                    uploads_dir = UPLOAD_DIR
                    file_exists = False
                    
                    if os.path.exists(uploads_dir):
                        for existing_file in os.listdir(uploads_dir):
                            if existing_file.endswith(('.pdf', '.PDF')):
                                existing_path = os.path.join(uploads_dir, existing_file)
                                existing_hash = hashlib.sha256()
                                try:
                                    with open(existing_path, "rb") as f:
                                        for byte_block in iter(lambda: f.read(4096), b""):
                                            existing_hash.update(byte_block)
                                    if existing_hash.hexdigest() == file_hash:
                                        file_exists = True
                                        break
                                except:
                                    continue
                    
                    # Si archivo NO existe → Copiar a uploads + crear task
                    if not file_exists:
                        import uuid
                        doc_id = str(uuid.uuid4())
                        dest_path = os.path.join(uploads_dir, filename)
                        shutil.copy2(inbox_path, dest_path)
                        
                        # Crear registro en document_status
                        try:
                            document_status_store.insert(
                                document_id=doc_id,
                                filename=filename,
                                source='inbox',
                                status=DocStatus.UPLOAD_DONE
                            )
                            processing_queue_store.enqueue_task(doc_id, filename, TaskType.OCR, priority=1)
                            logger.info(f"✅ Inbox: Added new file {filename} (hash: {file_hash[:8]}...)")
                        except Exception as e:
                            logger.warning(f"⚠️  Inbox: Error registering {filename}: {e}")
                    
                    # Si archivo SÍ existe → Mover a processed
                    else:
                        processed_dir = os.path.join(inbox_dir, "processed")
                        os.makedirs(processed_dir, exist_ok=True)
                        processed_path = os.path.join(processed_dir, filename)
                        shutil.move(inbox_path, processed_path)
                        logger.info(f"📦 Inbox: Duplicate detected, moved {filename} to processed/")
                        
            except Exception as e:
                logger.error(f"❌ Inbox monitor error: {e}")
        
        # Get database connection with proper error handling
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        # PASO 1: Documentos con upload_done sin OCR task → Crear task OCR
        cursor.execute("""
            SELECT ds.document_id, ds.filename
            FROM document_status ds
            WHERE ds.status IN (%s, %s)
            AND NOT EXISTS (
                SELECT 1 FROM processing_queue pq
                WHERE pq.document_id = ds.document_id
                AND pq.task_type = %s
                AND pq.status IN (%s, %s)
            )
            LIMIT 50
        """, (DocStatus.UPLOAD_DONE, DocStatus.OCR_PENDING, TaskType.OCR, QueueStatus.PENDING, QueueStatus.PROCESSING))
        pending_for_ocr = cursor.fetchall()
        if debug_mode:
            logger.debug(f"🔄 [Master Pipeline] Found {len(pending_for_ocr)} pending documents for OCR")
        if pending_for_ocr:
            for row in pending_for_ocr:
                doc_id, filename = row['document_id'], row['filename']
                processing_queue_store.enqueue_task(doc_id, filename, TaskType.OCR, priority=1)
            logger.info(f"✅ Created {len(pending_for_ocr)} OCR tasks from pending documents")
        else:
            if debug_mode:
                logger.debug(f"🔄 [Master Pipeline] No pending documents found. Checking database...")
                # Debug: check total document count
                cursor.execute("SELECT COUNT(*) FROM document_status")
                result = cursor.fetchone()
                total_docs = result[list(result.keys())[0]] if result else None
                cursor.execute("SELECT COUNT(*) FROM document_status WHERE status IN (%s, %s)", (DocStatus.UPLOAD_DONE, DocStatus.OCR_PENDING))
                result = cursor.fetchone()
                pending_count = result[list(result.keys())[0]] if result else None
                logger.debug(f"   Total documents in DB: {total_docs}, Pending: {pending_count}")
        
        # PASO 2: Documentos con OCR completado sin Chunking task → Crear Chunking tasks
        cursor.execute("""
            SELECT ds.document_id, ds.filename
            FROM document_status ds
            WHERE ds.processing_stage = %s
            AND ds.status = %s
            AND ds.ocr_text IS NOT NULL
            AND LENGTH(ds.ocr_text) > 0
            AND NOT EXISTS (
                SELECT 1 FROM processing_queue pq
                WHERE pq.document_id = ds.document_id
                AND pq.task_type = %s
                AND pq.status IN (%s, %s)
            )
            LIMIT 50
        """, (Stage.OCR, DocStatus.OCR_DONE, TaskType.CHUNKING, QueueStatus.PENDING, QueueStatus.PROCESSING))
        ready_for_chunking = cursor.fetchall()
        if ready_for_chunking:
            for row in ready_for_chunking:
                doc_id, filename = row['document_id'], row['filename']
                processing_queue_store.enqueue_task(doc_id, filename, TaskType.CHUNKING, priority=1)
            logger.info(f"✅ Created {len(ready_for_chunking)} Chunking tasks")
        
        # PASO 3: Documentos con Chunking completado sin Indexing task → Crear Indexing tasks
        cursor.execute("""
            SELECT ds.document_id, ds.filename
            FROM document_status ds
            WHERE ds.processing_stage = %s
            AND ds.status = %s
            AND NOT EXISTS (
                SELECT 1 FROM processing_queue pq
                WHERE pq.document_id = ds.document_id
                AND pq.task_type = %s
                AND pq.status IN (%s, %s)
            )
            LIMIT 50
        """, (Stage.CHUNKING, DocStatus.CHUNKING_DONE, TaskType.INDEXING, QueueStatus.PENDING, QueueStatus.PROCESSING))
        ready_for_indexing = cursor.fetchall()
        if ready_for_indexing:
            for row in ready_for_indexing:
                doc_id, filename = row['document_id'], row['filename']
                processing_queue_store.enqueue_task(doc_id, filename, TaskType.INDEXING, priority=1)
            logger.info(f"✅ Created {len(ready_for_indexing)} Indexing tasks")
        
        # PASO 3.5: Reconciliación — news_items de docs indexados/completed sin registro en news_item_insights
        # Detecta items que nunca se encolaron (e.g. procesados antes de que existiera el pipeline de insights)
        cursor.execute("""
            SELECT ni.news_item_id, ni.document_id, ni.filename, ni.title, ni.text_hash,
                   COALESCE(ni.item_index, 0) as item_index
            FROM news_items ni
            JOIN document_status ds ON ds.document_id = ni.document_id
            WHERE ds.status IN (%s, %s)
            AND NOT EXISTS (
                SELECT 1 FROM news_item_insights nii
                WHERE nii.news_item_id = ni.news_item_id
            )
            LIMIT 100
        """, (DocStatus.INDEXING_DONE, DocStatus.COMPLETED))
        orphan_news_items = cursor.fetchall()
        if orphan_news_items:
            for row in orphan_news_items:
                news_item_insights_store.enqueue(
                    news_item_id=row['news_item_id'],
                    document_id=row['document_id'],
                    filename=row['filename'],
                    item_index=int(row['item_index']),
                    title=row.get('title') or '',
                    text_hash=row.get('text_hash'),
                )
            logger.info(f"🔄 Reconciliation: created {len(orphan_news_items)} missing insight records for completed/indexed docs")
            
            # Reopen completed docs that now have pending insights back to indexing_done
            reopened_doc_ids = set(row['document_id'] for row in orphan_news_items)
            for reopen_id in reopened_doc_ids:
                cursor.execute("""
                    UPDATE document_status
                    SET status = %s, processing_stage = %s
                    WHERE document_id = %s AND status = %s
                """, (DocStatus.INDEXING_DONE, Stage.INDEXING, reopen_id, DocStatus.COMPLETED))
            conn.commit()
            reopened = sum(1 for _ in reopened_doc_ids)
            logger.info(f"🔄 Reopened {reopened} completed docs to indexing_done for pending insights")
        
        # PASO 4: News items sin Insights task → Marcar como pending para workers
        cursor.execute("""
            SELECT nii.news_item_id, nii.document_id, nii.filename, nii.title
            FROM news_item_insights nii
            WHERE nii.status NOT IN (%s, %s)
            ORDER BY nii.news_item_id ASC
            LIMIT 100
        """, (InsightStatus.DONE, InsightStatus.GENERATING))
        ready_for_insights = cursor.fetchall()
        if ready_for_insights:
            for news_item_id, doc_id, filename, title in ready_for_insights:
                cursor.execute("""
                    UPDATE news_item_insights
                    SET status = %s
                    WHERE news_item_id = %s AND status NOT IN (%s, %s)
                """, (InsightStatus.PENDING, news_item_id, InsightStatus.DONE, InsightStatus.GENERATING))
            conn.commit()
            logger.info(f"✅ Marked {len(ready_for_insights)} news items as pending for insights processing")
        
        # PASO 5: Documentos con todos los insights completados → Marcar como 'completed'
        cursor.execute("""
            SELECT ds.document_id, ds.filename
            FROM document_status ds
            WHERE ds.status = %s
            AND EXISTS (
                SELECT 1 FROM news_items ni WHERE ni.document_id = ds.document_id
            )
            AND NOT EXISTS (
                SELECT 1 FROM news_item_insights nii
                WHERE nii.document_id = ds.document_id
                AND nii.status != %s
            )
            LIMIT 50
        """, (DocStatus.INDEXING_DONE, InsightStatus.DONE))
        ready_for_completion = cursor.fetchall()
        if ready_for_completion:
            for row in ready_for_completion:
                doc_id, filename = row['document_id'], row['filename']
                cursor.execute("""
                    UPDATE document_status
                    SET status = %s, processing_stage = %s
                    WHERE document_id = %s
                """, (DocStatus.COMPLETED, Stage.COMPLETED, doc_id))
            conn.commit()
            logger.info(f"✅ Marked {len(ready_for_completion)} documents as completed (all insights done)")
        
        # PASO 6: Despachar workers genéricamente para TODAS las colas
        # El Master es el ÚNICO que asigna tareas a workers
        # Workers son genéricos y pueden procesar cualquier tipo de tarea
        try:
            # Configuración total de workers disponibles
            TOTAL_WORKERS = 25  # Pool total de workers
            
            task_limits = {
                TaskType.OCR: max(2, min(int(os.getenv("OCR_PARALLEL_WORKERS", "5")), 10)),
                TaskType.CHUNKING: max(2, min(int(os.getenv("CHUNKING_PARALLEL_WORKERS", "6")), 10)),
                TaskType.INDEXING: max(2, min(int(os.getenv("INDEXING_PARALLEL_WORKERS", "6")), 10)),
                TaskType.INSIGHTS: max(2, min(int(os.getenv("INSIGHTS_PARALLEL_WORKERS", "3")), 10)),
            }
            
            cursor.execute("""
                SELECT COUNT(*) as total_active
                FROM worker_tasks
                WHERE status IN (%s, %s)
            """, (WorkerStatus.ASSIGNED, WorkerStatus.STARTED))
            result = cursor.fetchone()
            total_active = result[list(result.keys())[0]] if result else 0
            
            cursor.execute("""
                SELECT worker_type, COUNT(*) as count
                FROM worker_tasks
                WHERE status IN (%s, %s)
                GROUP BY worker_type
            """, (WorkerStatus.ASSIGNED, WorkerStatus.STARTED))
            active_by_type = {row['worker_type']: row['count'] for row in cursor.fetchall()}
            
            if debug_mode:
                logger.debug(f"🔄 [Master] Active workers: {total_active}/{TOTAL_WORKERS} total")
                for wtype, count in active_by_type.items():
                    logger.debug(f"    - {wtype}: {count} active")
            
            # Si tenemos slots disponibles, asignar tareas
            slots_available = TOTAL_WORKERS - total_active
            
            if slots_available > 0:
                # Obtener tareas pending de TODAS las colas, ordenadas por prioridad
                # CRITICAL: Usar SELECT FOR UPDATE SKIP LOCKED para evitar race conditions
                # cuando múltiples schedulers ejecutan simultáneamente
                cursor.execute("""
                    SELECT id, document_id, filename, task_type, priority
                    FROM processing_queue
                    WHERE status = %s
                    ORDER BY priority DESC, created_at ASC
                    LIMIT %s
                    FOR UPDATE SKIP LOCKED
                """, (QueueStatus.PENDING, slots_available * 2))
                
                pending_tasks = cursor.fetchall()
                
                dispatched_count = 0
                for row in pending_tasks:
                    task_id, doc_id, filename, task_type, priority = row['id'], row['document_id'], row['filename'], row['task_type'], row['priority']
                    if dispatched_count >= slots_available:
                        break
                    
                    # Verificar si este tipo de tarea ya alcanzó su límite
                    current_count = active_by_type.get(task_type.upper(), 0)
                    limit = task_limits.get(task_type, 5)
                    
                    if current_count >= limit:
                        if debug_mode:
                            logger.debug(f"⏸️  [{task_type}] Limit reached ({current_count}/{limit}), skipping")
                        continue
                    
                    # Asignar tarea a un worker genérico
                    worker_id = f"{task_type}_{os.getpid()}_{int(time.time() * 1000) % 100000}"
                    
                    try:
                        # CRITICAL: Para insights, necesitamos obtener news_item_id ANTES de assign_worker
                        # porque insights usa "insight_{news_item_id}" como document_id único para el semáforo
                        assign_doc_id = doc_id  # Default: usar doc_id
                        if task_type == TaskType.INSIGHTS:
                            cursor.execute("""
                                SELECT news_item_id FROM news_item_insights
                                WHERE document_id = %s AND status IN (%s, %s)
                                LIMIT 1
                            """, (doc_id, InsightStatus.PENDING, InsightStatus.QUEUED))
                            insights_row = cursor.fetchone()
                            if insights_row:
                                news_item_id = insights_row['news_item_id']
                                assign_doc_id = f"insight_{news_item_id}"  # Usar identificador único para insights
                            else:
                                cursor.execute("UPDATE processing_queue SET status = %s WHERE id = %s", (QueueStatus.COMPLETED, task_id))
                                conn.commit()
                                continue
                        
                        # CRITICAL: Primero intentar asignar worker (verifica duplicados atómicamente con SELECT FOR UPDATE)
                        # Esto actúa como semáforo centralizado - solo UN worker puede asignarse por documento/tarea
                        assigned = processing_queue_store.assign_worker(
                            worker_id, task_type.upper(), assign_doc_id, task_type
                        )
                        
                        if not assigned:
                            # Otro worker ya está procesando este documento - saltar (semáforo bloqueado)
                            logger.debug(f"⏸️  [{task_type}] Document {assign_doc_id} already assigned to another worker, skipping")
                            continue
                        
                        cursor.execute("""
                            UPDATE processing_queue
                            SET status = %s
                            WHERE id = %s
                        """, (QueueStatus.PROCESSING, task_id))
                        conn.commit()  # Commit la actualización de status
                        
                        _task_handlers = {
                            TaskType.OCR: lambda: asyncio.run(_ocr_worker_task(doc_id, filename, worker_id)),
                            TaskType.CHUNKING: lambda: asyncio.run(_chunking_worker_task(doc_id, filename, worker_id)),
                            TaskType.INDEXING: lambda: asyncio.run(_indexing_worker_task(doc_id, filename, worker_id)),
                        }

                        if task_type in _task_handlers:
                            from threading import Thread
                            worker_thread = Thread(
                                target=_task_handlers[task_type],
                                name=f"worker-{worker_id}",
                                daemon=True
                            )
                            worker_thread.start()
                            dispatched_count += 1
                        elif task_type == TaskType.INSIGHTS:
                            cursor.execute("""
                                SELECT news_item_id, title FROM news_item_insights
                                WHERE document_id = %s AND status IN (%s, %s)
                                LIMIT 1
                            """, (doc_id, InsightStatus.PENDING, InsightStatus.QUEUED))
                            insights_row = cursor.fetchone()
                            if insights_row:
                                news_item_id, title = insights_row
                                
                                from threading import Thread
                                worker_thread = Thread(
                                    target=lambda: asyncio.run(_insights_worker_task(news_item_id, doc_id, filename, title or '', worker_id)),
                                    name=f"worker-{worker_id}",
                                    daemon=True
                                )
                                worker_thread.start()
                                dispatched_count += 1
                            else:
                                cursor.execute("UPDATE processing_queue SET status = %s WHERE id = %s", (QueueStatus.COMPLETED, task_id))
                                conn.commit()
                                # assign_doc_id contiene "insight_{news_item_id}" que se obtuvo arriba
                                processing_queue_store.update_worker_status(
                                    worker_id, assign_doc_id, 'insights', 'error',
                                    error_message="No insights row found"
                                )
                                continue
                        else:
                            logger.warning(f"⚠️  [{task_type}] Unknown task type, marking as pending")
                            cursor.execute("UPDATE processing_queue SET status = %s WHERE id = %s", (QueueStatus.PENDING, task_id))
                            conn.commit()
                            continue
                        
                        logger.info(f"✅ [Master] Dispatched {task_type} worker {worker_id} for {filename}")
                        # Note: dispatched_count ya se incrementó arriba para cada tipo de tarea
                        active_by_type[task_type.upper()] = active_by_type.get(task_type.upper(), 0) + 1
                        
                    except Exception as dispatch_error:
                        logger.error(f"❌ [Master] Failed to dispatch {task_type} worker: {dispatch_error}")
                        cursor.execute("UPDATE processing_queue SET status = %s WHERE id = %s", (QueueStatus.PENDING, task_id))
                
                if dispatched_count > 0:
                    logger.info(f"🚀 [Master] Dispatched {dispatched_count} workers ({slots_available} slots available)")
            else:
                if debug_mode:
                    logger.debug(f"⏸️  [Master] All workers busy ({total_active}/{TOTAL_WORKERS})")
                        
        except Exception as e:
            logger.error(f"❌ Error dispatching workers: {e}")
            logger.error(traceback.format_exc())
        
        # Resumen
        total_created = len(pending_for_ocr) + len(ready_for_chunking) + len(ready_for_indexing) + len(ready_for_insights) + len(ready_for_completion)
        if total_created > 0:
            logger.info(f"📊 Master Pipeline Scheduler: Created {total_created} new tasks")
        elif debug_mode:
            logger.debug(f"🔄 [Master Pipeline] Cycle complete - no new tasks (pending_ocr={len(pending_for_ocr)}, chunking={len(ready_for_chunking)}, indexing={len(ready_for_indexing)}, insights={len(ready_for_insights)}, completed={len(ready_for_completion)})")

    except Exception as e:
        logger.error(f"❌ Error in master_pipeline_scheduler: {e}")
        logger.error(traceback.format_exc())
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


@app.on_event("startup")
async def startup_event():
    """Initialize services at startup"""
    global ocr_service, embeddings_service, rag_pipeline, qdrant_connector

    logger.info("=" * 80)
    logger.info("🚀 STARTING RAG BACKEND")
    logger.info("=" * 80)
    logger.info(f"Configuration:")
    logger.info(f"  - LLM Provider: {LLM_PROVIDER}")
    logger.info(f"  - LLM Model: {LLM_MODEL}")
    if LLM_PROVIDER == "openai":
        logger.info(f"  - OpenAI API Key: {'***' + OPENAI_API_KEY[-4:] if OPENAI_API_KEY else 'NOT SET'}")
    else:
        logger.info(f"  - OLLAMA: {OLLAMA_BASE_URL}")
    logger.info(f"  - QDRANT: {QDRANT_HOST}:{QDRANT_PORT}")
    logger.info(f"  - Embedding: {EMBEDDING_MODEL}")
    logger.info(f"  - Relevance Threshold: {RELEVANCE_THRESHOLD}")
    logger.info(f"  - Upload Dir: {UPLOAD_DIR}")
    logger.info(f"  - CUDA Devices: {CUDA_VISIBLE_DEVICES}")
    if INBOX_DIR:
        logger.info(f"  - Inbox Dir: {INBOX_DIR} (escaneo al arranque y cada 5 min)")
    logger.info("=" * 80)
    
    try:
        # 1. Qdrant Connection
        logger.info("🔗 [1/6] Connecting to Qdrant...")
        qdrant_connector = QdrantConnector(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            api_key=QDRANT_API_KEY if QDRANT_API_KEY else None
        )
        qdrant_connector.connect()
        logger.info("✅ Qdrant connected")

        # 2. OCR Service
        logger.info("🔗 [2/6] Loading OCR Service...")
        try:
            ocr_service = get_ocr_service()
            logger.info("✅ OCR Service ready")
        except Exception as e:
            logger.warning(f"⚠️  OCR Service failed: {e}")
            logger.warning("    → System will continue without OCR")
            ocr_service = None

        # 3. Embedding Service
        logger.info(f"🔗 [3/6] Loading Embedding Service ({EMBEDDING_MODEL})...")
        embeddings_service = EmbeddingsService(model_name=EMBEDDING_MODEL)
        logger.info("✅ Embedding Service ready")

        # 4. LLM Provider setup
        if LLM_PROVIDER == "openai":
            logger.info(f"🔗 [4/6] Using OpenAI API (model: {LLM_MODEL})...")
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai. Set it in .env")
            logger.info("✅ OpenAI API key configured")
        else:
            logger.info(f"🔗 [4/6] Connecting to Ollama ({OLLAMA_BASE_URL})...")
            wait_for_ollama(OLLAMA_BASE_URL, timeout=300)
            ensure_model(OLLAMA_BASE_URL, LLM_MODEL)

        # 5. RAG Pipeline
        logger.info(f"🔗 [5/6] Initializing RAG Pipeline (provider: {LLM_PROVIDER}, model: {LLM_MODEL})...")
        rag_pipeline = RAGPipeline(
            qdrant_connector=qdrant_connector,
            embeddings_service=embeddings_service,
            llm_model=LLM_MODEL,
            ollama_base_url=OLLAMA_BASE_URL,
            relevance_threshold=RELEVANCE_THRESHOLD,
            llm_provider=LLM_PROVIDER,
            openai_api_key=OPENAI_API_KEY,
        )
        logger.info("✅ RAG Pipeline ready")

        # 6. Backup Scheduler
        logger.info("🔗 [6/6] Starting Backup Scheduler...")
        backup_scheduler.start()
        logger.info("✅ Backup Scheduler ready")
        if INBOX_DIR:
            if ocr_service and rag_pipeline:
                backup_scheduler.add_inbox_job(INBOX_DIR, run_inbox_scan, interval_minutes=5)
                # Primer escaneo retrasado 60 s para que Tika y el pipeline estén estables (evita saturar Tika con muchos workers a la vez)
                import threading
                def run_inbox_after_delay():
                    time.sleep(60)
                    run_inbox_scan()
                threading.Thread(target=run_inbox_after_delay, name="inbox_scan_startup", daemon=True).start()
                logger.info("  - Inbox: primer escaneo en 60 s; luego cada 5 min")
            else:
                logger.warning("⚠️  INBOX_DIR set but services not ready - inbox scan disabled")

        if rag_pipeline and qdrant_connector:
            backup_scheduler.add_daily_report_job(run_daily_report_job, hour=23, minute=0)
            backup_scheduler.add_weekly_report_job(run_weekly_report_job, day_of_week=0, hour=6, minute=0)
        
        if INSIGHTS_QUEUE_ENABLED:
            logger.info("✅ Insights queue enabled (workers handle via pool, no scheduler needed)")
        
        # OCR processing: workers from pool handle via semaphore
        if ocr_service and rag_pipeline:
            logger.info("✅ OCR processing enabled (workers handle via pool, no scheduler needed)")
        
        # Master Pipeline Scheduler - Orquesta TODO (cada 10 segundos para testing)
        import sys
        print("\n\n🔄 ===== STARTING MASTER PIPELINE SCHEDULER ===== 🔄\n", flush=True)
        sys.stdout.flush()
        logger.info("🔄 Starting Master Pipeline Scheduler (every 10 seconds)...")
        try:
            backup_scheduler.add_job(
                master_pipeline_scheduler,
                trigger_type='interval',
                job_id='master_pipeline_job',
                seconds=10
            )
            logger.info("✅ Master Pipeline Scheduler initialized")
            print("✅ ===== MASTER PIPELINE SCHEDULER REGISTERED ===== ✅\n", flush=True)
        except Exception as e:
            logger.error(f"❌ Failed to initialize Master Pipeline Scheduler: {e}")
            logger.error(traceback.format_exc())
            print(f"❌ ERROR REGISTERING MASTER PIPELINE: {e}\n", flush=True)

        # Workers Health Check - Auto-restart workers if needed (every 30 seconds)
        print("\n\n🏥 ===== STARTING WORKERS HEALTH CHECK ===== 🏥\n", flush=True)
        sys.stdout.flush()
        logger.info("🏥 Starting Workers Health Check (every 30 seconds)...")
        try:
            backup_scheduler.add_job(
                workers_health_check,
                trigger_type='interval',
                job_id='workers_health_check_job',
                seconds=30
            )
            logger.info("✅ Workers Health Check initialized")
            print("✅ ===== WORKERS HEALTH CHECK REGISTERED ===== ✅\n", flush=True)
        except Exception as e:
            logger.error(f"❌ Failed to initialize Workers Health Check: {e}")
            logger.error(traceback.format_exc())
            print(f"❌ ERROR REGISTERING WORKERS HEALTH CHECK: {e}\n", flush=True)

        # Initialize worker pools (persistent workers that listen to DB semaphore)
        # COMMENTED OUT: Workers will be started later via lazy initialization to avoid DB contention at startup
        # logger.info("👷 Initializing worker pools...")
        # from worker_pool import WorkerPool
        # 
        # # OCR worker pool
        # if ocr_service and rag_pipeline:
        #     global ocr_pool
        #     ocr_pool = WorkerPool(
        #         worker_type='ocr',
        #         pool_size=2,  # 2 persistent OCR workers
        #         worker_task_func=_ocr_worker_task,
        #         db_connection_factory=document_status_store.get_connection
        #     )
        #     ocr_pool.start()
        # 
        # # Insights worker pool
        # if INSIGHTS_QUEUE_ENABLED and rag_pipeline:
        #     global insights_pool
        #     insights_pool = WorkerPool(
        #         worker_type='insights',
        #         pool_size=2,  # 2 persistent Insights workers
        #         worker_task_func=_insights_worker_task,
        #         db_connection_factory=document_status_store.get_connection
        #     )
        #     insights_pool.start()
        # 
        # logger.info("✅ Worker pools initialized")
        
        # STARTUP RECOVERY (must run before queue seeding)
        # Cleans orphaned worker_tasks, processing_queue, document_status,
        # and insights left by a previous crash/restart.
        logger.info("🔄 Running startup recovery (orphaned task cleanup)...")
        await detect_crashed_workers()
        
        # Seed processing queue for any upload_pending documents
        logger.info("📋 Seeding processing queue...")
        _initialize_processing_queue()

        logger.info("=" * 80)
        logger.info("🎉 BACKEND FULLY INITIALIZED")
        logger.info("=" * 80)

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ ERROR DURING STARTUP: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup at shutdown"""
    logger.info("🛑 Shutting down RAG Backend...")
    backup_scheduler.stop()
    if qdrant_connector:
        qdrant_connector.disconnect()
        logger.info("✅ Cleanup completed")


def run_daily_report_job():
    """Scheduled job: generate daily report for today (by news_date)."""
    from datetime import date
    generate_daily_report_for_date(date.today().isoformat())


def generate_daily_report_for_date(report_date: str) -> bool:
    """
    Generate (or regenerate) the daily report for report_date (YYYY-MM-DD) using documents
    whose news_date equals report_date. Saves to daily_report_store; on replace, updated_at is set.
    Returns True if a report was saved, False if no indexed documents for that date (or error).
    """
    if not qdrant_connector or not rag_pipeline:
        logger.warning("Daily report: Qdrant or RAG pipeline not ready, skipping")
        return False
    doc_ids = document_status_store.get_document_ids_by_news_date(report_date)
    if not doc_ids:
        logger.info(f"Daily report: no indexed documents for news_date={report_date}, skipping")
        return False
    try:
        chunks = qdrant_connector.get_chunks_by_document_ids(doc_ids, max_chunks=2000)
        if not chunks:
            logger.warning(f"Daily report: no chunks retrieved for {report_date}")
            return False
        by_doc = {}
        for c in chunks:
            fid = c.get("document_id", "")
            fname = c.get("filename", "unknown")
            if fid not in by_doc:
                by_doc[fid] = {"filename": fname, "texts": []}
            by_doc[fid]["texts"].append(c.get("text", ""))
        context_parts = []
        for doc_id, data in by_doc.items():
            context_parts.append(f"[{data['filename']}]\n" + "\n".join(data["texts"]))
        context = "\n\n---\n\n".join(context_parts)
        if len(context) > 120000:
            context = context[:120000] + "\n\n[... texto recortado por límite ...]"
        content = rag_pipeline.generate_report_from_context(context, report_date)
        daily_report_store.insert(report_date, content)
        notification_store.insert("daily", report_date, message=f"Reporte del {report_date} actualizado")
        logger.info(f"Daily report generated for {report_date}")
        return True
    except Exception as e:
        logger.error(f"Daily report generation failed for {report_date}: {e}", exc_info=True)
        return False


def run_weekly_report_job():
    """Scheduled job: generate weekly report for previous week (Monday–Sunday)."""
    from datetime import date, timedelta
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    generate_weekly_report_for_week(last_monday.isoformat())


def generate_weekly_report_for_week(week_start: str) -> bool:
    """Generate weekly report for week starting week_start (Monday YYYY-MM-DD). Week = week_start to week_start+6 days."""
    if not qdrant_connector or not rag_pipeline:
        logger.warning("Weekly report: Qdrant or RAG pipeline not ready, skipping")
        return False
    from datetime import datetime as dt, timedelta
    try:
        start = dt.strptime(week_start, "%Y-%m-%d").date()
    except ValueError:
        logger.warning(f"Weekly report: invalid week_start {week_start}")
        return False
    end = start + timedelta(days=6)
    week_end = end.isoformat()
    doc_ids = document_status_store.get_document_ids_by_news_date_range(week_start, week_end)
    if not doc_ids:
        logger.info(f"Weekly report: no indexed documents for week {week_start}–{week_end}, skipping")
        return False
    try:
        chunks = qdrant_connector.get_chunks_by_document_ids(doc_ids, max_chunks=3000)
        if not chunks:
            return False
        by_doc = {}
        for c in chunks:
            fid = c.get("document_id", "")
            fname = c.get("filename", "unknown")
            if fid not in by_doc:
                by_doc[fid] = {"filename": fname, "texts": []}
            by_doc[fid]["texts"].append(c.get("text", ""))
        context_parts = [f"[{d['filename']}]\n" + "\n".join(d["texts"]) for d in by_doc.values()]
        context = "\n\n---\n\n".join(context_parts)
        if len(context) > 150000:
            context = context[:150000] + "\n\n[... texto recortado ...]"
        content = rag_pipeline.generate_weekly_report_from_context(context, week_start, week_end)
        weekly_report_store.insert(week_start, content)
        notification_store.insert("weekly", week_start, message=f"Reporte semanal ({week_start}) actualizado")
        logger.info(f"Weekly report generated for week {week_start}–{week_end}")
        return True
    except Exception as e:
        logger.error(f"Weekly report failed for {week_start}: {e}", exc_info=True)
        return False


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5
    temperature: float = 0.0  # 0.0 = completely deterministic, eliminates variability in responses


class SourceInfo(BaseModel):
    filename: str
    document_id: str
    similarity_score: float
    chunk_index: Optional[int] = None
    text: Optional[str] = None 


class QueryResponse(BaseModel):
    answer: str
    sources: List[SourceInfo]
    processing_time: float
    num_sources: int


class DocumentMetadata(BaseModel):
    filename: str
    upload_date: str
    document_id: str
    num_chunks: int
    status: str
    source: Optional[str] = None
    indexed_at: Optional[str] = None
    error_message: Optional[str] = None
    news_date: Optional[str] = None  # Fecha de la noticia (YYYY-MM-DD), inferida del nombre
    processing_stage: Optional[str] = None  # "ocr" | "chunking" | "indexing" mientras status=processing
    insights_status: Optional[str] = None   # pending | queued | generating | done | error
    insights_progress: Optional[str] = None # "0/1" o "1/1" para barra de estado


class DocumentsListResponse(BaseModel):
    documents: List[DocumentMetadata]
    total: int
    insights_summary: Optional[dict] = None  # { total_indexed, with_insights_done } para barra global


class DocumentStatusItem(BaseModel):
    """Modelo para el endpoint /api/documents/status usado por DocumentsTable.jsx"""
    document_id: str
    filename: str
    status: str
    uploaded_at: str
    news_items_count: int = 0
    insights_done: int = 0
    insights_total: int = 0


class HealthResponse(BaseModel):
    status: str
    backend_version: str
    qdrant_connected: bool
    services: dict
    configuration: dict


# ============================================================================
# HEALTH & INFO ENDPOINTS
# ============================================================================

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    all_ready = all([ocr_service, embeddings_service, rag_pipeline, qdrant_connector])
    
    return HealthResponse(
        status="healthy" if all_ready else "degraded",
        backend_version="1.0.0",
        qdrant_connected=qdrant_connector.is_connected() if qdrant_connector else False,
        services={
            "ocr": ocr_service is not None,
            "embeddings": embeddings_service is not None,
            "rag_pipeline": rag_pipeline is not None,
            "qdrant": qdrant_connector is not None
        },
        configuration={
            "llm_provider": LLM_PROVIDER,
            "llm_model": LLM_MODEL,
            "embedding_model": EMBEDDING_MODEL,
            "relevance_threshold": RELEVANCE_THRESHOLD,
        }
    )


@app.get("/info")
async def get_info():
    """Configuration information"""
    return {
        "backend": "RAG Enterprise v1.0.0",
        "qdrant": f"{QDRANT_HOST}:{QDRANT_PORT}",
        "llm_model": LLM_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "cuda_devices": CUDA_VISIBLE_DEVICES,
        "relevance_threshold": RELEVANCE_THRESHOLD,
    }


# ============================================================================
# AUTHENTICATION ENDPOINTS
# ============================================================================

@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    User login - returns JWT token

    Default credentials:
    - Admin: username=admin, password=<from logs or ADMIN_DEFAULT_PASSWORD env var>
    - Get password: docker compose logs backend | grep "Password:"
    """
    user = db.authenticate_user(request.username, request.password)

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Incorrect username or password"
        )

    # Create JWT token
    token = create_user_token(user)

    logger.info(f"✅ Login successful: {user['username']} (role: {user['role']})")

    # Convert datetime objects to strings for response
    created_at = user["created_at"]
    if isinstance(created_at, datetime):
        created_at = created_at.isoformat()
    
    last_login = user.get("last_login")
    if isinstance(last_login, datetime):
        last_login = last_login.isoformat()

    return LoginResponse(
        access_token=token,
        token_type="bearer",
        user=UserInfo(
            id=user["id"],
            username=user["username"],
            email=user["email"],
            role=user["role"],
            created_at=created_at,
            last_login=last_login
        )
    )


@app.get("/api/auth/me", response_model=UserInfo)
async def get_current_user_info(current_user: CurrentUser = Depends(get_current_user)):
    """Get current user information"""
    user = db.get_user_by_id(current_user.user_id)

    return UserInfo(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        created_at=user["created_at"],
        last_login=user.get("last_login")
    )


@app.get("/api/auth/users", response_model=UserListResponse)
async def list_users(current_user: CurrentUser = Depends(require_admin)):
    """List all users (ADMIN only)"""
    users = db.list_users()

    return UserListResponse(
        users=[
            UserInfo(
                id=u["id"],
                username=u["username"],
                email=u["email"],
                role=u["role"],
                created_at=u["created_at"],
                last_login=u.get("last_login")
            )
            for u in users
        ],
        total=len(users)
    )


@app.post("/api/auth/users", response_model=UserInfo)
async def create_user(
    user_data: UserCreate,
    current_user: CurrentUser = Depends(require_admin)
):
    """Create new user (ADMIN only)"""
    user_id = db.create_user(
        username=user_data.username,
        email=user_data.email,
        password=user_data.password,
        role=user_data.role
    )

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="User creation error (username or email already exists)"
        )

    user = db.get_user_by_id(user_id)

    return UserInfo(
        id=user["id"],
        username=user["username"],
        email=user["email"],
        role=user["role"],
        created_at=user["created_at"],
        last_login=user.get("last_login")
    )


@app.put("/api/auth/users/{user_id}", response_model=MessageResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    current_user: CurrentUser = Depends(require_admin)
):
    """Update user (ADMIN only)"""
    if user_data.role:
        success = db.update_user_role(user_id, user_data.role)
        if not success:
            raise HTTPException(status_code=404, detail="User not found")

    return MessageResponse(message=f"User {user_id} updated")


@app.delete("/api/auth/users/{user_id}", response_model=MessageResponse)
async def delete_user(
    user_id: int,
    current_user: CurrentUser = Depends(require_admin)
):
    """Delete user (ADMIN only)"""
    # Don't allow self-deletion
    if user_id == current_user.user_id:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own account"
        )

    success = db.delete_user(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")

    return MessageResponse(message=f"User {user_id} deleted")


@app.post("/api/auth/change-password", response_model=MessageResponse)
async def change_password(
    request: PasswordChange,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Change current user's password"""
    user = db.get_user_by_id(current_user.user_id)

    # Verify old password
    if not db.verify_password(request.old_password, user["password_hash"]):
        raise HTTPException(
            status_code=400,
            detail="Current password is incorrect"
        )

    # Change password
    success = db.change_password(current_user.user_id, request.new_password)

    if not success:
        raise HTTPException(status_code=500, detail="Password change error")

    logger.info(f"✅ Password changed for user: {current_user.username}")

    return MessageResponse(message="Password changed successfully")


# ============================================================================
# DOCUMENT MANAGEMENT
# ============================================================================

# Supported formats
ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
    '.odt', '.rtf', '.html', '.xml', '.json', '.csv', '.md',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp'
}

@app.post("/api/documents/upload")
async def upload_document(
    file: UploadFile = File(...),
    background_tasks: BackgroundTasks = None,
    current_user: CurrentUser = Depends(require_upload_permission)
):
    """
    Upload a document (any format) and process it in the background
    Supported formats: PDF, DOCX, PPTX, XLSX, ODT, RTF, HTML, XML, JSON, CSV, Images

    Requires: SUPER_USER or ADMIN role
    """

    if not ocr_service or not embeddings_service or not rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="Services not initialized. Check /health"
        )

    # Check file extension
    from pathlib import Path
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format '{file_ext}' not supported. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Check file size before reading entire content
    # First read content to check size
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)

    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {file_size_mb:.1f}MB. Maximum allowed: {MAX_UPLOAD_SIZE_MB}MB"
        )

    try:
        # Calculate SHA256 hash for deduplication
        file_hash = hashlib.sha256(content).hexdigest()
        
        # Check if file already exists (by hash)
        existing_doc = document_status_store.find_by_hash(file_hash)
        if existing_doc:
            logger.info(f"📋 Duplicate detected: '{file.filename}' already exists as '{existing_doc['filename']}'")
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Duplicate file detected, not reprocessed",
                    "status": "duplicate",
                    "existing_document_id": existing_doc['document_id'],
                    "existing_filename": existing_doc['filename'],
                    "file_hash": file_hash
                }
            )
        
        # Create document_id with timestamp FIRST
        document_id = f"{datetime.now().timestamp()}_{file.filename}"
        file_path = os.path.join(UPLOAD_DIR, document_id)
        # Note: content was already read above for size validation

        # Save file with the document_id (with timestamp)
        with open(file_path, "wb") as f:
            f.write(content)

        document_status_store.insert(
            document_id, file.filename, "upload", DocStatus.UPLOAD_PROCESSING,
            news_date=parse_news_date_from_filename(file.filename),
            file_hash=file_hash,
        )

        logger.info(f"📄 File received: '{file.filename}' ({len(content)} bytes)")
        logger.info(f"   Document ID: {document_id}")
        logger.info(f"   File path: {file_path}")
        logger.info(f"   File hash: {file_hash[:16]}...")

        # Add background task
        background_tasks.add_task(
            _process_document_sync,
            file_path,
            document_id,
            file.filename
        )

        return JSONResponse(
            status_code=202,
            content={
                "message": "Document received, processing in progress",
                "document_id": document_id,
                "filename": file.filename,
                "size_bytes": len(content),
                "file_hash": file_hash
            }
        )

    except Exception as e:
        logger.error(f"❌ Upload error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


def _extract_ocr_only(file_path: str, document_id: str, filename: str) -> tuple[str, str, Optional[str]]:
    """Extract text via OCR. Returns (text, doc_type, content_hash)."""
    text = ""
    doc_type = "unknown"
    content_hash = None
    
    try:
        # Compute content hash
        try:
            with open(file_path, "rb") as fh:
                file_bytes = fh.read()
            content_hash = hashlib.sha256(file_bytes).hexdigest()
            logger.info(f"Content hash for {filename}: {content_hash}")
        except Exception as hash_err:
            logger.warning(f"Could not compute content hash for {filename}: {hash_err}")
        
        # Extract text via OCR
        logger.info(f"  [OCR] Extracting text...")
        start_ocr = datetime.now()
        
        try:
            text = ocr_service.extract_text(file_path)
            doc_type = detect_document_type(text)
            structured_fields = extract_structured_fields(text, doc_type)
            logger.info(f"Document Type: {doc_type}")
            logger.info(f"Structured Fields: {structured_fields}")
        except Exception as e:
            logger.error(f"❌ OCR FAILED: {str(e)}", exc_info=True)
            raise
        
        ocr_time = (datetime.now() - start_ocr).total_seconds()
        logger.info(f"✅ Extracted {len(text)} characters in {ocr_time:.2f}s")
        
        if not text or len(text.strip()) == 0:
            raise ValueError("OCR returned empty text")
        
        return text, doc_type, content_hash
        
    except Exception as e:
        logger.error(f"OCR extraction failed for {filename}: {e}")
        raise


def _perform_chunking(text: str, document_id: str, filename: str, doc_type: str) -> list:
    """Perform text segmentation and chunking. Returns list of chunk records."""
    chunk_records = []
    
    try:
        logger.info(f"  [CHUNKING] Segmenting and chunking...")
        start_chunk = datetime.now()
        
        items = segment_news_items_from_text(text)
        if not items:
            raise ValueError("No news items detected in text")
        
        now_iso = datetime.utcnow().isoformat()
        for idx, it in enumerate(items):
            title = (it.get("title") or f"Noticia {idx + 1}").strip()
            body = it.get("text") or ""
            body_norm = _normalize_text_for_hash(body)
            text_hash = hashlib.sha256(body_norm.encode("utf-8")).hexdigest() if body_norm else None
            
            news_item_id = f"{document_id}::{idx}"
            item_chunks = rag_pipeline.chunk_text(body, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
            for j, ch in enumerate(item_chunks):
                chunk_records.append({
                    "document_id": document_id,
                    "filename": filename,
                    "upload_date": now_iso,
                    "chunk_index": j,
                    "news_item_id": news_item_id,
                    "news_title": title,
                    "news_item_index": idx,
                    "news_item_chunk_index": j,
                    "text": ch,
                    "chunk_size": len(ch),
                    "document_type": doc_type,
                    "structured_fields": str(extract_structured_fields(text, doc_type)),
                })
        
        # Persist items metadata in SQLite
        news_item_store.upsert_items(
            document_id=document_id,
            filename=filename,
            items=[{
                "news_item_id": f"{document_id}::{i}",
                "item_index": i,
                "title": (items[i].get("title") or f"Noticia {i + 1}").strip(),
                "status": DocStatus.INDEXING_DONE,
                "text_hash": hashlib.sha256(_normalize_text_for_hash(items[i].get("text") or "").encode("utf-8")).hexdigest()
                if _normalize_text_for_hash(items[i].get("text") or "") else None,
            } for i in range(len(items))],
        )
        
        chunk_time = (datetime.now() - start_chunk).total_seconds()
        logger.info(f"✅ Created {len(chunk_records)} chunk records in {chunk_time:.2f}s")
        
        return chunk_records
        
    except Exception as e:
        logger.error(f"Chunking failed for {filename}: {e}")
        raise


def _perform_indexing(chunk_records: list, document_id: str, filename: str) -> None:
    """Index chunk records into Qdrant."""
    try:
        logger.info(f"  [INDEXING] Embedding and indexing {len(chunk_records)} chunks...")
        start_index = datetime.now()
        
        rag_pipeline.index_chunk_records(chunk_records)
        
        index_time = (datetime.now() - start_index).total_seconds()
        logger.info(f"✅ Indexed on Qdrant in {index_time:.2f}s")
        
    except Exception as e:
        logger.error(f"Indexing failed for {filename}: {e}")
        raise


def _process_document_sync(file_path: str, document_id: str, filename: str):
    """Sync document processing (OCR → chunk → index). Used by upload and inbox scan."""
    text = None
    chunks = None
    chunk_records = None
    content_hash: Optional[str] = None
    try:
        document_status_store.update_status(document_id, DocStatus.OCR_PROCESSING, processing_stage=Stage.OCR)

        logger.info("=" * 80)
        logger.info(f"📇 PROCESSING START: {filename}")
        logger.info(f"   Document ID: {document_id}")
        logger.info(f"   File path: {file_path}")
        logger.info("=" * 80)

        # Compute content hash once (para deduplicar insights entre archivos idénticos)
        try:
            with open(file_path, "rb") as fh:
                file_bytes = fh.read()
            content_hash = hashlib.sha256(file_bytes).hexdigest()
            logger.info(f"Content hash for {filename}: {content_hash}")
        except Exception as hash_err:
            logger.warning(f"Could not compute content hash for {filename}: {hash_err}")
            content_hash = None

        # STEP 1: OCR Extraction
        logger.info(f"  [1/3] OCR Extraction...")
        start_ocr = datetime.now()

        try:
            text = ocr_service.extract_text(file_path)

            # NEW: Detect document type and extract structured fields
            doc_type = detect_document_type(text)
            structured_fields = extract_structured_fields(text, doc_type)

            logger.info(f"Document Type: {doc_type}")
            logger.info(f"Structured Fields: {structured_fields}")
            
            # Store OCR text in database for diagnostic purposes
            document_status_store.store_ocr_text(document_id, text)
        except Exception as e:
            logger.error(f"      ❌ OCR FAILED: {str(e)}", exc_info=True)
            text = ""

        ocr_time = (datetime.now() - start_ocr).total_seconds()
        logger.info(f"        ✅ Extracted {len(text)} characters in {ocr_time:.2f}s")

        if not text or len(text.strip()) == 0:
            logger.warning(f"⚠️  WARNING: OCR returned empty text!")
            document_status_store.update_status(document_id, DocStatus.ERROR, error_message="OCR returned empty text")
            return
        
        # STEP 2: Segmentación en noticias + chunking
        document_status_store.update_status(document_id, DocStatus.CHUNKING_PROCESSING, processing_stage=Stage.CHUNKING)
        logger.info(f"  [2/3] News segmentation + chunking...")
        start_chunk = datetime.now()

        try:
            items = segment_news_items_from_text(text)
            if not items:
                document_status_store.update_status(document_id, DocStatus.ERROR, error_message="No news items detected")
                return

            # STEP 2.1: Check for existing items by text_hash to avoid duplicates on reprocessing
            existing_items_by_hash = {}
            existing_items = news_item_store.list_by_document_id(document_id)
            for existing in existing_items:
                if existing.get("text_hash"):
                    existing_items_by_hash[existing["text_hash"]] = existing
            
            logger.info(f"   Found {len(existing_items)} existing news items for this document")
            
            # Build chunk records across all items (index in one embedding batch)
            chunk_records = []
            now_iso = datetime.utcnow().isoformat()
            items_to_upsert = []
            new_items_count = 0
            reused_items_count = 0
            
            for idx, it in enumerate(items):
                title = (it.get("title") or f"Noticia {idx + 1}").strip()
                body = it.get("text") or ""
                body_norm = _normalize_text_for_hash(body)
                text_hash = hashlib.sha256(body_norm.encode("utf-8")).hexdigest() if body_norm else None

                # Check if this item already exists (by text_hash)
                if text_hash and text_hash in existing_items_by_hash:
                    # Item already exists - reuse the existing news_item_id
                    existing_item = existing_items_by_hash[text_hash]
                    news_item_id = existing_item["news_item_id"]
                    reused_items_count += 1
                    logger.debug(f"   ♻️  Reusing existing item: {news_item_id} (hash: {text_hash[:16]}...)")
                else:
                    # New item - generate new ID
                    news_item_id = f"{document_id}::{idx}"
                    new_items_count += 1
                    logger.debug(f"   ✨ New item: {news_item_id} (hash: {text_hash[:16] if text_hash else 'N/A'}...)")
                
                # Store item for upsert
                items_to_upsert.append({
                    "news_item_id": news_item_id,
                    "item_index": idx,
                    "title": title,
                    "status": DocStatus.INDEXING_DONE,
                    "text_hash": text_hash,
                })
                
                item_chunks = rag_pipeline.chunk_text(body, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP)
                for j, ch in enumerate(item_chunks):
                    chunk_records.append(
                        {
                            "document_id": document_id,
                            "filename": filename,
                            "upload_date": now_iso,
                            "chunk_index": j,
                            "news_item_id": news_item_id,  # Use the correct ID (reused or new)
                            "news_title": title,
                            "news_item_index": idx,
                            "news_item_chunk_index": j,
                            "text": ch,
                            "chunk_size": len(ch),
                            "document_type": doc_type,
                            "structured_fields": str(structured_fields),
                        }
                    )
            
            logger.info(f"   📊 Items summary: {new_items_count} new, {reused_items_count} reused (total: {len(items_to_upsert)})")
            
            # Persist items metadata in SQLite
            news_item_store.upsert_items(
                document_id=document_id,
                filename=filename,
                items=items_to_upsert,
            )
        except Exception as e:
            logger.error(f"      ❌ CHUNKING FAILED: {str(e)}", exc_info=True)
            document_status_store.update_status(document_id, DocStatus.ERROR, error_message=f"Chunking failed: {e}")
            return

        chunk_time = (datetime.now() - start_chunk).total_seconds()
        logger.info(f"        ✅ {len(chunk_records or [])} chunk record(s) created in {chunk_time:.2f}s")

        if not chunk_records:
            logger.error(f"❌ ERROR: No chunks created!")
            document_status_store.update_status(document_id, DocStatus.ERROR, error_message="No chunks created")
            return
        
        # STEP 3: Embedding & Indexing
        document_status_store.update_status(document_id, DocStatus.INDEXING_PROCESSING, processing_stage=Stage.INDEXING)
        logger.info(f"  [3/3] Embedding & Indexing...")
        start_index = datetime.now()

        try:
            rag_pipeline.index_chunk_records(chunk_records)
        except Exception as e:
            logger.error(f"      ❌ INDEXING FAILED: {str(e)}", exc_info=True)
            document_status_store.update_status(document_id, DocStatus.ERROR, error_message=f"Indexing failed: {e}")
            return

        index_time = (datetime.now() - start_index).total_seconds()
        logger.info(f"        ✅ Indexed on Qdrant in {index_time:.2f}s")

        # SUMMARY
        total_time = (datetime.now() - start_ocr).total_seconds()
        logger.info("=" * 80)
        logger.info(f"✅ PROCESSING COMPLETED: {filename}")
        logger.info(f"   Total time: {total_time:.2f}s")
        logger.info(f"   - OCR: {ocr_time:.2f}s")
        logger.info(f"   - Chunking: {chunk_time:.2f}s")
        logger.info(f"   - Indexing: {index_time:.2f}s")
        logger.info(f"   Chunks: {len(chunk_records) if chunk_records is not None else 0}")
        logger.info(f"   Characters: {len(text)}")
        logger.info("=" * 80)

        document_status_store.update_status(
            document_id,
            DocStatus.INDEXING_DONE,
            indexed_at=datetime.utcnow().isoformat(),
            num_chunks=len(chunk_records),
            news_date=parse_news_date_from_filename(filename),
            processing_stage=Stage.INDEXING,
        )
        news_date = parse_news_date_from_filename(filename)
        if news_date and not INGEST_DEFER_REPORT_GENERATION:
            try:
                do_generate = True
                if INGEST_REPORT_THROTTLE_MINUTES > 0:
                    now = datetime.utcnow()
                    last = _last_daily_report_by_date.get(news_date)
                    if last and (now - last).total_seconds() < INGEST_REPORT_THROTTLE_MINUTES * 60:
                        do_generate = False
                        logger.info(f"Report throttle: skip daily report for {news_date} (last generated {int((now - last).total_seconds() / 60)} min ago)")
                    else:
                        _last_daily_report_by_date[news_date] = now
                if do_generate:
                    generate_daily_report_for_date(news_date)
            except Exception as report_err:
                logger.warning(f"Report generation after index failed: {report_err}")

        if INSIGHTS_QUEUE_ENABLED and rag_pipeline:
            try:
                # Encolar insights por noticia (news_item_id). Dedupe por text_hash del item.
                items = news_item_store.list_by_document_id(document_id)
                for it in items:
                    nid = it["news_item_id"]
                    title = it.get("title") or ""
                    item_index = int(it.get("item_index") or 0)
                    text_hash = it.get("text_hash") or None

                    existing = news_item_insights_store.get_done_by_text_hash(text_hash) if text_hash else None
                    news_item_insights_store.enqueue(
                        news_item_id=nid,
                        document_id=document_id,
                        filename=filename,
                        item_index=item_index,
                        title=title,
                        text_hash=text_hash,
                    )
                    if existing and existing.get("content"):
                        news_item_insights_store.set_status(nid, news_item_insights_store.STATUS_DONE, content=existing.get("content"))
                        logger.info(f"News item insights reused for {nid} ({title})")
                logger.info(f"News item insights queued/reused for {len(items)} item(s)")
            except Exception as eq_err:
                logger.warning(f"News item insights enqueue/reuse failed: {eq_err}")

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ CRITICAL PROCESSING ERROR {filename}: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        document_status_store.update_status(document_id, DocStatus.ERROR, error_message=str(e))

    finally:
        # 🧹 CRITICAL: Memory cleanup to prevent OOM on next upload
        logger.info("🧹 Cleaning up memory...")

        # Delete large variables
        if text is not None:
            del text
        if chunks is not None:
            del chunks
        if chunk_records is not None:
            del chunk_records

        # Force Python garbage collection
        gc.collect()

        # Clear GPU memory
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            allocated = torch.cuda.memory_allocated() / 1024**3
            logger.info(f"   GPU memory after cleanup: {allocated:.2f}GB")

        logger.info("✅ Memory cleanup completed")


def run_insights_queue_job():
    """Process one document from the insights queue (LLM report per file). Retry with backoff on 429."""
    if not INSIGHTS_QUEUE_ENABLED or not rag_pipeline or not qdrant_connector:
        return
    pending = document_insights_store.get_next_pending(limit=1)
    if not pending:
        return
    row = pending[0]
    document_id = row["document_id"]
    filename = row["filename"]
    document_insights_store.set_status(document_id, document_insights_store.STATUS_GENERATING)
    try:
        chunks = qdrant_connector.get_chunks_by_document_ids([document_id], max_chunks=500)
        if not chunks:
            document_insights_store.set_status(document_id, document_insights_store.STATUS_ERROR, error_message="No chunks")
            return
        by_doc = {}
        for c in chunks:
            fid = c.get("document_id", "")
            if fid not in by_doc:
                by_doc[fid] = []
            by_doc[fid].append(c.get("text", ""))
        context = "\n\n".join(by_doc.get(document_id, []))
        if len(context) > 80000:
            context = context[:80000] + "\n\n[... truncado ...]"
        for attempt in range(INSIGHTS_MAX_RETRIES):
            try:
                content = rag_pipeline.generate_insights_from_context(context, filename)
                document_insights_store.set_status(document_id, document_insights_store.STATUS_DONE, content=content)
                logger.info(f"Insights generated for {filename}")
                return
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait = INSIGHTS_THROTTLE_SECONDS * (2 ** attempt)
                    logger.warning(f"Insights 429 for {filename}, waiting {wait}s (attempt {attempt + 1}/{INSIGHTS_MAX_RETRIES})")
                    time.sleep(wait)
                else:
                    raise
        document_insights_store.set_status(document_id, document_insights_store.STATUS_ERROR, error_message="Max retries (429)")
    except Exception as e:
        logger.error(f"Insights generation failed for {filename}: {e}", exc_info=True)
        document_insights_store.set_status(document_id, document_insights_store.STATUS_ERROR, error_message=str(e))


def run_news_item_insights_queue_job():
    """Process one news item from the insights queue (LLM report per noticia). Retry with backoff on 429."""
    if not INSIGHTS_QUEUE_ENABLED or not rag_pipeline or not qdrant_connector:
        return
    pending = news_item_insights_store.get_next_pending(limit=1)
    if not pending:
        return
    row = pending[0]
    news_item_id = row["news_item_id"]
    document_id = row["document_id"]
    filename = row["filename"]
    title = row.get("title") or ""
    
    # DEDUP: Check text_hash before calling GPT
    text_hash = row.get("text_hash")
    if text_hash:
        existing = news_item_insights_store.get_done_by_text_hash(text_hash)
        if existing and existing.get("content") and existing.get("news_item_id") != news_item_id:
            news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_DONE, content=existing["content"])
            logger.info(f"♻️ Reused insight via text_hash for {news_item_id} ({title}) (saved GPT call)")
            return
    
    news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_GENERATING)
    try:
        chunks = qdrant_connector.get_chunks_by_news_item_ids([news_item_id], max_chunks=500)
        if not chunks:
            news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_ERROR, error_message="No chunks")
            return
        texts = [c.get("text", "") for c in chunks if c.get("text")]
        context = "\n\n".join(texts)
        if len(context) > 80000:
            context = context[:80000] + "\n\n[... truncado ...]"
        label = f"{filename} — {title}".strip(" —")
        for attempt in range(INSIGHTS_MAX_RETRIES):
            try:
                content = rag_pipeline.generate_insights_from_context(context, label)
                news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_DONE, content=content)
                logger.info(f"News item insights generated for {news_item_id} ({title})")
                return
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait = INSIGHTS_THROTTLE_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"News item insights 429 for {news_item_id}, waiting {wait}s "
                        f"(attempt {attempt + 1}/{INSIGHTS_MAX_RETRIES})"
                    )
                    time.sleep(wait)
                else:
                    raise
        news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_ERROR, error_message="Max retries (429)")
    except Exception as e:
        logger.error(f"News item insights generation failed for {news_item_id}: {e}", exc_info=True)
        news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_ERROR, error_message=str(e))


async def _insights_worker_task(news_item_id: str, document_id: str, filename: str, title: str, worker_id: str):
    """
    Background worker for insights generation: processes ONE task independently.
    Each worker has its own worker_id. If crashed, task marked 'started' for recovery.
    Checks text_hash dedup BEFORE calling GPT to reuse existing insights and save costs.
    """
    try:
        logger.info(f"[{worker_id}] Assigned insights for: {title or 'untitled'}")
        
        # Mark as started
        processing_queue_store.update_worker_status(
            worker_id, f"insight_{news_item_id}", 'insights', 'started'
        )
        
        # DEDUP: Check if an insight with the same text_hash already exists (saves GPT costs)
        try:
            conn_dedup = document_status_store.get_connection()
            cur_dedup = conn_dedup.cursor()
            cur_dedup.execute(
                "SELECT text_hash FROM news_item_insights WHERE news_item_id = %s",
                (news_item_id,)
            )
            row_hash = cur_dedup.fetchone()
            text_hash = row_hash['text_hash'] if row_hash and row_hash.get('text_hash') else None
            conn_dedup.close()
        except Exception:
            text_hash = None
        
        if text_hash:
            existing = news_item_insights_store.get_done_by_text_hash(text_hash)
            if existing and existing.get("content") and existing.get("news_item_id") != news_item_id:
                news_item_insights_store.set_status(
                    news_item_id,
                    news_item_insights_store.STATUS_DONE,
                    content=existing["content"]
                )
                processing_queue_store.update_worker_status(
                    worker_id, f"insight_{news_item_id}", 'insights', 'completed'
                )
                processing_queue_store.mark_task_completed(f"insight_{news_item_id}", 'insights')
                logger.info(f"[{worker_id}] ♻️ Reused insight via text_hash for {news_item_id} (saved GPT call)")
                return
        
        # Set to generating in insights store
        news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_GENERATING)
        
        # Fetch chunks from Qdrant
        chunks = qdrant_connector.get_chunks_by_news_item_ids([news_item_id], max_chunks=500)
        if not chunks:
            logger.warning(f"[{worker_id}] No chunks found for {news_item_id}")
            news_item_insights_store.set_status(
                news_item_id, 
                news_item_insights_store.STATUS_ERROR, 
                error_message="No chunks"
            )
            processing_queue_store.update_worker_status(
                worker_id, f"insight_{news_item_id}", 'insights', 'error',
                error_message="No chunks"
            )
            processing_queue_store.mark_task_completed(f"insight_{news_item_id}", 'insights')
            return
        
        # Build context
        texts = [c.get("text", "") for c in chunks if c.get("text")]
        context = "\n\n".join(texts)
        if len(context) > 80000:
            context = context[:80000] + "\n\n[... truncado ...]"
        
        label = f"{filename} — {title}".strip(" —")
        
        logger.info(f"[{worker_id}] Generating insights for {news_item_id} ({len(context)} chars)")
        
        # Generate insights with retry on 429
        for attempt in range(INSIGHTS_MAX_RETRIES):
            try:
                # Run in thread to avoid blocking
                content = await asyncio.to_thread(
                    rag_pipeline.generate_insights_from_context,
                    context,
                    label
                )
                
                news_item_insights_store.set_status(
                    news_item_id,
                    news_item_insights_store.STATUS_DONE,
                    content=content
                )
                
                processing_queue_store.update_worker_status(
                    worker_id, f"insight_{news_item_id}", 'insights', 'completed'
                )
                processing_queue_store.mark_task_completed(f"insight_{news_item_id}", 'insights')
                
                logger.info(f"[{worker_id}] ✅ Insights generated for {news_item_id}")
                return
                
            except requests.exceptions.HTTPError as e:
                if e.response is not None and e.response.status_code == 429:
                    wait = INSIGHTS_THROTTLE_SECONDS * (2 ** attempt)
                    logger.warning(
                        f"[{worker_id}] 429 Rate Limit - waiting {wait}s "
                        f"(attempt {attempt + 1}/{INSIGHTS_MAX_RETRIES})"
                    )
                    await asyncio.sleep(wait)
                else:
                    raise
        
        # Max retries exceeded
        news_item_insights_store.set_status(
            news_item_id,
            news_item_insights_store.STATUS_ERROR,
            error_message="Max retries (429)"
        )
        processing_queue_store.update_worker_status(
            worker_id, f"insight_{news_item_id}", 'insights', 'error',
            error_message="Max retries (429)"
        )
        processing_queue_store.mark_task_completed(f"insight_{news_item_id}", 'insights')
        
    except Exception as e:
        logger.error(f"[{worker_id}] Insights error: {e}", exc_info=True)
        try:
            err_msg = str(e)[:200]
            news_item_insights_store.set_status(
                news_item_id,
                news_item_insights_store.STATUS_ERROR,
                error_message=err_msg
            )
            processing_queue_store.update_worker_status(
                worker_id, f"insight_{news_item_id}", 'insights', 'error',
                error_message=err_msg
            )
            processing_queue_store.mark_task_completed(f"insight_{news_item_id}", 'insights')
        except Exception as e2:
            logger.error(f"[{worker_id}] Failed to mark error: {e2}")


def run_news_item_insights_queue_job_parallel():
    """
    Scheduler job (every 15s): checks database semaphore, dispatches ONE insights worker.
    
    Same pattern as OCR:
    1. Check worker_tasks: count active insights workers
    2. If active < max (2): there's a free slot
    3. Get ONE pending 'insights' task from processing_queue
    4. Create unique worker_id
    5. Spawn background worker (async)
    6. Return immediately (non-blocking)
    """
    if not INSIGHTS_QUEUE_ENABLED or not rag_pipeline or not qdrant_connector:
        return
    
    try:
        parallel_workers = max(2, min(
            int(os.getenv("INSIGHTS_PARALLEL_WORKERS", "2")),
            10
        ))
        
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        # Check semaphore: active insights workers
        cursor.execute("""
            SELECT COUNT(*) as active
            FROM worker_tasks
            WHERE status IN ('assigned', 'started')
            AND worker_type = 'Insights'
        """)
        result = cursor.fetchone()
        active_workers = result[list(result.keys())[0]] if result else 0
        
        if active_workers >= parallel_workers:
            logger.debug(f"Insights: {active_workers}/{parallel_workers} busy, skipping")
            conn.close()
            return
        
        # Get ONE pending insights task
        # First try: from processing_queue if task_type='insights'
        cursor.execute("""
            SELECT * FROM processing_queue
            WHERE status = 'pending' AND task_type = 'insights'
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
        """)
        
        task_row = cursor.fetchone()
        
        if not task_row:
            # Fallback: try news_item_insights with STATUS_PENDING/QUEUED
            cursor.execute("""
                SELECT news_item_id, document_id, filename, title FROM news_item_insights
                WHERE status IN ('pending', 'queued')
                ORDER BY news_item_id ASC
                LIMIT 1
            """)
            
            insights_row = cursor.fetchone()
            if not insights_row:
                conn.close()
                return
            
            insights_dict = dict(insights_row)
            news_item_id = insights_dict['news_item_id']
            document_id = insights_dict['document_id']
            filename = insights_dict['filename']
            title = insights_dict.get('title', '')
        else:
            # From processing_queue
            task_dict = dict(task_row)
            document_id = task_dict['document_id']
            filename = task_dict['filename']
            news_item_id = task_dict['document_id']  # Using document_id as proxy
            title = ""
        
        conn.close()
        
        # Create unique worker
        worker_id = f"insights_{os.getpid()}_{int(time.time() * 1000) % 100000}"
        
        logger.info(f"Insights scheduler: Dispatching {worker_id} for {title or filename}")
        
        # CRITICAL: Primero intentar asignar worker (verifica duplicados atómicamente con SELECT FOR UPDATE)
        # Esto actúa como semáforo centralizado - solo UN worker puede asignarse por news_item_id
        # Usamos "insight_{news_item_id}" como document_id único para insights
        assigned = processing_queue_store.assign_worker(
            worker_id, 'Insights', f"insight_{news_item_id}", 'insights'
        )
        
        if not assigned:
            # Otro worker ya está procesando este insight - saltar (semáforo bloqueado)
            logger.debug(f"⏸️  [Insights] News item {news_item_id} already assigned to another worker, skipping")
            conn.close()
            return
        
        # Si hay tarea en processing_queue, marcar como processing solo si asignación fue exitosa
        if task_row:
            task_id = task_dict.get('id')
            if task_id:
                cursor.execute("""
                    UPDATE processing_queue
                    SET status = 'processing'
                    WHERE id = %s
                """, (task_id,))
                conn.commit()
        
        # Spawn background worker in a separate thread (solo si asignación fue exitosa)
        try:
            from threading import Thread
            worker_thread = Thread(
                target=lambda: asyncio.run(_insights_worker_task(news_item_id, document_id, filename, title, worker_id)),
                name=f"insights-worker-{worker_id}",
                daemon=True
            )
            worker_thread.start()
            logger.info(f"Insights worker {worker_id} thread started")
        except Exception as e:
            logger.error(f"Failed to start insights worker thread: {e}", exc_info=True)
            # Revertir asignación si falla el spawn
            processing_queue_store.update_worker_status(
                worker_id, f"insight_{news_item_id}", 'insights', 'error',
                error_message=f"Failed to start thread: {str(e)[:200]}"
            )
        
    except Exception as e:
        logger.error(f"Insights scheduler error: {e}", exc_info=True)


# ============================================================================
# GENERIC TASK DISPATCHER & HANDLERS
# ============================================================================

async def _handle_ocr_task(task_data: dict, worker_id: str):
    """Handler for OCR tasks - extracts text only"""
    document_id = task_data['document_id']
    filename = task_data['filename']
    
    logger.info(f"[{worker_id}] OCR task: {filename}")
    processing_queue_store.update_worker_status(worker_id, document_id, 'ocr', 'started')
    
    try:
        file_path = os.path.join(UPLOAD_DIR, document_id)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")
        
        text, doc_type, content_hash = await asyncio.to_thread(_extract_ocr_only, file_path, document_id, filename)
        
        # Store OCR result
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE document_status
            SET status = %s, processing_stage = %s, indexed_at = %s
            WHERE document_id = %s
        """, (DocStatus.OCR_DONE, Stage.OCR, datetime.utcnow().isoformat(), document_id))
        conn.commit()
        conn.close()
        
        processing_queue_store.update_worker_status(worker_id, document_id, 'ocr', 'completed')
        processing_queue_store.mark_task_completed(document_id, 'ocr')
        logger.info(f"[{worker_id}] ✅ OCR completed: {filename}")
        
    except Exception as e:
        logger.error(f"[{worker_id}] OCR failed: {e}", exc_info=True)
        document_status_store.update_status(document_id, DocStatus.ERROR, error_message=str(e)[:200])
        processing_queue_store.update_worker_status(worker_id, document_id, 'ocr', 'error', error_message=str(e)[:200])
        processing_queue_store.mark_task_completed(document_id, 'ocr')
        raise


async def _handle_chunking_task(task_data: dict, worker_id: str):
    """Handler for Chunking tasks - segments and chunks text"""
    document_id = task_data['document_id']
    filename = task_data['filename']
    
    logger.info(f"[{worker_id}] Chunking task: {filename}")
    processing_queue_store.update_worker_status(worker_id, document_id, 'chunking', 'started')
    
    try:
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ocr_text, doc_type FROM document_status WHERE document_id = %s", (document_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result['ocr_text']:
            raise ValueError("No OCR text found for chunking")
        
        ocr_text, doc_type = result['ocr_text'], result['doc_type'] or "unknown"
        chunk_records = await asyncio.to_thread(_perform_chunking, ocr_text, document_id, filename, doc_type)
        
        document_status_store.update_status(document_id, DocStatus.CHUNKING_DONE, processing_stage=Stage.CHUNKING, num_chunks=len(chunk_records))
        processing_queue_store.update_worker_status(worker_id, document_id, 'chunking', 'completed')
        processing_queue_store.mark_task_completed(document_id, 'chunking')
        logger.info(f"[{worker_id}] ✅ Chunking completed: {len(chunk_records)} chunks")
        
    except Exception as e:
        logger.error(f"[{worker_id}] Chunking failed: {e}", exc_info=True)
        document_status_store.update_status(document_id, DocStatus.ERROR, error_message=str(e)[:200])
        processing_queue_store.update_worker_status(worker_id, document_id, 'chunking', 'error', error_message=str(e)[:200])
        processing_queue_store.mark_task_completed(document_id, 'chunking')
        raise


async def _handle_indexing_task(task_data: dict, worker_id: str):
    """Handler for Indexing tasks - reconstructs chunks from OCR text and indexes into Qdrant."""
    document_id = task_data['document_id']
    filename = task_data['filename']
    
    logger.info(f"[{worker_id}] Indexing task: {filename}")
    processing_queue_store.update_worker_status(worker_id, document_id, TaskType.INDEXING, WorkerStatus.STARTED)
    
    try:
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ocr_text, doc_type FROM document_status WHERE document_id = %s", (document_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result['ocr_text']:
            raise ValueError("No OCR text available for indexing")
        
        ocr_text = result['ocr_text']
        doc_type = result['doc_type'] or "unknown"
        
        chunk_records = await asyncio.to_thread(_perform_chunking, ocr_text, document_id, filename, doc_type)
        
        if not chunk_records:
            raise ValueError("No chunk records generated for indexing")
        
        logger.info(f"[{worker_id}] Indexing {len(chunk_records)} chunks into Qdrant...")
        await asyncio.to_thread(rag_pipeline.index_chunk_records, chunk_records)
        
        document_status_store.update_status(
            document_id, DocStatus.INDEXING_DONE,
            processing_stage=Stage.INDEXING,
            indexed_at=datetime.utcnow().isoformat(),
            num_chunks=len(chunk_records)
        )
        document_status_store.mark_for_reprocessing(document_id, requested=False)
        
        if INSIGHTS_QUEUE_ENABLED and rag_pipeline:
            items = news_item_store.list_by_document_id(document_id)
            for it in items:
                news_item_insights_store.enqueue(
                    news_item_id=it["news_item_id"],
                    document_id=document_id,
                    filename=filename,
                    item_index=int(it.get("item_index") or 0),
                    title=it.get("title") or "",
                    text_hash=it.get("text_hash") or None,
                )
            logger.info(f"[{worker_id}] Queued {len(items)} insights tasks")
        
        processing_queue_store.update_worker_status(worker_id, document_id, TaskType.INDEXING, WorkerStatus.COMPLETED)
        processing_queue_store.mark_task_completed(document_id, TaskType.INDEXING)
        logger.info(f"[{worker_id}] ✅ Indexing completed: {len(chunk_records)} chunks indexed")
        
    except Exception as e:
        logger.error(f"[{worker_id}] Indexing failed: {e}", exc_info=True)
        document_status_store.update_status(document_id, DocStatus.ERROR, error_message=str(e)[:200])
        processing_queue_store.update_worker_status(worker_id, document_id, TaskType.INDEXING, WorkerStatus.ERROR, error_message=str(e)[:200])
        processing_queue_store.mark_task_completed(document_id, TaskType.INDEXING)
        raise


async def _handle_insights_task(task_data: dict, worker_id: str):
    """Handler for Insights tasks - generates LLM insights.
    Checks text_hash dedup BEFORE calling GPT to reuse existing insights and save costs."""
    news_item_id = task_data.get('news_item_id')
    document_id = task_data.get('document_id')
    filename = task_data.get('filename', '')
    title = task_data.get('title', '')
    
    if not news_item_id:
        raise ValueError("news_item_id is required for insights tasks")
    
    logger.info(f"[{worker_id}] Insights task: {title or filename}")
    processing_queue_store.update_worker_status(worker_id, f"insight_{news_item_id}", 'insights', 'started')
    
    # DEDUP: Check text_hash before calling GPT
    try:
        conn_dedup = document_status_store.get_connection()
        cur_dedup = conn_dedup.cursor()
        cur_dedup.execute("SELECT text_hash FROM news_item_insights WHERE news_item_id = %s", (news_item_id,))
        row_hash = cur_dedup.fetchone()
        text_hash = row_hash['text_hash'] if row_hash and row_hash.get('text_hash') else None
        conn_dedup.close()
    except Exception:
        text_hash = None
    
    if text_hash:
        existing = news_item_insights_store.get_done_by_text_hash(text_hash)
        if existing and existing.get("content") and existing.get("news_item_id") != news_item_id:
            news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_DONE, content=existing["content"])
            processing_queue_store.update_worker_status(worker_id, f"insight_{news_item_id}", 'insights', 'completed')
            processing_queue_store.mark_task_completed(f"insight_{news_item_id}", 'insights')
            logger.info(f"[{worker_id}] ♻️ Reused insight via text_hash for {news_item_id} (saved GPT call)")
            return
    
    news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_GENERATING)
    
    try:
        chunks = qdrant_connector.get_chunks_by_news_item_ids([news_item_id], max_chunks=500)
        if not chunks:
            raise ValueError("No chunks found")
        
        texts = [c.get("text", "") for c in chunks if c.get("text")]
        context = "\n\n".join(texts)[:80000]
        label = f"{filename} — {title}".strip(" —")
        
        content = rag_pipeline.generate_insights_from_context(context, label)
        news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_DONE, content=content)
        
        processing_queue_store.update_worker_status(worker_id, f"insight_{news_item_id}", 'insights', 'completed')
        logger.info(f"[{worker_id}] ✅ Insights generated")
        
    except Exception as e:
        logger.error(f"[{worker_id}] Insights failed: {e}", exc_info=True)
        news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_ERROR, error_message=str(e)[:200])
        processing_queue_store.update_worker_status(worker_id, f"insight_{news_item_id}", 'insights', 'error', error_message=str(e)[:200])
        raise


async def generic_task_dispatcher(task_type: str, task_data: dict, worker_id: str):
    """
    Generic task dispatcher - routes tasks to specialized handlers.
    This allows a single worker pool to handle all task types efficiently.
    """
    handlers = {
        'ocr': _handle_ocr_task,
        'chunking': _handle_chunking_task,
        'indexing': _handle_indexing_task,
        'insights': _handle_insights_task,
    }
    
    handler = handlers.get(task_type)
    if not handler:
        raise ValueError(f"Unknown task type: {task_type}")
    
    logger.debug(f"[{worker_id}] Dispatching {task_type} task")
    return await handler(task_data, worker_id)


async def _ocr_worker_task(document_id: str, filename: str, worker_id: str):
    """
    Background worker task: processes ONE OCR task independently.
    Each worker has its own ID and marks progress in worker_tasks table.
    If worker crashes, task is marked 'started' with worker_id for recovery.
    """
    try:
        logger.info(f"[{worker_id}] Assigned OCR task for: {filename}")
        
        # Mark as started (worker_id identifies this worker's progress)
        processing_queue_store.update_worker_status(
            worker_id, document_id, 'ocr', 'started'
        )
        
        # Get file path
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM document_status WHERE document_id = %s
        """, (document_id,))
        doc_record = cursor.fetchone()
        conn.close()
        
        if not doc_record:
            logger.error(f"[{worker_id}] Document not in status table: {document_id}")
            processing_queue_store.update_worker_status(
                worker_id, document_id, 'ocr', 'error',
                error_message="Document not found in DB"
            )
            processing_queue_store.mark_task_completed(document_id, 'ocr')
            return
        
        file_path = os.path.join(UPLOAD_DIR, document_id)
        
        if not os.path.exists(file_path):
            logger.error(f"[{worker_id}] File not found: {file_path}")
            document_status_store.update_status(document_id, DocStatus.ERROR, error_message="File not found")
            processing_queue_store.update_worker_status(
                worker_id, document_id, 'ocr', 'error',
                error_message="File not found"
            )
            processing_queue_store.mark_task_completed(document_id, 'ocr')
            return
        
        logger.info(f"[{worker_id}] Processing OCR: {filename} ({len(open(file_path, 'rb').read()) / 1024 / 1024:.1f}MB)")
        
        # Run sync OCR extraction only (no chunking/indexing)
        # Extract OCR text
        try:
            text, doc_type, content_hash = await asyncio.to_thread(_extract_ocr_only, file_path, document_id, filename)
            
            # Store OCR text in database (CRITICAL: chunking worker needs this)
            document_status_store.store_ocr_text(document_id, text)
            
            # Store OCR text and metadata in document_status
            conn = document_status_store.get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE document_status
                SET status = %s, 
                    processing_stage = %s,
                    indexed_at = %s,
                    num_chunks = 0,
                    doc_type = %s
                WHERE document_id = %s
            """, (DocStatus.OCR_DONE, Stage.OCR, datetime.utcnow().isoformat(), doc_type, document_id))
            conn.commit()
            conn.close()
            
            logger.info(f"[{worker_id}] ✅ OCR completed: {filename}")
            
        except Exception as e:
            logger.error(f"[{worker_id}] OCR extraction failed: {e}", exc_info=True)
            raise
        
        # Mark completed (slot freed automatically for next worker)
        processing_queue_store.update_worker_status(
            worker_id, document_id, 'ocr', 'completed'
        )
        processing_queue_store.mark_task_completed(document_id, 'ocr')
        
        logger.info(f"[{worker_id}] ✅ OCR completed: {filename}")
        
    except Exception as e:
        logger.error(f"[{worker_id}] OCR worker error: {e}", exc_info=True)
        try:
            err_msg = str(e)[:200]
            document_status_store.update_status(document_id, DocStatus.ERROR, error_message=err_msg)
            processing_queue_store.update_worker_status(
                worker_id, document_id, 'ocr', 'error',
                error_message=err_msg
            )
            processing_queue_store.mark_task_completed(document_id, 'ocr')
        except Exception as e2:
            logger.error(f"[{worker_id}] Failed to mark error: {e2}")


async def _chunking_worker_task(document_id: str, filename: str, worker_id: str):
    """
    Worker task: Performs chunking on documents that have completed OCR.
    Reads OCR text from the document, performs segmentation and chunking,
    then stores chunks and marks document as chunking_done.
    
    NOTE: assign_worker() was already called atomically by master scheduler before
    this worker was dispatched. This ensures only ONE worker processes each document.
    """
    try:
        logger.info(f"[{worker_id}] Assigned Chunking task for: {filename}")
        
        # Mark as started (assign_worker already marked as 'assigned' atomically)
        processing_queue_store.update_worker_status(
            worker_id, document_id, 'chunking', 'started'
        )
        
        # Get document record and OCR text (should exist from OCR worker)
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ocr_text, doc_type FROM document_status WHERE document_id = %s
        """, (document_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result['ocr_text']:
            logger.error(f"[{worker_id}] No OCR text found for {document_id}")
            document_status_store.update_status(document_id, DocStatus.ERROR, error_message="No OCR text for chunking")
            processing_queue_store.update_worker_status(
                worker_id, document_id, 'chunking', 'error',
                error_message="No OCR text"
            )
            processing_queue_store.mark_task_completed(document_id, 'chunking')
            return
        
        ocr_text = result['ocr_text']
        doc_type = result['doc_type'] or "unknown"
        
        logger.info(f"[{worker_id}] Starting chunking for {filename}...")
        
        # Perform chunking
        try:
            chunk_records = await asyncio.to_thread(_perform_chunking, ocr_text, document_id, filename, doc_type)
            
            # Update document status
            document_status_store.update_status(
                document_id,
                DocStatus.CHUNKING_DONE,
                processing_stage=Stage.CHUNKING,
                num_chunks=len(chunk_records)
            )
            
            logger.info(f"[{worker_id}] ✅ Chunking completed: {len(chunk_records)} chunks created")
            
        except Exception as e:
            logger.error(f"[{worker_id}] Chunking failed: {e}", exc_info=True)
            raise
        
        # Mark completed
        processing_queue_store.update_worker_status(
            worker_id, document_id, 'chunking', 'completed'
        )
        processing_queue_store.mark_task_completed(document_id, 'chunking')
        
    except Exception as e:
        logger.error(f"[{worker_id}] Chunking worker error: {e}", exc_info=True)
        try:
            err_msg = str(e)[:200]
            document_status_store.update_status(document_id, DocStatus.ERROR, error_message=err_msg)
            processing_queue_store.update_worker_status(
                worker_id, document_id, 'chunking', 'error',
                error_message=err_msg
            )
            processing_queue_store.mark_task_completed(document_id, 'chunking')
        except Exception as e2:
            logger.error(f"[{worker_id}] Failed to mark error: {e2}")


async def _indexing_worker_task(document_id: str, filename: str, worker_id: str):
    """
    Worker task: Reconstructs chunks from OCR text and indexes into Qdrant.
    
    NOTE: assign_worker() was already called atomically by master scheduler before
    this worker was dispatched. This ensures only ONE worker processes each document.
    """
    try:
        logger.info(f"[{worker_id}] Assigned Indexing task for: {filename}")
        
        processing_queue_store.update_worker_status(
            worker_id, document_id, TaskType.INDEXING, WorkerStatus.STARTED
        )
        
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ocr_text, doc_type FROM document_status WHERE document_id = %s", (document_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result['ocr_text']:
            raise ValueError("No OCR text available for indexing")
        
        ocr_text = result['ocr_text']
        doc_type = result['doc_type'] or "unknown"
        
        chunk_records = await asyncio.to_thread(_perform_chunking, ocr_text, document_id, filename, doc_type)
        
        if not chunk_records:
            raise ValueError("No chunk records generated for indexing")
        
        logger.info(f"[{worker_id}] Indexing {len(chunk_records)} chunks into Qdrant...")
        await asyncio.to_thread(rag_pipeline.index_chunk_records, chunk_records)
        
        document_status_store.update_status(
            document_id, DocStatus.INDEXING_DONE,
            processing_stage=Stage.INDEXING,
            indexed_at=datetime.utcnow().isoformat(),
            num_chunks=len(chunk_records)
        )
        document_status_store.mark_for_reprocessing(document_id, requested=False)
        
        if INSIGHTS_QUEUE_ENABLED and rag_pipeline:
            try:
                items = news_item_store.list_by_document_id(document_id)
                for it in items:
                    news_item_insights_store.enqueue(
                        news_item_id=it["news_item_id"],
                        document_id=document_id,
                        filename=filename,
                        item_index=int(it.get("item_index") or 0),
                        title=it.get("title") or "",
                        text_hash=it.get("text_hash") or None,
                    )
                logger.info(f"[{worker_id}] Queued {len(items)} insights tasks")
            except Exception as eq_err:
                logger.warning(f"[{worker_id}] Insights enqueue failed: {eq_err}")
        
        processing_queue_store.update_worker_status(
            worker_id, document_id, TaskType.INDEXING, WorkerStatus.COMPLETED
        )
        processing_queue_store.mark_task_completed(document_id, TaskType.INDEXING)
        logger.info(f"[{worker_id}] ✅ Indexing completed: {len(chunk_records)} chunks indexed")
        
    except Exception as e:
        logger.error(f"[{worker_id}] Indexing worker error: {e}", exc_info=True)
        try:
            err_msg = str(e)[:200]
            document_status_store.update_status(document_id, DocStatus.ERROR, error_message=err_msg)
            processing_queue_store.update_worker_status(
                worker_id, document_id, TaskType.INDEXING, WorkerStatus.ERROR,
                error_message=err_msg
            )
            processing_queue_store.mark_task_completed(document_id, TaskType.INDEXING)
        except Exception as e2:
            logger.error(f"[{worker_id}] Failed to mark error: {e2}")


def run_document_ocr_queue_job_parallel():
    """
    Scheduler job (runs every 15s): checks database semaphore and dispatches workers.
    
    Logic:
    1. Check worker_tasks: count active workers (status='assigned' or 'started')
    2. If active < max_workers (2): there's a free slot
    3. Check processing_queue: any pending 'ocr' tasks?
    4. If yes: create unique worker_id, assign task, spawn background worker
    
    Each worker is independent and has its own worker_id. If a worker crashes,
    its task remains in worker_tasks with worker_id marked, enabling recovery.
    
    No ThreadPoolExecutor needed - just let async handle it.
    """
    if not ocr_service or not rag_pipeline or not qdrant_connector:
        return
    
    try:
        parallel_workers = max(2, min(
            int(os.getenv("OCR_PARALLEL_WORKERS", "2")),
            10
        ))
        
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        # Check database semaphore: how many workers are active?
        cursor.execute("""
            SELECT COUNT(*) as active
            FROM worker_tasks
            WHERE status IN ('assigned', 'started')
            AND worker_type = 'OCR'
        """)
        result = cursor.fetchone()
        active_workers = result[list(result.keys())[0]] if result else 0
        
        if active_workers >= parallel_workers:
            logger.debug(f"OCR scheduler: {active_workers}/{parallel_workers} workers busy, skipping")
            conn.close()
            return
        
        # There's a free slot! Check for pending task and mark as processing atomically
        # Use SELECT FOR UPDATE to prevent race conditions
        cursor.execute("""
            SELECT * FROM processing_queue
            WHERE status = 'pending' AND task_type = 'ocr'
            ORDER BY priority DESC, created_at ASC
            LIMIT 1
            FOR UPDATE SKIP LOCKED
        """)
        
        task_row = cursor.fetchone()
        
        if not task_row:
            conn.close()
            return
        
        task = dict(task_row)
        task_id = task['id']
        document_id = task['document_id']
        filename = task['filename']
        conn.close()  # Close connection before assign_worker (it opens its own)
        
        # Create unique worker ID (will be marked in worker_tasks)
        worker_id = f"ocr_{os.getpid()}_{int(time.time() * 1000) % 100000}"
        
        logger.info(f"OCR scheduler: Attempting to assign worker {worker_id} for {filename}")
        
        # CRITICAL: Primero asignar worker (verifica duplicados atómicamente con SELECT FOR UPDATE)
        # Esto actúa como semáforo centralizado - solo UN worker puede asignarse por documento/tarea
        assigned = processing_queue_store.assign_worker(
            worker_id, 'OCR', document_id, 'ocr'
        )
        
        if not assigned:
            # Otro worker ya está procesando este documento - saltar (semáforo bloqueado)
            logger.warning(f"OCR scheduler: Document {document_id} already assigned to another worker, skipping")
            return
        
        # Solo marcar como processing si la asignación fue exitosa (worker ya tiene el lock)
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE processing_queue
            SET status = 'processing'
            WHERE id = %s
        """, (task_id,))
        conn.commit()
        conn.close()
        
        logger.info(f"OCR scheduler: Successfully assigned worker {worker_id} for {filename}")
        
        # Spawn background worker task in a separate thread (only if assignment succeeded)
        # APScheduler is already in a thread, but we need to avoid blocking it
        try:
            from threading import Thread
            worker_thread = Thread(
                target=lambda: asyncio.run(_ocr_worker_task(document_id, filename, worker_id)),
                name=f"ocr-worker-{worker_id}",
                daemon=True
            )
            worker_thread.start()
            logger.info(f"OCR worker {worker_id} thread started")
        except Exception as e:
            logger.error(f"Failed to start OCR worker thread: {e}", exc_info=True)
                    
    except Exception as e:
        logger.error(f"OCR scheduler error: {e}", exc_info=True)


async def detect_crashed_workers():
    """
    Startup recovery: clean ALL orphaned state left by a previous process.

    On restart every in-flight task is dead because the threads that owned
    them died with the old container/process.

    ═══════════════════════════════════════════════════════════════════
    PIPELINE STATE MACHINE  (document_status.status)
    ═══════════════════════════════════════════════════════════════════

    Each document flows through stages. Each stage has 3 internal states:
        {stage}_pending  →  {stage}_processing  →  {stage}_done

    Full flow:
        upload_pending → upload_processing → upload_done
          → ocr_pending → ocr_processing → ocr_done
          → chunking_pending → chunking_processing → chunking_done
          → indexing_pending → indexing_processing → indexing_done
          → (insights handled per news_item in news_item_insights table)
          → completed

    Terminal states: error, paused

    Transition ownership (example: stage=indexing, prev=chunking):
        {prev}_done → task pending  : master_pipeline_scheduler (creates task)
        task pending → {stage}_processing : master_pipeline_scheduler (assigns worker)
        {stage}_processing → {stage}_done : worker thread (completes work)

    ═══════════════════════════════════════════════════════════════════
    ORPHAN RECOVERY RULES  (this function)
    ═══════════════════════════════════════════════════════════════════

    On restart, NO threads are alive. Everything in-flight is orphaned:

      1. worker_tasks   started/assigned  → DELETE
         (no live thread owns them)

      2. processing_queue  processing     → pending
         (no worker is consuming them; scheduler will re-dispatch)

      3. document_status   {stage}_processing → {prev_stage}_done
         (roll back so master scheduler re-creates the correct task)
         Rollback map ({stage}_processing → {prev_stage}_done):
           ocr_processing      → upload_done
           chunking_processing → ocr_done
           indexing_processing  → chunking_done
           insights_processing  → indexing_done

      4. news_item_insights  generating   → pending
         (InsightStatus.GENERATING with no live thread)

    After this runs, the master scheduler's normal 10s cycle will:
      - See *_done docs and create next-stage tasks
      - See pending queue entries and dispatch workers
      - The pipeline resumes exactly where it left off

    Must run BEFORE the master scheduler starts dispatching.
    ═══════════════════════════════════════════════════════════════════
    """
    try:
        conn = document_status_store.get_connection()
        cursor = conn.cursor()

        # 1) worker_tasks: everything started/assigned is orphaned
        cursor.execute(
            "DELETE FROM worker_tasks WHERE status IN (%s, %s)",
            (WorkerStatus.STARTED, WorkerStatus.ASSIGNED),
        )
        wt_deleted = cursor.rowcount
        if wt_deleted:
            logger.warning(f"🧹 Startup: deleted {wt_deleted} orphaned worker_tasks")

        # 2) processing_queue: 'processing' entries have no live worker
        cursor.execute(
            "UPDATE processing_queue SET status = %s WHERE status = %s",
            (QueueStatus.PENDING, QueueStatus.PROCESSING),
        )
        pq_reset = cursor.rowcount
        if pq_reset:
            logger.warning(f"🧹 Startup: reset {pq_reset} processing_queue → pending")

        # 3) document_status: roll back *_processing to previous done stage
        stage_rollback = {
            DocStatus.OCR_PROCESSING:       DocStatus.UPLOAD_DONE,
            DocStatus.CHUNKING_PROCESSING:  DocStatus.OCR_DONE,
            DocStatus.INDEXING_PROCESSING:  DocStatus.CHUNKING_DONE,
            DocStatus.INSIGHTS_PROCESSING:  DocStatus.INDEXING_DONE,
        }
        ds_total = 0
        for stuck_status, rollback_status in stage_rollback.items():
            cursor.execute(
                "UPDATE document_status SET status = %s, error_message = NULL "
                "WHERE status = %s RETURNING document_id",
                (rollback_status, stuck_status),
            )
            count = cursor.rowcount
            if count:
                ds_total += count
                logger.warning(
                    f"🧹 Startup: {count} docs {stuck_status} → {rollback_status}"
                )

        # 4) insights: 'generating' with no live thread → pending
        cursor.execute(
            "UPDATE news_item_insights SET status = %s, error_message = NULL "
            "WHERE status = %s",
            (InsightStatus.PENDING, InsightStatus.GENERATING),
        )
        ins_reset = cursor.rowcount
        if ins_reset:
            logger.warning(f"🧹 Startup: reset {ins_reset} insights {InsightStatus.GENERATING} → {InsightStatus.PENDING}")

        conn.commit()
        conn.close()

        total = wt_deleted + pq_reset + ds_total + ins_reset
        if total:
            logger.info(
                f"🔄 Startup recovery complete: "
                f"{wt_deleted} workers, {pq_reset} queue, "
                f"{ds_total} docs, {ins_reset} insights cleaned"
            )
        else:
            logger.info("✅ Startup recovery: no orphaned tasks found")

    except Exception as e:
        logger.error(f"Startup recovery error: {e}", exc_info=True)


def _get_event_loop():
    """
    Get or create event loop for scheduler jobs.
    APScheduler runs jobs in threads, so we need to get the running loop
    or create a new one if none exists.
    """
    try:
        # If there's a running loop, use it
        return asyncio.get_running_loop()
    except RuntimeError:
        # No running loop - create one for this thread
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                raise RuntimeError("Loop closed")
            return loop
        except RuntimeError:
            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop


def _run_async_in_scheduler(coro):
    """
    Helper to run async coroutines from scheduler jobs (which run in threads).
    This bridges the gap between APScheduler (sync) and asyncio (async).
    """
    try:
        loop = _get_event_loop()
        
        # If loop is running, schedule the coroutine
        if loop.is_running():
            # This shouldn't happen in scheduler context, but handle it
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(coro, loop)
            return future.result(timeout=5)
        else:
            # Loop not running, run the coroutine
            return loop.run_until_complete(coro)
    except Exception as e:
        logger.error(f"Error running async in scheduler: {e}", exc_info=True)
        raise


def workers_health_check():
    """
    Verifica periódicamente si hay workers activos y los reinicia si es necesario.
    Se ejecuta cada 30 segundos para asegurar que siempre haya workers procesando.
    """
    global generic_worker_pool
    
    try:
        # Solo verificar si los servicios están listos
        if not ocr_service or not rag_pipeline:
            logger.debug("⏭️  Workers health check skipped: Services not ready")
            return
        
        # Get worker pool size from env (same as start_workers endpoint)
        total_workers = int(os.getenv('PIPELINE_WORKERS_COUNT', 20))
        
        # Verificar si el pool existe y está corriendo
        if generic_worker_pool is None or not generic_worker_pool.running:
            logger.warning("⚠️  Workers health check: No active worker pool detected!")
            logger.info("🔄 Auto-starting workers...")
            
            from worker_pool import GenericWorkerPool
            
            # Stop existing pool if it exists but isn't running
            if generic_worker_pool is not None and not generic_worker_pool.running:
                logger.info("♻️ Stopping stale worker pool...")
                try:
                    generic_worker_pool.stop()
                except Exception as e:
                    logger.warning(f"Error stopping stale pool: {e}")
            
            # Create new pool
            logger.info(f"🚀 Creating new worker pool with {total_workers} workers...")
            generic_worker_pool = GenericWorkerPool(
                pool_size=total_workers,
                task_dispatcher_func=generic_task_dispatcher,
                db_connection_factory=document_status_store.get_connection
            )
            
            # Start pool
            generic_worker_pool.start()
            logger.info(f"✅ Worker pool auto-started: {total_workers} workers ready")
            
            return
        
        # Si el pool existe y está corriendo, verificar que tenga workers activos
        active_count = len([w for w in generic_worker_pool.workers if w.is_alive()])
        
        if active_count == 0:
            logger.error(f"❌ Workers health check: Pool running but NO alive threads!")
            logger.info("🔄 Restarting worker pool...")
            
            try:
                generic_worker_pool.stop()
            except Exception as e:
                logger.warning(f"Error stopping dead pool: {e}")
            
            # Recreate pool
            from worker_pool import GenericWorkerPool
            generic_worker_pool = GenericWorkerPool(
                pool_size=total_workers,
                task_dispatcher_func=generic_task_dispatcher,
                db_connection_factory=document_status_store.get_connection
            )
            generic_worker_pool.start()
            logger.info(f"✅ Worker pool restarted: {total_workers} workers ready")
            
        elif active_count < generic_worker_pool.pool_size:
            logger.warning(f"⚠️  Workers health check: Only {active_count}/{generic_worker_pool.pool_size} workers alive")
            # No reiniciar aquí, solo alertar - puede ser normal si algunos threads terminaron tasks
        else:
            logger.info(f"✓ Workers health check OK: {active_count}/{generic_worker_pool.pool_size} workers alive")
        
    except Exception as e:
        logger.error(f"❌ Workers health check failed: {e}", exc_info=True)


def run_inbox_scan():
    """
    Scan INBOX_DIR for new files and queue them for event-driven OCR processing.
    Does NOT perform OCR inline - lets OCR scheduler handle via processing_queue.
    Called by scheduler every 5 min.
    """
    if not INBOX_DIR or not os.path.isdir(INBOX_DIR):
        return
    if not qdrant_connector:  # Only need Qdrant, not ocr_service (workers handle OCR)
        logger.warning("Inbox scan skipped: Qdrant not ready")
        return
    
    processed_dir = os.path.join(INBOX_DIR, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Find valid files to queue
    files_to_queue = []
    for name in os.listdir(INBOX_DIR):
        if name == "processed":
            continue
        path = os.path.join(INBOX_DIR, name)
        if not os.path.isfile(path):
            continue
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        try:
            if os.path.getsize(path) > max_bytes:
                logger.warning(f"Inbox: skip {name} (>{MAX_UPLOAD_SIZE_MB}MB)")
                continue
        except OSError:
            continue
        files_to_queue.append((path, name))

    if not files_to_queue:
        return

    logger.info(f"Inbox: queueing {len(files_to_queue)} file(s) for OCR processing")

    # Queue files (FAST - no OCR here, just queue)
    queued = 0
    duplicates = 0
    for path, name in files_to_queue:
        try:
            # Calculate hash first
            file_hash = hashlib.sha256()
            with open(path, 'rb') as f:
                for chunk in iter(lambda: f.read(8192), b''):
                    file_hash.update(chunk)
            file_hash_hex = file_hash.hexdigest()
            
            # Check if duplicate exists in BD
            existing_doc = document_status_store.find_by_hash(file_hash_hex)
            if existing_doc:
                # Duplicate found, move to processed
                processed_dir = os.path.join(INBOX_DIR, "processed")
                os.makedirs(processed_dir, exist_ok=True)
                processed_path = os.path.join(processed_dir, name)
                shutil.move(path, processed_path)
                logger.info(f"📦 Inbox: Duplicate detected, moved {name} to processed/ (matches {existing_doc['filename']})")
                duplicates += 1
                continue
            
            document_id = f"{datetime.now().timestamp()}_{name}"
            dest_path = os.path.join(UPLOAD_DIR, document_id)
            
            # Copy file to UPLOAD_DIR
            shutil.copy2(path, dest_path)
            logger.info(f"Inbox: {name} → {document_id}")
            
            # Create document_status entry with source='inbox' and file_hash
            news_date = parse_news_date_from_filename(name)
            document_status_store.insert(
                document_id, name, source="inbox", status=DocStatus.UPLOAD_DONE,
                news_date=news_date,
                file_hash=file_hash_hex
            )
            
            processing_queue_store.enqueue_task(
                document_id=document_id,
                filename=name,
                task_type=TaskType.OCR
            )
            
            logger.info(f"Inbox: queued {name} for OCR (hash: {file_hash_hex[:16]}...)")
            queued += 1
            
            # Move source to processed/ AFTER queuing succeeds
            try:
                shutil.move(path, os.path.join(processed_dir, name))
            except OSError as e:
                logger.warning(f"Could not move {name} to processed/: {e}")
                
        except Exception as e:
            logger.error(f"Inbox queue failed for {name}: {e}", exc_info=True)

    if queued > 0 or duplicates > 0:
        logger.info(f"Inbox: queued {queued}/{len(files_to_queue)} files, {duplicates} duplicates skipped")


@app.get("/api/documents", response_model=DocumentsListResponse)
async def list_documents(
    status: Optional[str] = None,
    source: Optional[str] = None,
):
    """List all documents with status (pending, processing, indexed, error). Merges DB status with Qdrant indexed docs."""
    try:
        rows = document_status_store.get_all(status_filter=status, source_filter=source)
        by_id = {}
        for r in rows:
            # Convert datetime objects to strings for PostgreSQL compatibility
            ingested_at = r["ingested_at"]
            if isinstance(ingested_at, datetime):
                ingested_at = ingested_at.isoformat()
            
            indexed_at = r.get("indexed_at")
            if isinstance(indexed_at, datetime):
                indexed_at = indexed_at.isoformat()
            
            news_date = r.get("news_date")
            if isinstance(news_date, datetime):
                news_date = news_date.isoformat()
            
            by_id[r["document_id"]] = DocumentMetadata(
                filename=r["filename"],
                upload_date=ingested_at or "",
                document_id=r["document_id"],
                num_chunks=r["num_chunks"] or 0,
                status=r["status"],
                source=r.get("source"),
                indexed_at=indexed_at,
                error_message=r.get("error_message"),
                news_date=news_date,
                processing_stage=r.get("processing_stage"),
                insights_status=None,
                insights_progress=None,
            )
        # Backfill: docs in Qdrant but not in our table (indexed before feature)
        if qdrant_connector:
            try:
                qdrant_docs = qdrant_connector.get_indexed_documents()
                for d in qdrant_docs:
                    if d["document_id"] not in by_id:
                        by_id[d["document_id"]] = DocumentMetadata(
                            filename=d["filename"],
                            upload_date=d.get("upload_date", ""),
                            document_id=d["document_id"],
                            num_chunks=d.get("num_chunks", 0),
                            status=DocStatus.INDEXING_DONE,
                            source=None,
                            indexed_at=None,
                            error_message=None,
                            news_date=None,
                            processing_stage=None,
                            insights_status=None,
                            insights_progress=None,
                        )
            except Exception as e:
                logger.warning(f"Could not merge Qdrant docs: {e}")
        doc_ids = list(by_id.keys())
        # Preferir insights por noticia (news_item_insights) cuando existan items para el documento.
        item_counts = news_item_store.get_counts_by_document_ids(doc_ids) if doc_ids else {}
        item_progress = news_item_insights_store.get_progress_by_document_ids(doc_ids) if doc_ids else {}
        legacy_map = document_insights_store.get_status_by_document_ids(doc_ids) if doc_ids else {}

        total_units = 0
        done_units = 0

        for doc_id, meta in by_id.items():
            total_items = int(item_counts.get(doc_id, 0) or 0)
            prog = item_progress.get(doc_id) or {}
            done = int(prog.get("done", 0) or 0)
            generating = int(prog.get("generating", 0) or 0)
            queued = int(prog.get("queued", 0) or 0)
            pending = int(prog.get("pending", 0) or 0)
            error = int(prog.get("error", 0) or 0)

            if total_items > 0:
                meta.insights_progress = f"{done}/{total_items}"
                if done >= total_items:
                    meta.insights_status = "done"
                elif generating > 0:
                    meta.insights_status = "generating"
                elif queued > 0:
                    meta.insights_status = "queued"
                elif pending > 0:
                    meta.insights_status = "pending"
                elif error > 0:
                    meta.insights_status = "error"
                else:
                    meta.insights_status = "pending"

                if meta.status == DocStatus.INDEXING_DONE:
                    total_units += total_items
                    done_units += min(done, total_items)
            else:
                # Legacy: 1 doc = 1 insights
                info = legacy_map.get(doc_id, {})
                meta.insights_status = info.get("status")
                meta.insights_progress = info.get("progress", "0/1")
                if meta.status == DocStatus.INDEXING_DONE:
                    total_units += 1
                    done_units += 1 if meta.insights_status == document_insights_store.STATUS_DONE else 0
        docs = list(by_id.values())
        docs.sort(key=lambda x: x.upload_date or "", reverse=True)
        total_indexed = total_units
        with_insights_done = done_units
        return DocumentsListResponse(
            documents=docs,
            total=len(docs),
            insights_summary={"total_indexed": total_indexed, "with_insights_done": with_insights_done},
        )
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/status", response_model=List[DocumentStatusItem])
async def get_documents_status():
    """
    Endpoint específico para DocumentsTable.jsx del frontend.
    Retorna status de documentos con campos esperados por el dashboard.
    """
    try:
        # Obtener todos los documentos
        rows = document_status_store.get_all(status_filter=None, source_filter=None)
        
        # Obtener IDs de documentos
        doc_ids = [r["document_id"] for r in rows]
        
        # Obtener counts de news_items por documento
        item_counts = news_item_store.get_counts_by_document_ids(doc_ids) if doc_ids else {}
        
        # Obtener progreso de insights por documento
        item_progress = news_item_insights_store.get_progress_by_document_ids(doc_ids) if doc_ids else {}
        
        # Construir respuesta
        result = []
        for r in rows:
            doc_id = r["document_id"]
            
            # Convertir uploaded_at a ISO string
            uploaded_at = r.get("ingested_at")
            if isinstance(uploaded_at, datetime):
                uploaded_at = uploaded_at.isoformat()
            
            # Obtener news_items_count
            news_items_count = int(item_counts.get(doc_id, 0) or 0)
            
            # Obtener insights progress
            prog = item_progress.get(doc_id) or {}
            insights_done = int(prog.get("done", 0) or 0)
            insights_total = news_items_count if news_items_count > 0 else 0
            
            result.append(DocumentStatusItem(
                document_id=doc_id,
                filename=r["filename"],
                status=r["status"],
                uploaded_at=uploaded_at or "",
                news_items_count=news_items_count,
                insights_done=insights_done,
                insights_total=insights_total
            ))
        
        # Ordenar por fecha de subida (más recientes primero)
        result.sort(key=lambda x: x.uploaded_at or "", reverse=True)
        
        return result
    except Exception as e:
        logger.error(f"Error getting documents status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/{document_id}/insights")
async def get_document_insights(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Legacy: insights por documento (reporte por archivo). Para PDFs multi-noticia usar /news-items."""
    row = document_insights_store.get_by_document_id(document_id)
    if not row or row.get("status") != document_insights_store.STATUS_DONE:
        raise HTTPException(status_code=404, detail="Insights not available for this document")
    return {"document_id": document_id, "filename": row.get("filename", ""), "content": row.get("content") or ""}


@app.get("/api/documents/{document_id}/segmentation-diagnostic")
async def get_segmentation_diagnostic(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Diagnostic endpoint: Shows how the document was segmented into news items.
    Returns raw OCR text excerpt, detected titles, and segmentation statistics.
    """
    try:
        # Get document info
        doc = document_status_store.get(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get OCR text
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ocr_text FROM document_status WHERE document_id = %s", (document_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result or not result['ocr_text']:
            raise HTTPException(status_code=404, detail="OCR text not available")
        
        ocr_text = result['ocr_text']
        
        # Re-run segmentation to see what it detects
        items = segment_news_items_from_text(ocr_text)
        
        # Get actual stored news items
        stored_items = news_item_store.list_by_document_id(document_id)
        
        # Analyze text characteristics
        lines = ocr_text.split("\n")
        total_lines = len(lines)
        non_empty_lines = len([l for l in lines if l.strip()])
        avg_line_length = sum(len(l) for l in lines) / max(1, len(lines))
        
        # Find potential title candidates
        title_candidates = []
        for i, line in enumerate(lines[:100]):  # First 100 lines
            stripped = line.strip()
            if len(stripped) >= 12 and len(stripped) <= 140:
                letters = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", stripped)
                if letters:
                    upper = sum(1 for ch in letters if ch.isupper())
                    upper_ratio = upper / len(letters)
                    if upper_ratio >= 0.5:  # Mostly uppercase
                        title_candidates.append({
                            "line_number": i + 1,
                            "text": stripped,
                            "upper_ratio": round(upper_ratio, 2)
                        })
        
        return {
            "document_id": document_id,
            "filename": doc.get("filename"),
            "ocr_stats": {
                "total_chars": len(ocr_text),
                "total_lines": total_lines,
                "non_empty_lines": non_empty_lines,
                "avg_line_length": round(avg_line_length, 2)
            },
            "ocr_excerpt": ocr_text[:2000] + ("..." if len(ocr_text) > 2000 else ""),
            "segmentation_result": {
                "detected_items": len(items),
                "items_preview": [
                    {
                        "title": item.get("title"),
                        "body_length": len(item.get("text", "")),
                        "body_excerpt": item.get("text", "")[:200] + "..."
                    }
                    for item in items[:5]
                ]
            },
            "stored_items": {
                "count": len(stored_items),
                "items": [
                    {
                        "news_item_id": item.get("news_item_id"),
                        "item_index": item.get("item_index"),
                        "title": item.get("title"),
                        "status": item.get("status")
                    }
                    for item in stored_items
                ]
            },
            "title_candidates": title_candidates[:20]
        }
        
    except Exception as e:
        logger.error(f"Segmentation diagnostic error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/documents/{document_id}/news-items")
async def list_news_items_for_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """List news items detected for a document, with insights status per item."""
    items = news_item_store.list_by_document_id(document_id)
    insights = news_item_insights_store.list_by_document_id(document_id)
    insights_by_id = {r["news_item_id"]: r for r in insights}
    out = []
    for it in items:
        nid = it["news_item_id"]
        ins = insights_by_id.get(nid, {})
        out.append(
            {
                "news_item_id": nid,
                "document_id": document_id,
                "item_index": it.get("item_index"),
                "title": it.get("title"),
                "insights_status": ins.get("status"),
                "error_message": ins.get("error_message"),
            }
        )
    return {"document_id": document_id, "items": out, "total": len(out)}


@app.get("/api/news-items/{news_item_id}/insights")
async def get_news_item_insights(
    news_item_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get LLM insights for one news item (markdown)."""
    row = news_item_insights_store.get_by_news_item_id(news_item_id)
    if not row or row.get("status") != news_item_insights_store.STATUS_DONE:
        raise HTTPException(status_code=404, detail="Insights not available for this news item")
    return {
        "news_item_id": news_item_id,
        "document_id": row.get("document_id"),
        "title": row.get("title") or "",
        "content": row.get("content") or "",
    }


@app.get("/api/documents/{document_id}/download")
async def download_document(document_id: str):
    """Download the original uploaded document"""
    from fastapi.responses import FileResponse
    import glob

    try:
        # Get the document info from database to find the actual filename
        doc = document_status_store.get(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document not found in database: {document_id}")
        
        # Get the filename from the database
        filename = doc.get('filename')
        if not filename:
            raise HTTPException(status_code=404, detail=f"Filename not found for document: {document_id}")
        
        # Search for the file in the upload folder
        # Try multiple patterns as the file might be stored with different naming conventions
        search_patterns = [
            os.path.join(UPLOAD_DIR, filename),  # Direct filename from DB
            os.path.join(UPLOAD_DIR, document_id),  # document_id as filename
            os.path.join(UPLOAD_DIR, f"*{filename}"),  # Wildcard prefix
        ]
        
        file_path = None
        for pattern in search_patterns:
            if '*' in pattern:
                files = glob.glob(pattern)
                if files:
                    file_path = files[0]
                    break
            elif os.path.exists(pattern):
                file_path = pattern
                break
        
        if not file_path:
            logger.error(f"❌ File not found for document {document_id}")
            logger.error(f"   Filename from DB: {filename}")
            logger.error(f"   Searched patterns: {search_patterns}")
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")

        logger.info(f"📥 Download document: {document_id}")
        logger.info(f"   Filename: {filename}")
        logger.info(f"   Path: {file_path}")

        # Extract the original file name (without timestamp)
        # Format: 1762533561.231156_TU-81-08-Ed.-Gennaio-2025-1.pdf
        basename = os.path.basename(file_path)
        original_filename = basename.split('_', 1)[1] if '_' in basename else basename

        return FileResponse(
            path=file_path,
            media_type='application/pdf',  # Changed to PDF for browser preview
            filename=original_filename,
            headers={
                'Content-Disposition': f'inline; filename="{original_filename}"'  # 'inline' for preview, 'attachment' for download
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/documents/{document_id}/requeue")
async def requeue_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Requeue a document for reprocessing (OCR + Chunking + Indexing).
    
    IMPORTANT: This will NOT delete news_items or insights. Instead:
    - Existing news items are preserved (matched by text_hash)
    - New news items detected will be added
    - Insights are only generated for new items that don't have insights yet
    
    This will:
    1. Delete chunks from Qdrant (will be re-indexed)
    2. Keep news_items and news_item_insights (preserve historical data)
    3. Mark document status as 'processing' with stage 'ocr'
    4. Add document to processing queue
    5. During reprocessing:
       - OCR text is extracted again
       - News segmentation detects items
       - For each detected item:
         * Check if text_hash matches existing item → skip if exists
         * Add new items that don't exist yet
       - Insights are generated only for new items without insights
    
    Requires: Authentication
    """
    try:
        # Get document info
        doc = document_status_store.get(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        filename = doc['filename']
        source = doc.get('source', 'upload')
        news_date = doc.get('news_date')
        
        logger.info(f"🔄 Requeuing document for reprocessing: {filename} ({document_id})")
        logger.info(f"   ⚠️  Preserving existing news_items and insights (will match by text_hash)")
        
        # Get existing news items for logging
        existing_items = news_item_store.list_by_document_id(document_id)
        logger.info(f"   📰 Existing news items: {len(existing_items)} (will be preserved)")
        
        # Get existing insights for logging
        existing_insights = news_item_insights_store.get_progress_by_document_ids([document_id])
        insight_stats = existing_insights.get(document_id, {})
        logger.info(f"   💡 Existing insights: {insight_stats.get('done', 0)} done, {insight_stats.get('pending', 0)} pending")
        
        # 1. Delete ONLY chunks from Qdrant (vectors will be re-indexed)
        if qdrant_connector:
            try:
                qdrant_connector.delete_document(document_id)
                logger.info(f"   ✓ Deleted chunks from Qdrant (will re-index)")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not delete from Qdrant: {e}")
        
        # 2. DO NOT delete news_items or insights - they will be preserved!
        # The reprocessing logic will compare by text_hash and skip duplicates
        logger.info(f"   ✓ Preserving news_items and insights (no deletion)")
        
        # 3. Reset document status to ocr_processing
        document_status_store.update_status(
            document_id, 
            DocStatus.OCR_PROCESSING, 
            processing_stage="ocr",
            num_chunks=0,
            indexed_at=None,
            error_message=None
        )
        # Clear OCR text to force reprocessing
        document_status_store.store_ocr_text(document_id, None)
        # Mark as reprocess requested (persists across restarts)
        document_status_store.mark_for_reprocessing(document_id, requested=True)
        logger.info(f"   ✓ Reset document status to 'processing:ocr' and marked for reprocessing")
        
        # 4. Add to processing queue
        processing_queue_store.enqueue_task(document_id, filename, "ocr", priority=10)
        logger.info(f"   ✓ Added to processing queue")
        
        logger.info(f"✅ Document requeued successfully: {filename}")
        logger.info(f"   During reprocessing:")
        logger.info(f"   - New OCR text will be extracted")
        logger.info(f"   - News items will be detected and compared by text_hash")
        logger.info(f"   - Only NEW items (different hash) will be added")
        logger.info(f"   - Insights will be generated only for new items without insights")
        
        return {
            "message": f"Document {filename} requeued for reprocessing (preserving {len(existing_items)} existing news items)",
            "document_id": document_id,
            "status": DocStatus.OCR_PROCESSING,
            "stage": "ocr",
            "preserved_items": len(existing_items),
            "preserved_insights": insight_stats.get('done', 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Requeue error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workers/retry-errors")
async def retry_error_workers(
    document_ids: Optional[List[str]] = None,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Retry processing for documents that had errors.
    
    If document_ids is provided, retry only those documents.
    If document_ids is None or empty, retry ALL documents with errors from the last 24 hours.
    
    This will:
    1. Find documents with error status in worker_tasks (last 24h)
    2. Reset their status to 'processing' with stage 'ocr'
    3. Clear error messages
    4. Re-enqueue them in processing_queue with high priority (10)
    5. Preserve existing news_items and insights (matched by text_hash)
    
    Requires: Authentication
    """
    try:
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        if document_ids and len(document_ids) > 0:
            # Retry specific documents
            placeholders = ','.join(['%s'] * len(document_ids))
            cursor.execute(f"""
                SELECT DISTINCT wt.document_id, ds.filename
                FROM worker_tasks wt
                LEFT JOIN document_status ds ON wt.document_id = ds.document_id
                WHERE wt.status = 'error'
                AND wt.completed_at > NOW() - INTERVAL '24 hours'
                AND wt.document_id IN ({placeholders})
            """, document_ids)
            error_docs = cursor.fetchall()
        else:
            # Retry ALL documents with errors from last 24h
            cursor.execute("""
                SELECT DISTINCT wt.document_id, ds.filename
                FROM worker_tasks wt
                LEFT JOIN document_status ds ON wt.document_id = ds.document_id
                WHERE wt.status = 'error'
                AND wt.completed_at > NOW() - INTERVAL '24 hours'
                ORDER BY wt.completed_at DESC
            """)
            error_docs = cursor.fetchall()
        
        conn.close()
        
        if not error_docs:
            return {
                "message": "No documents with errors found in the last 24 hours",
                "retried_count": 0,
                "retried_documents": []
            }
        
        retried_count = 0
        retried_documents = []
        errors = []
        
        for row in error_docs:
            document_id = row.get('document_id')
            filename = row.get('filename') or document_id
            
            try:
                # Use the existing requeue logic
                doc = document_status_store.get(document_id)
                if not doc:
                    errors.append(f"Document {document_id} not found")
                    continue
                
                # Reset document status
                document_status_store.update_status(
                    document_id,
                    DocStatus.OCR_PROCESSING,
                    processing_stage="ocr",
                    num_chunks=0,
                    indexed_at=None,
                    error_message=None
                )
                
                # Clear OCR text to force reprocessing
                document_status_store.store_ocr_text(document_id, None)
                
                # Mark for reprocessing
                document_status_store.mark_for_reprocessing(document_id, requested=True)
                
                # Re-enqueue with high priority
                processing_queue_store.enqueue_task(document_id, filename, "ocr", priority=10)
                
                retried_count += 1
                retried_documents.append({
                    "document_id": document_id,
                    "filename": filename
                })
                
                logger.info(f"✅ Retried document with error: {filename} ({document_id})")
                
            except Exception as e:
                error_msg = f"Error retrying {filename}: {str(e)}"
                errors.append(error_msg)
                logger.error(error_msg, exc_info=True)
        
        logger.info(f"🔄 Retry errors completed: {retried_count} documents retried, {len(errors)} errors")
        
        return {
            "message": f"Retried {retried_count} document(s) with errors",
            "retried_count": retried_count,
            "retried_documents": retried_documents,
            "errors": errors if errors else None
        }
        
    except Exception as e:
        logger.error(f"❌ Retry errors error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/documents/{document_id}")
async def delete_document(
    document_id: str,
    current_user: CurrentUser = Depends(require_delete_permission)
):
    """
    Delete document from index

    Requires: SUPER_USER or ADMIN role
    """
    if not qdrant_connector:
        raise HTTPException(status_code=503, detail="Qdrant not connected")

    try:
        logger.info(f"🗑️  Deleting document: {document_id}")
        qdrant_connector.delete_document(document_id)
        document_status_store.delete(document_id)
        document_insights_store.delete(document_id)
        news_item_insights_store.delete_by_document_id(document_id)
        news_item_store.delete_by_document_id(document_id)
        logger.info(f"✅ Document deleted: {document_id}")
        return {"message": f"Document {document_id} deleted"}
    except Exception as e:
        logger.error(f"Deletion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# RAG QUERY
# ============================================================================

@app.post("/api/query", response_model=QueryResponse)
async def query_rag(
    request: QueryRequest,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Main query - Complete RAG Pipeline WITH CONVERSATIONAL MEMORY

    Requires: Authentication (all roles can make queries)

    Processes:
    1. Retrieve conversation history for the user
    2. Query embedding
    3. Retrieval from Qdrant
    4. LLM generation with historical context
    5. Save response in memory
    6. Return answer + sources
    """

    # Use real user ID instead of "default"
    user_id = str(current_user.user_id)
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="RAG Pipeline not initialized")
    
    try:
        start_time = datetime.now()

        # Initialize conversation for this user if it doesn't exist
        if user_id not in user_conversations:
            user_conversations[user_id] = []

        conversation_history = user_conversations[user_id]

        logger.info("=" * 80)
        logger.info(f"❓ QUERY (user: {user_id}): '{request.query}'")
        logger.info(f"   top_k: {request.top_k}")
        logger.info(f"   temperature: {request.temperature}")
        logger.info(f"   History length: {len(conversation_history)} exchanges")
        logger.info("=" * 80)

        # Pass history to the pipeline
        answer, sources = rag_pipeline.query(
            query=request.query,
            top_k=request.top_k,
            temperature=request.temperature,
            history=conversation_history  # ← CONVERSATIONAL MEMORY
        )

        # Save the new exchange in memory
        conversation_history.append({
            "user": request.query,
            "assistant": answer
        })

        # Limit to last 20 exchanges to not consume too much memory
        if len(conversation_history) > 20:
            user_conversations[user_id] = conversation_history[-20:]

        processing_time = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 80)
        logger.info(f"✅ QUERY COMPLETED in {processing_time:.2f}s")
        logger.info(f"   Answer length: {len(answer)} chars")
        logger.info(f"   Sources: {len(sources)}")
        for src in sources:
            logger.info(f"     - {src['filename']} (relevance: {src['similarity_score']:.2%})")
        logger.info(f"   Conversation saved ({len(user_conversations[user_id])} exchanges)")
        logger.info("=" * 80)
        
        return QueryResponse(
            answer=answer,
            sources=[SourceInfo(**src) for src in sources],
            processing_time=processing_time,
            num_sources=len(sources)
        )
        
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ QUERY ERROR: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

@app.post("/api/admin/reindex-all")
async def reindex_all(background_tasks: BackgroundTasks):
    """Reindex all documents"""
    if not rag_pipeline:
        raise HTTPException(status_code=503, detail="RAG Pipeline not initialized")

    logger.info("🔄 Starting reindexing of all documents...")
    background_tasks.add_task(rag_pipeline.reindex_all_documents)
    return {"message": "Reindexing in progress..."}


@app.delete("/api/admin/memory/{user_id}")
async def clear_user_memory(user_id: str):
    """Clear conversational memory for a specific user"""
    if user_id in user_conversations:
        num_exchanges = len(user_conversations[user_id])
        del user_conversations[user_id]
        logger.info(f"🧹 Memory cleared for user '{user_id}' ({num_exchanges} exchanges removed)")
        return {
            "message": f"Memory cleared for user '{user_id}'",
            "exchanges_removed": num_exchanges
        }
    else:
        return {
            "message": f"No memory found for user '{user_id}'",
            "exchanges_removed": 0
        }


@app.delete("/api/admin/memory")
async def clear_all_memory():
    """Clear ALL conversational memory for all users"""
    total_users = len(user_conversations)
    total_exchanges = sum(len(conv) for conv in user_conversations.values())
    user_conversations.clear()
    logger.info(f"🧹 Global memory cleared: {total_users} users, {total_exchanges} total exchanges")
    return {
        "message": "Global memory cleared",
        "users_removed": total_users,
        "exchanges_removed": total_exchanges
    }


@app.get("/api/admin/memory")
async def get_memory_stats():
    """Conversational memory statistics"""
    stats = {
        "total_users": len(user_conversations),
        "users": {}
    }
    for user_id, history in user_conversations.items():
        stats["users"][user_id] = {
            "exchanges": len(history),
            "last_questions": [msg["user"] for msg in history[-3:]]
        }
    return stats


@app.get("/api/admin/stats")
async def get_stats():
    """System statistics"""
    if not qdrant_connector:
        raise HTTPException(status_code=503, detail="Qdrant not connected")

    try:
        return qdrant_connector.get_stats()
    except Exception as e:
        logger.error(f"Statistics error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/admin/logging")
async def get_logging_config(current_user: CurrentUser = Depends(get_current_user)):
    """Get current logging configuration"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return {
        "current_level": get_effective_log_level(),
        "default_level": LOG_LEVEL,
        "has_override": _log_level_override is not None,
        "available_levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
    }


@app.put("/api/admin/logging")
async def update_logging_config(
    level: str,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Change log level at runtime without restarting"""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        set_log_level(level)
        return {
            "success": True,
            "new_level": level.upper(),
            "message": f"Log level changed to {level.upper()} (no restart required)"
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/admin/data-integrity")
async def get_data_integrity(current_user: CurrentUser = Depends(get_current_user)):
    """Data integrity metrics: files vs DB, insights linkage, schema validation."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        # 1. FILES vs DB
        uploads_dir = UPLOAD_DIR
        disk_files = set()
        if os.path.isdir(uploads_dir):
            disk_files = {f for f in os.listdir(uploads_dir) if f.endswith('.pdf')}
        
        cursor.execute("SELECT COUNT(*) as total, COUNT(file_hash) as with_hash FROM document_status")
        result = cursor.fetchone()
        total_db, with_hash = result['total'], result['with_hash']
        
        cursor.execute("SELECT document_id FROM document_status")
        db_doc_ids = {row['document_id'] for row in cursor.fetchall()}
        
        orphaned_disk = disk_files - db_doc_ids
        orphaned_db = db_doc_ids - disk_files
        match_pct = round(len(disk_files & db_doc_ids) / (len(disk_files) or 1) * 100, 1)
        
        if total_db > 0:
            match_pct = round(len(disk_files & db_doc_ids) / max(len(disk_files), total_db) * 100, 1)
        
        files = {
            "total_disk": len(disk_files),
            "total_db": total_db,
            "match": match_pct,
            "orphaned_count": len(orphaned_db),
        }
        
        # 2. INSIGHTS
        cursor.execute("""
            SELECT COUNT(*) FROM news_item_insights nii
            WHERE EXISTS (SELECT 1 FROM document_status ds WHERE ds.document_id = nii.document_id)
        """)
        result = cursor.fetchone()
        linked_insights = result[list(result.keys())[0]] if result else None
        
        cursor.execute("SELECT COUNT(*) FROM news_item_insights")
        result = cursor.fetchone()
        total_insights = result[list(result.keys())[0]] if result else None
        
        cursor.execute("""
            SELECT COUNT(*) FROM news_item_insights nii
            WHERE NOT EXISTS (SELECT 1 FROM document_status ds WHERE ds.document_id = nii.document_id)
        """)
        result = cursor.fetchone()
        orphaned_insights = result[list(result.keys())[0]] if result else None
        
        insights = {
            "total": total_insights,
            "linked": linked_insights,
            "link_percentage": round((linked_insights / (total_insights or 1)) * 100, 1),
            "orphaned_count": orphaned_insights,
        }
        
        # 3. NEWS ITEMS & CHUNKS
        cursor.execute("SELECT COUNT(*) FROM news_items")
        result = cursor.fetchone()
        news_total = result[list(result.keys())[0]] if result else None
        
        cursor.execute("SELECT COALESCE(SUM(num_chunks), 0) FROM document_status")
        result = cursor.fetchone()
        chunks_total = result[list(result.keys())[0]] if result else 0
        
        data_loss_percentage = 0.0
        if total_db > 0 and len(orphaned_db) > 0:
            data_loss_percentage = round(len(orphaned_db) / total_db * 100, 1)
        
        # 4. SCHEMA
        schema = {"join_valid": True, "fk_active": False}
        
        # 5. OVERALL STATUS
        recommendations = []
        if match_pct < 100:
            recommendations.append({"priority": "high", "message": f"{len(orphaned_db)} registros en BD sin archivo físico"})
        if orphaned_insights > 0:
            recommendations.append({"priority": "medium", "message": f"{orphaned_insights} insights con documento inexistente"})
        
        overall = "healthy" if match_pct >= 99 and orphaned_insights == 0 else "warning" if match_pct >= 95 else "error"
        
        conn.close()
        
        return {
            "overall_status": overall,
            "timestamp": datetime.now().isoformat(),
            "files": files,
            "insights": insights,
            "news_items": {"total": news_total},
            "chunks": {"total": int(chunks_total)},
            "data_loss_percentage": data_loss_percentage,
            "schema": schema,
            "recommendations": recommendations,
        }
    except Exception as e:
        logger.error(f"Data integrity error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# DAILY REPORTS (reporte diario por fecha de noticia)
# ============================================================================

@app.get("/api/reports/daily")
async def list_daily_reports(
    limit: int = 100,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List daily reports (report_date, created_at, updated_at). All authenticated users."""
    reports = daily_report_store.get_all(limit=limit)
    result = []
    for r in reports:
        report_date = r["report_date"]
        if isinstance(report_date, datetime):
            report_date = report_date.isoformat()
        
        created_at = r.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        
        updated_at = r.get("updated_at")
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()
        
        result.append({
            "report_date": report_date,
            "created_at": created_at,
            "updated_at": updated_at,
        })
    
    return {"reports": result}


@app.get("/api/reports/daily/{report_date}")
async def get_daily_report(
    report_date: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get full content of a daily report by date (YYYY-MM-DD)."""
    report = daily_report_store.get_by_date(report_date)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report for date {report_date}")
    return {
        "report_date": report["report_date"],
        "content": report["content"],
        "created_at": report.get("created_at"),
        "updated_at": report.get("updated_at"),
    }


@app.get("/api/reports/daily/{report_date}/download", response_class=PlainTextResponse)
async def download_daily_report(
    report_date: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Download daily report as plain text/markdown."""
    report = daily_report_store.get_by_date(report_date)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report for date {report_date}")
    return PlainTextResponse(
        content=report["content"],
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="reporte-{report_date}.md"'},
    )


@app.post("/api/reports/daily/{report_date}/generate")
async def trigger_daily_report_generation(
    report_date: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Admin: trigger generation/regeneration of daily report for a date (YYYY-MM-DD)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", report_date):
        raise HTTPException(status_code=400, detail="report_date must be YYYY-MM-DD")
    ok = generate_daily_report_for_date(report_date)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"No indexed documents with news_date={report_date} or generation failed",
        )
    return {"message": f"Report generated for {report_date}", "report_date": report_date}


# ============================================================================
# WEEKLY REPORTS (reporte semanal por rango news_date)
# ============================================================================

@app.get("/api/reports/weekly")
async def list_weekly_reports(
    limit: int = 52,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List weekly reports (week_start = Monday YYYY-MM-DD, created_at, updated_at). All authenticated users."""
    reports = weekly_report_store.get_all(limit=limit)
    result = []
    for r in reports:
        week_start = r["week_start"]
        if isinstance(week_start, datetime):
            week_start = week_start.isoformat()
        
        created_at = r.get("created_at")
        if isinstance(created_at, datetime):
            created_at = created_at.isoformat()
        
        updated_at = r.get("updated_at")
        if isinstance(updated_at, datetime):
            updated_at = updated_at.isoformat()
        
        result.append({
            "week_start": week_start,
            "created_at": created_at,
            "updated_at": updated_at,
        })
    
    return {"reports": result}


@app.get("/api/reports/weekly/{week_start}")
async def get_weekly_report(
    week_start: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get full content of a weekly report by week_start (Monday YYYY-MM-DD)."""
    report = weekly_report_store.get_by_week_start(week_start)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report for week {week_start}")
    return {
        "week_start": report["week_start"],
        "content": report["content"],
        "created_at": report.get("created_at"),
        "updated_at": report.get("updated_at"),
    }


@app.get("/api/reports/weekly/{week_start}/download", response_class=PlainTextResponse)
async def download_weekly_report(
    week_start: str,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Download weekly report as markdown."""
    report = weekly_report_store.get_by_week_start(week_start)
    if not report:
        raise HTTPException(status_code=404, detail=f"No report for week {week_start}")
    return PlainTextResponse(
        content=report["content"],
        media_type="text/markdown",
        headers={"Content-Disposition": f'attachment; filename="reporte-semanal-{week_start}.md"'},
    )


@app.post("/api/reports/weekly/{week_start}/generate")
async def trigger_weekly_report_generation(
    week_start: str,
    current_user: CurrentUser = Depends(require_admin),
):
    """Admin: trigger generation/regeneration of weekly report (week_start = Monday YYYY-MM-DD)."""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", week_start):
        raise HTTPException(status_code=400, detail="week_start must be YYYY-MM-DD")
    ok = generate_weekly_report_for_week(week_start)
    if not ok:
        raise HTTPException(
            status_code=422,
            detail=f"No indexed documents for that week or generation failed",
        )
    return {"message": f"Weekly report generated for {week_start}", "week_start": week_start}


# ============================================================================
# NOTIFICATIONS (bandeja en la app: reportes actualizados)
# ============================================================================

@app.get("/api/notifications")
async def list_notifications(
    limit: int = 50,
    current_user: CurrentUser = Depends(get_current_user),
):
    """List notifications for current user (report updates). All authenticated users."""
    items = notification_store.get_all_for_user(current_user.user_id, limit=limit)
    unread_count = notification_store.get_unread_count(current_user.user_id)
    return {"notifications": items, "unread_count": unread_count}


@app.patch("/api/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Mark one notification as read."""
    notification_store.mark_read(notification_id, current_user.user_id)
    return {"ok": True}


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Mark all notifications as read for current user."""
    count = notification_store.mark_all_read(current_user.user_id)
    return {"ok": True, "marked": count}


# ============================================================================
# BACKUP & RESTORE ENDPOINTS
# ============================================================================

@app.get("/api/admin/backup/status")
async def get_backup_status(current_user: CurrentUser = Depends(require_admin)):
    """Get backup system status"""
    return backup_service.get_status()


@app.get("/api/admin/backup/providers")
async def list_backup_providers(current_user: CurrentUser = Depends(require_admin)):
    """List configured cloud providers and supported types"""
    return {
        "providers": backup_service.list_providers(),
        "supported_types": backup_service.get_supported_providers()
    }


@app.post("/api/admin/backup/providers")
async def add_backup_provider(
    provider: BackupProviderCreate,
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Add a new cloud provider for backup.

    Example configurations:
    - Mega: {"name": "mega", "type": "mega", "config": {"user": "email", "pass": "password"}}
    - S3: {"name": "aws", "type": "s3", "config": {"provider": "AWS", "access_key_id": "...", "secret_access_key": "...", "region": "eu-west-1"}}
    - Google Drive: {"name": "gdrive", "type": "drive", "config": {"token": "{...}"}}
    - WebDAV/Nextcloud: {"name": "nextcloud", "type": "webdav", "config": {"url": "https://...", "user": "...", "pass": "..."}}
    """
    return backup_service.add_provider(
        name=provider.name,
        provider_type=provider.type,
        config=provider.config
    )


@app.delete("/api/admin/backup/providers/{name}")
async def remove_backup_provider(
    name: str,
    current_user: CurrentUser = Depends(require_admin)
):
    """Remove a configured cloud provider"""
    backup_service.remove_provider(name)
    return {"message": f"Provider '{name}' removed"}


@app.post("/api/admin/backup/providers/{name}/test")
async def test_backup_provider(
    name: str,
    current_user: CurrentUser = Depends(require_admin)
):
    """Test connection to a cloud provider"""
    return backup_service.test_provider(name)


@app.post("/api/admin/backup/run")
async def run_backup(
    request: BackupRunRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Trigger a manual backup.

    If 'provider' is specified, the backup will be uploaded to that cloud provider.
    Otherwise, it will be stored locally only.
    """
    background_tasks.add_task(
        _execute_manual_backup, request.provider, request.remote_path
    )
    return {"message": "Backup started", "status": "running"}


def _execute_manual_backup(provider: Optional[str], remote_path: str):
    """Execute manual backup in background"""
    start_time = datetime.now()
    entry = {
        "type": "manual",
        "started_at": start_time.isoformat(),
        "provider": provider
    }

    try:
        result = backup_service.create_backup()
        entry["backup_name"] = result["backup_name"]
        entry["size_bytes"] = result["size_bytes"]

        if provider:
            upload_result = backup_service.upload_to_cloud(
                result["archive_path"], provider, remote_path
            )
            entry["cloud_upload"] = upload_result

        entry["status"] = "success"
        entry["duration_seconds"] = (datetime.now() - start_time).total_seconds()
        logger.info(f"Manual backup completed: {result['backup_name']}")

    except Exception as e:
        entry["status"] = "error"
        entry["error"] = str(e)
        entry["duration_seconds"] = (datetime.now() - start_time).total_seconds()
        logger.error(f"Manual backup failed: {e}")

    finally:
        backup_service.log_backup(entry)


@app.get("/api/admin/backup/schedule")
async def get_backup_schedule(current_user: CurrentUser = Depends(require_admin)):
    """Get current backup schedule"""
    return backup_scheduler.get_schedule()


@app.post("/api/admin/backup/schedule")
async def set_backup_schedule(
    request: BackupScheduleRequest,
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Set or update the backup schedule.

    Cron expression examples:
    - "0 2 * * *"     → Daily at 2:00 AM
    - "0 3 * * 0"     → Weekly on Sunday at 3:00 AM
    - "0 1 1 * *"     → Monthly on the 1st at 1:00 AM
    - "0 */6 * * *"   → Every 6 hours
    """
    return backup_scheduler.set_schedule(
        cron_expression=request.cron,
        provider=request.provider,
        remote_path=request.remote_path,
        retention=request.retention,
        enabled=request.enabled
    )


@app.get("/api/admin/backup/history")
async def get_backup_history(current_user: CurrentUser = Depends(require_admin)):
    """Get backup execution history"""
    return {"history": backup_service.get_history()}


@app.get("/api/admin/backup/local")
async def list_local_backups(current_user: CurrentUser = Depends(require_admin)):
    """List local backup files"""
    return {"backups": backup_service.list_local_backups()}


@app.delete("/api/admin/backup/local/{filename}")
async def delete_local_backup(
    filename: str,
    current_user: CurrentUser = Depends(require_admin)
):
    """Delete a local backup file"""
    if backup_service.delete_local_backup(filename):
        return {"message": f"Backup '{filename}' deleted"}
    raise HTTPException(status_code=404, detail="Backup not found")


@app.get("/api/admin/backup/cloud/{provider}")
async def list_cloud_backups(
    provider: str,
    current_user: CurrentUser = Depends(require_admin)
):
    """List backups stored on a cloud provider"""
    return {"backups": backup_service.list_cloud_backups(provider)}


@app.post("/api/admin/backup/cloud/{provider}/download")
async def download_cloud_backup(
    provider: str,
    filename: str,
    current_user: CurrentUser = Depends(require_admin)
):
    """Download a backup from cloud to local storage"""
    local_path = backup_service.download_from_cloud(provider, filename)
    return {"message": f"Downloaded to {local_path}", "local_path": local_path}


@app.post("/api/admin/backup/restore")
async def restore_backup(
    request: BackupRestoreRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser = Depends(require_admin)
):
    """
    Restore from a local backup archive.

    WARNING: This will overwrite current data. Use with caution.
    """
    archive_path = os.path.join(BACKUP_DIR, request.filename)
    if not os.path.exists(archive_path):
        raise HTTPException(status_code=404, detail="Backup file not found")

    background_tasks.add_task(
        _execute_restore,
        archive_path,
        request.restore_db,
        request.restore_uploads,
        request.restore_qdrant
    )
    return {"message": "Restore started", "status": "running"}


def _execute_restore(archive_path: str, restore_db: bool, restore_uploads: bool, restore_qdrant: bool):
    """Execute restore in background"""
    try:
        result = backup_service.restore_from_backup(
            archive_path, restore_db, restore_uploads, restore_qdrant
        )
        logger.info(f"Restore completed: {result}")
    except Exception as e:
        logger.error(f"Restore failed: {e}")


# ============================================================================
# DASHBOARD SUMMARY - Métricas consolidadas
# ============================================================================

@app.get("/api/dashboard/summary")
async def get_dashboard_summary(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get consolidated dashboard metrics (files, news items, OCR, chunking, insights, errors).
    
    Uses inbox files as source of truth for total count.
    """
    try:
        import os
        from pathlib import Path
        
        # Count actual files in inbox (excluding processed folder)
        INBOX_DIR = os.getenv("INBOX_DIR", "/app/inbox")
        inbox_files = []
        processed_dir = os.path.join(INBOX_DIR, "processed")
        
        if os.path.isdir(INBOX_DIR):
            for filename in os.listdir(INBOX_DIR):
                filepath = os.path.join(INBOX_DIR, filename)
                if filename != "processed" and os.path.isfile(filepath):
                    inbox_files.append(filename)
        
        total_inbox_files = len(inbox_files)
        
        # 1. ARCHIVOS - Total based on INBOX, completed from DB
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
              COUNT(*) as total_in_db,
              SUM(CASE WHEN status IN (%s, %s, %s, %s, %s) THEN 1 ELSE 0 END) as completed,
              SUM(CASE WHEN status LIKE '%%_processing' THEN 1 ELSE 0 END) as processing,
              SUM(CASE WHEN status = %s THEN 1 ELSE 0 END) as errors,
              MIN(ingested_at) as date_first,
              MAX(ingested_at) as date_last
            FROM document_status
        """, (
            DocStatus.INDEXING_DONE, DocStatus.INSIGHTS_PENDING, DocStatus.INSIGHTS_PROCESSING,
            DocStatus.INSIGHTS_DONE, DocStatus.COMPLETED, DocStatus.ERROR,
        ))
        files_data = cursor.fetchone()
        
        # Use INBOX count as total, but show DB counts for completed/processing/errors
        total_files = max(total_inbox_files, files_data['total_in_db'] or 0)  # Use max to handle edge cases
        completed_files = files_data['completed'] or 0
        processing_files = files_data['processing'] or 0
        error_files = files_data['errors'] or 0
        
        files = {
            "total": total_files,
            "completed": completed_files,
            "processing": processing_files,
            "errors": error_files,
            "pending": max(0, total_files - completed_files - error_files),  # Files not yet processed
            "percentage_done": round((completed_files or 0) / (total_files or 1) * 100, 2),
            "date_first": files_data['date_first'],
            "date_last": files_data['date_last'],
            "inbox_count": total_inbox_files,
        }
        
        # 2. NOTICIAS - Calcular con ponderación por INBOX total
        # Primero, obtener noticias actuales (todas, de todos los documentos)
        cursor.execute("""
            SELECT 
              COUNT(DISTINCT ni.news_item_id) as total_current,
              SUM(CASE WHEN nii.status = 'done' THEN 1 ELSE 0 END) as done,
              SUM(CASE WHEN nii.status IN ('pending', 'queued', 'generating') THEN 1 ELSE 0 END) as pending,
              SUM(CASE WHEN nii.status = 'error' THEN 1 ELSE 0 END) as errors,
              MIN(ni.created_at) as date_first,
              MAX(ni.created_at) as date_last
            FROM news_items ni
            LEFT JOIN news_item_insights nii ON ni.news_item_id = nii.news_item_id
        """)
        news_data = cursor.fetchone()
        
        # Estimar noticias totales esperadas basado en promedio por archivo (usando INBOX total)
        completed_files = files["completed"] or 1
        current_news = news_data['total_current'] or 0
        news_per_file = current_news / completed_files if completed_files > 0 else 0
        pending_files = total_files - completed_files  # Files from INBOX that aren't indexed yet
        expected_total_news = int(current_news + (pending_files * news_per_file))
        
        news_items = {
            "total": expected_total_news,
            "done": news_data['done'] or 0,
            "pending": news_data['pending'] or 0,
            "errors": news_data['errors'] or 0,
            "percentage_done": round((news_data['done'] or 0) / (expected_total_news or 1) * 100, 2),
            "date_first": news_data['date_first'],
            "date_last": news_data['date_last'],
        }
        
        # 3. OCR (Extracción) - Total based on INBOX files
        ocr = {
            "total": total_files,
            "successful": completed_files,
            "processing": processing_files,
            "errors": error_files,
            "percentage_success": round((completed_files or 0) / (total_files or 1) * 100, 2),
        }
        
        # 4. CHUNKING - Estimar basado en archivos INBOX
        chunks_per_file = 20  # Estimación conservadora
        chunks_estimate = {
            "total_chunks": total_files * chunks_per_file,
            "indexed": completed_files * chunks_per_file,
            "pending": pending_files * chunks_per_file,
            "errors": 0,
            "percentage_indexed": round((completed_files or 0) / (total_files or 1) * 100, 2),
        }
        
        # 5. INDEXACIÓN (Qdrant) - Mismo que chunking
        indexing = {
            "total": chunks_estimate["total_chunks"],
            "active": chunks_estimate["indexed"],
            "pending": chunks_estimate["pending"],
            "errors": 0,
            "percentage_indexed": chunks_estimate["percentage_indexed"],
        }
        
        # 6. INSIGHTS - Con ponderación por archivos pendientes
        cursor.execute("""
            SELECT 
              COUNT(DISTINCT nii.news_item_id) as total_current,
              SUM(CASE WHEN nii.status = 'done' THEN 1 ELSE 0 END) as done,
              SUM(CASE WHEN nii.status IN ('pending', 'queued', 'generating') THEN 1 ELSE 0 END) as pending,
              SUM(CASE WHEN nii.status = 'error' THEN 1 ELSE 0 END) as errors
            FROM news_item_insights nii
            WHERE nii.document_id IN (SELECT document_id FROM document_status)
        """)
        insights_data = cursor.fetchone()
        
        # Estimar insights totales esperados usando el mismo promedio de noticias
        expected_total_insights = expected_total_news  # Mismo total que noticias esperadas
        
        # Calcular ETA (estimado basado en velocidad de paralelización)
        parallel_workers = 4
        pending_batches = (insights_data['pending'] or 0) / parallel_workers
        seconds_per_batch = 15  # 4 items en ~15s
        eta_seconds = int(pending_batches * seconds_per_batch)
        
        insights = {
            "total": expected_total_insights,
            "done": insights_data['done'] or 0,
            "pending": insights_data['pending'] or 0,
            "errors": insights_data['errors'] or 0,
            "percentage_done": round((insights_data['done'] or 0) / (expected_total_insights or 1) * 100, 2),
            "parallel_workers": parallel_workers,
            "eta_seconds": eta_seconds,
        }
        
        # 7. ERRORES (Resumen)
        cursor.execute("""
            SELECT 
              COUNT(*) as total_with_errors,
              0 as ocr_errors,
              0 as chunking_errors,
              0 as indexing_errors
            FROM document_status
            WHERE status = %s
        """, (DocStatus.ERROR,))
        errors_data = cursor.fetchone()
        errors = {
            "documents_with_errors": errors_data['total_with_errors'] or 0,
            "ocr_errors": errors_data['ocr_errors'] or 0,
            "chunking_errors": errors_data['chunking_errors'] or 0,
            "indexing_errors": errors_data['indexing_errors'] or 0,
        }
        
        conn.close()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "files": files,
            "news_items": news_items,
            "ocr": ocr,
            "chunking": chunks_estimate,
            "indexing": indexing,
            "insights": insights,
            "errors": errors,
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching summary")


# ============================================================================
# WORKERS STATUS - Monitor de trabajadores activos
# ============================================================================

@app.get("/api/workers/status")
async def get_workers_status(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get detailed status of Generic Worker Pool - shows each worker and their specific current task."""
    global generic_worker_pool
    
    try:
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        # Get ACTIVE workers from worker_tasks (this is the actual running workers)
        cursor.execute("""
            SELECT wt.worker_id, wt.task_type, wt.document_id, ds.filename, wt.status, wt.started_at, wt.error_message, wt.completed_at
            FROM worker_tasks wt
            LEFT JOIN document_status ds ON wt.document_id = ds.document_id
            WHERE wt.status IN (%s, %s)
            ORDER BY wt.task_type, wt.document_id
        """, (WorkerStatus.ASSIGNED, WorkerStatus.STARTED))
        active_workers = cursor.fetchall()
        
        # Get RECENT error workers (last 24 hours) for dashboard visibility
        cursor.execute("""
            SELECT wt.worker_id, wt.task_type, wt.document_id, ds.filename, wt.status, wt.started_at, wt.error_message, wt.completed_at
            FROM worker_tasks wt
            LEFT JOIN document_status ds ON wt.document_id = ds.document_id
            WHERE wt.status = 'error'
            AND wt.completed_at > NOW() - INTERVAL '24 hours'
            ORDER BY wt.completed_at DESC
            LIMIT 50
        """)
        error_workers = cursor.fetchall()
        
        # Get ACTIVE tasks being processed (status='processing') - fallback
        cursor.execute("""
            SELECT task_type, document_id, filename, status 
            FROM processing_queue 
            WHERE status = 'processing'
            ORDER BY task_type, document_id
        """)
        active_pipeline_tasks = cursor.fetchall()
        
        # Get ACTIVE insights being generated
        cursor.execute("""
            SELECT news_item_id, document_id, filename, title 
            FROM news_item_insights 
            WHERE status = 'generating'
            ORDER BY news_item_id
        """)
        active_insights_tasks = cursor.fetchall()
        
        # Get PENDING task counts
        cursor.execute("""
            SELECT task_type, COUNT(*) 
            FROM processing_queue 
            WHERE status = 'pending'
            GROUP BY task_type
        """)
        pending_counts = {row['task_type']: row['count'] for row in cursor.fetchall()}
        
        cursor.execute("""
            SELECT COUNT(*) 
            FROM news_item_insights 
            WHERE status IN ('pending', 'queued')
        """)
        result = cursor.fetchone()
        pending_counts['insights'] = result[list(result.keys())[0]] if result else 0
        
        conn.close()
        
        # Pool status
        pool_active = generic_worker_pool is not None and generic_worker_pool.running
        pool_size = generic_worker_pool.pool_size if pool_active else 0
        
        workers_status = []
        worker_idx = 0
        
        # Process ONLY real workers from worker_tasks table (not virtual workers from tasks)
        # active_workers contains actual running workers with status='started' or 'processing'
        for row in active_workers:
            worker_id = row.get('worker_id')
            task_type = row.get('task_type')
            document_id = row.get('document_id')
            filename = row.get('filename')
            status = row.get('status')
            started_at = row.get('started_at')
            
            worker_idx += 1
            type_map = {
                'ocr': 'OCR',
                'chunking': 'Chunking',
                'indexing': 'Indexing',
                'insights': 'Insights'
            }
            # Convert started_at if it's a datetime, otherwise use as-is
            if started_at:
                if hasattr(started_at, 'isoformat'):
                    started_at_str = started_at.isoformat()
                else:
                    started_at_str = str(started_at)
            else:
                started_at_str = None
            
            # Calculate duration if started_at is available
            duration_sec = None
            if started_at_str and started_at:
                try:
                    if hasattr(started_at, 'timestamp'):
                        # It's a datetime object
                        duration_sec = int((datetime.now() - started_at).total_seconds())                                                                                                                                                                                                                                                                                                                                                                                                                                       
                    else:
                        # It's a string, parse it
                        from datetime import datetime as dt
                        started_dt = dt.fromisoformat(started_at_str.replace('Z', '+00:00'))
                        duration_sec = int((datetime.now(started_dt.tzinfo) - started_dt).total_seconds())
                except Exception as e:
                    logger.debug(f"Could not calculate duration: {e}")
                    pass
            
            workers_status.append({
                "worker_id": worker_id or f"pipeline_worker_{worker_idx}",
                "id": worker_id or f"pipeline_worker_{worker_idx}",  # Keep for backward compatibility
                "type": type_map.get(task_type, "Generic"),
                "worker_number": worker_idx,
                "status": "active",
                "current_task": f"{filename or 'Processing'}",
                "document_id": document_id,
                "filename": filename,
                "task_type": task_type,
                "tasks_assigned": 1,
                "tasks_completed": 0,
                "errors": 0,
                "started_at": started_at_str,
                "duration": duration_sec,
                "last_update": datetime.now().isoformat(),
            })
        
        # Process ERROR workers (recent errors from last 24 hours)
        # Always show errors, even if pool is not active
        for row in error_workers:
            worker_id = row.get('worker_id')
            task_type = row.get('task_type')
            document_id = row.get('document_id')
            filename = row.get('filename')
            status = row.get('status')
            started_at = row.get('started_at')
            error_message = row.get('error_message')
            completed_at = row.get('completed_at')
            
            worker_idx += 1
            type_map = {
                'ocr': 'OCR',
                'chunking': 'Chunking',
                'indexing': 'Indexing',
                'insights': 'Insights'
            }
            
            # Convert started_at if it's a datetime, otherwise use as-is
            if started_at:
                if hasattr(started_at, 'isoformat'):
                    started_at_str = started_at.isoformat()
                else:
                    started_at_str = str(started_at)
            else:
                started_at_str = None
            
            # Calculate duration from started_at to completed_at
            duration_sec = None
            if started_at and completed_at:
                try:
                    if hasattr(started_at, 'timestamp') and hasattr(completed_at, 'timestamp'):
                        duration_sec = int((completed_at - started_at).total_seconds())
                    else:
                        from datetime import datetime as dt
                        start_dt = dt.fromisoformat(started_at_str.replace('Z', '+00:00')) if isinstance(started_at_str, str) else started_at
                        if isinstance(completed_at, str):
                            completed_dt = dt.fromisoformat(completed_at.replace('Z', '+00:00'))
                        else:
                            completed_dt = completed_at
                        duration_sec = int((completed_dt - start_dt).total_seconds())
                except Exception as e:
                    logger.debug(f"Could not calculate error duration: {e}")
                    pass
            
            workers_status.append({
                "worker_id": worker_id or f"pipeline_worker_{worker_idx}",
                "id": worker_id or f"pipeline_worker_{worker_idx}",  # Keep for backward compatibility
                "type": type_map.get(task_type, "Generic"),
                "worker_number": worker_idx,
                "status": "error",
                "current_task": f"{filename or 'Unknown'}",
                "document_id": document_id,
                "filename": filename,
                "task_type": task_type,
                "tasks_assigned": 1,
                "tasks_completed": 0,
                "errors": 1,
                "error_message": error_message or "Unknown error",
                "started_at": started_at_str,
                "completed_at": completed_at.isoformat() if completed_at and hasattr(completed_at, 'isoformat') else (str(completed_at) if completed_at else None),
                "duration": duration_sec,
                "last_update": datetime.now().isoformat(),
            })
            
        # Calculate IDLE workers based on REAL active workers count
        # Only count actual workers from worker_tasks, not tasks from processing_queue
        # Note: error workers don't count against pool_size (they're historical)
        if pool_active:
            real_active_count = len(active_workers)  # Real workers only
            idle_count = max(0, pool_size - real_active_count)  # Ensure non-negative
            
            for i in range(idle_count):
                worker_idx += 1
                # Show breakdown of pending tasks
                total_pending = sum(pending_counts.values())
                pending_breakdown = ", ".join([f"{count} {task_type}" for task_type, count in pending_counts.items() if count > 0])
                
                # Show idle workers as "Generic" type
                workers_status.append({
                    "worker_id": f"pipeline_worker_{worker_idx}",
                    "id": f"pipeline_worker_{worker_idx}",  # Keep for backward compatibility
                    "type": "Generic",
                    "worker_number": worker_idx,
                    "status": "idle",
                    "current_task": f"Waiting ({total_pending} pending: {pending_breakdown})" if total_pending > 0 else "Idle - No pending tasks",
                    "task_type": "any",
                    "tasks_assigned": 0,
                    "tasks_completed": 0,
                    "errors": 0,
                    "duration": None,
                    "last_update": datetime.now().isoformat(),
                })
        
        # Tika Service (OCR backend) - with cached health check
        tika_status = "healthy"
        current_time = time.time()
        
        # Check if cache is still valid
        if (current_time - _tika_health_cache["last_check"]) < _tika_health_cache["cache_ttl"]:
            # Use cached status
            tika_status = _tika_health_cache["status"]
        else:
            # Perform health check with very short timeout (500ms)
            # Use the same Tika URL as OCRService (supports external Tika)
            from ocr_service import OCRService
            tika_url = OCRService.TIKA_URL
            try:
                response = requests.head(f"{tika_url}/", timeout=0.5)
                tika_status = "healthy" if response.status_code < 500 else "unhealthy"
            except requests.exceptions.Timeout:
                # Timeout doesn't mean unhealthy - Tika might be processing
                tika_status = "healthy"
            except:
                tika_status = "unreachable"
            
            # Update cache
            _tika_health_cache["status"] = tika_status
            _tika_health_cache["last_check"] = current_time
        
        workers_status.append({
            "id": "tika_service",
            "type": "Service",
            "worker_number": 0,
            "status": tika_status,
            "current_task": "OCR Backend Server",
            "tasks_completed": 0,
            "errors": 0,
            "last_update": datetime.now().isoformat(),
        })
        
        # Qdrant Service (Vector DB)
        qdrant_status = "healthy"
        try:
            if qdrant_connector:
                # Intentar conexión a Qdrant
                qdrant_connector.client.get_collections()
                qdrant_status = "healthy"
            else:
                qdrant_status = "unavailable"
        except:
            qdrant_status = "unhealthy"
        
        workers_status.append({
            "id": "qdrant_service",
            "type": "Service",
            "worker_number": 0,
            "status": qdrant_status,
            "current_task": "Vector Database Server",
            "tasks_completed": 0,
            "errors": 0,
            "last_update": datetime.now().isoformat(),
        })
        
        # Calculate summary statistics
        total_workers_shown = len([w for w in workers_status if w["type"] != "Service"])
        active_workers_count = len([w for w in workers_status if w["status"] == "active"])
        idle_workers_count = len([w for w in workers_status if w["status"] == "idle"])
        error_workers_count = len([w for w in workers_status if w["status"] == "error"])
        
        return {
            "timestamp": datetime.now().isoformat(),
            "workers": workers_status,
            "summary": {
                "total_workers": total_workers_shown,
                "active_workers": active_workers_count,
                "idle_workers": idle_workers_count,
                "error_workers": error_workers_count,
                "pool_size": pool_size,
                "pending_tasks": pending_counts,  # Show pending tasks breakdown
                "unhealthy_services": len([w for w in workers_status if w["type"] == "Service" and w["status"] != "healthy"]),
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching workers status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching workers status")


@app.get("/api/dashboard/analysis")
async def get_dashboard_analysis(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Comprehensive dashboard analysis endpoint.
    Provides detailed analysis of errors, pipeline status, workers, and database state.
    """
    try:
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        # ===== 1. ERROR ANALYSIS =====
        # Group errors by type and stage
        cursor.execute("""
            SELECT 
                error_message,
                processing_stage,
                COUNT(*) as count,
                (ARRAY_AGG(document_id ORDER BY document_id DESC))[1:10] as document_ids,
                (ARRAY_AGG(filename ORDER BY document_id DESC))[1:10] as filenames
            FROM document_status
            WHERE status = %s
            GROUP BY error_message, processing_stage
            ORDER BY count DESC
        """, (DocStatus.ERROR,))
        error_groups_raw = cursor.fetchall()
        
        error_groups = []
        real_errors_count = 0
        shutdown_errors_count = 0
        
        for row in error_groups_raw:
            error_msg = row['error_message'] or 'Sin mensaje de error'
            is_shutdown_error = 'Shutdown ordenado' in error_msg
            
            if is_shutdown_error:
                shutdown_errors_count += row['count']
            else:
                real_errors_count += row['count']
            
            # Determine cause and auto-fix capability
            cause = "Desconocido"
            can_auto_fix = False
            
            if 'No OCR text found for chunking' in error_msg:
                cause = "Documentos procesados antes del fix de guardado de OCR text"
                can_auto_fix = True
            elif 'Shutdown ordenado' in error_msg:
                cause = "Shutdown ordenado ejecutado - esperado"
                can_auto_fix = False
            elif 'OCR returned empty text' in error_msg:
                cause = "OCR falló o timeout - necesita reprocesamiento"
                can_auto_fix = True
            elif 'chunk_count' in error_msg:
                cause = "Bug corregido: acceso a columna incorrecta en indexing worker"
                can_auto_fix = True
            elif 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                cause = "Timeout durante procesamiento"
                can_auto_fix = True
            
            error_groups.append({
                "error_message": error_msg,
                "stage": row['processing_stage'] or 'unknown',
                "count": row['count'],
                "cause": cause,
                "can_auto_fix": can_auto_fix,
                "document_ids": row['document_ids'] or [],
                "filenames": row['filenames'] or []
            })
        
        # ===== 2. PIPELINE ANALYSIS =====
        stages_analysis = []
        
        # OCR Stage
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'completed') as completed
            FROM processing_queue
            WHERE task_type = 'ocr'
        """)
        ocr_queue = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM document_status
            WHERE status = %s
            AND processing_stage = 'ocr'
            AND ocr_text IS NOT NULL
            AND LENGTH(ocr_text) > 0
            AND NOT EXISTS (
                SELECT 1 FROM processing_queue pq
                WHERE pq.document_id = document_status.document_id
                AND pq.task_type = 'chunking'
                AND pq.status IN (%s, %s)
            )
        """, (DocStatus.OCR_DONE, QueueStatus.PENDING, QueueStatus.PROCESSING))
        ocr_ready_for_chunking = cursor.fetchone()['count']
        
        ocr_blockers = []
        if ocr_ready_for_chunking == 0:
            ocr_blockers.append({
                "reason": "No hay documentos con status='ocr_done' y texto OCR válido",
                "count": 0,
                "solution": "Esperando que documentos completen OCR correctamente"
            })
        
        stages_analysis.append({
            "name": "OCR",
            "pending_tasks": ocr_queue['pending'] or 0,
            "processing_tasks": ocr_queue['processing'] or 0,
            "completed_tasks": ocr_queue['completed'] or 0,
            "ready_for_next": ocr_ready_for_chunking,
            "blockers": ocr_blockers
        })
        
        # Chunking Stage
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'completed') as completed
            FROM processing_queue
            WHERE task_type = 'chunking'
        """)
        chunking_queue = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM document_status
            WHERE processing_stage = 'chunking'
            AND status = %s
            AND NOT EXISTS (
                SELECT 1 FROM processing_queue pq
                WHERE pq.document_id = document_status.document_id
                AND pq.task_type = 'indexing'
                AND pq.status IN (%s, %s)
            )
        """, (DocStatus.CHUNKING_DONE, QueueStatus.PENDING, QueueStatus.PROCESSING))
        chunking_ready_for_indexing = cursor.fetchone()['count']
        
        chunking_blockers = []
        if chunking_ready_for_indexing == 0:
            chunking_blockers.append({
                "reason": "No hay documentos con chunking_done",
                "count": 0,
                "solution": "Esperando que documentos completen chunking"
            })
        
        stages_analysis.append({
            "name": "Chunking",
            "pending_tasks": chunking_queue['pending'] or 0,
            "processing_tasks": chunking_queue['processing'] or 0,
            "completed_tasks": chunking_queue['completed'] or 0,
            "ready_for_next": chunking_ready_for_indexing,
            "blockers": chunking_blockers
        })
        
        # Indexing Stage
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'completed') as completed
            FROM processing_queue
            WHERE task_type = 'indexing'
        """)
        indexing_queue = cursor.fetchone()
        
        indexing_blockers = []
        if (indexing_queue['pending'] or 0) == 0:
            indexing_blockers.append({
                "reason": "No hay documentos con chunking_done listos para indexing",
                "count": 0,
                "solution": "Esperando que documentos completen chunking"
            })
        
        stages_analysis.append({
            "name": "Indexing",
            "pending_tasks": indexing_queue['pending'] or 0,
            "processing_tasks": indexing_queue['processing'] or 0,
            "completed_tasks": indexing_queue['completed'] or 0,
            "ready_for_next": 0,
            "blockers": indexing_blockers
        })
        
        # Insights Stage
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'completed') as completed
            FROM processing_queue
            WHERE task_type = 'insights'
        """)
        insights_queue = cursor.fetchone()
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM news_item_insights
            WHERE status NOT IN ('done', 'generating')
        """)
        insights_pending = cursor.fetchone()['count']
        
        stages_analysis.append({
            "name": "Insights",
            "pending_tasks": insights_queue['pending'] or 0,
            "processing_tasks": insights_queue['processing'] or 0,
            "completed_tasks": insights_queue['completed'] or 0,
            "ready_for_next": insights_pending,
            "blockers": []
        })
        
        # ===== 3. WORKERS ANALYSIS =====
        # Active workers with execution time
        cursor.execute("""
            SELECT 
                wt.worker_id,
                wt.worker_type,
                wt.task_type,
                wt.document_id,
                wt.status,
                wt.started_at,
                EXTRACT(EPOCH FROM (NOW() - wt.started_at)) / 60 as minutes_running,
                ds.filename
            FROM worker_tasks wt
            LEFT JOIN document_status ds ON ds.document_id = wt.document_id
            WHERE wt.status IN ('assigned', 'started')
            ORDER BY wt.started_at ASC
        """)
        active_workers_raw = cursor.fetchall()
        
        active_workers = []
        stuck_workers = []
        
        for row in active_workers_raw:
            minutes = row['minutes_running'] or 0
            is_stuck = minutes > 20
            
            worker_data = {
                "worker_id": row['worker_id'],
                "worker_type": row['worker_type'],
                "task_type": row['task_type'],
                "document_id": row['document_id'],
                "filename": row['filename'],
                "status": row['status'],
                "started_at": row['started_at'].isoformat() if row['started_at'] else None,
                "execution_time_minutes": round(minutes, 1),
                "is_stuck": is_stuck,
                "timeout_limit": 25 if row['task_type'] == 'ocr' else 10,
                "progress_percent": min(100, round((minutes / 25) * 100, 1)) if row['task_type'] == 'ocr' else min(100, round((minutes / 10) * 100, 1))
            }
            
            active_workers.append(worker_data)
            if is_stuck:
                stuck_workers.append(worker_data)
        
        # Workers by type
        cursor.execute("""
            SELECT 
                worker_type,
                task_type,
                status,
                COUNT(*) as count
            FROM worker_tasks
            WHERE completed_at > NOW() - INTERVAL '24 hours'
            GROUP BY worker_type, task_type, status
            ORDER BY worker_type, task_type, status
        """)
        workers_by_type_raw = cursor.fetchall()
        
        workers_by_type = {}
        for row in workers_by_type_raw:
            key = f"{row['worker_type']}/{row['task_type']}"
            if key not in workers_by_type:
                workers_by_type[key] = {}
            workers_by_type[key][row['status']] = row['count']
        
        # ===== 4. DATABASE STATUS ANALYSIS =====
        # Processing Queue by type and status
        cursor.execute("""
            SELECT 
                task_type,
                status,
                COUNT(*) as count
            FROM processing_queue
            GROUP BY task_type, status
            ORDER BY task_type, status
        """)
        queue_by_type = cursor.fetchall()
        
        processing_queue_by_type = {}
        for row in queue_by_type:
            if row['task_type'] not in processing_queue_by_type:
                processing_queue_by_type[row['task_type']] = {}
            processing_queue_by_type[row['task_type']][row['status']] = row['count']
        
        # Worker Tasks summary
        cursor.execute("""
            SELECT 
                status,
                COUNT(*) as count
            FROM worker_tasks
            GROUP BY status
        """)
        worker_tasks_summary_raw = cursor.fetchall()
        
        worker_tasks_summary = {}
        for row in worker_tasks_summary_raw:
            worker_tasks_summary[row['status']] = row['count']
        
        # Detect orphaned tasks (processing without active worker)
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM processing_queue pq
            WHERE pq.status = 'processing'
            AND NOT EXISTS (
                SELECT 1 FROM worker_tasks wt
                WHERE wt.document_id = pq.document_id
                AND wt.task_type = pq.task_type
                AND wt.status IN ('assigned', 'started')
            )
        """)
        orphaned_tasks = cursor.fetchone()['count']
        
        # Detect inconsistencies
        inconsistencies = []
        
        # Doc ocr_done but worker still active
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM document_status ds
            INNER JOIN worker_tasks wt ON wt.document_id = ds.document_id AND wt.task_type = 'ocr'
            WHERE ds.status = %s
            AND wt.status IN (%s, %s)
        """, (DocStatus.OCR_DONE, WorkerStatus.ASSIGNED, WorkerStatus.STARTED))
        ocr_done_worker_active = cursor.fetchone()['count']
        
        if ocr_done_worker_active > 0:
            inconsistencies.append({
                "type": "doc_ocr_done_but_worker_active",
                "description": "Documentos con status='ocr_done' pero worker aún activo",
                "count": ocr_done_worker_active,
                "severity": "low",  # Puede ser normal si worker está finalizando
                "can_auto_fix": False
            })
        
        conn.close()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "errors": {
                "groups": error_groups,
                "real_errors": real_errors_count,
                "shutdown_errors": shutdown_errors_count,
                "total_errors": real_errors_count + shutdown_errors_count
            },
            "pipeline": {
                "stages": stages_analysis,
                "total_blockers": sum(len(s['blockers']) for s in stages_analysis)
            },
            "workers": {
                "active": len(active_workers),
                "stuck": len(stuck_workers),
                "stuck_list": stuck_workers,
                "active_list": active_workers,
                "by_type": workers_by_type,
                "summary": worker_tasks_summary
            },
            "database": {
                "processing_queue": {
                    "by_type": processing_queue_by_type,
                    "orphaned_tasks": orphaned_tasks
                },
                "worker_tasks": worker_tasks_summary,
                "inconsistencies": inconsistencies
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching dashboard analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard analysis: {str(e)}")


@app.post("/api/workers/start")
async def start_workers():
    """Start the unified generic worker pool"""
    global generic_worker_pool
    try:
        from worker_pool import GenericWorkerPool
        
        logger.info("🚀 Starting unified generic worker pool...")
        
        # Check if pool exists AND is running, otherwise recreate
        pool_needs_start = (
            generic_worker_pool is None or 
            not generic_worker_pool.running
        )
        
        if pool_needs_start and ocr_service and rag_pipeline:
            # Stop existing pool if it exists but isn't running
            if generic_worker_pool is not None and not generic_worker_pool.running:
                logger.info("♻️ Stopping stale worker pool...")
                generic_worker_pool.stop()
            
            # Calculate total pool size from env vars
            total_workers = int(os.getenv('PIPELINE_WORKERS_COUNT', 20))
            
            logger.info(f"👷 Initializing generic worker pool with {total_workers} workers...")
            generic_worker_pool = GenericWorkerPool(
                pool_size=total_workers,
                task_dispatcher_func=generic_task_dispatcher,
                db_connection_factory=document_status_store.get_connection
            )
            generic_worker_pool.start()
            logger.info(f"✅ Generic worker pool started with {total_workers} workers")
            logger.info("   Workers can handle: OCR, Chunking, Indexing, Insights")
        elif generic_worker_pool and generic_worker_pool.running:
            logger.info(f"ℹ️ Worker pool already running with {generic_worker_pool.pool_size} workers")
        
        return {
            "status": "success",
            "message": "Generic worker pool started successfully",
            "pool_active": generic_worker_pool is not None and generic_worker_pool.running,
            "pool_size": generic_worker_pool.pool_size if generic_worker_pool else 0,
            "supported_tasks": ["ocr", "chunking", "indexing", "insights"]
        }
    except Exception as e:
        logger.error(f"❌ Error starting worker pool: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error starting worker pool: {str(e)}")


@app.post("/api/workers/shutdown")
async def shutdown_workers_gracefully():
    """
    Shutdown ordenado de workers con rollback de tareas en proceso.
    
    Este endpoint:
    1. Detiene todos los workers activos
    2. Hace rollback de tareas en 'processing' a 'pending' para que puedan ser reprocesadas
    3. Limpia worker_tasks de workers activos
    4. Marca documentos en estados intermedios correctamente
    5. No deja errores en la base de datos
    
    Útil para:
    - Reinicios ordenados del sistema
    - Actualizaciones de código
    - Mantenimiento planificado
    """
    global generic_worker_pool
    
    try:
        logger.info("🛑 Iniciando shutdown ordenado de workers...")
        
        # PASO 1: Detener todos los workers activos
        if generic_worker_pool and generic_worker_pool.running:
            logger.info("⏸️  Deteniendo worker pool...")
            generic_worker_pool.stop()
            logger.info("✅ Worker pool detenido")
        else:
            logger.info("ℹ️  No hay worker pool activo")
        
        # PASO 2: Hacer rollback de tareas en 'processing' a 'pending'
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        # Contar tareas en processing
        cursor.execute("""
            SELECT task_type, COUNT(*) as count
            FROM processing_queue
            WHERE status = 'processing'
            GROUP BY task_type
        """)
        processing_tasks = cursor.fetchall()
        total_processing = sum(row['count'] for row in processing_tasks)
        
        if total_processing > 0:
            logger.info(f"🔄 Haciendo rollback de {total_processing} tareas en 'processing'...")
            
            # Rollback: cambiar 'processing' → 'pending' para que puedan ser reprocesadas
            cursor.execute("""
                UPDATE processing_queue
                SET status = 'pending'
                WHERE status = 'processing'
            """)
            conn.commit()
            
            logger.info(f"✅ {total_processing} tareas revertidas a 'pending':")
            for row in processing_tasks:
                logger.info(f"   - {row['task_type']}: {row['count']} tareas")
        else:
            logger.info("ℹ️  No hay tareas en 'processing' para hacer rollback")
        
        # PASO 3: Limpiar worker_tasks de workers activos (assigned/started)
        cursor.execute("""
            SELECT worker_type, task_type, COUNT(*) as count
            FROM worker_tasks
            WHERE status IN ('assigned', 'started')
            GROUP BY worker_type, task_type
        """)
        active_worker_tasks = cursor.fetchall()
        total_active = sum(row['count'] for row in active_worker_tasks)
        
        if total_active > 0:
            logger.info(f"🧹 Limpiando {total_active} registros de worker_tasks activos...")
            
            # Marcar como 'error' con mensaje de shutdown ordenado
            cursor.execute("""
                UPDATE worker_tasks
                SET status = 'error',
                    completed_at = %s,
                    error_message = 'Shutdown ordenado - tarea revertida a pending'
                WHERE status IN ('assigned', 'started')
            """, (datetime.utcnow().isoformat(),))
            conn.commit()
            
            logger.info(f"✅ {total_active} registros de worker_tasks marcados como 'error' (shutdown ordenado):")
            for row in active_worker_tasks:
                logger.info(f"   - {row['worker_type']}/{row['task_type']}: {row['count']} workers")
        else:
            logger.info("ℹ️  No hay worker_tasks activos para limpiar")
        
        # PASO 4: Verificar y corregir documentos en estados intermedios
        # Documentos que están en upload_pending o _processing (legacy: processing/queued)
        cursor.execute("""
            SELECT processing_stage, status, COUNT(*) as count
            FROM document_status
            WHERE status IN (%s, %s, %s, %s, %s)
            AND processing_stage IS NOT NULL
            GROUP BY processing_stage, status
        """, (
            DocStatus.UPLOAD_PENDING, DocStatus.OCR_PROCESSING,
            DocStatus.CHUNKING_PROCESSING, DocStatus.INDEXING_PROCESSING,
            DocStatus.INSIGHTS_PROCESSING,
        ))
        intermediate_docs = cursor.fetchall()
        
        if intermediate_docs:
            logger.info("📄 Documentos en estados intermedios (se mantendrán para reprocesamiento):")
            for row in intermediate_docs:
                logger.info(f"   - {row['processing_stage']}/{row['status']}: {row['count']} documentos")
        
        # PASO 5: Verificar que no queden inconsistencias
        # Tareas en processing_queue con status 'processing' pero sin worker activo
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM processing_queue pq
            WHERE pq.status = 'processing'
            AND NOT EXISTS (
                SELECT 1 FROM worker_tasks wt
                WHERE wt.document_id = pq.document_id
                AND wt.task_type = pq.task_type
                AND wt.status IN ('assigned', 'started')
            )
        """)
        orphaned_tasks = cursor.fetchone()['count']
        
        if orphaned_tasks > 0:
            logger.warning(f"⚠️  Encontradas {orphaned_tasks} tareas huérfanas (processing sin worker), corrigiendo...")
            cursor.execute("""
                UPDATE processing_queue
                SET status = 'pending'
                WHERE status = 'processing'
                AND NOT EXISTS (
                    SELECT 1 FROM worker_tasks wt
                    WHERE wt.document_id = processing_queue.document_id
                    AND wt.task_type = processing_queue.task_type
                    AND wt.status IN ('assigned', 'started')
                )
            """)
            conn.commit()
            logger.info(f"✅ {orphaned_tasks} tareas huérfanas corregidas")
        
        conn.close()
        
        logger.info("✅ Shutdown ordenado completado exitosamente")
        
        return {
            "status": "success",
            "message": "Shutdown ordenado completado",
            "details": {
                "tasks_rolled_back": total_processing,
                "worker_tasks_cleaned": total_active,
                "orphaned_tasks_fixed": orphaned_tasks,
                "tasks_by_type": {row['task_type']: row['count'] for row in processing_tasks} if processing_tasks else {}
            }
        }
        
    except Exception as e:
        logger.error(f"❌ Error en shutdown ordenado: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error en shutdown ordenado: {str(e)}")


# ============================================================================
# ROOT
# ============================================================================

@app.get("/")
async def root():
    """Endpoint root"""
    return {
        "message": "RAG Enterprise Backend v1.0.0",
        "docs": "/docs",
        "health": "/health",
        "info": "/info"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )