"""
Workers router — status, start info, shutdown, retry errors.

Uses `import app as app_module` for caches, qdrant_connector, and repositories.
"""
import logging
import time
from datetime import datetime

import requests
from fastapi import APIRouter, Depends, HTTPException, Request

import app as app_module
from adapters.driving.api.v1.utils.ingestion_policy import evaluate_document, legacy_block_detail
from middleware import CurrentUser, get_current_user, require_admin
from pipeline_states import DocStatus, TaskType, WorkerStatus, Stage
from core.domain.value_objects.document_id import DocumentId
from core.domain.value_objects.pipeline_status import PipelineStatus, StageEnum, StateEnum
from pipeline_runtime_store import set_all_pauses

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status")
async def get_workers_status(
    current_user: CurrentUser = Depends(get_current_user),
):
    """Get detailed status of workers - shows each worker and their specific current task."""
    # NOTA: generic_worker_pool eliminado en Fase 5C

    cached = app_module._cache_get("workers_status")
    if cached is not None:
        return cached
    try:
        active_workers = await app_module.worker_repository.list_active_with_documents()
        error_workers = await app_module.worker_repository.list_recent_errors_with_documents()
        pending_counts = await app_module.worker_repository.get_pending_task_counts()
        pending_counts = pending_counts or {}
        active_insights_tasks = app_module.news_item_repository.list_active_insight_tasks_sync()
        pending_counts["insights"] = app_module.news_item_repository.count_pending_or_queued_insights_sync()
        pending_counts["indexing_insights"] = app_module.news_item_repository.count_ready_for_indexing_insights_sync()
        
        # Pool status - No hay generic_worker_pool, reportar en base a master_pipeline_scheduler
        # Todos los workers son ahora despachos individuales desde scheduler
        pool_active = True  # Master scheduler siempre corre si backend levantó
        pool_size = len(active_workers)  # Count actual running workers
        
        workers_status = []
        worker_idx = 0
        
        # Map insight_{news_item_id} → filename/title para workers insights (JOIN con document_status falla)
        insight_display = {
            f"insight_{r['news_item_id']}": (r.get('filename') or r.get('title') or r['news_item_id'])[:60]
            for r in active_insights_tasks
        }
        
        # Process ONLY real workers from worker_tasks table (not virtual workers from tasks)
        # active_workers contains actual running workers with status='started' or 'processing'
        for row in active_workers:
            worker_id = row.get('worker_id')
            task_type = row.get('task_type')
            document_id = row.get('document_id')
            filename = row.get('filename')
            if not filename and task_type in ('insights', 'indexing_insights') and document_id:
                filename = insight_display.get(document_id)
            status = row.get('status')
            started_at = row.get('started_at')
            
            worker_idx += 1
            type_map = {
                'ocr': 'OCR',
                'chunking': 'Chunking',
                'indexing': 'Indexing',
                'insights': 'Insights',
                'indexing_insights': 'Indexing Insights'
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
                'insights': 'Insights',
                'indexing_insights': 'Indexing Insights'
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
        if (current_time - app_module._tika_health_cache["last_check"]) < app_module._tika_health_cache["cache_ttl"]:
            # Use cached status
            tika_status = app_module._tika_health_cache["status"]
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
            app_module._tika_health_cache["status"] = tika_status
            app_module._tika_health_cache["last_check"] = current_time
        
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
            if app_module.qdrant_connector:
                # Intentar conexión a Qdrant
                app_module.qdrant_connector.client.get_collections()
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
        
        result = {
            "timestamp": datetime.now().isoformat(),
            "workers": workers_status,
            "summary": {
                "total_workers": total_workers_shown,
                "active_workers": active_workers_count,
                "idle_workers": idle_workers_count,
                "error_workers": error_workers_count,
                "pool_size": pool_size,
                "pending_tasks": pending_counts,
                "unhealthy_services": len([w for w in workers_status if w["type"] == "Service" and w["status"] != "healthy"]),
            }
        }
        app_module._cache_set("workers_status", result)
        return result
        
    except Exception as e:
        logger.error(f"Error fetching workers status: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Error fetching workers status")

@router.post("/start")
async def start_workers(current_user: CurrentUser = Depends(require_admin)):
    """
    Info endpoint - Workers are always running via master_pipeline_scheduler.
    Fase 5C: GenericWorkerPool removed, master scheduler handles all dispatch.
    """
    logger.info(f"[{current_user.username}] Checked worker status")

    return {
        "status": "info",
        "message": "Workers are managed by master_pipeline_scheduler (runs every 10s)",
        "architecture": "Master scheduler dispatches workers directly",
        "pool_active": True,  # Master scheduler is always active
        "supported_tasks": ["ocr", "chunking", "indexing", "insights"],
        "note": "No manual start needed - master scheduler auto-dispatches"
    }


@router.post("/shutdown")
async def shutdown_workers_gracefully(current_user: CurrentUser = Depends(require_admin)):
    """
    Shutdown ordenado de workers con rollback de tareas en proceso (ADMIN only).

    Fase 5C: GenericWorkerPool removed. Now performs cleanup only:
    1. Rollback tareas 'processing' → 'pending'
    2. Limpia worker_tasks activos
    3. Marca documentos intermedios correctamente
    4. Activa pausas pipeline para detener dispatch

    Workers son despachados por master_pipeline_scheduler cada 10s.
    Para detener workers: activar pausas pipeline.
    """
    try:
        logger.info(f"🛑 Shutdown workers ordenado (by {current_user.username})...")

        # PASO 1: Activar todas las pausas para detener dispatch
        import insights_pipeline_control as _ipc
        set_all_pauses(True)
        _ipc.refresh_from_db()
        logger.info("✅ Pipeline pausas activadas (detiene nuevo dispatch)")

        # PASO 2: Rollback tareas 'processing' → 'pending'
        processing_tasks = await app_module.worker_repository.reset_processing_tasks()
        total_processing = sum(processing_tasks.values())
        if total_processing > 0:
            logger.info(f"🔄 Rollback {total_processing} tareas 'processing' → 'pending'...")
            for task_type, count in processing_tasks.items():
                logger.info(f"   • {task_type}: {count}")
            logger.info("✅ Tareas revertidas a pending")

        # PASO 3: Limpiar worker_tasks activos
        total_active = await app_module.worker_repository.delete_active_worker_tasks()
        if total_active > 0:
            logger.info(f"🧹 Limpiando {total_active} worker_tasks activos...")
            logger.info("✅ worker_tasks activos limpiados")

        return {
            "status": "success",
            "message": "Workers shutdown completado",
            "actions_taken": [
                "Pipeline pausas activadas (detiene dispatch)",
                f"{total_processing} tareas revertidas a pending",
                f"{total_active} worker_tasks limpiados",
            ],
            "note": "Para reactivar: POST /api/admin/insights-pipeline con todas las pausas en false"
        }

    except Exception as e:
        logger.error(f"❌ Error en shutdown: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/retry-errors")
async def retry_error_workers(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user)
):
    """
    Retry processing for documents and insights that had errors.
    Body: { "document_ids": ["id1", "insight_123", ...] } or {} for retry all.
    IDs con prefijo "insight_" son news_item_insights; el resto son document_status.
    """
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    document_ids = body.get("document_ids") if isinstance(body, dict) else None
    force_legacy = bool(body.get("force_legacy")) if isinstance(body, dict) else False
    try:
        # Separar IDs en documentos vs insights
        doc_ids = []
        insight_ids = []
        if document_ids and len(document_ids) > 0:
            for did in document_ids:
                if isinstance(did, str) and did.startswith("insight_"):
                    insight_ids.append(did[8:])
                else:
                    doc_ids.append(did)
        
        error_docs = []
        error_insights = []
        retry_all = not document_ids or len(document_ids) == 0
        
        # Documentos via DocumentRepository
        if doc_ids:
            for doc_id in doc_ids:
                row = app_module.document_repository.get_by_id_sync(doc_id)
                if row and row.get("status") == DocStatus.ERROR:
                    error_docs.append(row)
        elif retry_all:
            error_docs = app_module.document_repository.list_all_sync(
                skip=0,
                limit=None,
                status=DocStatus.ERROR,
            )
        
        # Insights via store
        if insight_ids:
            error_insights = app_module.news_item_repository.list_insight_errors_sync(insight_ids)
        elif retry_all:
            error_insights = app_module.news_item_repository.list_insight_errors_sync()
        
        if not error_docs and not error_insights:
            return {
                "message": "No documents or insights with errors found",
                "retried_count": 0,
                "retried_documents": []
            }
        
        retried_count = 0
        retried_documents = []
        errors = []
        skipped_legacy = []
        
        # Reintentar insights (reset a pending)
        for row in error_insights:
            news_item_id = row.get('news_item_id')
            filename = row.get('filename') or row.get('title') or news_item_id
            try:
                app_module.news_item_repository.set_insight_status_sync(
                    news_item_id,
                    "insights_pending",
                    error_message=None,
                )
                retried_count += 1
                retried_documents.append({"document_id": f"insight_{news_item_id}", "filename": filename})
                logger.info(f"✅ Retried insight: {news_item_id} ({filename})")
            except Exception as e:
                err_msg = f"Error retrying insight {news_item_id}: {str(e)}"
                errors.append(err_msg)
                logger.error(err_msg, exc_info=True)
        
        # Reintentar documentos
        for row in error_docs:
            document_id = row.get('document_id')
            filename = row.get('filename') or document_id
            
            try:
                doc = app_module.document_repository.get_by_id_sync(document_id)
                if not doc:
                    errors.append(f"Document {document_id} not found")
                    continue
                legacy_decision = evaluate_document(doc)
                if legacy_decision.is_legacy and not force_legacy:
                    reason = legacy_block_detail(legacy_decision)
                    logger.warning(f"⛔ Retry-errors bloqueado para {document_id}: {reason}")
                    skipped_legacy.append({"document_id": document_id, "reason": reason})
                    continue
                
                # Decidir qué etapa reintentar según processing_stage y ocr_text
                has_ocr = doc.get('ocr_text') and len(str(doc.get('ocr_text') or '').strip()) > 0
                stage = (doc.get('processing_stage') or '').lower()
                
                if not has_ocr or stage in ('ocr', 'upload', ''):
                    # OCR falló o no hay texto → retry OCR completo
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
                        metadata={'source': 'retry-errors', 'force_legacy': force_legacy}
                    )
                    await app_module.document_repository.store_ocr_text(DocumentId(document_id), None)
                    await app_module.document_repository.mark_for_reprocessing(DocumentId(document_id), requested=True)
                    await app_module.worker_repository.enqueue_task(document_id, filename, TaskType.OCR, priority=10)
                    logger.info(f"   → Retry OCR (no ocr_text or stage={stage})")
                elif stage == 'chunking':
                    # Chunking falló (ej. Server disconnected) → retry chunking
                    app_module.document_repository.update_status_sync(
                        document_id,
                        PipelineStatus.create(StageEnum.CHUNKING, StateEnum.PROCESSING),
                        processing_stage=Stage.CHUNKING,
                        clear_indexed_at=True,
                        clear_error_message=True,
                    )
                    app_module.stage_timing_repository.record_stage_start_sync(
                        document_id=document_id,
                        stage='chunking',
                        metadata={'source': 'retry-errors', 'force_legacy': force_legacy}
                    )
                    await app_module.worker_repository.enqueue_task(document_id, filename, TaskType.CHUNKING, priority=10)
                    logger.info(f"   → Retry chunking (stage=chunking)")
                else:
                    # Indexing falló o stage=indexing → retry indexing
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
                        metadata={'source': 'retry-errors', 'mode': 'indexing_only', 'force_legacy': force_legacy}
                    )
                    await app_module.worker_repository.enqueue_task(document_id, filename, TaskType.INDEXING, priority=10)
                    logger.info(f"   → Retry indexing only (ocr+chunking done)")
                
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
            "skipped_legacy_documents": skipped_legacy or None,
            "errors": errors if errors else None,
            "force_legacy_applied": force_legacy,
        }
        
    except Exception as e:
        logger.error(f"❌ Retry errors error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
