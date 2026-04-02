"""
Documents router — list, status, insights, diagnostics, news items, download.

Legacy helpers (_cache_*, segment_news_items_from_text, document_repository) are
accessed via lazy `import app` inside handlers to avoid circular imports during
app module load.
"""
from datetime import datetime
import logging
import os
import re
import traceback
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse

from database import (
    document_insights_store,
    document_status_store,
    news_item_insights_store,
    news_item_store,
)
from file_ingestion_service import resolve_file_path
from middleware import CurrentUser, get_current_user
from pipeline_states import DocStatus

from adapters.driving.api.v1.schemas.document_schemas import (
    DocumentMetadata,
    DocumentsListResponse,
    DocumentStatusItem,
)

router = APIRouter()
logger = logging.getLogger(__name__)


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
        rows = document_status_store.get_all(status_filter=status, source_filter=source)
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
        rows = document_status_store.get_all(status_filter=None, source_filter=None)

        doc_ids = [r["document_id"] for r in rows]

        item_counts = news_item_store.get_counts_by_document_ids(doc_ids) if doc_ids else {}

        item_progress = news_item_insights_store.get_progress_by_document_ids(doc_ids) if doc_ids else {}

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
    row = document_insights_store.get_by_document_id(document_id)
    if not row or row.get("status") != document_insights_store.STATUS_DONE:
        raise HTTPException(status_code=404, detail="Insights not available for this document")
    return {"document_id": document_id, "filename": row.get("filename", ""), "content": row.get("content") or ""}


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

        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT ocr_text FROM document_status WHERE document_id = %s", (document_id,))
        result = cursor.fetchone()
        conn.close()

        if not result or not result["ocr_text"]:
            raise HTTPException(status_code=404, detail="OCR text not available")

        ocr_text = result["ocr_text"]

        items = app_module.segment_news_items_from_text(ocr_text)

        stored_items = news_item_store.list_by_document_id(document_id)

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
