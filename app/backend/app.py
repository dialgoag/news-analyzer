"""
RAG Enterprise Backend - FastAPI Application
Manages: OCR, Embedding, RAG Pipeline, Qdrant Integration
"""

from fastapi import FastAPI, File, UploadFile, HTTPException, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
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

from rag_pipeline import RAGPipeline, RateLimitError, wait_for_ollama, ensure_model
from ocr_service import get_ocr_service, OCRService
from embeddings_service import EmbeddingsService, PerplexityEmbeddingsService
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
from file_ingestion_service import ingest_from_upload, resolve_file_path

# Repository imports (Hexagonal Architecture - REQ-021 Fase 5)
from adapters.driven.persistence.postgres import (
    PostgresDocumentRepository,
    PostgresNewsItemRepository,
    PostgresWorkerRepository
)
from adapters.driven.persistence.postgres.stage_timing_repository_impl import PostgresStageTimingRepository
from core.domain.value_objects.document_id import DocumentId
from core.domain.value_objects.pipeline_status import PipelineStatus, StageEnum, StateEnum, TerminalStateEnum
from core.application.services.report_service import ReportService

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

# Initialize Repositories (Hexagonal Architecture - REQ-021 Fase 5)
# These will gradually replace direct database.py access
document_repository = PostgresDocumentRepository()
news_item_repository = PostgresNewsItemRepository()
worker_repository = PostgresWorkerRepository()
stage_timing_repository = PostgresStageTimingRepository()

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
_perplexity_model = os.getenv("PERPLEXITY_MODEL", "sonar-pro")
LLM_MODEL = os.getenv("LLM_MODEL", "") or (
    _openai_model if LLM_PROVIDER == "openai" else
    _perplexity_model if LLM_PROVIDER == "perplexity" else
    _ollama_model
)
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
CHUNK_SIZE = max(200, int(os.getenv("CHUNK_SIZE", "2000")))
CHUNK_OVERLAP = max(0, int(os.getenv("CHUNK_OVERLAP", "300")))

# Cola de reporte por archivo (insights): throttling OpenAI
INSIGHTS_QUEUE_ENABLED = os.getenv("INSIGHTS_QUEUE_ENABLED", "true").strip().lower() in ("1", "true", "yes")
INSIGHTS_THROTTLE_SECONDS = max(10, int(os.getenv("INSIGHTS_THROTTLE_SECONDS", "60")))
INSIGHTS_MAX_RETRIES = max(1, min(10, int(os.getenv("INSIGHTS_MAX_RETRIES", "5"))))


def generate_insights_for_queue(context: str, label: str):
    """Call insights LLM with runtime provider order from admin settings."""
    import insights_pipeline_control as _ipc

    order = _ipc.provider_order_for_rag()
    om = _ipc.ollama_model_for_insights()
    return rag_pipeline.generate_insights_with_fallback(
        context,
        label,
        provider_order=order,
        insights_ollama_model=om,
    )


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

# ============================================================================
# HEXAGONAL ARCHITECTURE - API ROUTERS (REQ-021 Fase 6)
# ============================================================================
# Register modular routers from adapters/driving/api/v1/routers/
# These routers coexist with legacy endpoints in app.py during transition
try:
    from adapters.driving.api.v1.routers import auth as auth_router
    from adapters.driving.api.v1.routers import documents as documents_router
    from adapters.driving.api.v1.routers import dashboard as dashboard_router
    from adapters.driving.api.v1.routers import workers as workers_router
    from adapters.driving.api.v1.routers import reports as reports_router
    from adapters.driving.api.v1.routers import notifications as notifications_router
    from adapters.driving.api.v1.routers import query as query_router
    from adapters.driving.api.v1.routers import admin as admin_router
    from adapters.driving.api.v1.routers import news_items as news_items_router
    
    # Register all routers
    app.include_router(auth_router.router, prefix="/api/auth", tags=["auth_v2"])
    app.include_router(documents_router.router, prefix="/api/documents", tags=["documents_v2"])
    app.include_router(dashboard_router.router, prefix="/api/dashboard", tags=["dashboard_v2"])
    app.include_router(workers_router.router, prefix="/api/workers", tags=["workers_v2"])
    app.include_router(reports_router.router, prefix="/api/reports", tags=["reports_v2"])
    app.include_router(notifications_router.router, prefix="/api/notifications", tags=["notifications_v2"])
    app.include_router(query_router.router, prefix="/api", tags=["query_v2"])
    app.include_router(admin_router.router, prefix="/api/admin", tags=["admin_v2"])
    app.include_router(news_items_router.router, prefix="/api/news-items", tags=["news-items_v2"])
    
    logger.info("✅ Registered 9 modular routers (v2 - Hexagonal Architecture)")
    logger.info("   Auth (7), Documents (6), Dashboard (3), Workers (4), Reports (8),")
    logger.info("   Notifications (3), Query (1), Admin (24), NewsItems (1)")
    logger.info("   Total: 57 endpoints in modular routers")
except ImportError as e:
    logger.warning(f"⚠️ Could not load modular routers: {e}")
    logger.warning("   Legacy endpoints in app.py will continue to work")


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Return JSON with CORS headers for unhandled exceptions (fixes CORS-blocked 500s)."""
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": f"Internal server error: {type(exc).__name__}"},
    )


# ---------------------------------------------------------------------------
# Simple TTL cache for dashboard endpoints
# ---------------------------------------------------------------------------
import threading as _cache_threading

_dashboard_cache: Dict[str, dict] = {}
_dashboard_cache_lock = _cache_threading.Lock()

_CACHE_TTL = {
    "dashboard_summary": 15,
    "dashboard_analysis": 15,
    "documents_list": 10,
    "documents_status": 10,
    "workers_status": 10,
}


def _cache_get(key: str):
    with _dashboard_cache_lock:
        entry = _dashboard_cache.get(key)
        if entry and (time.time() - entry["ts"]) < _CACHE_TTL.get(key, 15):
            return entry["data"]
    return None


def _cache_set(key: str, data):
    with _dashboard_cache_lock:
        _dashboard_cache[key] = {"data": data, "ts": time.time()}


# Global services
ocr_service: Optional[OCRService] = None
embeddings_service: Optional[EmbeddingsService] = None
rag_pipeline: Optional[RAGPipeline] = None
qdrant_connector: Optional[QdrantConnector] = None
report_service: Optional[ReportService] = None
# generic_worker_pool removed in Fase 5C (master scheduler handles all dispatch)

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
        pending_docs = document_repository.list_all_sync(
            limit=None,
            status=DocStatus.UPLOAD_PENDING,
        )

        if pending_docs:
            for row in pending_docs:
                worker_repository.enqueue_task_sync(
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
            stale_cleaned = worker_repository.delete_old_completed_sync(hours=1)
            if stale_cleaned:
                logger.debug(f"🧹 Cleaned {stale_cleaned} stale completed worker_tasks")

            crashed_workers = worker_repository.list_stuck_workers_sync(
                threshold_minutes=5,
                statuses=[WorkerStatus.STARTED, WorkerStatus.ASSIGNED],
            )
            
            if crashed_workers:
                logger.warning(f"🔧 Detected {len(crashed_workers)} crashed workers, recovering...")
                
                for row in crashed_workers:
                    worker_id = row.get("worker_id")
                    doc_id = row.get("document_id")
                    task_type = row.get("task_type")
                    # Infer insights when doc_id="insight_{id}" (worker_tasks puede tener task_type NULL)
                    if not task_type and doc_id and str(doc_id).startswith("insight_"):
                        task_type = TaskType.INSIGHTS
                    if not task_type:
                        logger.debug(f"   ⏭ Skipping {worker_id} — no task_type (phantom entry)")
                        worker_repository.delete_worker_task_sync(worker_id)
                        continue

                    worker_repository.delete_worker_task_sync(worker_id)
                    if (task_type or "").lower() == "insights" and doc_id and str(doc_id).startswith("insight_doc_"):
                        # Insights lock per document_id: doc_id="insight_doc_{document_id}"
                        crashed_document_id = doc_id[len("insight_doc_"):]
                        worker_repository.reset_processing_task_sync(
                            crashed_document_id,
                            TaskType.INSIGHTS,
                        )
                        recovered_rows = news_item_repository.set_insights_pending_for_document_sync(
                            crashed_document_id,
                            InsightStatus.GENERATING,
                        )
                        if recovered_rows:
                            logger.info(
                                f"   ↻ Recovered insights for document {crashed_document_id[:30]}... "
                                f"({recovered_rows} item(s)) → pending"
                            )
                    elif (task_type or "").lower() == "insights" and doc_id and str(doc_id).startswith("insight_"):
                        # Legacy insights lock: doc_id="insight_{news_item_id}"
                        news_item_id = doc_id[8:]  # strip "insight_"
                        updated_rows = news_item_repository.set_insight_status_if_current_sync(
                            news_item_id,
                            InsightStatus.GENERATING,
                            InsightStatus.PENDING,
                            clear_error=True,
                        )
                        if updated_rows:
                            logger.info(f"   ↻ Recovered insights for {news_item_id[:30]}... → pending")
                    elif (task_type or "").lower() == "indexing_insights" and doc_id and str(doc_id).startswith("insight_"):
                        news_item_id = doc_id[8:]
                        updated_rows = news_item_repository.set_insight_status_if_current_sync(
                            news_item_id,
                            InsightStatus.INDEXING,
                            InsightStatus.DONE,
                        )
                        if updated_rows:
                            logger.info(f"   ↻ Recovered indexing_insights for {news_item_id[:30]}... → done (retry)")
                    else:
                        # OCR/Chunking/Indexing: processing_queue + document_status
                        worker_repository.reset_processing_task_sync(
                            doc_id,
                            task_type,
                        )
                        rollback_to = _RUNTIME_ROLLBACK.get(task_type)
                        if rollback_to:
                            current_status = PipelineTransitions.processing_status(
                                PipelineTransitions.stage_for_task(task_type)
                            )
                            current_doc = document_repository.get_by_id_sync(doc_id)
                            if current_doc and current_doc.get("status") == current_status:
                                document_repository.update_status_sync(
                                    doc_id,
                                    PipelineStatus.from_string(rollback_to, status_type="document"),
                                    clear_error_message=True,
                                )
                        logger.info(f"   ↻ Recovered {task_type} for {doc_id[:30]}... → {rollback_to}")
            
            # Reset orphaned processing (processing sin worker activo)
            # EXCLUIR insights: worker_tasks usa document_id="insight_{id}", processing_queue usa doc_id
            orphans_fixed = worker_repository.reset_orphaned_processing_sync(
                exclude_task_type=TaskType.INSIGHTS
            )
            if orphans_fixed:
                if orphans_fixed > 20:
                    logger.error(f"⚠️ Reset {orphans_fixed} orphans in one cycle — posible loop, revisar")
                else:
                    logger.warning(f"🧹 Reset {orphans_fixed} orphaned processing_queue → pending (no active worker)")

            # Reset orphaned indexing_insights (status=indexing sin worker_tasks — legacy o insert fallido)
            idx_insights_orphans = news_item_repository.reset_orphaned_indexing_insights_sync()
            if idx_insights_orphans:
                logger.warning(f"🧹 Reset {idx_insights_orphans} orphaned indexing_insights → done (retry)")
        except Exception as e:
            logger.error(f"❌ Error cleaning crashed workers: {e}")
        
        # PASO 1: Documentos marcados para reprocesamiento
        try:
            docs_to_reprocess = document_repository.list_pending_reprocess_sync()
            if docs_to_reprocess:
                logger.info(f"🔄 Found {len(docs_to_reprocess)} documents marked for reprocessing")
                for doc in docs_to_reprocess:
                    doc_id = doc['document_id']
                    filename = doc['filename']

                    if not worker_repository.has_queue_task_sync(doc_id, TaskType.OCR):
                        worker_repository.enqueue_task_sync(doc_id, filename, TaskType.OCR, priority=10)
                        logger.info(f"   ✅ Enqueued {filename} for reprocessing")
                    else:
                        logger.debug(f"   ⏳ {filename} already in queue, skipping")
        except Exception as e:
            logger.error(f"❌ Error checking reprocess queue: {e}")
        
        # PASO 1: Monitorear Inbox (delegado a file_ingestion_service)
        if INBOX_DIR and os.path.exists(INBOX_DIR):
            try:
                from file_ingestion_service import ingest_from_inbox, ALLOWED_EXTENSIONS
                processed_dir = os.path.join(INBOX_DIR, "processed")
                for name in os.listdir(INBOX_DIR):
                    if name == "processed":
                        continue
                    inbox_path = os.path.join(INBOX_DIR, name)
                    if not os.path.isfile(inbox_path):
                        continue
                    if Path(name).suffix.lower() not in ALLOWED_EXTENSIONS:
                        continue
                    try:
                        doc_id = ingest_from_inbox(inbox_path, name, UPLOAD_DIR, processed_dir)
                    except Exception as e:
                        logger.warning(f"⚠️  Inbox: Error ingesting {name}: {e}")
            except Exception as e:
                logger.error(f"❌ Inbox monitor error: {e}")
        
        # PASO 1: Documentos con upload_done/ocr_pending sin OCR task → crear task OCR
        pending_for_ocr = []
        for status in (DocStatus.UPLOAD_DONE, DocStatus.OCR_PENDING):
            docs = document_repository.list_all_sync(limit=None, status=status)
            for row in docs:
                doc_id = row["document_id"]
                if worker_repository.has_queue_task_sync(doc_id, TaskType.OCR):
                    continue
                pending_for_ocr.append(row)
                if len(pending_for_ocr) >= 50:
                    break
            if len(pending_for_ocr) >= 50:
                break
        if debug_mode:
            logger.debug(f"🔄 [Master Pipeline] Found {len(pending_for_ocr)} pending documents for OCR")
        if pending_for_ocr:
            for row in pending_for_ocr:
                doc_id, filename = row['document_id'], row['filename']
                worker_repository.enqueue_task_sync(doc_id, filename, TaskType.OCR, priority=1)
            logger.info(f"✅ Created {len(pending_for_ocr)} OCR tasks from pending documents")
        else:
            if debug_mode:
                logger.debug(f"🔄 [Master Pipeline] No pending documents found. Checking database...")
                total_docs = len(document_repository.list_all_sync(limit=None))
                pending_count = len(document_repository.list_all_sync(limit=None, status=DocStatus.UPLOAD_DONE)) + len(
                    document_repository.list_all_sync(limit=None, status=DocStatus.OCR_PENDING)
                )
                logger.debug(f"   Total documents in DB: {total_docs}, Pending: {pending_count}")
        
        # PASO 2: Documentos con OCR completado sin Chunking task → Crear Chunking tasks
        ready_for_chunking = []
        for row in document_repository.list_all_sync(limit=None, status=DocStatus.OCR_DONE):
            if row.get("processing_stage") != Stage.OCR:
                continue
            if not (row.get("ocr_text") or "").strip():
                continue
            doc_id = row["document_id"]
            if worker_repository.has_queue_task_sync(doc_id, TaskType.CHUNKING):
                continue
            ready_for_chunking.append(row)
            if len(ready_for_chunking) >= 50:
                break
        if ready_for_chunking:
            for row in ready_for_chunking:
                doc_id, filename = row['document_id'], row['filename']
                worker_repository.enqueue_task_sync(doc_id, filename, TaskType.CHUNKING, priority=1)
            logger.info(f"✅ Created {len(ready_for_chunking)} Chunking tasks")
        
        # PASO 3: Documentos listos para Indexing sin task en cola → Crear Indexing tasks
        # Incluye: chunking_done (normal) e indexing_pending (recovery/rollback sin task creada)
        ready_for_indexing = []
        for status in (DocStatus.CHUNKING_DONE, DocStatus.INDEXING_PENDING):
            docs = document_repository.list_all_sync(limit=None, status=status)
            for row in docs:
                doc_id = row["document_id"]
                if worker_repository.has_queue_task_sync(doc_id, TaskType.INDEXING):
                    continue
                ready_for_indexing.append(row)
                if len(ready_for_indexing) >= 50:
                    break
            if len(ready_for_indexing) >= 50:
                break
        if ready_for_indexing:
            for row in ready_for_indexing:
                doc_id, filename = row['document_id'], row['filename']
                worker_repository.enqueue_task_sync(doc_id, filename, TaskType.INDEXING, priority=1)
            logger.info(f"✅ Created {len(ready_for_indexing)} Indexing tasks")
        
        # PASO 3.5: Reconciliación — news_items de docs indexados/completed sin registro en news_item_insights
        # Detecta items que nunca se encolaron (e.g. procesados antes de que existiera el pipeline de insights)
        orphan_news_items = []
        eligible_docs = []
        eligible_docs.extend(document_repository.list_all_sync(limit=None, status=DocStatus.INDEXING_DONE))
        eligible_docs.extend(document_repository.list_all_sync(limit=None, status=DocStatus.COMPLETED))
        for doc in eligible_docs:
            doc_id = doc["document_id"]
            for item in news_item_repository.list_by_document_id_sync(doc_id):
                news_item_id = item.get("news_item_id")
                if not news_item_id:
                    continue
                if news_item_repository.list_insights_by_news_item_id_sync(news_item_id):
                    continue
                orphan_news_items.append({
                    "news_item_id": news_item_id,
                    "document_id": item.get("document_id") or doc_id,
                    "filename": item.get("filename") or doc.get("filename"),
                    "title": item.get("title") or "",
                    "text_hash": item.get("text_hash"),
                    "item_index": int(item.get("item_index") or 0),
                })
                if len(orphan_news_items) >= 100:
                    break
            if len(orphan_news_items) >= 100:
                break
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
                current_doc = document_repository.get_by_id_sync(reopen_id)
                if current_doc and current_doc.get("status") == DocStatus.COMPLETED:
                    document_repository.update_status_sync(
                        reopen_id,
                        PipelineStatus.create(StageEnum.INDEXING, StateEnum.DONE),
                        processing_stage=Stage.INDEXING,
                    )
            reopened = sum(1 for _ in reopened_doc_ids)
            logger.info(f"🔄 Reopened {reopened} completed docs to indexing_done for pending insights")
        
        # PASO 4: News items sin Insights task → Marcar como pending para workers
        ready_for_insights = []
        seen_news = set()
        for doc in document_repository.list_all_sync(limit=None):
            doc_id = doc["document_id"]
            for insight in news_item_repository.list_insights_by_document_id_sync(doc_id):
                news_item_id = insight.get("news_item_id")
                if not news_item_id or news_item_id in seen_news:
                    continue
                status = insight.get("status")
                if status in (InsightStatus.DONE, InsightStatus.GENERATING):
                    continue
                seen_news.add(news_item_id)
                ready_for_insights.append(insight)
                if len(ready_for_insights) >= 100:
                    break
            if len(ready_for_insights) >= 100:
                break
        if ready_for_insights:
            docs_to_enqueue: Dict[str, str] = {}
            for row in ready_for_insights:
                news_item_id = row['news_item_id']
                doc_id = row['document_id']
                filename = row.get('filename') or ''
                current_status = row.get("status")
                if current_status not in (InsightStatus.DONE, InsightStatus.GENERATING):
                    news_item_repository.set_insight_status_if_current_sync(
                        news_item_id,
                        current_status,
                        InsightStatus.PENDING,
                    )
                if doc_id:
                    docs_to_enqueue.setdefault(doc_id, filename)
            logger.info(f"✅ Marked {len(ready_for_insights)} news items as pending for insights processing")
            
            enqueued_docs = 0
            for doc_id, filename in docs_to_enqueue.items():
                success = worker_repository.enqueue_task_sync(
                    doc_id,
                    filename or doc_id,
                    TaskType.INSIGHTS,
                    priority=1
                )
                if success:
                    enqueued_docs += 1
            if enqueued_docs:
                logger.info(f"📥 Enqueued {enqueued_docs} document(s) for insights processing")
        
        # PASO 5: Documentos con todos los insights completados Y indexados en Qdrant → Marcar como 'completed'
        ready_for_completion = []
        for row in document_repository.list_all_sync(limit=None, status=DocStatus.INDEXING_DONE):
            doc_id = row["document_id"]
            news_items = news_item_repository.list_by_document_id_sync(doc_id)
            if not news_items:
                continue
            insights = news_item_repository.list_insights_by_document_id_sync(doc_id)
            if not insights:
                continue
            all_done_and_indexed = all(
                insight.get("status") == InsightStatus.DONE and insight.get("indexed_in_qdrant_at")
                for insight in insights
            )
            if all_done_and_indexed:
                ready_for_completion.append(row)
            if len(ready_for_completion) >= 50:
                break
        if ready_for_completion:
            for row in ready_for_completion:
                doc_id, filename = row['document_id'], row['filename']
                document_repository.update_status_sync(
                    doc_id,
                    PipelineStatus.terminal(TerminalStateEnum.COMPLETED),
                    processing_stage=Stage.COMPLETED,
                )
            logger.info(f"✅ Marked {len(ready_for_completion)} documents as completed (all insights done)")
        
        # PASO 6: Despachar workers genéricamente para TODAS las colas
        # El Master es el ÚNICO que asigna tareas a workers
        # Workers son genéricos y pueden procesar cualquier tipo de tarea
        try:
            # Configuración total de workers disponibles (usar todo el pool cuando hay trabajo)
            TOTAL_WORKERS = int(os.getenv("PIPELINE_WORKERS_COUNT", "25"))
            # Límites por tipo: pueden usar hasta TOTAL_WORKERS si hay trabajo
            task_limits = {
                TaskType.OCR: max(1, min(int(os.getenv("OCR_PARALLEL_WORKERS", "25")), TOTAL_WORKERS)),
                TaskType.CHUNKING: max(1, min(int(os.getenv("CHUNKING_PARALLEL_WORKERS", "25")), TOTAL_WORKERS)),
                TaskType.INDEXING: max(1, min(int(os.getenv("INDEXING_PARALLEL_WORKERS", "25")), TOTAL_WORKERS)),
                TaskType.INSIGHTS: max(1, min(int(os.getenv("INSIGHTS_PARALLEL_WORKERS", "1")), TOTAL_WORKERS)),
            }
            
            workers_counts = worker_repository.get_active_workers_counts_sync()
            total_active = int(workers_counts.get("total_active") or 0)
            active_by_type = dict(workers_counts.get("active_by_type") or {})
            
            if debug_mode:
                logger.debug(f"🔄 [Master] Active workers: {total_active}/{TOTAL_WORKERS} total")
                for wtype, count in active_by_type.items():
                    logger.debug(f"    - {wtype}: {count} active")
            
            # Si tenemos slots disponibles, asignar tareas
            slots_available = TOTAL_WORKERS - total_active
            
            if slots_available > 0:
                pending_tasks = worker_repository.list_pending_tasks_for_dispatch_sync(
                    max(1, slots_available * 2)
                )
                
                dispatched_count = 0
                import insights_pipeline_control as _ipc
                for row in pending_tasks:
                    task_id, doc_id, filename, task_type, priority = row['id'], row['document_id'], row['filename'], row['task_type'], row['priority']
                    if dispatched_count >= slots_available:
                        break

                    if _ipc.is_step_paused(str(task_type).lower()):
                        continue
                    
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
                        selected_insight_news_item_id = None
                        selected_insight_title = ""
                        if task_type == TaskType.INSIGHTS:
                            insights_row = news_item_repository.get_next_pending_insight_for_document_sync(doc_id)
                            if insights_row:
                                selected_insight_news_item_id = insights_row['news_item_id']
                                selected_insight_title = insights_row.get('title') or ""
                                # Lock por documento: garantiza procesamiento serial de news por documento.
                                assign_doc_id = f"insight_doc_{doc_id}"
                            else:
                                worker_repository.set_queue_task_status_sync(task_id, QueueStatus.COMPLETED)
                                continue
                        
                        # CRITICAL: Primero intentar asignar worker (verifica duplicados atómicamente con SELECT FOR UPDATE)
                        # Esto actúa como semáforo centralizado - solo UN worker puede asignarse por documento/tarea
                        assigned = worker_repository.assign_worker_to_task_sync(
                            worker_id, task_type.upper(), assign_doc_id, task_type
                        )
                        
                        if not assigned:
                            # Otro worker ya está procesando este documento - saltar (semáforo bloqueado)
                            logger.debug(f"⏸️  [{task_type}] Document {assign_doc_id} already assigned to another worker, skipping")
                            continue
                        
                        worker_repository.set_queue_task_status_sync(task_id, QueueStatus.PROCESSING)
                        
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
                            if selected_insight_news_item_id:
                                from threading import Thread
                                worker_thread = Thread(
                                    target=lambda: asyncio.run(
                                        _insights_worker_task(
                                            selected_insight_news_item_id,
                                            doc_id,
                                            filename,
                                            selected_insight_title,
                                            worker_id,
                                            assign_doc_id,
                                        )
                                    ),
                                    name=f"worker-{worker_id}",
                                    daemon=True
                                )
                                worker_thread.start()
                                dispatched_count += 1
                            else:
                                worker_repository.set_queue_task_status_sync(task_id, QueueStatus.COMPLETED)
                                # assign_doc_id contiene "insight_{news_item_id}" que se obtuvo arriba
                                worker_repository.update_worker_status_sync(
                                    worker_id, assign_doc_id, 'insights', 'error',
                                    error_message="No insights row found"
                                )
                                continue
                        else:
                            logger.warning(f"⚠️  [{task_type}] Unknown task type, marking as pending")
                            worker_repository.set_queue_task_status_sync(task_id, QueueStatus.PENDING)
                            continue
                        
                        logger.info(f"✅ [Master] Dispatched {task_type} worker {worker_id} for {filename}")
                        # Note: dispatched_count ya se incrementó arriba para cada tipo de tarea
                        active_by_type[task_type.upper()] = active_by_type.get(task_type.upper(), 0) + 1
                        
                    except Exception as dispatch_error:
                        logger.error(f"❌ [Master] Failed to dispatch {task_type} worker: {dispatch_error}")
                        worker_repository.set_queue_task_status_sync(task_id, QueueStatus.PENDING)
                
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
        # 1. OCR Service
        logger.info("🔗 [1/6] Loading OCR Service...")
        try:
            ocr_service = get_ocr_service()
            logger.info("✅ OCR Service ready")
        except Exception as e:
            logger.warning(f"⚠️  OCR Service failed: {e}")
            logger.warning("    → System will continue without OCR")
            ocr_service = None

        # 2. Embedding Service (needed before Qdrant for vector_size)
        EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "huggingface").strip().lower()
        if EMBEDDING_PROVIDER == "perplexity":
            logger.info(f"🔗 [2/6] Loading Perplexity Embeddings ({os.getenv('PERPLEXITY_EMBED_MODEL', 'pplx-embed-v1-4b')})...")
            if not os.getenv("PERPLEXITY_API_KEY"):
                raise ValueError("PERPLEXITY_API_KEY required when EMBEDDING_PROVIDER=perplexity")
            embed_dim = int(os.getenv("EMBEDDING_DIMENSION", "1024"))
            embeddings_service = PerplexityEmbeddingsService(
                model=os.getenv("PERPLEXITY_EMBED_MODEL", "pplx-embed-v1-4b"),
                dimensions=embed_dim,
            )
        else:
            logger.info(f"🔗 [2/6] Loading Embedding Service ({EMBEDDING_MODEL})...")
            embeddings_service = EmbeddingsService(model_name=EMBEDDING_MODEL)
        logger.info("✅ Embedding Service ready")

        # 3. Qdrant Connection
        logger.info("🔗 [3/6] Connecting to Qdrant...")
        qdrant_connector = QdrantConnector(
            host=QDRANT_HOST,
            port=QDRANT_PORT,
            api_key=QDRANT_API_KEY if QDRANT_API_KEY else None,
            vector_size=embeddings_service.get_embedding_dimension(),
        )
        qdrant_connector.connect()
        logger.info("✅ Qdrant connected")

        # 4. LLM Provider setup (insights: OpenAI/Perplexity/Ollama)
        if LLM_PROVIDER == "openai":
            logger.info(f"🔗 [4/6] Using OpenAI API (model: {LLM_MODEL})...")
            if not OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai. Set it in .env")
            logger.info("✅ OpenAI API key configured")
        elif LLM_PROVIDER == "perplexity":
            logger.info(f"🔗 [4/6] Using Perplexity API (model: {LLM_MODEL})...")
            if not os.getenv("PERPLEXITY_API_KEY"):
                raise ValueError("PERPLEXITY_API_KEY is required when LLM_PROVIDER=perplexity. Set it in .env")
            logger.info("✅ Perplexity API key configured")
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
        report_service = ReportService(
            document_repository=document_repository,
            qdrant_connector=qdrant_connector,
            rag_pipeline=rag_pipeline,
            daily_report_store=daily_report_store,
            weekly_report_store=weekly_report_store,
            notification_store=notification_store,
        )
        logger.info("✅ ReportService ready")

        import insights_pipeline_control as _ipc_controls
        _ipc_controls.refresh_from_db()
        logger.info("✅ Pipeline runtime controls (pauses / insights LLM) loaded from database")

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

        # Workers Health Check removed in Fase 5C
        # Master Pipeline Scheduler handles all worker dispatch directly
        print("\n✅ ===== WORKER DISPATCH HANDLED BY MASTER SCHEDULER ===== ✅\n", flush=True)
        logger.info("✅ Master Scheduler handles all worker dispatch (no separate health check needed)")

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
    whose news_date equals report_date.
    """
    if not report_service:
        logger.warning("Daily report: ReportService not ready, skipping")
        return False
    return report_service.generate_daily_report(report_date)


def run_weekly_report_job():
    """Scheduled job: generate weekly report for previous week (Monday–Sunday)."""
    from datetime import date, timedelta
    today = date.today()
    last_monday = today - timedelta(days=today.weekday() + 7)
    generate_weekly_report_for_week(last_monday.isoformat())


def generate_weekly_report_for_week(week_start: str) -> bool:
    """Generate weekly report for week starting week_start (Monday YYYY-MM-DD). Week = week_start to week_start+6 days."""
    if not report_service:
        logger.warning("Weekly report: ReportService not ready, skipping")
        return False
    return report_service.generate_weekly_report(week_start)


# ============================================================================
# PYDANTIC MODELS
# ============================================================================

class InsightsPipelineUpdate(BaseModel):
    """Partial update for pipeline runtime controls (admin); persisted in pipeline_runtime_kv."""
    pause_generation: Optional[bool] = None
    pause_indexing_insights: Optional[bool] = None
    pause_steps: Optional[Dict[str, bool]] = None
    pause_all: Optional[bool] = None
    resume_all: Optional[bool] = None
    provider_mode: Optional[str] = None
    provider_order: Optional[List[str]] = None
    ollama_model: Optional[str] = None  # empty/null clears override (use env / default)


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


class ParallelNewsItem(BaseModel):
    news_item_id: str
    document_id: str
    title: Optional[str] = None
    item_index: int = 0
    news_status: Optional[str] = None
    insight_status: Optional[str] = None
    index_status: Optional[str] = None
    error_message: Optional[str] = None


class ParallelDocumentFlow(BaseModel):
    document_id: str
    filename: str
    status: str
    processing_stage: Optional[str] = None
    ingested_at: Optional[str] = None
    news_items_total: int = 0
    news_items: List[ParallelNewsItem] = Field(default_factory=list)


class ParallelFlowResponse(BaseModel):
    documents: List[ParallelDocumentFlow]
    meta: Dict[str, int]


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


# NOTE:
# Auth API is now served only by adapters.driving.api.v1.routers.auth


# ============================================================================
# DOCUMENT MANAGEMENT
# ============================================================================

# Supported formats
ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx',
    '.odt', '.rtf', '.html', '.xml', '.json', '.csv', '.md',
    '.jpg', '.jpeg', '.png', '.gif', '.bmp'
}

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
    upload_stage_closed = False
    try:
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING),
            processing_stage=Stage.OCR,
            clear_error_message=True
        )

        try:
            stage_timing_repository.record_stage_end_sync(
                document_id=document_id,
                stage='upload',
                status='done'
            )
            upload_stage_closed = True
        except Exception as timing_err:
            logger.warning(f"Stage timing end (upload→done) failed for {document_id}: {timing_err}")

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
            document_repository.store_ocr_text_sync(document_id, text)
        except Exception as e:
            logger.error(f"      ❌ OCR FAILED: {str(e)}", exc_info=True)
            text = ""

        ocr_time = (datetime.now() - start_ocr).total_seconds()
        logger.info(f"        ✅ Extracted {len(text)} characters in {ocr_time:.2f}s")

        if not text or len(text.strip()) == 0:
            logger.warning(f"⚠️  WARNING: OCR returned empty text!")
            document_repository.update_status_sync(
                document_id,
                PipelineStatus.terminal(TerminalStateEnum.ERROR),
                error_message="OCR returned empty text",
                processing_stage=Stage.OCR
            )
            return
        
        # STEP 2: Segmentación en noticias + chunking
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.create(StageEnum.CHUNKING, StateEnum.PROCESSING),
            processing_stage=Stage.CHUNKING,
            clear_indexed_at=True
        )
        logger.info(f"  [2/3] News segmentation + chunking...")
        start_chunk = datetime.now()

        try:
            items = segment_news_items_from_text(text)
            if not items:
                document_repository.update_status_sync(
                    document_id,
                    PipelineStatus.terminal(TerminalStateEnum.ERROR),
                    error_message="No news items detected",
                    processing_stage=Stage.CHUNKING
                )
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
            document_repository.update_status_sync(
                document_id,
                PipelineStatus.terminal(TerminalStateEnum.ERROR),
                error_message=f"Chunking failed: {e}",
                processing_stage=Stage.CHUNKING
            )
            return

        chunk_time = (datetime.now() - start_chunk).total_seconds()
        logger.info(f"        ✅ {len(chunk_records or [])} chunk record(s) created in {chunk_time:.2f}s")

        if not chunk_records:
            logger.error(f"❌ ERROR: No chunks created!")
            document_repository.update_status_sync(
                document_id,
                PipelineStatus.terminal(TerminalStateEnum.ERROR),
                error_message="No chunks created",
                processing_stage=Stage.CHUNKING
            )
            return
        
        # STEP 3: Embedding & Indexing
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.create(StageEnum.INDEXING, StateEnum.PROCESSING),
            processing_stage=Stage.INDEXING
        )
        logger.info(f"  [3/3] Embedding & Indexing...")
        start_index = datetime.now()

        try:
            rag_pipeline.index_chunk_records(chunk_records)
        except Exception as e:
            logger.error(f"      ❌ INDEXING FAILED: {str(e)}", exc_info=True)
            document_repository.update_status_sync(
                document_id,
                PipelineStatus.terminal(TerminalStateEnum.ERROR),
                error_message=f"Indexing failed: {e}",
                processing_stage=Stage.INDEXING
            )
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

        news_date = parse_news_date_from_filename(filename)
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.create(StageEnum.INDEXING, StateEnum.DONE),
            indexed_at=datetime.utcnow().isoformat(),
            num_chunks=len(chunk_records),
            news_date=news_date,
            processing_stage=Stage.INDEXING
        )
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
                        news_item_insights_store.set_status(
                            nid, news_item_insights_store.STATUS_DONE,
                            content=existing.get("content"), llm_source=existing.get("llm_source")
                        )
                        logger.info(f"News item insights reused for {nid} ({title})")
                logger.info(f"News item insights queued/reused for {len(items)} item(s)")
            except Exception as eq_err:
                logger.warning(f"News item insights enqueue/reuse failed: {eq_err}")

    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ CRITICAL PROCESSING ERROR {filename}: {str(e)}")
        logger.error(traceback.format_exc())
        logger.error("=" * 80)
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.terminal(TerminalStateEnum.ERROR),
            error_message=str(e)
        )
        if not upload_stage_closed:
            try:
                stage_timing_repository.record_stage_end_sync(
                    document_id=document_id,
                    stage='upload',
                    status='error',
                    error_message=str(e)[:200]
                )
            except Exception as timing_err:
                logger.warning(f"Stage timing end (upload→error) failed for {document_id}: {timing_err}")

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
    import insights_pipeline_control as _ipc
    if _ipc.is_generation_paused():
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
                content, _ = generate_insights_for_queue(context, filename)
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
    import insights_pipeline_control as _ipc
    if _ipc.is_generation_paused():
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
            news_item_insights_store.set_status(
                news_item_id, news_item_insights_store.STATUS_DONE,
                content=existing["content"], llm_source=existing.get("llm_source")
            )
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
                content, llm_source = generate_insights_for_queue(context, label)
                news_item_insights_store.set_status(news_item_id, news_item_insights_store.STATUS_DONE, content=content, llm_source=llm_source)
                logger.info(f"News item insights generated for {news_item_id} ({title}) via {llm_source}")
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


async def _insights_worker_task(
    news_item_id: str,
    document_id: str,
    filename: str,
    title: str,
    worker_id: str,
    worker_task_doc_id: str | None = None,
):
    """
    Background worker for insights generation with LangGraph + LangMem.
    
    Workflow:
    1. Check text_hash dedup (reuse existing insights from other news_items)
    2. Fetch chunks from Qdrant
    3. Build context
    4. Call InsightsWorkerService (LangGraph workflow + LangMem cache)
    5. Save results with provider/token metadata
    
    Features:
    - LangMem cache (PostgreSQL-backed, 30 days TTL)
    - Text hash deduplication (saves API calls across news_items)
    - LangGraph workflow (extraction + analysis + validation + retry)
    - Provider fallback (OpenAI → Ollama)
    - Token tracking
    
    REQ-021 Phase 5F: Added stage timing tracking (records at document-level)
    """
    try:
        task_doc_id = worker_task_doc_id or f"insight_{news_item_id}"
        logger.info(f"[{worker_id}] Assigned insights for: {title or 'untitled'}")
        
        # 1. RECORD STAGE START for this specific news_item (NEW: stage timing)
        stage_timing_repository.record_stage_start_sync(
            document_id=document_id,
            news_item_id=news_item_id,  # Tracking individual news_item
            stage='insights',
            metadata={'worker_id': worker_id, 'news_item_id': news_item_id, 'title': title}
        )
        
        # 2. Mark as started
        worker_repository.update_worker_status_sync(
            worker_id, task_doc_id, 'insights', 'started'
        )
        
        # DEDUP: Check if an insight with the same text_hash already exists (saves API costs)
        # This is different from LangMem cache: text_hash dedup reuses insights from OTHER news_items
        text_hash = news_item_repository.get_text_hash_for_news_item_sync(news_item_id)
        
        if text_hash:
            existing = news_item_repository.get_done_insight_by_text_hash_sync(text_hash)
            if existing and existing.get("content") and existing.get("news_item_id") != news_item_id:
                news_item_repository.set_insight_status_sync(
                    news_item_id,
                    InsightStatus.DONE,
                    content=existing["content"],
                    llm_source=existing.get("llm_source", "dedup")
                )
                
                # RECORD STAGE END as done (dedup = done sin API call)
                stage_timing_repository.record_stage_end_sync(
                    document_id=document_id,
                    news_item_id=news_item_id,
                    stage='insights',
                    status='done'
                )
                
                worker_repository.update_worker_status_sync(
                    worker_id, task_doc_id, 'insights', 'completed'
                )
                worker_repository.mark_task_completed_sync(task_doc_id, 'insights')
                logger.info(
                    f"[{worker_id}] ♻️ Reused insight via text_hash dedup for {news_item_id} "
                    f"(saved API call)"
                )
                return
        
        # Set to generating in insights store
        news_item_repository.set_insight_status_sync(news_item_id, InsightStatus.GENERATING)
        
        # Fetch chunks from Qdrant
        chunks = qdrant_connector.get_chunks_by_news_item_ids([news_item_id], max_chunks=500)
        if not chunks:
            logger.warning(f"[{worker_id}] No chunks found for {news_item_id}")
            
            # RECORD STAGE END with error
            stage_timing_repository.record_stage_end_sync(
                document_id=document_id,
                news_item_id=news_item_id,
                stage='insights',
                status='error',
                error_message="No chunks"
            )
            
            news_item_repository.set_insight_status_sync(
                news_item_id, 
                InsightStatus.ERROR, 
                error_message="No chunks"
            )
            worker_repository.update_worker_status_sync(
                worker_id, task_doc_id, 'insights', 'error',
                error_message="No chunks"
            )
            worker_repository.mark_task_completed_sync(task_doc_id, 'insights')
            return
        
        # Build context
        texts = [c.get("text", "") for c in chunks if c.get("text")]
        context = "\n\n".join(texts)
        if len(context) > 80000:
            context = context[:80000] + "\n\n[... truncado ...]"
        
        logger.info(
            f"[{worker_id}] Generating insights for {news_item_id} "
            f"({len(context)} chars, {len(chunks)} chunks)"
        )
        
        # Generate insights with InsightsWorkerService (LangGraph + LangMem)
        from core.application.services.insights_worker_service import get_insights_worker_service
        
        service = get_insights_worker_service(
            cache_backend="postgres",
            cache_ttl_days=30,  # 30 days
            cache_max_size=10000
        )
        
        result = await service.generate_insights(
            news_item_id=news_item_id,
            document_id=document_id,
            context=context,
            title=title or filename,
            max_attempts=INSIGHTS_MAX_RETRIES
        )
        
        # Log cache/dedup information
        if result.from_cache:
            logger.info(
                f"[{worker_id}] ♻️ LangMem cache HIT for {news_item_id} "
                f"(saved {result.total_tokens} tokens, ~${result.total_tokens * 0.00002:.4f})"
            )
        else:
            logger.info(
                f"[{worker_id}] 💸 API call made: "
                f"provider={result.provider_used}, model={result.model_used}, "
                f"tokens={result.total_tokens} "
                f"(extract={result.extraction_tokens}, analyze={result.analysis_tokens})"
            )
        
        # Save to database
        llm_source = f"{result.provider_used}/{result.model_used}"
        news_item_repository.set_insight_status_sync(
            news_item_id,
            InsightStatus.DONE,
            content=result.content,
            llm_source=llm_source
        )
        
        # 3. RECORD STAGE END as done (NEW: stage timing)
        stage_timing_repository.record_stage_end_sync(
            document_id=document_id,
            news_item_id=news_item_id,
            stage='insights',
            status='done'
        )
        
        worker_repository.update_worker_status_sync(
            worker_id, task_doc_id, 'insights', 'completed'
        )
        worker_repository.mark_task_completed_sync(task_doc_id, 'insights')
        
        logger.info(
            f"[{worker_id}] ✅ Insights generated for {news_item_id}: "
            f"{len(result.content)} chars, {result.total_tokens} tokens"
        )
        
    except Exception as e:
        logger.error(f"[{worker_id}] Insights error: {e}", exc_info=True)
        try:
            err_msg = str(e)[:200]
            
            # RECORD STAGE END with error (NEW: stage timing)
            stage_timing_repository.record_stage_end_sync(
                document_id=document_id,
                news_item_id=news_item_id,
                stage='insights',
                status='error',
                error_message=err_msg
            )
            
            news_item_repository.set_insight_status_sync(
                news_item_id,
                InsightStatus.ERROR,
                error_message=err_msg
            )
            worker_repository.update_worker_status_sync(
                worker_id, task_doc_id, 'insights', 'error',
                error_message=err_msg
            )
            worker_repository.mark_task_completed_sync(task_doc_id, 'insights')
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
    import insights_pipeline_control as _ipc
    if _ipc.is_generation_paused():
        return

    try:
        parallel_workers = max(1, min(
            int(os.getenv("INSIGHTS_PARALLEL_WORKERS", "1")),
            10
        ))

        # Check semaphore: active insights workers
        workers_counts = worker_repository.get_active_workers_counts_sync()
        active_workers = int((workers_counts.get("active_by_type") or {}).get("Insights", 0))
        
        if active_workers >= parallel_workers:
            logger.debug(f"Insights: {active_workers}/{parallel_workers} busy, skipping")
            return
        
        # Get ONE pending insights task
        # First try: from processing_queue if task_type='insights'
        task_dict = worker_repository.get_pending_task_sync(TaskType.INSIGHTS)
        
        if not task_dict:
            # Fallback hexagonal: usar store/repository en lugar de SQL directo
            insight_row = news_item_repository.get_next_pending_insight_sync()
            if not insight_row:
                return
            news_item_id = insight_row['news_item_id']
            document_id = insight_row['document_id']
            filename = insight_row.get('filename') or document_id
            title = insight_row.get('title', '')
        else:
            # From processing_queue
            document_id = task_dict['document_id']
            filename = task_dict['filename']
            insight_row = news_item_repository.get_next_pending_insight_for_document_sync(document_id)
            if not insight_row:
                task_id = task_dict.get('id')
                if task_id:
                    worker_repository.set_queue_task_status_sync(task_id, QueueStatus.COMPLETED)
                return
            news_item_id = insight_row['news_item_id']
            title = insight_row.get('title') or ""
        
        # Create unique worker
        worker_id = f"insights_{os.getpid()}_{int(time.time() * 1000) % 100000}"
        
        logger.info(f"Insights scheduler: Dispatching {worker_id} for {title or filename}")
        
        # CRITICAL: Primero intentar asignar worker (verifica duplicados atómicamente con SELECT FOR UPDATE)
        # Esto actúa como semáforo centralizado - solo UN worker puede asignarse por news_item_id
        # Usamos "insight_{news_item_id}" como document_id único para insights
        assigned = worker_repository.assign_worker_to_task_sync(
            worker_id, 'Insights', f"insight_{news_item_id}", 'insights'
        )
        
        if not assigned:
            # Otro worker ya está procesando este insight - saltar (semáforo bloqueado)
            logger.debug(f"⏸️  [Insights] News item {news_item_id} already assigned to another worker, skipping")
            return
        
        # Si hay tarea en processing_queue, marcar como processing solo si asignación fue exitosa
        if task_dict:
            task_id = task_dict.get('id')
            if task_id:
                worker_repository.set_queue_task_status_sync(task_id, QueueStatus.PROCESSING)
        
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
            worker_repository.update_worker_status_sync(
                worker_id, f"insight_{news_item_id}", 'insights', 'error',
                error_message=f"Failed to start thread: {str(e)[:200]}"
            )
        
    except Exception as e:
        logger.error(f"Insights scheduler error: {e}", exc_info=True)



# ============================================================================
# WORKER TASKS (Refactored with Hexagonal Architecture - REQ-021 Fase 5A)
# ============================================================================
# Legacy GenericWorkerPool handlers removed in Fase 5C
# Master scheduler now dispatches directly to repository-based workers
# ============================================================================

async def _ocr_worker_task(document_id: str, filename: str, worker_id: str):
    """
    Background worker task: processes ONE OCR task independently.
    Each worker has its own ID and marks progress in worker_tasks table.
    If worker crashes, task is marked 'started' with worker_id for recovery.
    
    REQ-021 Fase 5: Refactored to use DocumentRepository (Hexagonal Architecture)
    REQ-021 Phase 5F: Added stage timing tracking with document_stage_timing
    """
    try:
        logger.info(f"[{worker_id}] Assigned OCR task for: {filename}")
        
        # 1. RECORD STAGE START (NEW: stage timing)
        stage_timing_repository.record_stage_start_sync(
            document_id=document_id,
            stage='ocr',
            metadata={'worker_id': worker_id, 'filename': filename}
        )
        
        # 2. Mark as started (worker_id identifies this worker's progress)
        worker_repository.update_worker_status_sync(
            worker_id, document_id, 'ocr', 'started'
        )
        
        # Get document using repository
        doc_id = DocumentId(document_id)
        document = await document_repository.get_by_id(doc_id)
        
        if not document:
            logger.error(f"[{worker_id}] Document not in status table: {document_id}")
            
            # RECORD STAGE END with error
            stage_timing_repository.record_stage_end_sync(
                document_id, 'ocr', 'error', error_message="Document not found in DB"
            )
            
            worker_repository.update_worker_status_sync(
                worker_id, document_id, 'ocr', 'error',
                error_message="Document not found in DB"
            )
            worker_repository.mark_task_completed_sync(document_id, 'ocr')
            return
        
        # Resolve actual file path (handles .pdf extension, Fix #95)
        try:
            file_path = resolve_file_path(document_id, UPLOAD_DIR)
        except FileNotFoundError as e:
            logger.error(f"[{worker_id}] File not found: {e}")
            
            # RECORD STAGE END with error
            stage_timing_repository.record_stage_end_sync(
                document_id, 'ocr', 'error', error_message="File not found"
            )
            
            # Update document status to error using repository
            error_status = PipelineStatus.terminal(TerminalStateEnum.ERROR)
            await document_repository.update_status(
                doc_id, 
                error_status,
                error_message="File not found"
            )
            
            worker_repository.update_worker_status_sync(
                worker_id, document_id, 'ocr', 'error',
                error_message="File not found"
            )
            worker_repository.mark_task_completed_sync(document_id, 'ocr')
            return
        
        logger.info(f"[{worker_id}] Processing OCR: {filename} ({len(open(file_path, 'rb').read()) / 1024 / 1024:.1f}MB)")
        
        # Run sync OCR extraction only (no chunking/indexing)
        # Extract OCR text
        try:
            text, doc_type, content_hash = await asyncio.to_thread(_extract_ocr_only, file_path, document_id, filename)
            
            # Store OCR text in database (CRITICAL: chunking worker needs this)
            await document_repository.store_ocr_text(doc_id, text)
            
            # Update document status and metadata using repository
            ocr_done_status = PipelineStatus.create(StageEnum.OCR, StateEnum.DONE)
            await document_repository.update_status(
                doc_id,
                ocr_done_status,
                processing_stage=Stage.OCR,
                indexed_at=datetime.utcnow().isoformat(),
                num_chunks=0,
                doc_type=doc_type,
            )
            
            # 3. RECORD STAGE END as done (NEW: stage timing)
            stage_timing_repository.record_stage_end_sync(
                document_id, 'ocr', 'done'
            )
            
            logger.info(f"[{worker_id}] ✅ OCR completed: {filename}")
            
        except Exception as e:
            logger.error(f"[{worker_id}] OCR extraction failed: {e}", exc_info=True)
            raise
        
        # Mark completed (slot freed automatically for next worker)
        worker_repository.update_worker_status_sync(
            worker_id, document_id, 'ocr', 'completed'
        )
        worker_repository.mark_task_completed_sync(document_id, 'ocr')
        
        logger.info(f"[{worker_id}] ✅ OCR completed: {filename}")
        
    except Exception as e:
        logger.error(f"[{worker_id}] OCR worker error: {e}", exc_info=True)
        try:
            err_msg = str(e)[:200]
            
            # RECORD STAGE END with error (NEW: stage timing)
            stage_timing_repository.record_stage_end_sync(
                document_id, 'ocr', 'error', error_message=err_msg
            )
            
            # Update status using repository
            error_status = PipelineStatus.terminal(TerminalStateEnum.ERROR)
            doc_id = DocumentId(document_id)
            await document_repository.update_status(
                doc_id,
                error_status,
                error_message=err_msg
            )
            
            worker_repository.update_worker_status_sync(
                worker_id, document_id, 'ocr', 'error',
                error_message=err_msg
            )
            worker_repository.mark_task_completed_sync(document_id, 'ocr')
        except Exception as e2:
            logger.error(f"[{worker_id}] Failed to mark error: {e2}")



async def _chunking_worker_task(document_id: str, filename: str, worker_id: str):
    """
    Worker task: Performs chunking on documents that have completed OCR.
    Reads OCR text from the document, performs segmentation and chunking,
    then stores chunks and marks document as chunking_done.
    
    NOTE: assign_worker() was already called atomically by master scheduler before
    this worker was dispatched. This ensures only ONE worker processes each document.
    
    REQ-021 Fase 5: Refactored to use DocumentRepository (Hexagonal Architecture)
    REQ-021 Phase 5F: Added stage timing tracking with document_stage_timing
    """
    try:
        logger.info(f"[{worker_id}] Assigned Chunking task for: {filename}")
        
        # 1. RECORD STAGE START (NEW: stage timing)
        stage_timing_repository.record_stage_start_sync(
            document_id=document_id,
            stage='chunking',
            metadata={'worker_id': worker_id, 'filename': filename}
        )
        
        # 2. Mark as started (assign_worker already marked as 'assigned' atomically)
        worker_repository.update_worker_status_sync(
            worker_id, document_id, 'chunking', 'started'
        )
        
        # Get document using repository
        doc_id = DocumentId(document_id)
        document = await document_repository.get_by_id(doc_id)
        
        if not document or not document.ocr_text:
            logger.error(f"[{worker_id}] No OCR text found for {document_id}")
            
            # RECORD STAGE END with error
            stage_timing_repository.record_stage_end_sync(
                document_id, 'chunking', 'error', error_message="No OCR text"
            )
            
            error_status = PipelineStatus.terminal(TerminalStateEnum.ERROR)
            await document_repository.update_status(
                doc_id,
                error_status,
                error_message="No OCR text for chunking"
            )
            
            worker_repository.update_worker_status_sync(
                worker_id, document_id, 'chunking', 'error',
                error_message="No OCR text"
            )
            worker_repository.mark_task_completed_sync(document_id, 'chunking')
            return
        
        ocr_text = document.ocr_text
        doc_type = document.document_type.value if document.document_type else "unknown"
        
        logger.info(f"[{worker_id}] Starting chunking for {filename}...")
        
        # Perform chunking
        try:
            chunk_records = await asyncio.to_thread(_perform_chunking, ocr_text, document_id, filename, doc_type)
            
            # Update document status and metadata using repository
            chunking_done_status = PipelineStatus.create(StageEnum.CHUNKING, StateEnum.DONE)
            await document_repository.update_status(
                doc_id,
                chunking_done_status,
                processing_stage=Stage.CHUNKING,
                num_chunks=len(chunk_records),
            )
            
            # 3. RECORD STAGE END as done (NEW: stage timing)
            stage_timing_repository.record_stage_end_sync(
                document_id, 'chunking', 'done'
            )
            
            logger.info(f"[{worker_id}] ✅ Chunking completed: {len(chunk_records)} chunks created")
            
        except Exception as e:
            logger.error(f"[{worker_id}] Chunking failed: {e}", exc_info=True)
            raise
        
        # Mark completed
        worker_repository.update_worker_status_sync(
            worker_id, document_id, 'chunking', 'completed'
        )
        worker_repository.mark_task_completed_sync(document_id, 'chunking')
        
    except Exception as e:
        logger.error(f"[{worker_id}] Chunking worker error: {e}", exc_info=True)
        try:
            err_msg = str(e)[:200]
            
            # RECORD STAGE END with error
            stage_timing_repository.record_stage_end_sync(
                document_id, 'chunking', 'error', error_message=err_msg
            )
            
            # Update status using repository
            error_status = PipelineStatus.terminal(TerminalStateEnum.ERROR)
            doc_id = DocumentId(document_id)
            await document_repository.update_status(
                doc_id,
                error_status,
                error_message=err_msg
            )
            
            worker_repository.update_worker_status_sync(
                worker_id, document_id, 'chunking', 'error',
                error_message=err_msg
            )
            worker_repository.mark_task_completed_sync(document_id, 'chunking')
        except Exception as e2:
            logger.error(f"[{worker_id}] Failed to mark error: {e2}")


async def _indexing_worker_task(document_id: str, filename: str, worker_id: str):
    """
    Worker task: Reconstructs chunks from OCR text and indexes into Qdrant.
    
    NOTE: assign_worker() was already called atomically by master scheduler before
    this worker was dispatched. This ensures only ONE worker processes each document.
    
    REQ-021 Fase 5: Refactored to use DocumentRepository (Hexagonal Architecture)
    REQ-021 Phase 5F: Added stage timing tracking with document_stage_timing
    """
    try:
        logger.info(f"[{worker_id}] Assigned Indexing task for: {filename}")
        
        # 1. RECORD STAGE START (NEW: stage timing)
        stage_timing_repository.record_stage_start_sync(
            document_id=document_id,
            stage='indexing',
            metadata={'worker_id': worker_id, 'filename': filename}
        )
        
        # 2. Mark as started
        worker_repository.update_worker_status_sync(
            worker_id, document_id, TaskType.INDEXING, WorkerStatus.STARTED
        )
        
        # Get document using repository
        doc_id = DocumentId(document_id)
        document = await document_repository.get_by_id(doc_id)
        
        if not document or not document.ocr_text:
            # RECORD STAGE END with error
            stage_timing_repository.record_stage_end_sync(
                document_id, 'indexing', 'error', error_message="No OCR text available"
            )
            raise ValueError("No OCR text available for indexing")
        
        ocr_text = document.ocr_text
        doc_type = document.document_type.value if document.document_type else "unknown"
        
        chunk_records = await asyncio.to_thread(_perform_chunking, ocr_text, document_id, filename, doc_type)
        
        if not chunk_records:
            # RECORD STAGE END with error
            stage_timing_repository.record_stage_end_sync(
                document_id, 'indexing', 'error', error_message="No chunks generated"
            )
            raise ValueError("No chunk records generated for indexing")
        
        logger.info(f"[{worker_id}] Indexing {len(chunk_records)} chunks into Qdrant...")
        await asyncio.to_thread(rag_pipeline.index_chunk_records, chunk_records)
        
        # Update document status and metadata using repository
        indexing_done_status = PipelineStatus.create(StageEnum.INDEXING, StateEnum.DONE)
        await document_repository.update_status(
            doc_id,
            indexing_done_status,
            processing_stage=Stage.INDEXING,
            indexed_at=datetime.utcnow().isoformat(),
            num_chunks=len(chunk_records),
        )
        
        # 3. RECORD STAGE END as done (NEW: stage timing)
        stage_timing_repository.record_stage_end_sync(
            document_id, 'indexing', 'done'
        )
        
        await document_repository.mark_for_reprocessing(doc_id, requested=False)
        
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
        
        worker_repository.update_worker_status_sync(
            worker_id, document_id, TaskType.INDEXING, WorkerStatus.COMPLETED
        )
        worker_repository.mark_task_completed_sync(document_id, TaskType.INDEXING)
        logger.info(f"[{worker_id}] ✅ Indexing completed: {len(chunk_records)} chunks indexed")
        
    except Exception as e:
        logger.error(f"[{worker_id}] Indexing worker error: {e}", exc_info=True)
        try:
            err_msg = str(e)[:200]
            
            # RECORD STAGE END with error
            stage_timing_repository.record_stage_end_sync(
                document_id, 'indexing', 'error', error_message=err_msg
            )
            
            # Update status using repository
            error_status = PipelineStatus.terminal(TerminalStateEnum.ERROR)
            doc_id = DocumentId(document_id)
            await document_repository.update_status(
                doc_id,
                error_status,
                error_message=err_msg
            )
            
            worker_repository.update_worker_status_sync(
                worker_id, document_id, TaskType.INDEXING, WorkerStatus.ERROR,
                error_message=err_msg
            )
            worker_repository.mark_task_completed_sync(document_id, TaskType.INDEXING)
        except Exception as e2:
            logger.error(f"[{worker_id}] Failed to mark error: {e2}")



# ============================================================================
# CLEANUP & RECOVERY FUNCTIONS
# ============================================================================
# Individual schedulers (run_document_*_queue_job_parallel) removed in Fase 5C
# Master scheduler handles all dispatching directly
# ============================================================================

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
        # 1) worker_tasks: everything started/assigned is orphaned;
        #    completed entries are stale history that accumulates forever
        wt_deleted = worker_repository.delete_all_worker_tasks_sync()
        if wt_deleted:
            logger.warning(f"🧹 Startup: deleted {wt_deleted} worker_tasks (all orphaned on restart)")

        # 2) processing_queue: 'processing' entries have no live worker
        pq_reset = worker_repository.reset_all_processing_tasks_sync()
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
            docs = document_repository.list_all_sync(limit=None, status=stuck_status)
            count = len(docs)
            if count:
                for doc in docs:
                    document_repository.update_status_sync(
                        doc["document_id"],
                        PipelineStatus.from_string(rollback_status, status_type="document"),
                        clear_error_message=True,
                    )
                ds_total += count
                logger.warning(
                    f"🧹 Startup: {count} docs {stuck_status} → {rollback_status}"
                )

        # 4) insights: 'generating' with no live thread → pending
        ins_reset = news_item_repository.reset_generating_insights_sync()
        if ins_reset:
            logger.warning(f"🧹 Startup: reset {ins_reset} insights {InsightStatus.GENERATING} → {InsightStatus.PENDING}")

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



# ============================================================================
# INBOX SCANNING
# ============================================================================

def run_inbox_scan():
    """
    Scan INBOX_DIR for new files and queue them for OCR processing.
    Delegates to file_ingestion_service for consistent ingestion logic.
    Called by scheduler every 5 min.
    """
    if not INBOX_DIR or not os.path.isdir(INBOX_DIR):
        return
    if not qdrant_connector:
        logger.warning("Inbox scan skipped: Qdrant not ready")
        return

    from file_ingestion_service import ingest_from_inbox, ALLOWED_EXTENSIONS as INGEST_EXTENSIONS

    processed_dir = os.path.join(INBOX_DIR, "processed")
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    files_to_queue = []
    for name in os.listdir(INBOX_DIR):
        if name == "processed":
            continue
        path = os.path.join(INBOX_DIR, name)
        if not os.path.isfile(path):
            continue
        if Path(name).suffix.lower() not in INGEST_EXTENSIONS:
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

    queued = 0
    duplicates = 0
    for path, name in files_to_queue:
        try:
            doc_id = ingest_from_inbox(path, name, UPLOAD_DIR, processed_dir)
            if doc_id:
                queued += 1
            else:
                duplicates += 1
        except Exception as e:
            logger.error(f"Inbox queue failed for {name}: {e}", exc_info=True)

    if queued > 0 or duplicates > 0:
        logger.info(f"Inbox: queued {queued}/{len(files_to_queue)} files, {duplicates} duplicates skipped")


# Document list/status/insights/segmentation/news-items/download → adapters.driving.api.v1.routers.documents


# News-item insights and RAG query APIs are served only by
# adapters.driving.api.v1.routers.news_items and .query


# ============================================================================
# ADMIN ENDPOINTS
# ============================================================================

def _index_insight_in_qdrant(
    news_item_id: str,
    document_id: str,
    filename: str,
    title: str,
    content: str,
) -> bool:
    """Index a generated insight into Qdrant as content_type=insight."""
    if not qdrant_connector or not embeddings_service:
        return False
    if not (content or "").strip():
        return False
    vector = embeddings_service.embed_text(content, is_query=False)
    qdrant_connector.insert_insight_vector(
        vector=vector,
        news_item_id=news_item_id,
        document_id=document_id,
        filename=filename or "",
        text=content,
        title=title or "",
    )
    return True


def _run_reindex_all():
    """
    Reindex all documents: delete vectors from Qdrant, re-embed and re-insert.
    Use after changing embedding model or instruction prefix.
    Only docs with ocr_text are re-indexed (skips OCR+chunking).
    """
    if not qdrant_connector:
        logger.error("❌ Reindex: missing qdrant_connector")
        return
    docs = [
        {
            "document_id": row["document_id"],
            "filename": row.get("filename"),
        }
        for row in document_repository.list_all_sync(limit=None)
        if (row.get("ocr_text") or "").strip()
    ]
    if not docs:
        logger.warning("⚠️ Reindex: no documents with ocr_text found")
        return
    logger.info(f"🔄 Reindexing {len(docs)} documents (deleting from Qdrant, re-embedding)...")
    doc_ids = [r["document_id"] for r in docs]
    for i, row in enumerate(docs):
        doc_id = row["document_id"]
        filename = row["filename"] or doc_id
        try:
            qdrant_connector.delete_document(doc_id)
            document_repository.update_status_sync(
                doc_id,
                PipelineStatus.create(StageEnum.CHUNKING, StateEnum.DONE),
                processing_stage=Stage.CHUNKING,
                clear_indexed_at=True,
                clear_error_message=True,
            )
            stage_timing_repository.record_stage_start_sync(
                document_id=doc_id,
                stage='indexing',
                metadata={'source': 'reindex-all'}
            )
            worker_repository.enqueue_task_sync(doc_id, filename, TaskType.INDEXING, priority=10)
            if (i + 1) % 10 == 0 or i == 0:
                logger.info(f"   ✓ Queued {i + 1}/{len(docs)}: {filename[:50]}...")
        except Exception as e:
            logger.error(f"   ✗ {filename}: {e}")

    # Re-index existing insights (deleted with delete_document; DB still has them)
    if qdrant_connector and embeddings_service and doc_ids:
        insights_to_reindex = []
        for doc_id in doc_ids:
            for insight in news_item_repository.list_insights_by_document_id_sync(doc_id):
                status = insight.get("status")
                content = (insight.get("content") or "").strip()
                if status in ("insights_done", "insights_indexing") and content:
                    insights_to_reindex.append(insight)
        for r in insights_to_reindex:
            try:
                _index_insight_in_qdrant(
                    r["news_item_id"], r["document_id"], r["filename"] or "", r.get("title") or "", r["content"]
                )
                news_item_insights_store.set_indexed_in_qdrant(r["news_item_id"])
            except Exception as e:
                logger.warning(f"Reindex insight {r.get('news_item_id')}: {e}")
        if insights_to_reindex:
            logger.info(f"   ✓ Re-indexed {len(insights_to_reindex)} insights")

    logger.info(f"✅ Reindex queued: {len(docs)} documents. Workers will process them.")


def _execute_manual_backup(provider: Optional[str], remote_path: Optional[str]):
    """Execute manual backup in background for admin router helpers."""
    start_time = datetime.now()
    entry = {
        "type": "manual",
        "started_at": start_time.isoformat(),
        "provider": provider,
    }
    try:
        result = backup_service.create_backup()
        entry["backup_name"] = result["backup_name"]
        entry["size_bytes"] = result["size_bytes"]

        if provider:
            upload_result = backup_service.upload_to_cloud(
                result["archive_path"], provider, remote_path or ""
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


def _execute_restore(archive_path: str, restore_db: bool, restore_uploads: bool, restore_qdrant: bool):
    """Execute restore in background for admin router helpers."""
    try:
        result = backup_service.restore_from_backup(
            archive_path, restore_db, restore_uploads, restore_qdrant
        )
        logger.info(f"Restore completed: {result}")
    except Exception as e:
        logger.error(f"Restore failed: {e}")


# NOTE:
# Reports and notifications API are now served only by
# adapters.driving.api.v1.routers.reports and .notifications


# NOTE:
# Dashboard and workers status/control APIs are served only by
# adapters.driving.api.v1 routers (dashboard.py and workers.py).

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
