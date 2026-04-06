# Pipeline State Transitions - NewsAnalyzer-RAG

> **Documentación COMPLETA** de transiciones de estados en producción y domain model

**Single Source of Truth (Producción)**: `pipeline_states.py`  
**Domain Model (Nuevo, en desarrollo)**: `core/domain/value_objects/pipeline_status.py`  
**Fecha**: 2026-03-31

---

## ⚠️ AVISO: Dos Sistemas Coexisten

### 🟢 Sistema en PRODUCCIÓN (`pipeline_states.py`)

**Estados con prefijos de stage**: `ocr_pending`, `ocr_processing`, `ocr_done`, `chunking_done`, etc.

- ✅ **Usado en**: `app.py`, `database.py`, todas las queries SQL
- ✅ **Single source of truth** para código de producción
- ✅ **Este documento describe ESTE sistema primero**

### 🟡 Domain Model (En desarrollo, NO en producción aún)

**Estados genéricos**: `queued`, `processing`, `completed`, `generating`, `done`

- ⏳ **Usado en**: `entities/`, tests unitarios
- ⏳ **NO integrado** en código de producción todavía
- ⏳ **Fase 2 (Repositories)** lo integrará

---

## 📋 1. Document Pipeline (Producción)

### Convención de Nombres

**Patrón**: `{stage}_{state}`

Donde:
- `stage` = `upload`, `ocr`, `chunking`, `indexing`, `insights`
- `state` = `pending`, `processing`, `done`

**Excepciones** (sin prefijo):
- `completed` (terminal - toda la pipeline terminó)
- `error` (terminal - falló en algún paso)
- `paused` (pausado manualmente)

### Estados Completos (pipeline_states.py)

```python
class DocStatus:
    # Upload stage
    UPLOAD_PENDING = "upload_pending"
    UPLOAD_PROCESSING = "upload_processing"
    UPLOAD_DONE = "upload_done"
    
    # OCR stage
    OCR_PENDING = "ocr_pending"
    OCR_PROCESSING = "ocr_processing"
    OCR_DONE = "ocr_done"
    
    # Chunking stage
    CHUNKING_PENDING = "chunking_pending"
    CHUNKING_PROCESSING = "chunking_processing"
    CHUNKING_DONE = "chunking_done"
    
    # Indexing stage
    INDEXING_PENDING = "indexing_pending"
    INDEXING_PROCESSING = "indexing_processing"
    INDEXING_DONE = "indexing_done"
    
    # Insights stage
    INSIGHTS_PENDING = "insights_pending"
    INSIGHTS_PROCESSING = "insights_processing"
    INSIGHTS_DONE = "insights_done"
    
    # Terminal states (sin prefijo)
    COMPLETED = "completed"
    ERROR = "error"
    PAUSED = "paused"
```

### Flujo Completo (Happy Path)

```
upload_pending
    ↓
upload_processing
    ↓
upload_done
    ↓
ocr_pending
    ↓
ocr_processing
    ↓
ocr_done
    ↓
chunking_pending
    ↓
chunking_processing
    ↓
chunking_done
    ↓
indexing_pending
    ↓
indexing_processing
    ↓
indexing_done
    ↓
insights_pending (si INSIGHTS_QUEUE_ENABLED=true)
    ↓
insights_processing
    ↓
insights_done
    ↓
completed (TERMINAL)
```

### Patrón de Cada Stage

Cada stage (OCR, Chunking, Indexing, Insights) sigue:

```
{stage}_pending → {stage}_processing → {stage}_done → {next_stage}_pending
```

**Responsabilidades**:
- **Scheduler** (Master Pipeline): Crea tareas → pone estado `{stage}_pending`
- **Worker**: Toma tarea → pone `{stage}_processing` → ejecuta → pone `{stage}_done`
- **Scheduler** (próximo ciclo): Detecta `{stage}_done` → crea tarea siguiente stage

### Transiciones Válidas Detalladas

| Estado Actual | Siguiente Estado | Quién Lo Hace | Cuándo |
|--------------|------------------|---------------|--------|
| `upload_pending` | `upload_processing` | Upload handler | Empieza upload |
| `upload_processing` | `upload_done` | Upload handler | Upload completo |
| `upload_done` | `ocr_pending` | **Scheduler** | Detecta upload_done, crea tarea OCR |
| `ocr_pending` | `ocr_processing` | OCR Worker | Toma tarea de queue |
| `ocr_processing` | `ocr_done` | OCR Worker | OCR terminó exitoso |
| `ocr_done` | `chunking_pending` | **Scheduler** | Detecta ocr_done, crea tarea Chunking |
| `chunking_pending` | `chunking_processing` | OCR Worker* | Toma tarea (*mismo worker en realidad) |
| `chunking_processing` | `chunking_done` | OCR Worker | Chunking terminó |
| `chunking_done` | `indexing_pending` | **Scheduler** | Detecta chunking_done, crea tarea Indexing |
| `indexing_pending` | `indexing_processing` | OCR Worker | Toma tarea |
| `indexing_processing` | `indexing_done` | OCR Worker | Indexing terminó |
| `indexing_done` | `insights_pending` | **Scheduler** | Si INSIGHTS_QUEUE_ENABLED, crea tareas por news_item |
| `indexing_done` | `completed` | **Scheduler** | Si insights deshabilitado |
| `insights_pending` | `insights_processing` | Insights Worker | Toma tarea (por news_item) |
| `insights_processing` | `insights_done` | Insights Worker | Insights generado |
| `insights_done` | `completed` | **Scheduler** | Cuando TODOS los news_items tienen insights done |
| **(cualquiera)** | `error` | Worker/Handler | Si algo falla |
| `error` | `{stage}_pending` | **Admin manual** | Retry desde último stage fallido |
| `paused` | `{stage}_pending` | **Admin manual** | Resume desde donde pausó |

**⚠️ Nota Importante**: En producción (`app.py`), el **mismo worker de OCR** ejecuta los 3 pasos (OCR → Chunking → Indexing) en secuencia, cambiando el status en cada paso. No son workers separados (por ahora).

### Código Real de Producción

**app.py - _ocr_worker_task()** (simplificado):

```python
async def _ocr_worker_task(document_id: str, filename: str, file_path: str):
    try:
        # PASO 1: OCR
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.create(StageEnum.OCR, StateEnum.PROCESSING),
            processing_stage=Stage.OCR,
            clear_error_message=True,
        )
        stage_timing_repository.record_stage_start_sync(document_id, 'ocr')
        text = ocr_service.extract_text(file_path)

        # PASO 2: Chunking (mismo worker continúa)
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.create(StageEnum.CHUNKING, StateEnum.PROCESSING),
            processing_stage=Stage.CHUNKING,
            clear_indexed_at=True,
        )
        stage_timing_repository.record_stage_start_sync(document_id, 'chunking')
        items = segment_news_items_from_text(text)
        chunk_records = chunk_document(items)

        # PASO 3: Indexing (mismo worker continúa)
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.create(StageEnum.INDEXING, StateEnum.PROCESSING),
            processing_stage=Stage.INDEXING,
        )
        stage_timing_repository.record_stage_start_sync(document_id, 'indexing')
        rag_pipeline.index_chunk_records(chunk_records)

        # PASO 4: Marcar indexing completo
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.create(StageEnum.INDEXING, StateEnum.DONE),
            indexed_at=datetime.utcnow().isoformat(),
            num_chunks=len(chunk_records),
        )
        stage_timing_repository.record_stage_end_sync(document_id, 'indexing', 'done')

    except Exception as e:
        stage_timing_repository.record_stage_end_sync(
            document_id, 'ocr', 'error', error_message=str(e)
        )
        document_repository.update_status_sync(
            document_id,
            PipelineStatus.terminal(TerminalStateEnum.ERROR),
            error_message=str(e),
        )
```

**app.py - Master Pipeline Scheduler** (simplificado):

```python
async def _master_pipeline_scheduler():
    while True:
        # PASO 1: Detectar docs con upload_done/ocr_pending → crear tareas OCR
        cursor.execute("""
            SELECT document_id, filename 
            FROM document_status 
            WHERE status IN (%s, %s)
        """, (DocStatus.UPLOAD_DONE, DocStatus.OCR_PENDING))
        
        for row in cursor.fetchall():
            processing_queue_store.enqueue_task(
                row['document_id'], 
                row['filename'], 
                TaskType.OCR
            )
        
        # PASO 2: Detectar docs con ocr_done → crear tareas Chunking
        cursor.execute("""
            SELECT document_id, filename 
            FROM document_status 
            WHERE status = %s
        """, (DocStatus.OCR_DONE,))
        
        for row in cursor.fetchall():
            processing_queue_store.enqueue_task(
                row['document_id'], 
                row['filename'], 
                TaskType.CHUNKING
            )
        
        # PASO 3: Detectar docs con chunking_done → crear tareas Indexing
        # ... similar ...
        
        # PASO 4: Detectar docs con indexing_done → crear tareas Insights
        cursor.execute("""
            SELECT ni.news_item_id, ni.document_id 
            FROM news_items ni
            JOIN document_status ds ON ni.document_id = ds.document_id
            WHERE ds.status = %s
            AND NOT EXISTS (
                SELECT 1 FROM news_item_insights nii 
                WHERE nii.news_item_id = ni.news_item_id
            )
        """, (DocStatus.INDEXING_DONE,))
        
        for row in cursor.fetchall():
            news_item_insights_store.enqueue(
                news_item_id=row['news_item_id']
            )
        
        # PASO 5: Detectar docs con todos insights done → marcar COMPLETED
        cursor.execute("""
            UPDATE document_status 
            SET status = %s
            WHERE status = %s
            AND NOT EXISTS (
                SELECT 1 FROM news_item_insights nii
                WHERE nii.document_id = document_status.document_id
                AND (nii.status != %s OR nii.indexed_in_qdrant_at IS NULL)
            )
        """, (DocStatus.COMPLETED, DocStatus.INDEXING_DONE, InsightStatus.DONE))
        
        await asyncio.sleep(10)  # Check cada 10 segundos
```

---

## 🧠 2. Insight Pipeline (Producción)

### Estados (pipeline_states.py)

```python
class InsightStatus:
    """news_item_insights.status - Por noticia individual"""
    PENDING = "pending"           # No iniciado
    QUEUED = "queued"             # En cola para LLM
    GENERATING = "generating"     # LLM generando insights
    INDEXING = "indexing"         # Indexando en Qdrant (después de LLM)
    DONE = "done"                 # Completado (insights + indexado)
    ERROR = "error"               # Error en generación
```

**⚠️ Estos estados NO usan prefijos** porque ya están scope-ados a `news_item_insights` table.

### Flujo

```
pending → queued → generating → indexing → done
             ↑          ↓          ↓
             └─────── error ────────┘
```

### Transiciones

| Estado | Siguiente | Quién | Cuándo |
|--------|-----------|-------|--------|
| `pending` | `queued` | Scheduler | Detecta news_item sin insights |
| `queued` | `generating` | Insights Worker | Toma tarea, llama LLM |
| `generating` | `indexing` | Insights Worker | LLM terminó, va a indexar |
| `indexing` | `done` | Insights Worker | Indexado en Qdrant |
| **(cualquiera)** | `error` | Worker | Si falla LLM o indexing |
| `error` | `pending` | Admin/Retry | Reintentar |

---

## 👷 3. Worker Pipeline (Producción)

### Estados (pipeline_states.py)

```python
class WorkerStatus:
    """worker_tasks.status - Tracking de tareas background"""
    ASSIGNED = "assigned"         # Tarea asignada a worker
    STARTED = "started"           # Worker empezó ejecución
    COMPLETED = "completed"       # Tarea completada exitosamente
    ERROR = "error"               # Tarea falló
```

### Flujo

```
assigned → started → completed
             ↓
           error
```

---

## 🆚 Comparación: Producción vs. Domain Model

### Producción (pipeline_states.py)

```python
# Estados con prefijos explícitos
status = "ocr_pending"
status = "ocr_processing"
status = "ocr_done"
status = "chunking_pending"
# ...
```

**Ventajas**:
- ✅ **Auto-explicativo**: Ves `ocr_done` y sabes exactamente dónde está
- ✅ **SQL claro**: `WHERE status = 'ocr_done'` es más legible
- ✅ **No ambigüedad**: No necesitas combinar `status + stage`

**Desventajas**:
- ❌ **Muchos strings**: 18+ estados diferentes
- ❌ **No reutilizable**: No hay abstracción genérica de "pending", "processing", "done"

### Domain Model (core/domain/value_objects/pipeline_status.py)

```python
# Estados genéricos reutilizables
status = PipelineStatus.for_document("queued")      # Genérico
status = PipelineStatus.for_document("processing")  # Genérico
status = PipelineStatus.for_document("completed")   # Genérico
```

**Ventajas**:
- ✅ **Reutilizable**: Mismo enum para Document, NewsItem, Worker (con validaciones diferentes)
- ✅ **Type safety**: No strings sueltos
- ✅ **Validación automática**: `.can_transition_to()` valida reglas de negocio

**Desventajas**:
- ❌ **Menos específico**: `"queued"` sin contexto no dice si es OCR, Chunking, etc.
- ❌ **Todavía NO integrado** en producción

### Plan de Migración (Fase 2: Repositories)

**Opción A: Mapeo en Repositories**

Repository traduce entre sistemas:

```python
class PostgresDocumentRepository(DocumentRepositoryPort):
    def get(self, doc_id: DocumentId) -> Document:
        row = cursor.execute(
            "SELECT * FROM document_status WHERE document_id = %s", 
            (str(doc_id),)
        ).fetchone()
        
        # Mapeo: producción → domain model
        status_map = {
            "upload_pending": "queued",
            "upload_processing": "processing",
            "ocr_pending": "queued",
            "ocr_processing": "processing",
            "ocr_done": "processing",  # Todavía no completado
            "chunking_pending": "queued",
            # ...
            "indexing_done": "processing",  # Todavía no completado
            "completed": "completed"
        }
        
        domain_status = status_map.get(row['status'], "queued")
        
        return Document(
            id=DocumentId.from_string(row['document_id']),
            filename=row['filename'],
            status=PipelineStatus.for_document(domain_status),
            # ...
        )
```

**Opción B: Migrar DB gradualmente**

Mantener ambos sistemas temporalmente, migrar tabla por tabla.

---

## ✅ Resumen

### Sistema en Producción (Ahora)

- **Estados**: `ocr_pending`, `ocr_processing`, `ocr_done`, etc. (con prefijos)
- **Archivo**: `pipeline_states.py` (single source of truth)
- **Usado en**: TODO el código de producción
- **Convención**: `{stage}_{state}`

### Domain Model (En desarrollo)

- **Estados**: `queued`, `processing`, `completed`, etc. (genéricos)
- **Archivo**: `core/domain/value_objects/pipeline_status.py`
- **Usado en**: Entities, tests unitarios
- **Todavía NO integrado** en producción

### Próximo Paso (Fase 2)

Crear Repositories que:
1. Usen entities del domain model
2. Traduzcan entre estados de producción y domain model
3. Permitan migración gradual sin romper producción

---

**Última actualización**: 2026-03-31  
**Autor**: AI Assistant (generado desde `pipeline_states.py` + `app.py` + `database.py`)
