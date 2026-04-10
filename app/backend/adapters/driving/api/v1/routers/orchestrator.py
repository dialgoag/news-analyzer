"""
Orchestrator Dashboard API - Real-time Pipeline Observability

Provides endpoints to visualize the Orchestrator Agent pipeline:
- Document processing logs (all events per document)
- Pipeline results (intermediate and final results)
- Migration progress (legacy vs new data validation)
- Real-time pipeline status

Related: REQ-027_ORCHESTRATOR_MIGRATION.md, ObserverAgent integration
Date: 2026-04-10
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from adapters.driving.api.v1.dependencies import get_db_pool
from middleware import CurrentUser, get_current_user
import asyncpg

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Response Models
# ============================================================================

class ProcessingLogEvent(BaseModel):
    """Single event in the pipeline processing log"""
    id: int
    document_id: str
    stage: str
    status: str
    timestamp: datetime
    duration_sec: Optional[float]
    metadata: Optional[Dict[str, Any]]
    error_type: Optional[str]
    error_message: Optional[str]
    result_ref: Optional[str]
    result_size_bytes: Optional[int]


class DocumentProcessingTimeline(BaseModel):
    """Complete timeline of a document's processing"""
    document_id: str
    filename: str
    publication_date: Optional[str]
    newspaper_name: Optional[str]
    data_source: str
    migration_status: Optional[str]
    events: List[ProcessingLogEvent]
    total_duration: Optional[float]
    current_stage: Optional[str]
    errors_count: int


class PipelineStageMetrics(BaseModel):
    """Metrics for a specific pipeline stage"""
    stage: str
    total_processed: int
    successful: int
    failed: int
    avg_duration: Optional[float]
    median_duration: Optional[float]
    success_rate: float


class MigrationProgressResponse(BaseModel):
    """Migration progress for all stages"""
    stage: str
    total_documents: int
    validated_match: int
    validated_mismatch: int
    conflicts: int
    no_legacy_data: int
    migrated: int
    percent_migrated: float
    avg_similarity: Optional[float]


class GlobalMigrationProgress(BaseModel):
    """Overall migration progress across all stages"""
    stages: List[MigrationProgressResponse]
    overall_migrated: int
    overall_total: int
    overall_percent: float
    cleanup_ready: bool


# ============================================================================
# Endpoints
# ============================================================================

@router.get("/document-timeline/{document_id}", response_model=DocumentProcessingTimeline)
async def get_document_timeline(
    document_id: str,
    current_user: CurrentUser = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_db_pool)
):
    """
    Get complete processing timeline for a specific document.
    
    Shows:
    - All processing events (started, completed, error)
    - Stage durations
    - Errors (if any)
    - Result references
    """
    try:
        async with db_pool.acquire() as conn:
            # Get document metadata
            doc_row = await conn.fetchrow(
                """
                SELECT document_id, filename, publication_date, newspaper_name, 
                       data_source, migration_status
                FROM document_status
                WHERE document_id = $1
                """,
                document_id
            )
            
            if not doc_row:
                raise HTTPException(status_code=404, detail="Document not found")
            
            # Get all processing events
            events_rows = await conn.fetch(
                """
                SELECT id, document_id, stage, status, timestamp, duration_sec,
                       metadata, error_type, error_message, result_ref, result_size_bytes
                FROM document_processing_log
                WHERE document_id = $1
                ORDER BY timestamp ASC
                """,
                document_id
            )
            
            events = [ProcessingLogEvent(**dict(row)) for row in events_rows]
            
            # Calculate total duration (first event to last completed)
            total_duration = None
            if events:
                first_event = events[0].timestamp
                last_completed = max(
                    (e.timestamp for e in events if e.status == 'completed'),
                    default=None
                )
                if last_completed:
                    total_duration = (last_completed - first_event).total_seconds()
            
            # Get current stage
            current_stage = None
            if events:
                # Find last 'started' or 'in_progress' event
                for event in reversed(events):
                    if event.status in ('started', 'in_progress'):
                        current_stage = event.stage
                        break
            
            # Count errors
            errors_count = sum(1 for e in events if e.status == 'error')
            
            return DocumentProcessingTimeline(
                document_id=doc_row['document_id'],
                filename=doc_row['filename'],
                publication_date=doc_row['publication_date'].isoformat() if doc_row['publication_date'] else None,
                newspaper_name=doc_row['newspaper_name'],
                data_source=doc_row['data_source'],
                migration_status=doc_row['migration_status'],
                events=events,
                total_duration=total_duration,
                current_stage=current_stage,
                errors_count=errors_count
            )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching document timeline: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching timeline: {str(e)}")


@router.get("/pipeline-metrics", response_model=List[PipelineStageMetrics])
async def get_pipeline_metrics(
    current_user: CurrentUser = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    since_hours: Optional[int] = Query(24, description="Calculate metrics from the last N hours")
):
    """
    Get metrics for each pipeline stage.
    
    Shows:
    - Total processed documents per stage
    - Success/failure rates
    - Average and median durations
    """
    try:
        async with db_pool.acquire() as conn:
            # Calculate cutoff time
            cutoff = datetime.utcnow() - timedelta(hours=since_hours)
            
            # Get metrics for each stage
            metrics_rows = await conn.fetch(
                """
                SELECT 
                    stage,
                    COUNT(*) as total_processed,
                    COUNT(*) FILTER (WHERE status = 'completed') as successful,
                    COUNT(*) FILTER (WHERE status = 'error') as failed,
                    AVG(duration_sec) FILTER (WHERE status = 'completed') as avg_duration,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_sec) 
                        FILTER (WHERE status = 'completed') as median_duration
                FROM document_processing_log
                WHERE timestamp >= $1
                GROUP BY stage
                ORDER BY 
                    CASE stage
                        WHEN 'upload' THEN 1
                        WHEN 'validation' THEN 2
                        WHEN 'ocr' THEN 3
                        WHEN 'segmentation' THEN 4
                        WHEN 'chunking' THEN 5
                        WHEN 'indexing' THEN 6
                        WHEN 'insights' THEN 7
                        ELSE 99
                    END
                """,
                cutoff
            )
            
            metrics = []
            for row in metrics_rows:
                total = row['total_processed']
                successful = row['successful']
                success_rate = successful / total if total > 0 else 0.0
                
                metrics.append(PipelineStageMetrics(
                    stage=row['stage'],
                    total_processed=total,
                    successful=successful,
                    failed=row['failed'],
                    avg_duration=float(row['avg_duration']) if row['avg_duration'] else None,
                    median_duration=float(row['median_duration']) if row['median_duration'] else None,
                    success_rate=success_rate
                ))
            
            return metrics
    
    except Exception as e:
        logger.error(f"Error fetching pipeline metrics: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching metrics: {str(e)}")


@router.get("/migration-progress", response_model=GlobalMigrationProgress)
async def get_migration_progress(
    current_user: CurrentUser = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_db_pool)
):
    """
    Get migration progress from legacy system to Orchestrator.
    
    Shows:
    - Progress per stage (OCR, segmentation, chunking, indexing, insights)
    - Validation results (match, mismatch, conflict)
    - Overall migration percentage
    - Whether cleanup is ready (100% migrated)
    """
    try:
        async with db_pool.acquire() as conn:
            # Use the migration_progress view
            progress_rows = await conn.fetch(
                """
                SELECT stage, total_documents, validated_match, validated_mismatch,
                       conflicts, no_legacy_data, migrated, percent_migrated, avg_similarity
                FROM migration_progress
                ORDER BY 
                    CASE stage
                        WHEN 'upload' THEN 1
                        WHEN 'validation' THEN 2
                        WHEN 'ocr' THEN 3
                        WHEN 'segmentation' THEN 4
                        WHEN 'chunking' THEN 5
                        WHEN 'indexing' THEN 6
                        WHEN 'insights' THEN 7
                        ELSE 99
                    END
                """
            )
            
            stages = [
                MigrationProgressResponse(
                    stage=row['stage'],
                    total_documents=row['total_documents'],
                    validated_match=row['validated_match'],
                    validated_mismatch=row['validated_mismatch'],
                    conflicts=row['conflicts'],
                    no_legacy_data=row['no_legacy_data'],
                    migrated=row['migrated'],
                    percent_migrated=float(row['percent_migrated']),
                    avg_similarity=float(row['avg_similarity']) if row['avg_similarity'] else None
                )
                for row in progress_rows
            ]
            
            # Calculate overall progress
            total_migrated = sum(s.migrated for s in stages)
            total_documents = sum(s.total_documents for s in stages)
            overall_percent = (total_migrated / total_documents * 100) if total_documents > 0 else 0.0
            
            # Check if cleanup is ready (all stages 100% migrated)
            cleanup_ready = all(s.percent_migrated >= 100.0 for s in stages) if stages else False
            
            return GlobalMigrationProgress(
                stages=stages,
                overall_migrated=total_migrated,
                overall_total=total_documents,
                overall_percent=overall_percent,
                cleanup_ready=cleanup_ready
            )
    
    except Exception as e:
        logger.error(f"Error fetching migration progress: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching migration progress: {str(e)}")


@router.get("/recent-errors")
async def get_recent_errors(
    current_user: CurrentUser = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_db_pool),
    limit: int = Query(50, description="Number of recent errors to fetch")
):
    """
    Get recent pipeline errors for debugging.
    
    Shows:
    - Document ID and filename
    - Stage where error occurred
    - Error type and message
    - Timestamp
    """
    try:
        async with db_pool.acquire() as conn:
            errors_rows = await conn.fetch(
                """
                SELECT 
                    dpl.document_id,
                    ds.filename,
                    dpl.stage,
                    dpl.error_type,
                    dpl.error_message,
                    dpl.error_detail,
                    dpl.timestamp
                FROM document_processing_log dpl
                JOIN document_status ds ON dpl.document_id = ds.document_id
                WHERE dpl.status = 'error'
                ORDER BY dpl.timestamp DESC
                LIMIT $1
                """,
                limit
            )
            
            errors = [
                {
                    'document_id': row['document_id'],
                    'filename': row['filename'],
                    'stage': row['stage'],
                    'error_type': row['error_type'],
                    'error_message': row['error_message'],
                    'error_detail': row['error_detail'],
                    'timestamp': row['timestamp'].isoformat()
                }
                for row in errors_rows
            ]
            
            return {
                'total': len(errors),
                'errors': errors
            }
    
    except Exception as e:
        logger.error(f"Error fetching recent errors: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching errors: {str(e)}")


@router.get("/active-processing")
async def get_active_processing(
    current_user: CurrentUser = Depends(get_current_user),
    db_pool: asyncpg.Pool = Depends(get_db_pool)
):
    """
    Get documents currently being processed.
    
    Shows documents with 'started' or 'in_progress' events in the last 30 minutes.
    """
    try:
        async with db_pool.acquire() as conn:
            # Find documents with recent 'started' or 'in_progress' events
            cutoff = datetime.utcnow() - timedelta(minutes=30)
            
            active_rows = await conn.fetch(
                """
                SELECT DISTINCT ON (dpl.document_id)
                    dpl.document_id,
                    ds.filename,
                    dpl.stage,
                    dpl.status,
                    dpl.timestamp,
                    ds.data_source,
                    ds.migration_status
                FROM document_processing_log dpl
                JOIN document_status ds ON dpl.document_id = ds.document_id
                WHERE dpl.status IN ('started', 'in_progress')
                  AND dpl.timestamp >= $1
                ORDER BY dpl.document_id, dpl.timestamp DESC
                """,
                cutoff
            )
            
            active = [
                {
                    'document_id': row['document_id'],
                    'filename': row['filename'],
                    'stage': row['stage'],
                    'status': row['status'],
                    'timestamp': row['timestamp'].isoformat(),
                    'data_source': row['data_source'],
                    'migration_status': row['migration_status']
                }
                for row in active_rows
            ]
            
            return {
                'total': len(active),
                'active_documents': active
            }
    
    except Exception as e:
        logger.error(f"Error fetching active processing: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching active processing: {str(e)}")
