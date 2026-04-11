"""
Legacy Data Repository

Repository for managing legacy data migration from Event-Driven pipeline
to Orchestrator Agent. Handles reading legacy data, validation, and tracking.

Related: REQ-027_ORCHESTRATOR_MIGRATION.md, Migration 021
Date: 2026-04-10
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from uuid import UUID

import asyncpg

from adapters.driven.persistence.migration_models import (
    LegacyData,
    NewData,
    ValidationResult,
    MergedData,
    MigrationTrackingRecord,
    MigrationProgress,
    GlobalMigrationProgress,
    PipelineStage,
    ValidationStatus,
    MergeStrategy,
    calculate_similarity,
    determine_merge_strategy
)

logger = logging.getLogger(__name__)


class LegacyDataRepository:
    """
    Repository for legacy data migration operations.
    
    Responsibilities:
    - Read legacy data from old tables (document_status, news_items, etc.)
    - Save migration snapshots to migration_tracking
    - Validate legacy vs new data
    - Track migration progress
    - Manage merge strategies
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        self.db = db_pool
    
    # ========================================================================
    # Legacy Data Retrieval
    # ========================================================================
    
    async def get_legacy_data(
        self,
        document_id: Union[UUID, str],
        stage: PipelineStage
    ) -> Optional[LegacyData]:
        """
        Retrieve legacy data for a specific document and stage.
        
        Maps stage to appropriate source table and extracts relevant data.
        """
        # Convert UUID to str if needed
        doc_id = str(document_id) if isinstance(document_id, UUID) else document_id
        
        try:
            if stage == PipelineStage.UPLOAD:
                return await self._get_legacy_upload_data(doc_id)
            elif stage == PipelineStage.OCR:
                return await self._get_legacy_ocr_data(doc_id)
            elif stage == PipelineStage.SEGMENTATION:
                return await self._get_legacy_segmentation_data(doc_id)
            elif stage == PipelineStage.CHUNKING:
                return await self._get_legacy_chunking_data(doc_id)
            elif stage == PipelineStage.INDEXING:
                return await self._get_legacy_indexing_data(doc_id)
            elif stage == PipelineStage.INSIGHTS:
                return await self._get_legacy_insights_data(doc_id)
            else:
                logger.warning(f"No legacy data mapping for stage: {stage}")
                return None
        except Exception as e:
            logger.error(f"Error getting legacy data for {doc_id}/{stage}: {e}")
            return None
    
    async def _get_legacy_upload_data(self, document_id: str) -> Optional[LegacyData]:
        """Get legacy upload data from document_status"""
        row = await self.db.fetchrow(
            """
            SELECT filename, created_at, file_size
            FROM document_status
            WHERE document_id = $1
            """,
            document_id
        )
        
        if not row:
            return LegacyData(stage=PipelineStage.UPLOAD, exists=False)
        
        return LegacyData(
            stage=PipelineStage.UPLOAD,
            exists=True,
            data={
                'filename': row['filename'],
                'file_size': row['file_size']
            },
            timestamp=row['created_at'],
            source_table='document_status'
        )
    
    async def _get_legacy_ocr_data(self, document_id: UUID) -> Optional[LegacyData]:
        """Get legacy OCR data from document_status.ocr_text"""
        row = await self.db.fetchrow(
            """
            SELECT ocr_text, updated_at, doc_type
            FROM document_status
            WHERE document_id = $1 AND ocr_text IS NOT NULL
            """,
            document_id
        )
        
        if not row or not row['ocr_text']:
            return LegacyData(stage=PipelineStage.OCR, exists=False)
        
        return LegacyData(
            stage=PipelineStage.OCR,
            exists=True,
            data={
                'text': row['ocr_text'],
                'doc_type': row['doc_type']
            },
            timestamp=row['updated_at'],
            source_table='document_status'
        )
    
    async def _get_legacy_segmentation_data(self, document_id: UUID) -> Optional[LegacyData]:
        """Get legacy segmentation data from news_items"""
        rows = await self.db.fetch(
            """
            SELECT id, title, content, confidence, position
            FROM news_items
            WHERE document_id = $1
            ORDER BY position
            """,
            document_id
        )
        
        if not rows:
            return LegacyData(stage=PipelineStage.SEGMENTATION, exists=False)
        
        articles = [
            {
                'id': str(row['id']),
                'title': row['title'],
                'content': row['content'],
                'confidence': float(row['confidence']) if row['confidence'] else None,
                'position': row['position']
            }
            for row in rows
        ]
        
        return LegacyData(
            stage=PipelineStage.SEGMENTATION,
            exists=True,
            data={'articles': articles},
            timestamp=datetime.utcnow(),  # No timestamp in news_items, use now
            source_table='news_items'
        )
    
    async def _get_legacy_chunking_data(self, document_id: UUID) -> Optional[LegacyData]:
        """Get legacy chunking data from document_status"""
        row = await self.db.fetchrow(
            """
            SELECT num_chunks, updated_at
            FROM document_status
            WHERE document_id = $1 AND num_chunks IS NOT NULL
            """,
            document_id
        )
        
        if not row:
            return LegacyData(stage=PipelineStage.CHUNKING, exists=False)
        
        return LegacyData(
            stage=PipelineStage.CHUNKING,
            exists=True,
            data={'chunk_count': row['num_chunks']},
            timestamp=row['updated_at'],
            source_table='document_status'
        )
    
    async def _get_legacy_indexing_data(self, document_id: UUID) -> Optional[LegacyData]:
        """Get legacy indexing data from document_status"""
        row = await self.db.fetchrow(
            """
            SELECT indexed_at, num_chunks
            FROM document_status
            WHERE document_id = $1 AND indexed_at IS NOT NULL
            """,
            document_id
        )
        
        if not row:
            return LegacyData(stage=PipelineStage.INDEXING, exists=False)
        
        return LegacyData(
            stage=PipelineStage.INDEXING,
            exists=True,
            data={'indexed_at': row['indexed_at'].isoformat(), 'num_chunks': row['num_chunks']},
            timestamp=row['indexed_at'],
            source_table='document_status'
        )
    
    async def _get_legacy_insights_data(self, document_id: UUID) -> Optional[LegacyData]:
        """Get legacy insights data from insights table"""
        # Note: Adjust table name based on actual schema
        rows = await self.db.fetch(
            """
            SELECT news_item_id, insight_data, created_at
            FROM insights
            WHERE document_id = $1
            """,
            document_id
        )
        
        if not rows:
            return LegacyData(stage=PipelineStage.INSIGHTS, exists=False)
        
        insights = [
            {
                'news_item_id': str(row['news_item_id']),
                'data': row['insight_data']
            }
            for row in rows
        ]
        
        return LegacyData(
            stage=PipelineStage.INSIGHTS,
            exists=True,
            data={'insights': insights},
            timestamp=rows[0]['created_at'] if rows else datetime.utcnow(),
            source_table='insights'
        )
    
    # ========================================================================
    # Migration Snapshot Management
    # ========================================================================
    
    async def save_migration_snapshot(
        self,
        document_id: Union[UUID, str],
        stage: PipelineStage,
        legacy_data: Optional[LegacyData],
        new_data: NewData,
        validation_result: ValidationResult,
        merged_data: MergedData
    ) -> int:
        """
        Save complete migration snapshot to migration_tracking table.
        
        Returns: migration_tracking.id
        """
        # Convert UUID to str if needed
        doc_id = str(document_id) if isinstance(document_id, UUID) else document_id
        
        record_id = await self.db.fetchval(
            """
            INSERT INTO migration_tracking (
                document_id, stage,
                legacy_exists, legacy_data, legacy_timestamp, legacy_source_table,
                new_data, new_timestamp,
                validation_status, validation_result, similarity_score,
                merged_data, merge_strategy,
                created_at, validated_at
            ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7::jsonb, $8, $9, $10::jsonb, $11, $12::jsonb, $13, $14, $15)
            ON CONFLICT (document_id, stage) 
            DO UPDATE SET
                legacy_exists = EXCLUDED.legacy_exists,
                legacy_data = EXCLUDED.legacy_data,
                new_data = EXCLUDED.new_data,
                new_timestamp = EXCLUDED.new_timestamp,
                validation_status = EXCLUDED.validation_status,
                validation_result = EXCLUDED.validation_result,
                similarity_score = EXCLUDED.similarity_score,
                merged_data = EXCLUDED.merged_data,
                merge_strategy = EXCLUDED.merge_strategy,
                validated_at = EXCLUDED.validated_at
            RETURNING id
            """,
            doc_id,
            stage.value,
            legacy_data.exists if legacy_data else False,
            json.dumps(legacy_data.data) if legacy_data and legacy_data.exists else None,
            legacy_data.timestamp if legacy_data else None,
            legacy_data.source_table if legacy_data else None,
            json.dumps(new_data.data),
            new_data.timestamp,
            validation_result.status.value,
            json.dumps(validation_result.dict(exclude={'stage'})),
            validation_result.similarity_score,
            json.dumps(merged_data.data),
            merged_data.merge_strategy.value,
            datetime.utcnow(),
            datetime.utcnow()
        )
        
        logger.info(f"Saved migration snapshot: {doc_id}/{stage} (id={record_id})")
        return record_id
    
    # ========================================================================
    # Validation
    # ========================================================================
    
    async def validate_migration(
        self,
        document_id: Union[UUID, str],
        stage: PipelineStage,
        legacy_data: Optional[LegacyData],
        new_data: NewData
    ) -> ValidationResult:
        """
        Validate legacy vs new data for a stage.
        
        Compares data, calculates similarity, determines status.
        """
        # No legacy data = no validation needed
        if not legacy_data or not legacy_data.exists:
            return ValidationResult(
                stage=stage,
                status=ValidationStatus.NO_LEGACY,
                similarity_score=None,
                differences=[],
                recommendation=MergeStrategy.KEEP_NEW,
                details={'reason': 'No legacy data exists'}
            )
        
        # Calculate similarity
        similarity = calculate_similarity(legacy_data.data, new_data.data, stage)
        
        # Determine status
        if similarity >= 0.95:
            status = ValidationStatus.MATCH
        elif similarity >= 0.80:
            status = ValidationStatus.MISMATCH
        else:
            status = ValidationStatus.CONFLICT
        
        # Find differences
        differences = self._find_differences(legacy_data.data, new_data.data, stage)
        
        # Determine merge strategy
        validation_result = ValidationResult(
            stage=stage,
            status=status,
            similarity_score=similarity,
            differences=differences,
            recommendation=MergeStrategy.KEEP_NEW,  # Default
            details={
                'legacy_timestamp': legacy_data.timestamp.isoformat() if legacy_data.timestamp else None,
                'new_timestamp': new_data.timestamp.isoformat(),
                'agent_used': new_data.agent_used
            }
        )
        
        # Override recommendation based on validation
        validation_result.recommendation = determine_merge_strategy(validation_result)
        
        return validation_result
    
    def _find_differences(self, legacy: Dict[str, Any], new: Dict[str, Any], stage: PipelineStage) -> List[str]:
        """Find specific differences between legacy and new data"""
        differences = []
        
        if stage == PipelineStage.OCR:
            legacy_len = len(legacy.get('text', ''))
            new_len = len(new.get('text', ''))
            if abs(legacy_len - new_len) / max(legacy_len, new_len, 1) > 0.05:
                differences.append(f"Text length differs: legacy={legacy_len}, new={new_len}")
        
        elif stage == PipelineStage.SEGMENTATION:
            legacy_count = len(legacy.get('articles', []))
            new_count = len(new.get('articles', []))
            if legacy_count != new_count:
                differences.append(f"Article count differs: legacy={legacy_count}, new={new_count}")
        
        elif stage == PipelineStage.CHUNKING:
            legacy_count = legacy.get('chunk_count', 0)
            new_count = new.get('chunk_count', 0)
            if legacy_count != new_count:
                differences.append(f"Chunk count differs: legacy={legacy_count}, new={new_count}")
        
        return differences
    
    # ========================================================================
    # Migration Progress Tracking
    # ========================================================================
    
    async def mark_stage_migrated(
        self,
        document_id: Union[UUID, str],
        stage: PipelineStage,
        merged_data: Dict[str, Any]
    ):
        """Mark a stage as fully migrated"""
        doc_id = str(document_id) if isinstance(document_id, UUID) else document_id
        
        await self.db.execute(
            """
            UPDATE migration_tracking
            SET migrated_at = NOW(),
                merged_data = $3
            WHERE document_id = $1 AND stage = $2
            """,
            doc_id,
            stage.value,
            merged_data
        )
        
        logger.info(f"Marked stage migrated: {doc_id}/{stage}")
    
    async def mark_document_migrated(
        self,
        document_id: Union[UUID, str],
        validation_results: Dict[PipelineStage, ValidationResult]
    ):
        """
        Mark entire document as migrated.
        Updates document_status.
        """
        doc_id = str(document_id) if isinstance(document_id, UUID) else document_id
        
        # Check if all stages are migrated
        all_migrated = await self.db.fetchval(
            """
            SELECT COUNT(*) = COUNT(*) FILTER (WHERE migrated_at IS NOT NULL)
            FROM migration_tracking
            WHERE document_id = $1
            """,
            doc_id
        )
        
        if all_migrated:
            await self.db.execute(
                """
                UPDATE document_status
                SET data_source = 'orchestrator',
                    migration_status = 'completed',
                    migrated_at = NOW()
                WHERE document_id = $1
                """,
                doc_id
            )
            logger.info(f"Document fully migrated: {doc_id}")
        else:
            await self.db.execute(
                """
                UPDATE document_status
                SET migration_status = 'in_progress'
                WHERE document_id = $1
                """,
                doc_id
            )
    
    async def get_migration_progress(self) -> GlobalMigrationProgress:
        """
        Get global migration progress across all documents and stages.
        """
        # Get progress by stage
        rows = await self.db.fetch(
            """
            SELECT * FROM migration_progress
            """
        )
        
        by_stage = {}
        total_migrated = 0
        total_documents = 0
        total_conflicts = 0
        
        for row in rows:
            stage_progress = MigrationProgress(
                stage=PipelineStage(row['stage']),
                total_documents=row['total_documents'],
                validated_match=row['validated_match'],
                validated_mismatch=row['validated_mismatch'],
                conflicts=row['conflicts'],
                no_legacy_data=row['no_legacy_data'],
                migrated=row['migrated'],
                percent_migrated=float(row['percent_migrated']) if row['percent_migrated'] else 0.0,
                avg_similarity=float(row['avg_similarity']) if row['avg_similarity'] else None,
                first_migration_start=row['first_migration_start'],
                last_migration_complete=row['last_migration_complete']
            )
            by_stage[row['stage']] = stage_progress
            total_documents = max(total_documents, row['total_documents'])
            total_migrated = max(total_migrated, row['migrated'])
            total_conflicts += row['conflicts']
        
        percent_complete = (total_migrated / total_documents * 100.0) if total_documents > 0 else 0.0
        
        return GlobalMigrationProgress(
            total_documents=total_documents,
            total_migrated=total_migrated,
            percent_complete=percent_complete,
            by_stage=by_stage,
            total_conflicts=total_conflicts,
            cleanup_ready=(percent_complete >= 100.0)
        )
    
    async def get_conflicts(self, limit: int = 100) -> List[MigrationTrackingRecord]:
        """Get all migration conflicts that need manual review"""
        rows = await self.db.fetch(
            """
            SELECT * FROM migration_tracking
            WHERE validation_status = 'conflict'
            ORDER BY created_at DESC
            LIMIT $1
            """,
            limit
        )
        
        return [MigrationTrackingRecord(**dict(row)) for row in rows]
