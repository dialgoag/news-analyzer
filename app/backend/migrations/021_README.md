# Migration 021: Legacy Migration Tracking

## Status: ✅ APLICADA MANUALMENTE (2026-04-10)

### Ubicación del archivo original
`021_legacy_migration_tracking.sql.applied`

### Razón del renombre
La migración fue aplicada manualmente directamente en PostgreSQL debido a un conflicto con el sistema de transacciones de Yoyo (el archivo contenía `BEGIN`/`COMMIT` explícitos que causaban errores de SAVEPOINT).

### Cambios aplicados en BD

#### Tablas creadas:
- `migration_tracking` - Tracking de migración por etapa y documento
- `document_processing_log` - Timeline completo de eventos del pipeline (observabilidad)
- `pipeline_results` - Resultados intermedios del pipeline

#### Columnas agregadas a `document_status`:
- `data_source` (legacy/orchestrator)
- `migration_status` (pending/in_progress/validated/completed)
- `migrated_at`
- `publication_date`, `newspaper_name`, `sha8_prefix`, `metadata_parsed` (metadata de filename)
- `ocr_result_ref`, `segmentation_result_ref`, `chunking_result_ref`, `indexing_result_ref`, `insights_result_ref`

#### Vistas creadas:
- `migration_progress` - Progreso de migración por stage
- `migration_pending_documents` - Documentos pendientes de migración

#### Índices creados:
- Índices para búsqueda por fecha/periódico
- Índices para queries de dashboard
- Índices para tracking de migración

### Verificación
```sql
-- Verificar tablas
SELECT table_name FROM information_schema.tables 
WHERE table_schema = 'public' 
AND table_name IN ('migration_tracking', 'document_processing_log', 'pipeline_results');

-- Ver documentos legacy
SELECT COUNT(*) FROM document_status WHERE data_source = 'legacy';

-- Ver progreso de migración
SELECT * FROM migration_progress;
```

### Registro en Yoyo
```sql
INSERT INTO _yoyo_migration (migration_hash, migration_id, applied_at_utc) 
VALUES ('676d74bb8a1feeae575d24f7750d07c0785f3709c5b25894f3fe541d025e2545', '021_legacy_migration_tracking', '2026-04-10 14:24:50');
```

### Documentos marcados como legacy
338 documentos existentes fueron marcados con `data_source='legacy'` y `migration_status='pending'`.
