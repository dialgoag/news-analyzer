"""
Dashboard router — summary, analysis, parallel coordinates.

Uses `import app as app_module` for caches, document_repository, and
`_fetch_parallel_news_items` defined in app.py.
"""
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException

import app as app_module
from database import document_status_store, news_item_store, news_item_insights_store
from middleware import CurrentUser, get_current_user
from pipeline_states import DocStatus, QueueStatus, Stage, WorkerStatus

from adapters.driving.api.v1.schemas.dashboard_schemas import (
    ParallelDocumentFlow,
    ParallelFlowResponse,
    ParallelNewsItem,
)

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/summary")
async def get_dashboard_summary(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get consolidated dashboard metrics (files, news items, OCR, chunking, insights, errors).

    Uses inbox files as source of truth for total count.
    """
    cached = app_module._cache_get("dashboard_summary")
    if cached is not None:
        return cached
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
        total_docs = files_data['total_in_db'] or total_files  # document_status is source of truth

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
        
        # 4. CHUNKING - Documentos (granularidad doc; chunks internos por news_item)
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0) as pending,
                COALESCE(SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END), 0) as processing,
                COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) as completed
            FROM processing_queue WHERE task_type = 'chunking'
        """)
        ch = cursor.fetchone()
        ch_completed = ch['completed'] or 0
        ch_processing = ch['processing'] or 0
        ch_pending = max(0, total_docs - ch_completed - ch_processing)
        cursor.execute("SELECT COALESCE(SUM(num_chunks), 0) as n FROM document_status WHERE num_chunks > 0")
        total_chunks_val = cursor.fetchone()['n'] or 0
        cursor.execute("SELECT COUNT(*) as n FROM news_items")
        news_items_val = cursor.fetchone()['n'] or 0
        chunks_estimate = {
            "granularity": "document",
            "total": total_docs,
            "total_chunks": total_docs,
            "indexed": ch_completed,
            "completed": ch_completed,
            "pending": ch_pending,
            "processing": ch_processing,
            "errors": 0,
            "percentage_indexed": round((ch_completed or 0) / (total_docs or 1) * 100, 2),
            "chunks_total": int(total_chunks_val),
            "news_items_count": int(news_items_val),
        }

        # 5. INDEXACIÓN (Qdrant) - Documentos (granularidad doc; chunks internos por news_item)
        cursor.execute("""
            SELECT
                COALESCE(SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END), 0) as pending,
                COALESCE(SUM(CASE WHEN status = 'processing' THEN 1 ELSE 0 END), 0) as processing,
                COALESCE(SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END), 0) as completed
            FROM processing_queue WHERE task_type = 'indexing'
        """)
        idx = cursor.fetchone()
        idx_completed = idx['completed'] or 0
        idx_pending = max(0, total_docs - idx_completed - (idx['processing'] or 0))
        indexing = {
            "granularity": "document",
            "total": total_docs,
            "active": idx_completed,
            "completed": idx_completed,
            "pending": idx_pending,
            "errors": 0,
            "percentage_indexed": round((idx_completed or 0) / (total_docs or 1) * 100, 2),
            "total_chunks": int(total_chunks_val),
            "news_items_count": int(news_items_val),
        }
        
        # 6. INSIGHTS — granularidad news_item; JOIN news_items (cadena doc→news→insight)
        cursor.execute("""
            SELECT 
              COUNT(DISTINCT nii.news_item_id) as total_current,
              SUM(CASE WHEN nii.status = 'done' THEN 1 ELSE 0 END) as done,
              SUM(CASE WHEN nii.status IN ('pending', 'queued', 'generating') THEN 1 ELSE 0 END) as pending,
              SUM(CASE WHEN nii.status = 'error' THEN 1 ELSE 0 END) as errors
            FROM news_item_insights nii
            INNER JOIN news_items ni ON ni.news_item_id = nii.news_item_id
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
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "files": files,
            "news_items": news_items,
            "ocr": ocr,
            "chunking": chunks_estimate,
            "indexing": indexing,
            "insights": insights,
            "errors": errors,
        }
        app_module._cache_set("dashboard_summary", result)
        return result
        
    except Exception as e:
        logger.error(f"Error fetching dashboard summary: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching summary")


@router.get("/parallel-data", response_model=ParallelFlowResponse)
async def get_parallel_coordinates_data(
    limit: int = 80,
    max_news_per_doc: int = 20,
    current_user: CurrentUser = Depends(get_current_user),
):
    """Return document + news_item slices for the Parallel Coordinates visualization."""
    limit = max(10, min(limit, 250))
    max_news_per_doc = max(1, min(max_news_per_doc, 50))

    try:
        rows = app_module.document_repository.list_all_sync()
        selected_docs = rows[:limit]
        doc_ids = [row["document_id"] for row in selected_docs]
        news_totals = news_item_store.get_counts_by_document_ids(doc_ids) if doc_ids else {}
        news_map = app_module._fetch_parallel_news_items(doc_ids, max_news_per_doc)

        documents_payload: List[ParallelDocumentFlow] = []
        for row in selected_docs:
            doc_id = row["document_id"]
            ingested_at = row.get("ingested_at")
            if isinstance(ingested_at, datetime):
                ingested_at = ingested_at.isoformat()

            news_items = [ParallelNewsItem(**item) for item in news_map.get(doc_id, [])]
            documents_payload.append(
                ParallelDocumentFlow(
                    document_id=doc_id,
                    filename=row["filename"],
                    status=row["status"],
                    processing_stage=row.get("processing_stage"),
                    ingested_at=ingested_at,
                    news_items_total=int(news_totals.get(doc_id, 0) or 0),
                    news_items=news_items,
                )
            )

        return ParallelFlowResponse(
            documents=documents_payload,
            meta={
                "limit": limit,
                "max_news_per_doc": max_news_per_doc,
                "total_documents": len(documents_payload),
            }
        )
    except Exception as e:
        logger.error(f"Error building parallel dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching parallel data")


@router.get("/analysis")
async def get_dashboard_analysis(
    current_user: CurrentUser = Depends(get_current_user),
):
    """
    Comprehensive dashboard analysis endpoint.
    Provides detailed analysis of errors, pipeline status, workers, and database state.
    """
    cached = app_module._cache_get("dashboard_analysis")
    if cached is not None:
        return cached
    try:
        conn = document_status_store.get_connection()
        cursor = conn.cursor()
        
        # ===== 1. ERROR ANALYSIS =====
        # 1a. Errores de documentos (OCR, Chunking, Indexing)
        cursor.execute("""
            SELECT 
                error_message,
                processing_stage,
                COUNT(*) as count,
                ARRAY_AGG(document_id ORDER BY document_id) as document_ids,
                ARRAY_AGG(filename ORDER BY document_id) as filenames
            FROM document_status
            WHERE status = %s
            GROUP BY error_message, processing_stage
            ORDER BY count DESC
        """, (DocStatus.ERROR,))
        error_groups_raw = cursor.fetchall()
        
        # 1b. Errores de Insights (news_item_insights)
        cursor.execute("""
            SELECT 
                error_message,
                COUNT(*) as count,
                ARRAY_AGG('insight_' || news_item_id ORDER BY news_item_id) as document_ids,
                ARRAY_AGG(filename ORDER BY news_item_id) as filenames
            FROM news_item_insights
            WHERE status = %s
            GROUP BY error_message
            ORDER BY count DESC
        """, (news_item_insights_store.STATUS_ERROR,))
        insights_errors_raw = cursor.fetchall()
        
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
            elif 'Only PDF files are supported' in error_msg:
                cause = "Archivo no es PDF válido - reintentar no ayudará"
                can_auto_fix = False
            elif 'OCR returned empty text' in error_msg or 'OCRmyPDF failed' in error_msg:
                cause = "OCR falló, timeout o error de servicio - reintentar puede resolver"
                can_auto_fix = True
            elif 'Server disconnected' in error_msg or 'Connection aborted' in error_msg or 'RemoteDisconnected' in error_msg or 'Connection error' in error_msg:
                cause = "Conexión interrumpida - reintentar puede resolver"
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
        
        # 1c. Añadir grupos de errores de Insights
        for row in insights_errors_raw:
            error_msg = row['error_message'] or 'Sin mensaje de error'
            real_errors_count += row['count']
            cause = "Desconocido"
            can_auto_fix = False
            if 'Max retries (429)' in error_msg or '429' in error_msg:
                cause = "Rate limit LLM - reintentar puede resolver"
                can_auto_fix = True
            elif 'timeout' in error_msg.lower() or 'timed out' in error_msg.lower():
                cause = "Timeout durante generación de insight"
                can_auto_fix = True
            elif 'Server disconnected' in error_msg or 'Connection' in error_msg or 'RemoteDisconnected' in error_msg:
                cause = "Conexión interrumpida - reintentar puede resolver"
                can_auto_fix = True
            elif 'No chunks' in error_msg:
                cause = "Sin chunks para generar insight - verificar documento"
                can_auto_fix = False
            else:
                cause = "Error en generación LLM - reintentar puede resolver"
                can_auto_fix = True
            error_groups.append({
                "error_message": error_msg,
                "stage": "insights",
                "count": row['count'],
                "cause": cause,
                "can_auto_fix": can_auto_fix,
                "document_ids": row['document_ids'] or [],
                "filenames": row['filenames'] or []
            })
        
        # ===== 2. PIPELINE ANALYSIS =====
        # Total documentos = fuente de verdad (coherencia entre etapas)
        cursor.execute("SELECT COUNT(*) as n FROM document_status")
        total_documents = cursor.fetchone()['n'] or 0

        # Inbox file count — Upload no puede ser 0 si hay archivos en inbox
        import os
        inbox_count = 0
        inbox_dir = os.getenv("INBOX_DIR", "/app/inbox")
        if os.path.isdir(inbox_dir):
            inbox_count = sum(
                1 for f in os.listdir(inbox_dir)
                if f != "processed" and os.path.isfile(os.path.join(inbox_dir, f))
            )

        stages_analysis = []
        
        # Errores por processing_stage para cada etapa (document_status.status='error')
        cursor.execute("""
            SELECT COUNT(*) as c FROM document_status
            WHERE status = %s AND (processing_stage IS NULL OR processing_stage = %s)
        """, (DocStatus.ERROR, Stage.OCR))
        ocr_errors = cursor.fetchone()['c'] or 0
        cursor.execute("SELECT COUNT(*) as c FROM document_status WHERE status = %s AND processing_stage = %s", (DocStatus.ERROR, Stage.CHUNKING))
        ch_errors = cursor.fetchone()['c'] or 0
        cursor.execute("SELECT COUNT(*) as c FROM document_status WHERE status = %s AND processing_stage = %s", (DocStatus.ERROR, Stage.INDEXING))
        idx_errors = cursor.fetchone()['c'] or 0
        cursor.execute("SELECT COUNT(*) as c FROM document_status WHERE status = %s AND processing_stage = %s", (DocStatus.ERROR, Stage.UPLOAD))
        upload_errors = cursor.fetchone()['c'] or 0
        
        # Upload Stage (REQ-014.1) — upload_pending, upload_processing, upload_done, paused
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = %s) as pending,
                COUNT(*) FILTER (WHERE status = %s) as processing,
                COUNT(*) FILTER (WHERE status = %s) as completed,
                COUNT(*) FILTER (WHERE status = %s) as paused
            FROM document_status
        """, (DocStatus.UPLOAD_PENDING, DocStatus.UPLOAD_PROCESSING, DocStatus.UPLOAD_DONE, DocStatus.PAUSED))
        upload_data = cursor.fetchone()
        upload_pending = upload_data['pending'] or 0
        upload_processing = upload_data['processing'] or 0
        upload_completed = upload_data['completed'] or 0
        upload_paused = upload_data['paused'] or 0
        upload_total = upload_pending + upload_processing + upload_completed + upload_paused + upload_errors
        # Archivos en inbox sin fila en DB = pendientes de ingesta
        upload_pending = upload_pending + max(0, inbox_count - upload_total)
        upload_total_docs = upload_pending + upload_processing + upload_completed + upload_paused + upload_errors
        stages_analysis.append({
            "name": "Upload",
            "total_documents": upload_total_docs,
            "pending_tasks": upload_pending,
            "processing_tasks": upload_processing,
            "completed_tasks": upload_completed,
            "error_tasks": upload_errors,
            "paused_tasks": upload_paused,
            "ready_for_next": upload_completed,
            "inbox_documents": inbox_count,
            "blockers": []
        })
        
        # OCR Stage — processing_queue + document_status (fallback para docs sin fila en queue)
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'completed') as completed
            FROM processing_queue
            WHERE task_type = 'ocr'
        """)
        ocr_queue = cursor.fetchone()
        
        # Fuente de verdad para "completados": document_status (docs con ocr_done o más allá)
        cursor.execute("""
            SELECT COUNT(*) as n FROM document_status
            WHERE status IN (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            DocStatus.OCR_DONE, DocStatus.CHUNKING_PENDING, DocStatus.CHUNKING_PROCESSING, DocStatus.CHUNKING_DONE,
            DocStatus.INDEXING_PENDING, DocStatus.INDEXING_PROCESSING, DocStatus.INDEXING_DONE,
            DocStatus.INSIGHTS_PENDING, DocStatus.INSIGHTS_PROCESSING, DocStatus.INSIGHTS_DONE, DocStatus.COMPLETED
        ))
        ocr_done_from_docs = cursor.fetchone()['n'] or 0
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM document_status
            WHERE status = %s
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
        # Solo bloquear si Chunking necesita input pero OCR no produce (bloqueo real)
        cursor.execute("SELECT COUNT(*) FILTER (WHERE status IN ('pending','processing')) as n FROM processing_queue WHERE task_type = 'chunking'")
        ch_needs_input = (cursor.fetchone()['n'] or 0) > 0
        if ch_needs_input and ocr_ready_for_chunking == 0:
            ocr_blockers.append({
                "reason": "No hay documentos con status='ocr_done' y texto OCR válido",
                "count": 0,
                "solution": "Esperando que documentos completen OCR correctamente"
            })
        
        ocr_processing = ocr_queue['processing'] or 0
        ocr_completed = max(ocr_queue['completed'] or 0, ocr_done_from_docs)
        # Pending = cola real (no total-completed que incluye errores como "pendientes")
        ocr_pending = ocr_queue['pending'] or 0
        ocr_total_docs = ocr_pending + ocr_processing + ocr_completed + ocr_errors
        stages_analysis.append({
            "name": "OCR",
            "total_documents": ocr_total_docs,
            "pending_tasks": ocr_pending,
            "processing_tasks": ocr_processing,
            "completed_tasks": ocr_completed,
            "error_tasks": ocr_errors,
            "ready_for_next": ocr_ready_for_chunking,
            "blockers": ocr_blockers
        })
        
        # Chunking Stage — document_status como fallback para completed
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
            SELECT COUNT(*) as n FROM document_status
            WHERE status IN (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            DocStatus.CHUNKING_DONE, DocStatus.INDEXING_PENDING, DocStatus.INDEXING_PROCESSING, DocStatus.INDEXING_DONE,
            DocStatus.INSIGHTS_PENDING, DocStatus.INSIGHTS_PROCESSING, DocStatus.INSIGHTS_DONE, DocStatus.COMPLETED
        ))
        chunking_done_from_docs = cursor.fetchone()['n'] or 0
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM document_status
            WHERE status = %s
            AND NOT EXISTS (
                SELECT 1 FROM processing_queue pq
                WHERE pq.document_id = document_status.document_id
                AND pq.task_type = 'indexing'
                AND pq.status IN (%s, %s)
            )
        """, (DocStatus.CHUNKING_DONE, QueueStatus.PENDING, QueueStatus.PROCESSING))
        chunking_ready_for_indexing = cursor.fetchone()['count']
        
        chunking_blockers = []
        # Solo bloquear si Indexing necesita input pero Chunking no produce (bloqueo real)
        cursor.execute("SELECT COUNT(*) FILTER (WHERE status IN ('pending','processing')) as n FROM processing_queue WHERE task_type = 'indexing'")
        idx_needs_input = (cursor.fetchone()['n'] or 0) > 0
        if idx_needs_input and chunking_ready_for_indexing == 0:
            chunking_blockers.append({
                "reason": "No hay documentos con chunking_done",
                "count": 0,
                "solution": "Esperando que documentos completen chunking"
            })
        
        ch_completed = max(chunking_queue['completed'] or 0, chunking_done_from_docs)
        # Pending = cola real (no total-completed que incluye errores como "pendientes")
        ch_pending = chunking_queue['pending'] or 0
        cursor.execute("SELECT COALESCE(SUM(num_chunks), 0) as n FROM document_status WHERE num_chunks > 0")
        chunks_total = int(cursor.fetchone()['n'] or 0)
        cursor.execute("SELECT COUNT(*) as n FROM news_items")
        news_count = int(cursor.fetchone()['n'] or 0)
        chunking_total_docs = ch_pending + (chunking_queue['processing'] or 0) + ch_completed + ch_errors
        stages_analysis.append({
            "name": "Chunking",
            "granularity": "document",
            "total_documents": chunking_total_docs,
            "pending_tasks": ch_pending,
            "processing_tasks": chunking_queue['processing'] or 0,
            "completed_tasks": ch_completed,
            "error_tasks": ch_errors,
            "ready_for_next": chunking_ready_for_indexing,
            "blockers": chunking_blockers,
            "total_chunks": chunks_total,
            "news_items_count": news_count,
        })
        
        # Indexing Stage — document_status como fallback para completed
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'completed') as completed
            FROM processing_queue
            WHERE task_type = 'indexing'
        """)
        indexing_queue = cursor.fetchone()
        cursor.execute("""
            SELECT COUNT(*) as n FROM document_status
            WHERE status IN (%s, %s, %s, %s, %s)
        """, (
            DocStatus.INDEXING_DONE, DocStatus.INSIGHTS_PENDING, DocStatus.INSIGHTS_PROCESSING,
            DocStatus.INSIGHTS_DONE, DocStatus.COMPLETED
        ))
        indexing_done_from_docs = cursor.fetchone()['n'] or 0
        
        indexing_blockers = []
        # No añadir falso positivo: indexing con 0 pending significa que está al día, no bloqueado
        
        idx_completed = max(indexing_queue['completed'] or 0, indexing_done_from_docs)
        # Pending = cola real (no total-completed que incluye docs en error como "pendientes")
        idx_pending = indexing_queue['pending'] or 0
        idx_total_docs = idx_pending + (indexing_queue['processing'] or 0) + idx_completed + idx_errors
        stages_analysis.append({
            "name": "Indexing",
            "granularity": "document",
            "total_documents": idx_total_docs,
            "pending_tasks": idx_pending,
            "processing_tasks": indexing_queue['processing'] or 0,
            "completed_tasks": idx_completed,
            "error_tasks": idx_errors,
            "ready_for_next": 0,
            "blockers": indexing_blockers,
            "total_chunks": chunks_total,
            "news_items_count": news_count,
        })
        
        # Insights Stage — granularidad: news_item (1 doc → N news → N insights)
        # ID compuesto: (document_id, news_item_id); fuente: news_item_insights
        # JOIN news_items: solo insights de news_items válidos (cadena doc→news→insight)
        cursor.execute("""
            SELECT 
                COUNT(*) FILTER (WHERE nii.status IN ('pending', 'queued')) as pending,
                COUNT(*) FILTER (WHERE nii.status = 'generating') as processing,
                COUNT(*) FILTER (WHERE nii.status = 'done') as completed,
                COUNT(*) FILTER (WHERE nii.status = 'error') as errors,
                COUNT(*) as total
            FROM news_item_insights nii
            INNER JOIN news_items ni ON ni.news_item_id = nii.news_item_id
        """)
        insights_data = cursor.fetchone()
        total_insights = insights_data['total'] or 0
        ins_pending = insights_data['pending'] or 0
        ins_processing = insights_data['processing'] or 0
        ins_completed = insights_data['completed'] or 0
        # Vista documento: docs con todos los insights hechos vs docs con pendientes
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT nii.document_id) FILTER (
                    WHERE NOT EXISTS (
                        SELECT 1 FROM news_item_insights n2 
                        WHERE n2.document_id = nii.document_id 
                        AND n2.status NOT IN ('done', 'error')
                    )
                ) as docs_all_done,
                COUNT(DISTINCT nii.document_id) FILTER (
                    WHERE EXISTS (
                        SELECT 1 FROM news_item_insights n2 
                        WHERE n2.document_id = nii.document_id 
                        AND n2.status IN ('pending', 'queued', 'generating')
                    )
                ) as docs_with_pending
            FROM news_item_insights nii
            INNER JOIN news_items ni ON ni.news_item_id = nii.news_item_id
        """)
        ins_docs = cursor.fetchone()
        ins_errors = insights_data['errors'] or 0
        insights_total_docs = ins_pending + ins_processing + ins_completed + ins_errors
        insights_stage = {
            "name": "Insights",
            "granularity": "news_item",
            "total_documents": insights_total_docs,
            "pending_tasks": ins_pending,
            "processing_tasks": ins_processing,
            "completed_tasks": ins_completed,
            "error_tasks": ins_errors,
            "ready_for_next": 0,
            "docs_with_all_insights_done": ins_docs['docs_all_done'] or 0,
            "docs_with_pending_insights": ins_docs['docs_with_pending'] or 0,
            "blockers": []
        }
        stages_analysis.append(insights_stage)

        # Indexing Insights Stage — insights done but not yet in Qdrant
        cursor.execute("""
            SELECT
                COUNT(*) FILTER (WHERE nii.status = 'done' AND nii.indexed_in_qdrant_at IS NULL) as pending,
                COUNT(*) FILTER (WHERE nii.status = 'indexing') as processing,
                COUNT(*) FILTER (WHERE nii.indexed_in_qdrant_at IS NOT NULL) as completed,
                COUNT(*) FILTER (WHERE (nii.status = 'done' OR nii.status = 'indexing') AND nii.content IS NOT NULL) as total
            FROM news_item_insights nii
            INNER JOIN news_items ni ON ni.news_item_id = nii.news_item_id
            WHERE nii.content IS NOT NULL AND nii.status IN ('done', 'indexing')
        """)
        idx_ins_data = cursor.fetchone()
        idx_ins_pending = idx_ins_data['pending'] or 0
        idx_ins_processing = idx_ins_data['processing'] or 0
        idx_ins_completed = idx_ins_data['completed'] or 0
        idx_ins_total = idx_ins_data['total'] or 0
        # Indexing Insights: insights en error no aplican (son de stage Insights); errores de indexación no tienen status propio
        idx_ins_errors = 0
        idx_ins_total_docs = idx_ins_pending + idx_ins_processing + idx_ins_completed + idx_ins_errors
        stages_analysis.append({
            "name": "Indexing Insights",
            "granularity": "news_item",
            "total_documents": idx_ins_total_docs,
            "pending_tasks": idx_ins_pending,
            "processing_tasks": idx_ins_processing,
            "completed_tasks": idx_ins_completed,
            "error_tasks": idx_ins_errors,
            "ready_for_next": 0,
            "blockers": []
        })

        if insights_stage:
            insights_stage["ready_for_next"] = idx_ins_pending
        
        # ===== 3. WORKERS ANALYSIS =====
        # Active workers with execution time
        # Para insights: document_id="insight_{id}" → JOIN document_status falla; usar news_item_insights
        cursor.execute("""
            SELECT 
                wt.worker_id,
                wt.worker_type,
                wt.task_type,
                wt.document_id,
                wt.status,
                wt.started_at,
                EXTRACT(EPOCH FROM (NOW() - wt.started_at)) / 60 as minutes_running,
                COALESCE(ds.filename, 
                    CASE WHEN wt.task_type IN ('insights', 'indexing_insights') THEN
                        (SELECT COALESCE(nii.filename, nii.title) FROM news_item_insights nii 
                         WHERE nii.news_item_id = REPLACE(wt.document_id, 'insight_', '') LIMIT 1)
                    END
                ) as filename
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
            fn = row['filename']
            if not fn and row['task_type'] in ('insights', 'indexing_insights') and row['document_id']:
                # Fallback si subquery no matcheó
                fn = row['document_id']
            
            worker_data = {
                "worker_id": row['worker_id'],
                "worker_type": row['worker_type'],
                "task_type": row['task_type'],
                "document_id": row['document_id'],
                "filename": fn,
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
        
        result = {
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
        app_module._cache_set("dashboard_analysis", result)
        return result
        
    except Exception as e:
        logger.error(f"Error fetching dashboard analysis: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching dashboard analysis: {str(e)}")
