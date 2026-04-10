-- ============================================================================
-- Migration 021: Legacy Migration Tracking System
-- ============================================================================
-- Purpose: Preparar sistema para migración progresiva de Event-Driven a 
--          Orchestrator Agent con validación de datos legacy
-- Date: 2026-04-10
-- Related: REQ-027_ORCHESTRATOR_MIGRATION.md
-- ============================================================================

BEGIN;

-- ============================================================================
-- STEP 1: Marcar datos existentes como legacy
-- ============================================================================

-- Agregar columnas de tracking a document_status
ALTER TABLE document_status 
    ADD COLUMN IF NOT EXISTS data_source VARCHAR(20) DEFAULT 'legacy',
    ADD COLUMN IF NOT EXISTS migrated_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS migration_status VARCHAR(20) DEFAULT 'pending';
    -- Valores: pending | in_progress | validated | completed

COMMENT ON COLUMN document_status.data_source IS 'Source of data: legacy (event-driven) or orchestrator';
COMMENT ON COLUMN document_status.migrated_at IS 'Timestamp when migration completed';
COMMENT ON COLUMN document_status.migration_status IS 'Migration progress: pending, in_progress, validated, completed';

-- Agregar columnas para metadata extraída de filename
ALTER TABLE document_status
    ADD COLUMN IF NOT EXISTS publication_date DATE,
    ADD COLUMN IF NOT EXISTS newspaper_name VARCHAR(100),
    ADD COLUMN IF NOT EXISTS sha8_prefix VARCHAR(8),
    ADD COLUMN IF NOT EXISTS metadata_parsed BOOLEAN DEFAULT FALSE;

COMMENT ON COLUMN document_status.publication_date IS 'Publication date extracted from filename pattern {sha8}_{DD-MM-YY}-{Newspaper}.pdf';
COMMENT ON COLUMN document_status.newspaper_name IS 'Newspaper name extracted from filename';
COMMENT ON COLUMN document_status.sha8_prefix IS 'First 8 chars of SHA256 hash (from filename)';
COMMENT ON COLUMN document_status.metadata_parsed IS 'Whether filename metadata was successfully parsed';

-- Agregar columnas para referencias a resultados
ALTER TABLE document_status
    ADD COLUMN IF NOT EXISTS ocr_result_ref VARCHAR(500),
    ADD COLUMN IF NOT EXISTS segmentation_result_ref VARCHAR(500),
    ADD COLUMN IF NOT EXISTS chunking_result_ref VARCHAR(500),
    ADD COLUMN IF NOT EXISTS indexing_result_ref VARCHAR(500),
    ADD COLUMN IF NOT EXISTS insights_result_ref VARCHAR(500);

COMMENT ON COLUMN document_status.ocr_result_ref IS 'Reference to OCR result (filesystem path or postgresql://)';
COMMENT ON COLUMN document_status.segmentation_result_ref IS 'Reference to segmentation result';
COMMENT ON COLUMN document_status.chunking_result_ref IS 'Reference to chunking result';
COMMENT ON COLUMN document_status.indexing_result_ref IS 'Reference to indexing result';
COMMENT ON COLUMN document_status.insights_result_ref IS 'Reference to insights result';

-- ============================================================================
-- STEP 2: Crear tabla de tracking de migración por etapa
-- ============================================================================

CREATE TABLE IF NOT EXISTS migration_tracking (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL REFERENCES document_status(document_id) ON DELETE CASCADE,
    stage VARCHAR(50) NOT NULL,  -- 'upload', 'ocr', 'segmentation', 'chunking', 'indexing', 'insights'
    
    -- Datos legacy (snapshot)
    legacy_exists BOOLEAN DEFAULT FALSE,
    legacy_data JSONB,  -- Snapshot de datos viejos
    legacy_timestamp TIMESTAMPTZ,
    legacy_source_table VARCHAR(100),  -- 'document_status', 'news_items', etc.
    
    -- Datos nuevos (orchestrator)
    new_data JSONB,  -- Resultado del orchestrator
    new_timestamp TIMESTAMPTZ,
    
    -- Validación (comparación legacy vs nuevo)
    validation_status VARCHAR(20) DEFAULT 'pending',  -- 'pending' | 'match' | 'mismatch' | 'conflict' | 'no_legacy'
    validation_result JSONB,  -- Detalles de comparación: {similarity: 0.95, differences: [...]}
    similarity_score NUMERIC(5, 4),  -- 0.0000 - 1.0000
    
    -- Decisión final
    merged_data JSONB,  -- Mezcla de legacy + nuevo (con prioridad)
    merge_strategy VARCHAR(50),  -- 'keep_new' | 'keep_legacy' | 'merge_both' | 'manual_review'
    
    -- Timestamps
    created_at TIMESTAMPTZ DEFAULT NOW(),
    validated_at TIMESTAMPTZ,
    migrated_at TIMESTAMPTZ,
    
    -- Constraints
    CONSTRAINT unique_doc_stage UNIQUE (document_id, stage),
    CONSTRAINT valid_validation_status CHECK (validation_status IN ('pending', 'match', 'mismatch', 'conflict', 'no_legacy')),
    CONSTRAINT valid_merge_strategy CHECK (merge_strategy IN ('keep_new', 'keep_legacy', 'merge_both', 'manual_review')),
    CONSTRAINT valid_similarity CHECK (similarity_score IS NULL OR (similarity_score >= 0 AND similarity_score <= 1))
);

COMMENT ON TABLE migration_tracking IS 'Tracks migration progress and validation for each pipeline stage per document';

-- Índices para consultas comunes
CREATE INDEX IF NOT EXISTS idx_migration_doc_stage ON migration_tracking(document_id, stage);
CREATE INDEX IF NOT EXISTS idx_migration_validation_status ON migration_tracking(validation_status);
CREATE INDEX IF NOT EXISTS idx_migration_migrated ON migration_tracking(migrated_at) WHERE migrated_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_migration_conflicts ON migration_tracking(validation_status) WHERE validation_status = 'conflict';
CREATE INDEX IF NOT EXISTS idx_migration_pending ON migration_tracking(validation_status) WHERE validation_status = 'pending';

-- ============================================================================
-- STEP 3: Crear tabla de eventos del pipeline (observabilidad)
-- ============================================================================

CREATE TABLE IF NOT EXISTS document_processing_log (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL REFERENCES document_status(document_id) ON DELETE CASCADE,
    stage VARCHAR(50) NOT NULL,  -- 'upload', 'validation', 'ocr', 'segmentation', etc.
    status VARCHAR(20) NOT NULL,  -- 'started', 'in_progress', 'completed', 'error', 'skipped'
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    duration_sec NUMERIC(10, 3),
    
    -- Metadata del paso
    metadata JSONB,  -- {pages: 10, engine: 'ocrmypdf', confidence: 0.85, articles: 14, etc.}
    
    -- Errores (si aplica)
    error_type VARCHAR(100),
    error_message TEXT,
    error_detail JSONB,  -- {traceback, context, retry_count, etc.}
    
    -- Referencia al resultado completo (si es grande)
    result_ref VARCHAR(500),  -- Path a archivo: "local-data/results/{doc_id}/ocr_result.json"
    result_size_bytes BIGINT,
    
    -- Source del evento
    event_source VARCHAR(50) DEFAULT 'orchestrator',  -- 'orchestrator' | 'legacy'
    
    -- Constraints
    CONSTRAINT valid_status CHECK (status IN ('started', 'in_progress', 'completed', 'error', 'skipped')),
    CONSTRAINT valid_stage CHECK (stage IN ('upload', 'validation', 'ocr', 'ocr_validation', 'segmentation', 'chunking', 'indexing', 'insights', 'indexing_insights'))
);

COMMENT ON TABLE document_processing_log IS 'Timeline of all pipeline events with timing, errors, and result references (orchestrator observability)';

-- Índices para queries de dashboard
CREATE INDEX IF NOT EXISTS idx_processing_log_doc_stage ON document_processing_log(document_id, stage, timestamp);
CREATE INDEX IF NOT EXISTS idx_processing_log_timestamp ON document_processing_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_processing_log_status ON document_processing_log(status);
CREATE INDEX IF NOT EXISTS idx_processing_log_errors ON document_processing_log(status, error_type) WHERE status = 'error';
CREATE INDEX IF NOT EXISTS idx_processing_log_document ON document_processing_log(document_id);

-- ============================================================================
-- STEP 4: Crear tabla de resultados intermedios (para resultados pequeños)
-- ============================================================================

CREATE TABLE IF NOT EXISTS pipeline_results (
    id SERIAL PRIMARY KEY,
    document_id VARCHAR(255) NOT NULL REFERENCES document_status(document_id) ON DELETE CASCADE,
    stage VARCHAR(50) NOT NULL,
    
    -- Resultado (si < 1MB, guardarlo aquí directamente)
    result_data JSONB,  
    
    -- O referencia externa (si > 1MB)
    result_ref VARCHAR(500),  -- Path: "local-data/results/{doc_id}/ocr_result.json"
    result_size_bytes BIGINT,
    result_checksum VARCHAR(64),  -- SHA256 del resultado (validación integridad)
    
    -- Metadata
    created_at TIMESTAMPTZ DEFAULT NOW(),
    expires_at TIMESTAMPTZ,  -- Opcional: TTL para limpieza automática
    
    -- Constraints
    CONSTRAINT unique_doc_stage_result UNIQUE (document_id, stage),
    CONSTRAINT result_data_or_ref CHECK (
        (result_data IS NOT NULL AND result_ref IS NULL) OR
        (result_data IS NULL AND result_ref IS NOT NULL)
    )
);

COMMENT ON TABLE pipeline_results IS 'Stores intermediate pipeline results (small in JSONB, large as file references)';

CREATE INDEX IF NOT EXISTS idx_pipeline_results_doc_stage ON pipeline_results(document_id, stage);
CREATE INDEX IF NOT EXISTS idx_pipeline_results_expires ON pipeline_results(expires_at) WHERE expires_at IS NOT NULL;

-- ============================================================================
-- STEP 5: Crear vista para progreso de migración
-- ============================================================================

CREATE OR REPLACE VIEW migration_progress AS
SELECT 
    stage,
    COUNT(*) as total_documents,
    COUNT(*) FILTER (WHERE validation_status = 'match') as validated_match,
    COUNT(*) FILTER (WHERE validation_status = 'mismatch') as validated_mismatch,
    COUNT(*) FILTER (WHERE validation_status = 'conflict') as conflicts,
    COUNT(*) FILTER (WHERE validation_status = 'no_legacy') as no_legacy_data,
    COUNT(*) FILTER (WHERE migrated_at IS NOT NULL) as migrated,
    ROUND(100.0 * COUNT(*) FILTER (WHERE migrated_at IS NOT NULL) / NULLIF(COUNT(*), 0), 2) as percent_migrated,
    AVG(similarity_score) FILTER (WHERE similarity_score IS NOT NULL) as avg_similarity,
    MIN(created_at) as first_migration_start,
    MAX(migrated_at) as last_migration_complete
FROM migration_tracking
GROUP BY stage
ORDER BY stage;

COMMENT ON VIEW migration_progress IS 'Dashboard view: migration progress by pipeline stage';

-- Vista para documentos pendientes de migración
CREATE OR REPLACE VIEW migration_pending_documents AS
SELECT 
    ds.document_id,
    ds.filename,
    ds.publication_date,
    ds.newspaper_name,
    ds.data_source,
    ds.migration_status,
    ds.created_at,
    COUNT(mt.id) as stages_tracked,
    COUNT(mt.id) FILTER (WHERE mt.migrated_at IS NOT NULL) as stages_migrated,
    ARRAY_AGG(mt.stage ORDER BY mt.stage) FILTER (WHERE mt.migrated_at IS NULL) as pending_stages
FROM document_status ds
LEFT JOIN migration_tracking mt ON ds.document_id = mt.document_id
WHERE ds.data_source = 'legacy' AND ds.migration_status != 'completed'
GROUP BY ds.document_id, ds.filename, ds.publication_date, ds.newspaper_name, ds.data_source, ds.migration_status, ds.created_at
ORDER BY ds.created_at;

COMMENT ON VIEW migration_pending_documents IS 'Documents still pending migration with stage details';

-- ============================================================================
-- STEP 6: Índices para búsqueda humanizada (fecha + periódico)
-- ============================================================================

CREATE INDEX IF NOT EXISTS idx_document_publication_date ON document_status(publication_date DESC) WHERE publication_date IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_document_newspaper ON document_status(newspaper_name) WHERE newspaper_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_document_sha8 ON document_status(sha8_prefix) WHERE sha8_prefix IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_document_date_newspaper ON document_status(publication_date, newspaper_name) WHERE publication_date IS NOT NULL AND newspaper_name IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_document_migration_status ON document_status(migration_status, data_source);

-- ============================================================================
-- STEP 7: Marcar TODOS los documentos existentes como legacy
-- ============================================================================

-- Solo marcar como legacy si no tienen data_source ya asignado
UPDATE document_status 
SET 
    data_source = 'legacy', 
    migration_status = 'pending'
WHERE data_source IS NULL;

-- Log de migración inicial
DO $$
DECLARE
    legacy_count INTEGER;
BEGIN
    SELECT COUNT(*) INTO legacy_count FROM document_status WHERE data_source = 'legacy';
    RAISE NOTICE 'Migration 021 completed: % documents marked as legacy', legacy_count;
END$$;

-- ============================================================================
-- ROLLBACK PLAN (comentado, descomentar si necesitas revertir)
-- ============================================================================

/*
-- Para revertir esta migración:

DROP VIEW IF EXISTS migration_pending_documents;
DROP VIEW IF EXISTS migration_progress;
DROP TABLE IF EXISTS pipeline_results;
DROP TABLE IF NOT EXISTS document_processing_log;
DROP TABLE IF EXISTS migration_tracking;

ALTER TABLE document_status 
    DROP COLUMN IF EXISTS insights_result_ref,
    DROP COLUMN IF EXISTS indexing_result_ref,
    DROP COLUMN IF EXISTS chunking_result_ref,
    DROP COLUMN IF EXISTS segmentation_result_ref,
    DROP COLUMN IF EXISTS ocr_result_ref,
    DROP COLUMN IF EXISTS metadata_parsed,
    DROP COLUMN IF EXISTS sha8_prefix,
    DROP COLUMN IF EXISTS newspaper_name,
    DROP COLUMN IF EXISTS publication_date,
    DROP COLUMN IF EXISTS migration_status,
    DROP COLUMN IF EXISTS migrated_at,
    DROP COLUMN IF EXISTS data_source;
*/

COMMIT;

-- ============================================================================
-- VERIFICATION QUERIES (para testear después de aplicar migración)
-- ============================================================================

-- Verificar tablas creadas
-- SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_name IN ('migration_tracking', 'document_processing_log', 'pipeline_results');

-- Ver progreso de migración
-- SELECT * FROM migration_progress;

-- Ver documentos legacy pendientes
-- SELECT * FROM migration_pending_documents LIMIT 10;

-- Verificar columnas agregadas a document_status
-- SELECT column_name, data_type, is_nullable, column_default FROM information_schema.columns WHERE table_name = 'document_status' AND column_name IN ('data_source', 'migration_status', 'publication_date', 'newspaper_name');
