"""
Documents router — list, status, insights, diagnostics, news items, download, upload, requeue, delete.

Legacy helpers (_cache_*, segment_news_items_from_text, document_repository) are
accessed via lazy `import app` inside handlers to avoid circular imports during
app module load.

Complex endpoints (upload, requeue, delete) migrated from app.py for completeness.
"""
from datetime import datetime
import hashlib
import logging
import os
import re
import traceback
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks, Query
from fastapi.responses import FileResponse, JSONResponse

from file_ingestion_service import resolve_file_path, check_duplicate, compute_sha256, ingest_from_upload
from middleware import CurrentUser, get_current_user, require_admin, require_upload_permission, require_delete_permission
from pipeline_states import DocStatus, Stage
from adapters.driving.api.v1.utils.ingestion_policy import evaluate_document, legacy_block_detail

from adapters.driving.api.v1.schemas.document_schemas import (
    DocumentMetadata,
    DocumentsListResponse,
    DocumentStatusItem,
)

# Domain
from core.domain.value_objects import DocumentId, TaskType
from core.domain.value_objects.pipeline_status import PipelineStatus, StageEnum, StateEnum

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# CONSTANTS FOR UPLOAD
# ============================================================================
ALLOWED_EXTENSIONS = {
    ".pdf", ".docx", ".pptx", ".xlsx", ".odt", ".rtf",
    ".html", ".xml", ".json", ".csv",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff"
}
MAX_UPLOAD_SIZE_MB = 50
CHUNK_SIZE = 2000
CHUNK_OVERLAP = 300


def _upload_dir() -> str:
    return os.getenv("UPLOAD_DIR", "./uploads")


@router.get("", response_model=DocumentsListResponse)
async def list_documents(
    status: Optional[str] = None,
    source: Optional[str] = None,
):
    """List all documents with status. DB is source of truth (no Qdrant scroll)."""
    import app as app_module

    cache_key = f"documents_list:{status or ''}:{source or ''}"
    cached = app_module._cache_get(cache_key) if not status and not source else None
    if cached is not None:
        return cached
    try:
        rows = app_module.document_repository.list_all_sync(
            skip=0,
            limit=None,
            status=status,
            source=source,
        )
        by_id = {}
        for r in rows:
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
        doc_ids = list(by_id.keys())
        item_counts = app_module.news_item_repository.get_counts_by_document_ids_sync(doc_ids) if doc_ids else {}
        item_progress = app_module.news_item_repository.get_progress_by_document_ids_sync(doc_ids) if doc_ids else {}

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
                meta.insights_status = None
                meta.insights_progress = "0/0"
        docs = list(by_id.values())
        docs.sort(key=lambda x: x.upload_date or "", reverse=True)
        total_indexed = total_units
        with_insights_done = done_units
        resp = DocumentsListResponse(
            documents=docs,
            total=len(docs),
            insights_summary={"total_indexed": total_indexed, "with_insights_done": with_insights_done},
        )
        if not status and not source:
            app_module._cache_set("documents_list::", resp)
        return resp
    except Exception as e:
        logger.error(f"Error listing documents: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status", response_model=List[DocumentStatusItem])
async def get_documents_status():
    """
    Endpoint específico para DocumentsTable.jsx del frontend.
    Retorna status de documentos con campos esperados por el dashboard.
    """
    import app as app_module

    cached = app_module._cache_get("documents_status")
    if cached is not None:
        return cached
    try:
        rows = app_module.document_repository.list_all_sync(skip=0, limit=None)

        doc_ids = [r["document_id"] for r in rows]

        item_counts = app_module.news_item_repository.get_counts_by_document_ids_sync(doc_ids) if doc_ids else {}

        item_progress = app_module.news_item_repository.get_progress_by_document_ids_sync(doc_ids) if doc_ids else {}

        result = []
        for r in rows:
            doc_id = r["document_id"]

            uploaded_at = r.get("ingested_at")
            if isinstance(uploaded_at, datetime):
                uploaded_at = uploaded_at.isoformat()

            news_items_count = int(item_counts.get(doc_id, 0) or 0)

            prog = item_progress.get(doc_id) or {}
            insights_done = int(prog.get("done", 0) or 0)
            insights_total = news_items_count if news_items_count > 0 else 0

            result.append(
                DocumentStatusItem(
                    document_id=doc_id,
                    filename=r["filename"],
                    status=r["status"],
                    uploaded_at=uploaded_at or "",
                    news_items_count=news_items_count,
                    insights_done=insights_done,
                    insights_total=insights_total,
                )
            )

        result.sort(key=lambda x: x.uploaded_at or "", reverse=True)

        app_module._cache_set("documents_status", result)
        return result
    except Exception as e:
        logger.error(f"Error getting documents status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/insights")
async def get_document_insights(
    document_id: str,
    _current_user: CurrentUser = Depends(get_current_user),
):
    """Legacy: insights por documento (reporte por archivo). Para PDFs multi-noticia usar /news-items."""
    import app as app_module

    row = app_module.news_item_repository.get_document_insight_summary_sync(document_id)
    if not row:
        raise HTTPException(status_code=404, detail="Insights not available for this document")
    doc = app_module.document_repository.get_by_id_sync(document_id)
    return {
        "document_id": document_id,
        "filename": (doc or {}).get("filename", ""),
        "content": row.get("content") or "",
    }


@router.get("/{document_id}/segmentation-diagnostic")
async def get_segmentation_diagnostic(
    document_id: str,
    _current_user: CurrentUser = Depends(get_current_user),
):
    """
    Diagnostic endpoint: Shows how the document was segmented into news items.
    Returns raw OCR text excerpt, detected titles, and segmentation statistics.
    """
    import app as app_module

    try:
        doc = app_module.document_repository.get_by_id_sync(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        legacy_decision = evaluate_document(doc)
        if legacy_decision.is_legacy and not force_legacy:
            msg = legacy_block_detail(legacy_decision)
            logger.warning(f"⛔ Requeue bloqueado para {document_id}: {msg}")
            raise HTTPException(
                status_code=400,
                detail=f"{msg} Verifica el archivo y vuelve a llamar con force_legacy=true si procede.",
            )

        ocr_text = doc.get("ocr_text")
        if not ocr_text:
            raise HTTPException(status_code=404, detail="OCR text not available")

        items = app_module.segment_news_items_from_text(ocr_text)

        stored_items = app_module.news_item_repository.list_by_document_id_sync(document_id)

        lines = ocr_text.split("\n")
        total_lines = len(lines)
        non_empty_lines = len([l for l in lines if l.strip()])
        avg_line_length = sum(len(l) for l in lines) / max(1, len(lines))

        title_candidates = []
        for i, line in enumerate(lines[:100]):
            stripped = line.strip()
            if len(stripped) >= 12 and len(stripped) <= 140:
                letters = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]", stripped)
                if letters:
                    upper = sum(1 for ch in letters if ch.isupper())
                    upper_ratio = upper / len(letters)
                    if upper_ratio >= 0.5:
                        title_candidates.append(
                            {
                                "line_number": i + 1,
                                "text": stripped,
                                "upper_ratio": round(upper_ratio, 2),
                            }
                        )

        return {
            "document_id": document_id,
            "filename": doc.get("filename"),
            "ocr_stats": {
                "total_chars": len(ocr_text),
                "total_lines": total_lines,
                "non_empty_lines": non_empty_lines,
                "avg_line_length": round(avg_line_length, 2),
            },
            "ocr_excerpt": ocr_text[:2000] + ("..." if len(ocr_text) > 2000 else ""),
            "segmentation_result": {
                "detected_items": len(items),
                "items_preview": [
                    {
                        "title": item.get("title"),
                        "body_length": len(item.get("text", "")),
                        "body_excerpt": item.get("text", "")[:200] + "...",
                    }
                    for item in items[:5]
                ],
            },
            "stored_items": {
                "count": len(stored_items),
                "items": [
                    {
                        "news_item_id": item.get("news_item_id"),
                        "item_index": item.get("item_index"),
                        "title": item.get("title"),
                        "status": item.get("status"),
                    }
                    for item in stored_items
                ],
            },
            "title_candidates": title_candidates[:20],
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Segmentation diagnostic error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{document_id}/news-items")
async def list_news_items_for_document(
    document_id: str,
    _current_user: CurrentUser = Depends(get_current_user),
):
    """List news items detected for a document, with insights status per item."""
    import app as app_module
    items = app_module.news_item_repository.list_by_document_id_sync(document_id)
    insights = app_module.news_item_repository.list_insights_by_document_id_sync(document_id)
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


@router.get("/{document_id}/download")
async def download_document(document_id: str):
    """Download the original uploaded document"""
    import app as app_module

    try:
        doc = app_module.document_repository.get_by_id_sync(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail=f"Document not found in database: {document_id}")

        filename = doc.get("filename")
        if not filename:
            raise HTTPException(status_code=404, detail=f"Filename not found for document: {document_id}")

        upload_dir = _upload_dir()
        try:
            file_path = resolve_file_path(document_id, upload_dir)
        except FileNotFoundError:
            logger.error(f"❌ File not found for document {document_id}")
            logger.error(f"   Filename from DB: {filename}")
            raise HTTPException(status_code=404, detail=f"File not found: {filename}")

        logger.info(f"📥 Download document: {document_id}")
        logger.info(f"   Filename: {filename}")
        logger.info(f"   Path: {file_path}")

        original_filename = filename

        return FileResponse(
            path=file_path,
            media_type="application/pdf",
            filename=original_filename,
            headers={
                "Content-Disposition": f'inline; filename="{original_filename}"',
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Download error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# COMPLEX ENDPOINTS: UPLOAD, REQUEUE, DELETE
# ============================================================================

@router.post("/upload")
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
    import app as app_module

    if not app_module.ocr_service or not app_module.embeddings_service or not app_module.rag_pipeline:
        raise HTTPException(
            status_code=503,
            detail="Services not initialized. Check /health"
        )

    # Check file extension
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Format '{file_ext}' not supported. Supported: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )

    # Check file size before reading entire content
    content = await file.read()
    file_size_mb = len(content) / (1024 * 1024)

    if file_size_mb > MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=413,
            detail=f"File too large: {file_size_mb:.1f}MB. Maximum allowed: {MAX_UPLOAD_SIZE_MB}MB"
        )

    try:
        file_hash = compute_sha256(data=content)
        existing = check_duplicate(file_hash)
        if existing:
            logger.info(f"📋 Duplicate detected: '{file.filename}' already exists as '{existing['filename']}'")
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Duplicate file detected, not reprocessed",
                    "status": "duplicate",
                    "existing_document_id": existing['document_id'],
                    "existing_filename": existing['filename'],
                    "file_hash": file_hash
                }
            )

        upload_dir = _upload_dir()
        document_id, file_hash = ingest_from_upload(content, file.filename, upload_dir)

        # Resolve actual file path (handles .pdf extension, Fix #95)
        file_path = resolve_file_path(document_id, upload_dir)

        logger.info(f"📄 File received: '{file.filename}' ({len(content)} bytes)")
        logger.info(f"   Document ID: {document_id}")
        logger.info(f"   File path: {file_path}")
        logger.info(f"   File hash: {file_hash[:16]}...")

        background_tasks.add_task(
            app_module._process_document_sync,
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

    except ValueError as ve:
        return JSONResponse(status_code=200, content={"message": str(ve), "status": "duplicate"})
    except Exception as e:
        logger.error(f"❌ Upload error: {str(e)}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{document_id}/requeue")
async def requeue_document(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    force_legacy: bool = Query(
        False,
        description="Permite reintentar documentos legacy (source upload o antigüedad >= cutoff) después de validarlos manualmente.",
    ),
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
    import app as app_module

    try:
        # Get document info
        doc = app_module.document_repository.get_by_id_sync(document_id)
        if not doc:
            raise HTTPException(status_code=404, detail="Document not found")
        
        filename = doc['filename']
        
        logger.info(f"🔄 Requeuing document for reprocessing: {filename} ({document_id})")
        logger.info(f"   ⚠️  Preserving existing news_items and insights (will match by text_hash)")
        
        # Get existing news items for logging
        existing_items = app_module.news_item_repository.list_by_document_id_sync(document_id)
        logger.info(f"   📰 Existing news items: {len(existing_items)} (will be preserved)")
        
        # Get existing insights for logging
        existing_insights = app_module.news_item_repository.get_progress_by_document_ids_sync([document_id])
        insight_stats = existing_insights.get(document_id, {})
        logger.info(f"   💡 Existing insights: {insight_stats.get('done', 0)} done, {insight_stats.get('pending', 0)} pending")
        
        # 1. Delete ONLY chunks from Qdrant (vectors will be re-indexed)
        if app_module.qdrant_connector:
            try:
                app_module.qdrant_connector.delete_document(document_id)
                logger.info(f"   ✓ Deleted chunks from Qdrant (will re-index)")
            except Exception as e:
                logger.warning(f"   ⚠️  Could not delete from Qdrant: {e}")
        
        # 2. DO NOT delete news_items or insights - they will be preserved!
        logger.info(f"   ✓ Preserving news_items and insights (no deletion)")
        
        # 3. If ocr_text exists and doc failed at indexing → retry indexing only
        has_ocr = doc.get('ocr_text') and len(str(doc.get('ocr_text') or '').strip()) > 0
        if has_ocr:
            app_module.document_repository.update_status_sync(
                document_id,
                PipelineStatus.create(StageEnum.CHUNKING, StateEnum.DONE),
                processing_stage=Stage.CHUNKING,
                clear_indexed_at=True,
                clear_error_message=True,
            )
            app_module.stage_timing_repository.record_stage_start_sync(
                document_id=document_id,
                stage='indexing',
                metadata={'source': 'requeue', 'mode': 'indexing_only', 'force_legacy': force_legacy}
            )
            await app_module.worker_repository.enqueue_task(document_id, filename, TaskType.INDEXING, priority=10)
            logger.info(f"   ✓ Retry indexing only (ocr_text exists)")
        else:
            app_module.document_repository.update_status_sync(
                document_id,
                PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING),
                processing_stage=Stage.OCR,
                num_chunks=0,
                clear_indexed_at=True,
                clear_error_message=True,
            )
            app_module.stage_timing_repository.record_stage_start_sync(
                document_id=document_id,
                stage='ocr',
                metadata={'source': 'requeue', 'force_legacy': force_legacy}
            )
            await app_module.document_repository.store_ocr_text(DocumentId(document_id), None)
            await app_module.document_repository.mark_for_reprocessing(DocumentId(document_id), requested=True)
            await app_module.worker_repository.enqueue_task(document_id, filename, TaskType.OCR, priority=10)
            logger.info(f"   ✓ Reset to OCR and marked for reprocessing")
        logger.info(f"   ✓ Added to processing queue")
        
        logger.info(f"✅ Document requeued successfully: {filename}")
        if has_ocr:
            logger.info(f"   Retry indexing only (OCR+chunking already done)")
        else:
            logger.info(f"   Full reprocessing: OCR → chunking → indexing")
        
        return {
            "message": f"Document {filename} requeued" + (" (indexing only)" if has_ocr else " for full reprocessing") + f" (preserving {len(existing_items)} news items)",
            "document_id": document_id,
            "status": DocStatus.CHUNKING_DONE if has_ocr else DocStatus.OCR_PROCESSING,
            "stage": "indexing" if has_ocr else "ocr",
            "preserved_items": len(existing_items),
            "preserved_insights": insight_stats.get('done', 0)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Requeue error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{document_id}")
async def delete_document(
    document_id: str,
    current_user: CurrentUser = Depends(require_delete_permission)
):
    """
    Delete document from index

    Requires: SUPER_USER or ADMIN role
    """
    import app as app_module

    if not app_module.qdrant_connector:
        raise HTTPException(status_code=503, detail="Qdrant not connected")

    try:
        logger.info(f"🗑️  Deleting document: {document_id}")
        app_module.qdrant_connector.delete_document(document_id)
        app_module.stage_timing_repository.delete_for_document_sync(document_id)
        app_module.document_repository.delete_sync(document_id)
        app_module.news_item_repository.delete_insights_by_document_id_sync(document_id)
        app_module.news_item_repository.delete_by_document_id_sync(document_id)
        logger.info(f"✅ Document deleted: {document_id}")
        return {"message": f"Document {document_id} deleted"}
    except Exception as e:
        logger.error(f"Deletion error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
