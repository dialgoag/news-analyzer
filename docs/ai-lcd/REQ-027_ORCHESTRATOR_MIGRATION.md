# 🔄 REQ-027: Migración Progresiva a Orchestrator Agent con Validación y Limpieza Automática

> Refactor completo a arquitectura agéntica con migración validada de datos legacy

**Fecha**: 2026-04-10  
**Estado**: Propuesta Aprobada  
**Prioridad**: CRÍTICA  
**Tipo**: Arquitectura + Migración de Datos  
**Relacionado con**: REQ-026 (Observability), OCR_DIAGNOSIS_2026-04-10

---

## 🎯 OBJETIVO

Migrar de arquitectura Event-Driven (schedulers + workers independientes) a **Full Orchestrator Agent** con sub-agentes como tools, manteniendo compatibilidad con datos legacy hasta que toda la migración esté completa.

### Estrategia de Migración:

```
┌────────────────────────────────────────────────────────────────┐
│         FASE DE TRANSICIÓN (Coexistencia Legacy + Nuevo)       │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Orchestrator Agent (nuevo) procesa documentos                 │
│         │                                                      │
│         ├─► Nodo: LegacyDataAdapter                           │
│         │     • Lee datos viejos si existen                   │
│         │     • Valida contra resultado nuevo                 │
│         │     • Mezcla viejo + nuevo (con metadata)           │
│         │     • Marca legacy como "migrado"                   │
│         │                                                      │
│         └─► Nodo: MigrationTracker                            │
│               • Registra qué etapas ya se migraron            │
│               • Actualiza contador: documentos legacy restantes│
│               • Cuando legacy_count = 0 → flag para cleanup   │
│                                                                │
│  Event-Driven Workers (legacy) → Solo lectura (NO escribe)    │
│                                                                │
└────────────────────────────────────────────────────────────────┘

Resultado:
- Datos legacy + nuevos coexisten (con flag "source: legacy|orchestrator")
- Sistema valida consistencia automáticamente
- Cuando TODO esté migrado → Eliminar código legacy
```

---

## 📋 PETICIÓN DETALLADA

### FASE 1: Preparación de Datos Legacy

**Objetivo**: Marcar todos los datos existentes como "legacy" para rastrear migración.

#### 1.1. Migración de BD: Agregar Flags de Migración

```sql
-- migrations/021_legacy_migration_tracking.sql

-- Marcar datos existentes como legacy
ALTER TABLE document_status 
    ADD COLUMN data_source VARCHAR(20) DEFAULT 'legacy',
    ADD COLUMN migrated_at TIMESTAMPTZ,
    ADD COLUMN migration_status VARCHAR(20) DEFAULT 'pending'; 
    -- pending | in_progress | validated | completed

-- Tracking de migración por etapa
CREATE TABLE migration_tracking (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES document_status(document_id),
    stage VARCHAR(50) NOT NULL,  -- 'upload', 'ocr', 'segmentation', etc.
    
    -- Datos legacy
    legacy_exists BOOLEAN DEFAULT FALSE,
    legacy_data JSONB,  -- snapshot de datos viejos
    legacy_timestamp TIMESTAMPTZ,
    
    -- Datos nuevos (orchestrator)
    new_data JSONB,  -- resultado del orchestrator
    new_timestamp TIMESTAMPTZ,
    
    -- Validación
    validation_status VARCHAR(20),  -- 'pending' | 'match' | 'mismatch' | 'conflict'
    validation_result JSONB,  -- detalles de comparación
    
    -- Decisión final
    merged_data JSONB,  -- mezcla de legacy + nuevo (con prioridad)
    merge_strategy VARCHAR(50),  -- 'keep_new' | 'keep_legacy' | 'merge_both'
    
    migrated_at TIMESTAMPTZ,
    
    INDEX idx_doc_stage (document_id, stage),
    INDEX idx_validation_status (validation_status),
    INDEX idx_migrated (migrated_at)
);

-- Vista para rastrear progreso global
CREATE VIEW migration_progress AS
SELECT 
    stage,
    COUNT(*) as total_documents,
    COUNT(*) FILTER (WHERE validation_status = 'match') as validated,
    COUNT(*) FILTER (WHERE validation_status = 'mismatch') as conflicts,
    COUNT(*) FILTER (WHERE migrated_at IS NOT NULL) as migrated,
    ROUND(100.0 * COUNT(*) FILTER (WHERE migrated_at IS NOT NULL) / COUNT(*), 2) as percent_migrated
FROM migration_tracking
GROUP BY stage;

-- Marcar TODOS los documentos existentes como legacy
UPDATE document_status 
SET data_source = 'legacy', 
    migration_status = 'pending'
WHERE data_source IS NULL OR data_source = 'legacy';
```

#### 1.2. Repository: LegacyDataRepository

**Ubicación**: `backend/adapters/driven/persistence/legacy_data_repository.py`

**Responsabilidades**:
- Leer datos legacy de tablas antiguas
- Traducir formato viejo → formato nuevo
- Comparar legacy vs. nuevo (validación)
- Marcar como migrado

**Métodos clave**:
```python
async def get_legacy_data(document_id: str, stage: str) -> Optional[dict]
async def save_migration_snapshot(document_id: str, stage: str, legacy_data: dict, new_data: dict)
async def validate_migration(document_id: str, stage: str) -> ValidationResult
async def mark_stage_migrated(document_id: str, stage: str, merged_data: dict)
async def get_migration_progress() -> dict  # Para dashboard
```

---

### FASE 2: Orchestrator Agent con LegacyDataAdapter Node

**Objetivo**: Orchestrator lee datos legacy, procesa con nuevo sistema, valida y mezcla.

#### 2.1. Arquitectura del Orchestrator con Migración

```
┌─────────────────────────────────────────────────────────────────┐
│              PIPELINE ORCHESTRATOR AGENT (LangGraph)            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Estado (TypedDict):                                            │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ • document_id: str                                        │ │
│  │ • migration_mode: bool  (True si documento es legacy)     │ │
│  │ • legacy_data: dict  (datos viejos por etapa)            │ │
│  │ • new_data: dict  (datos nuevos generados)               │ │
│  │ • validation_results: dict  (comparaciones)              │ │
│  │ • merged_data: dict  (resultado final)                   │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  FLUJO CON MIGRACIÓN:                                           │
│                                                                 │
│  START                                                          │
│    ↓                                                            │
│  check_if_legacy_node                                           │
│    ├─► Si data_source = 'legacy' → migration_mode = True       │
│    └─► Si data_source = 'orchestrator' → migration_mode = False│
│    ↓                                                            │
│  validation_node                                                │
│    ├─► [Tool] validation_tool(filepath)                        │
│    ├─► Si migration_mode:                                      │
│    │     └─► legacy_adapter_node                               │
│    │           • Lee legacy: document_status.upload_*          │
│    │           • Compara: legacy.filename vs new.filename      │
│    │           • Valida: ¿coinciden?                           │
│    │           • Merge: prioridad = nuevo (más confiable)      │
│    │           • Marca migration_tracking: validated           │
│    └─► Continúa...                                             │
│    ↓                                                            │
│  ocr_node                                                       │
│    ├─► [Tool] ocr_tool(filepath)                               │
│    ├─► Si migration_mode:                                      │
│    │     └─► legacy_adapter_node                               │
│    │           • Lee legacy: document_status.ocr_text          │
│    │           • Compara: legacy.text vs new.text              │
│    │           • Valida: similarity > 95% → match              │
│    │           • Merge: usa nuevo (más preciso con OCRmyPDF)   │
│    │           • Marca migration_tracking: validated           │
│    └─► Continúa...                                             │
│    ↓                                                            │
│  segmentation_node                                              │
│    ├─► [Tool] segmentation_tool(text)                          │
│    ├─► Si migration_mode:                                      │
│    │     └─► legacy_adapter_node                               │
│    │           • Lee legacy: news_items (viejo)                │
│    │           • Compara: legacy.articles vs new.articles      │
│    │           • Valida: count, titles, confidence             │
│    │           • Merge: nuevo (LLM mejorado)                   │
│    │           • Marca migration_tracking: validated           │
│    └─► Continúa...                                             │
│    ↓                                                            │
│  ... (chunking, indexing, insights similar)                    │
│    ↓                                                            │
│  migration_finalization_node                                    │
│    ├─► Revisa: ¿Todas las etapas validadas?                    │
│    ├─► Persiste merged_data en tablas nuevas                   │
│    ├─► Marca document_status:                                  │
│    │     • data_source = 'orchestrator'                        │
│    │     • migration_status = 'completed'                      │
│    │     • migrated_at = NOW()                                 │
│    └─► Actualiza migration_tracking (todas etapas → migrated)  │
│    ↓                                                            │
│  END                                                            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 2.2. LegacyDataAdapter Node (Pydantic Validation)

**Ubicación**: `backend/adapters/driven/llm/graphs/nodes/legacy_adapter_node.py`

**Modelos Pydantic**:

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal

class LegacyData(BaseModel):
    """Datos legacy de una etapa"""
    stage: str
    exists: bool
    data: dict
    timestamp: Optional[datetime]
    source_table: str  # 'document_status', 'news_items', etc.

class NewData(BaseModel):
    """Datos nuevos generados por orchestrator"""
    stage: str
    data: dict
    timestamp: datetime
    agent_used: str  # 'ValidationAgent', 'OCRAgent', etc.

class ValidationResult(BaseModel):
    """Resultado de comparación legacy vs nuevo"""
    stage: str
    status: Literal['match', 'mismatch', 'conflict', 'no_legacy']
    similarity_score: Optional[float] = Field(ge=0.0, le=1.0)
    differences: list[str] = []
    recommendation: Literal['keep_new', 'keep_legacy', 'merge_both', 'manual_review']
    
    @validator('similarity_score')
    def validate_similarity(cls, v, values):
        if values.get('status') == 'match' and (v is None or v < 0.95):
            raise ValueError('Match status requires similarity >= 0.95')
        return v

class MergedData(BaseModel):
    """Datos finales después de merge"""
    stage: str
    data: dict
    sources: list[Literal['legacy', 'orchestrator']]
    merge_strategy: str
    metadata: dict  # info adicional del merge
```

**Lógica del Nodo**:

```python
async def legacy_adapter_node(state: OrchestratorState) -> OrchestratorState:
    """
    Nodo que lee datos legacy, compara con nuevos, valida y mezcla.
    Se ejecuta DESPUÉS de cada tool de procesamiento.
    """
    stage = state['current_stage']
    document_id = state['document_id']
    
    # 1. Leer datos legacy
    legacy_repo = LegacyDataRepository()
    legacy_data = await legacy_repo.get_legacy_data(document_id, stage)
    
    if not legacy_data or not legacy_data['exists']:
        # No hay legacy para esta etapa, continuar
        state['legacy_data'][stage] = None
        state['validation_results'][stage] = ValidationResult(
            stage=stage,
            status='no_legacy',
            recommendation='keep_new'
        )
        return state
    
    # 2. Obtener datos nuevos del estado actual
    new_data = state['new_data'][stage]
    
    # 3. Validar (comparar)
    validation_result = await validate_stage_data(
        legacy=legacy_data,
        new=new_data,
        stage=stage
    )
    
    # 4. Merge según estrategia
    merged = merge_data(
        legacy=legacy_data,
        new=new_data,
        validation=validation_result
    )
    
    # 5. Persistir snapshot de migración
    await legacy_repo.save_migration_snapshot(
        document_id=document_id,
        stage=stage,
        legacy_data=legacy_data,
        new_data=new_data,
        validation_result=validation_result,
        merged_data=merged
    )
    
    # 6. Actualizar estado
    state['legacy_data'][stage] = legacy_data
    state['validation_results'][stage] = validation_result
    state['merged_data'][stage] = merged
    
    return state
```

**Estrategias de Validación por Etapa**:

| Etapa | Validación | Estrategia Merge |
|-------|-----------|------------------|
| **Upload** | filename, file_size | Siempre nuevo (metadata mejorada) |
| **Validation** | pdf_valid, metadata_parsed | Nuevo (parser mejorado) |
| **OCR** | text similarity > 95% | Nuevo (OCRmyPDF > Tika) |
| **Segmentation** | article count, titles | Nuevo (LLM mejorado) |
| **Chunking** | chunk count, sizes | Nuevo (chunking inteligente) |
| **Indexing** | vector count, dimensions | Nuevo (re-index siempre) |
| **Insights** | insight structure | Nuevo (LangGraph > old) |

---

### FASE 3: MigrationTracker Node (Progreso Global)

**Objetivo**: Rastrear cuántos documentos legacy quedan, cuándo es momento de cleanup.

#### 3.1. MigrationTracker Node

**Ubicación**: `backend/adapters/driven/llm/graphs/nodes/migration_tracker_node.py`

**Responsabilidades**:
- Actualizar contadores de migración
- Calcular progreso global
- Detectar cuándo cleanup es posible
- Emitir eventos para dashboard

**Lógica**:

```python
async def migration_tracker_node(state: OrchestratorState) -> OrchestratorState:
    """
    Nodo final que actualiza tracking de migración.
    Se ejecuta AL FINAL del pipeline, después de todas las etapas.
    """
    document_id = state['document_id']
    
    # 1. Marcar documento como migrado
    await legacy_repo.mark_document_migrated(
        document_id=document_id,
        validation_results=state['validation_results']
    )
    
    # 2. Calcular progreso global
    progress = await legacy_repo.get_migration_progress()
    
    # 3. Log progreso
    logger.info(f"[Migration] Document {document_id} migrated. Progress: {progress['percent_complete']}%")
    
    # 4. Si 100% migrado → Emitir evento "cleanup_ready"
    if progress['percent_complete'] >= 100.0:
        logger.warning("🎉 ALL DOCUMENTS MIGRATED! Legacy cleanup ready.")
        await observer_tool.emit_event({
            'type': 'migration_complete',
            'metadata': progress,
            'action_required': 'legacy_cleanup'
        })
    
    # 5. Actualizar estado
    state['migration_progress'] = progress
    
    return state
```

#### 3.2. Dashboard de Migración

**Endpoint API**: `GET /api/migration/progress`

**Respuesta**:
```json
{
  "total_documents": 351,
  "migrated": 120,
  "percent_complete": 34.2,
  "by_stage": {
    "upload": {"total": 351, "migrated": 351, "percent": 100.0},
    "ocr": {"total": 351, "migrated": 120, "percent": 34.2},
    "segmentation": {"total": 351, "migrated": 85, "percent": 24.2},
    "chunking": {"total": 351, "migrated": 60, "percent": 17.1},
    "indexing": {"total": 351, "migrated": 40, "percent": 11.4},
    "insights": {"total": 351, "migrated": 20, "percent": 5.7}
  },
  "conflicts": 5,
  "estimated_completion": "2026-04-15",
  "cleanup_ready": false
}
```

**Vista en Dashboard**:
```
┌──────────────────────────────────────────────────────────┐
│          MIGRACIÓN A ORCHESTRATOR AGENT                  │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  Progreso Global: [████████░░░░░░░░░░] 34.2%            │
│                                                          │
│  Por Etapa:                                              │
│  Upload:       [████████████████████] 100.0% (351/351)   │
│  OCR:          [███████░░░░░░░░░░░░░]  34.2% (120/351)   │
│  Segmentation: [█████░░░░░░░░░░░░░░░]  24.2% ( 85/351)   │
│  Chunking:     [███░░░░░░░░░░░░░░░░░]  17.1% ( 60/351)   │
│  Indexing:     [██░░░░░░░░░░░░░░░░░░]  11.4% ( 40/351)   │
│  Insights:     [█░░░░░░░░░░░░░░░░░░░]   5.7% ( 20/351)   │
│                                                          │
│  Conflictos detectados: 5 (requieren revisión manual)    │
│                                                          │
│  Estimación de finalización: 15 abril 2026              │
│                                                          │
│  [Ver Conflictos] [Pausar Migración] [Informe Detallado]│
│                                                          │
└──────────────────────────────────────────────────────────┘
```

---

### FASE 4: Cleanup Legacy (Automático cuando 100% migrado)

**Objetivo**: Eliminar código, tablas y datos legacy cuando migración completa.

#### 4.1. Pre-Cleanup Validation

**Checklist automático**:
```python
async def validate_cleanup_ready() -> CleanupReadiness:
    """
    Valida que es seguro eliminar legacy.
    """
    checks = {
        'all_documents_migrated': await check_all_migrated(),
        'no_pending_validations': await check_no_pending(),
        'no_conflicts_unresolved': await check_no_conflicts(),
        'backup_created': await check_backup_exists(),
        'orchestrator_stable': await check_orchestrator_health()
    }
    
    return CleanupReadiness(
        ready=all(checks.values()),
        checks=checks,
        blocked_by=[k for k, v in checks.items() if not v]
    )
```

#### 4.2. Cleanup Stages

**Stage 1: Deprecar Workers Legacy (Soft Delete)**

```sql
-- Marcar schedulers legacy como disabled
UPDATE pipeline_runtime_kv 
SET value = jsonb_set(value, '{disabled}', 'true')
WHERE key LIKE 'scheduler.%' AND key NOT LIKE 'scheduler.orchestrator%';

-- Logs
INSERT INTO migration_log (event, timestamp, metadata)
VALUES ('legacy_schedulers_disabled', NOW(), '{"reason": "migration_complete"}');
```

**Stage 2: Archivar Tablas Legacy**

```sql
-- Renombrar tablas legacy (no eliminar aún, por precaución)
ALTER TABLE processing_queue RENAME TO processing_queue_legacy_archived;
ALTER TABLE worker_tasks RENAME TO worker_tasks_legacy_archived;

-- Mantener por 30 días, luego DROP
INSERT INTO cleanup_schedule (table_name, drop_after)
VALUES 
    ('processing_queue_legacy_archived', NOW() + INTERVAL '30 days'),
    ('worker_tasks_legacy_archived', NOW() + INTERVAL '30 days');
```

**Stage 3: Remover Código Legacy**

```
Archivos a eliminar (después de 30 días de pruebas):
- backend/app.py líneas 2800-3500 (workers legacy)
- backend/schedulers/*.py (schedulers viejos)
- backend/legacy/ (carpeta completa)

Mantener:
- backend/adapters/driven/persistence/legacy_data_repository.py (histórico)
- migrations/021_legacy_migration_tracking.sql (auditoría)
```

#### 4.3. Post-Cleanup Validation

**Tests automáticos**:
```python
async def test_orchestrator_handles_all_documents():
    """Validar que orchestrator procesa correctamente sin legacy."""
    
    # 1. Seleccionar 10 documentos random
    docs = await db.fetch("SELECT * FROM document_status ORDER BY RANDOM() LIMIT 10")
    
    # 2. Re-procesar con orchestrator
    for doc in docs:
        result = await orchestrator_agent.process_document(doc['document_id'])
        assert result['success'] == True
    
    # 3. Validar resultados
    for doc in docs:
        assert await validate_document_complete(doc['document_id'])
```

---

## 📊 TIMELINE DE MIGRACIÓN

```
┌────────────────────────────────────────────────────────────────┐
│                    TIMELINE DE MIGRACIÓN                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  Semana 1-2: FASE 1 (Preparación)                              │
│  ├─ Migración BD (tracking tables)                             │
│  ├─ LegacyDataRepository                                       │
│  └─ Marcar todos los docs como legacy                          │
│                                                                │
│  Semana 3-4: FASE 2 (Orchestrator + Adapter)                   │
│  ├─ PipelineOrchestratorAgent base                             │
│  ├─ Sub-agentes como tools                                     │
│  ├─ LegacyAdapterNode                                          │
│  └─ Tests con 10 documentos                                    │
│                                                                │
│  Semana 5-6: FASE 3 (MigrationTracker + Dashboard)             │
│  ├─ MigrationTrackerNode                                       │
│  ├─ Dashboard de progreso                                      │
│  ├─ Resolución de conflictos                                   │
│  └─ Lanzar orchestrator en producción (coexistiendo)           │
│                                                                │
│  Semana 7-10: Procesamiento Masivo                             │
│  ├─ Orchestrator procesa 351 documentos legacy                 │
│  ├─ Validación automática                                      │
│  ├─ Resolución de conflictos manuales                          │
│  └─ Monitoreo de progreso                                      │
│                                                                │
│  Semana 11: FASE 4 (Cleanup)                                   │
│  ├─ Validación 100% migrado                                    │
│  ├─ Backup final                                               │
│  ├─ Deprecar workers legacy                                    │
│  ├─ Archivar tablas legacy                                     │
│  └─ Tests post-cleanup                                         │
│                                                                │
│  Semana 12+: Estabilización                                    │
│  ├─ Monitoreo orchestrator en prod                             │
│  ├─ Performance tuning                                         │
│  └─ Eliminar código legacy (después de 30 días)                │
│                                                                │
└────────────────────────────────────────────────────────────────┘
```

---

## 🎯 CRITERIOS DE ÉXITO

### Migración Completa:
- [ ] 100% de documentos procesados con orchestrator
- [ ] 0 conflictos sin resolver
- [ ] Validación automática: > 95% similarity en todas las etapas
- [ ] Dashboard muestra "Migration Complete"
- [ ] Backup de datos legacy creado

### Calidad:
- [ ] Performance orchestrator >= Event-driven (tiempo de procesamiento)
- [ ] Observabilidad mejorada (timeline completo por documento)
- [ ] Recovery funcional (crash recovery con checkpoints)
- [ ] Tests automáticos pasando (100%)

### Cleanup:
- [ ] Workers legacy deshabilitados
- [ ] Tablas legacy archivadas
- [ ] Código legacy eliminado (después de 30 días)
- [ ] Documentación actualizada

---

## 📋 DECISIONES TÉCNICAS CLAVE

### 1. Estrategia de Merge por Etapa

| Etapa | Si Legacy = Nuevo | Si Legacy ≠ Nuevo | Prioridad |
|-------|------------------|-------------------|-----------|
| Upload | Skip re-upload | Usar nuevo (metadata mejorada) | Nuevo |
| OCR | Skip OCR | Similarity < 95% → Re-OCR | Nuevo |
| Segmentation | Skip | Confidence < 0.7 → Re-segment | Nuevo |
| Chunking | Skip | Re-chunk siempre | Nuevo |
| Indexing | Skip | Re-index siempre | Nuevo |
| Insights | Skip | Re-generate siempre | Nuevo |

### 2. Conflictos que Requieren Revisión Manual

- Similarity OCR < 80% (posible error en uno de los dos)
- Segmentation: count de artículos difiere en > 50%
- Metadata incompatible (fecha/periódico no coincide con filename)

### 3. Rollback Strategy

Si migración falla:
- Reactivar schedulers legacy (cambiar `disabled: false`)
- Orchestrator en modo read-only
- Investigar causa del fallo
- Fix + retry

---

## 📚 ARCHIVOS RELACIONADOS

**Documentación**:
- `AGENT_ORCHESTRATION_ARCHITECTURE.md` - Arquitectura base
- `OCR_DIAGNOSIS_2026-04-10.md` - Análisis de calidad OCR
- `EVENT_DRIVEN_ARCHITECTURE.md` - Sistema actual (legacy)

**Código a Crear**:
- `backend/adapters/driven/llm/graphs/pipeline_orchestrator_graph.py`
- `backend/adapters/driven/llm/graphs/nodes/legacy_adapter_node.py`
- `backend/adapters/driven/llm/graphs/nodes/migration_tracker_node.py`
- `backend/adapters/driven/persistence/legacy_data_repository.py`

**Migraciones BD**:
- `migrations/021_legacy_migration_tracking.sql`

**Tests**:
- `tests/integration/test_orchestrator_migration.py`

---

## 🚀 PRÓXIMOS PASOS

1. **Validar propuesta con usuario** ✅
2. **Implementar FASE 1** (Preparación BD + LegacyDataRepository)
3. **Implementar FASE 2** (Orchestrator + LegacyAdapterNode)
4. **Implementar FASE 3** (MigrationTracker + Dashboard)
5. **Ejecutar migración masiva** (351 documentos)
6. **Validar 100% completado**
7. **FASE 4: Cleanup** (eliminar legacy)

---

**Fecha de Inicio Estimada**: 2026-04-11  
**Fecha de Finalización Estimada**: 2026-06-30 (12 semanas)  
**Responsable**: diego.a + AI Agent
