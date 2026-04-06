# Sistema Estandarizado de Timestamps

## 🎯 Principio Unificador

**Patrón Universal**: Todo registro en el sistema tiene timestamps que rastrean su ciclo de vida:

```
created_at → Momento en que el registro/proceso INICIA
updated_at → Momento en que el registro/proceso CAMBIA (finaliza, error, progreso)
```

---

## 📊 Arquitectura: Dos Niveles de Timestamps

### Nivel 1: Document-Level (Tabla `document_status`)

Timestamps que aplican al **documento completo**:

```sql
document_status:
  created_at   → Primera vez que documento entra al sistema (= momento de upload)
  updated_at   → Última modificación de CUALQUIER campo (auto-trigger)
```

**Uso**:
- `created_at` se setea una vez en INSERT (inmutable)
- `updated_at` se actualiza automáticamente en cada UPDATE (DB trigger)

### Nivel 2: Stage-Level (Tabla `document_stage_timing`)

Timestamps que aplican a **cada etapa** del pipeline:

```sql
document_stage_timing:
  id               SERIAL PRIMARY KEY
  document_id      VARCHAR(255) NOT NULL (FK → document_status)
  stage            VARCHAR(50) NOT NULL ('upload', 'ocr', 'chunking', 'indexing', 'insights')
  status           VARCHAR(50) NOT NULL ('pending', 'processing', 'done', 'error', 'skipped')
  created_at       TIMESTAMP NOT NULL  → Stage INICIA
  updated_at       TIMESTAMP NOT NULL  → Stage FINALIZA o se modifica (auto-trigger)
  error_message    TEXT
  metadata         JSONB (worker_id, file_info, etc.)
  
  UNIQUE(document_id, stage)
```

**Patrón de uso**:

```python
# 1. Worker INICIA stage
stage_timing_repository.record_stage_start(
    document_id="doc-123",
    stage="ocr",
    metadata={"worker_id": "ocr-worker-1"}
)
# → INSERT (created_at=NOW, updated_at=NOW, status='processing')

# 2. Worker FINALIZA stage (éxito)
stage_timing_repository.record_stage_end(
    document_id="doc-123",
    stage="ocr",
    status="done"
)
# → UPDATE (updated_at=NOW, status='done')
# → Trigger auto-actualiza updated_at

# 3. Worker FINALIZA stage (error)
stage_timing_repository.record_stage_end(
    document_id="doc-123",
    stage="ocr",
    status="error",
    error_message="Tika timeout"
)
# → UPDATE (updated_at=NOW, status='error', error_message='...')
```

---

## ✅ Ventajas de Este Diseño

| Aspecto | Beneficio |
|---------|-----------|
| **Escalabilidad** | Agregar nuevo stage = solo INSERT (sin schema change) |
| **Flexibilidad** | Metadata JSONB permite data adicional sin ALTER TABLE |
| **Performance** | Fácil calcular duraciones, analizar cuellos de botella |
| **Auditabilidad** | Timeline completo de cada documento |
| **Normalización** | No duplica datos en document_status (tabla limpia) |

---

## 📋 Queries Comunes

### 1. Timeline completo de un documento

```sql
SELECT stage, status, created_at, updated_at,
       EXTRACT(EPOCH FROM (updated_at - created_at)) as duration_seconds
FROM document_stage_timing
WHERE document_id = 'doc-123'
ORDER BY created_at ASC;
```

**Output**:
```
stage     | status | created_at          | updated_at          | duration_seconds
----------|--------|---------------------|---------------------|------------------
upload    | done   | 2026-03-31 10:00:00 | 2026-03-31 10:00:05 | 5
ocr       | done   | 2026-03-31 10:00:05 | 2026-03-31 10:02:30 | 145
chunking  | done   | 2026-03-31 10:02:30 | 2026-03-31 10:02:45 | 15
indexing  | done   | 2026-03-31 10:02:45 | 2026-03-31 10:03:00 | 15
insights  | done   | 2026-03-31 10:03:00 | 2026-03-31 10:05:00 | 120
```

### 2. Performance promedio por stage

```sql
SELECT stage,
       COUNT(*) as total_docs,
       AVG(EXTRACT(EPOCH FROM (updated_at - created_at))) as avg_seconds,
       MIN(EXTRACT(EPOCH FROM (updated_at - created_at))) as min_seconds,
       MAX(EXTRACT(EPOCH FROM (updated_at - created_at))) as max_seconds
FROM document_stage_timing
WHERE status = 'done'
  AND updated_at IS NOT NULL
GROUP BY stage
ORDER BY avg_seconds DESC;
```

**Output**:
```
stage     | total_docs | avg_seconds | min_seconds | max_seconds
----------|------------|-------------|-------------|-------------
ocr       | 150        | 125.5       | 45.2        | 320.8
insights  | 120        | 95.3        | 60.1        | 180.4
chunking  | 145        | 12.8        | 8.5         | 25.3
indexing  | 140        | 10.2        | 5.1         | 20.7
upload    | 150        | 3.5         | 1.2         | 8.9
```

### 3. Documentos atascados en un stage

```sql
SELECT document_id, stage, status, 
       created_at,
       NOW() - created_at as time_stuck
FROM document_stage_timing
WHERE status IN ('pending', 'processing')
  AND NOW() - created_at > INTERVAL '30 minutes'
ORDER BY created_at ASC;
```

### 4. Tasa de éxito por stage

```sql
SELECT stage,
       COUNT(*) as total,
       SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) as success,
       SUM(CASE WHEN status = 'error' THEN 1 ELSE 0 END) as errors,
       ROUND(100.0 * SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM document_stage_timing
WHERE status IN ('done', 'error')
GROUP BY stage
ORDER BY success_rate ASC;
```

---

## 🔄 Mapeo con Campos Legacy

Para backward compatibility, mantenemos campos legacy en `document_status`:

| Campo Legacy | Nuevo Sistema | Notas |
|-------------|---------------|-------|
| `ingested_at` | `document_stage_timing[stage='upload'].updated_at` | Momento upload completó |
| `indexed_at` | `document_stage_timing[stage='indexing'].updated_at` | Momento indexing completó |

**Domain entity** incluye ambos:
```python
@dataclass
class Document:
    # New standard
    created_at: datetime
    updated_at: datetime
    
    # Legacy (deprecated pero mantenidos)
    ingested_at: datetime  # = upload_updated_at
    uploaded_at: datetime  # = created_at
    indexed_at: datetime   # = indexing_updated_at
```

**Repository** mapea correctamente entre DB y domain.

---

## ♻️ Backfill opcional para históricos

Antes de Migration 018, los documentos no tenían registros `stage='upload'`.  
Si necesitas métricas históricas previas al despliegue:

1. Ir a la carpeta backend y ejecutar el script:
   ```bash
   cd app/backend
   python scripts/backfill_upload_stage_timing.py --batch-size 1000
   ```
2. Flags útiles:
   - `--limit N` para procesar solo los primeros N documentos sin registro.
   - `--dry-run` para ver cuántas filas faltan sin insertar nada.

El script revisa `document_status` y crea filas `document_stage_timing` con:
- `stage='upload'`
- `status` derivado de `document_status.status` (`upload_pending|processing|done|error`)
- `metadata.backfill = "upload_stage"`

Las ingestas nuevas ya escriben `document_stage_timing` durante el alta (`file_ingestion_service`), por lo que el script solo es necesario una vez si quieres históricos.

---

## 🚀 Implementación en Workers

### Patrón Estándar (OCR Worker ejemplo):

```python
async def _ocr_worker_task(document_id: str, filename: str, worker_id: str):
    try:
        # 1. RECORD STAGE START
        stage_timing_repository.record_stage_start_sync(
            document_id=document_id,
            stage='ocr',
            metadata={'worker_id': worker_id, 'filename': filename}
        )
        
        # 2. Mark worker as started
        worker_repository.update_worker_status_sync(
            worker_id, document_id, 'ocr', 'started'
        )
        
        # 3. Process...
        text, doc_type, hash = await asyncio.to_thread(_extract_ocr_only, ...)
        await document_repository.store_ocr_text(doc_id, text)
        
        # 4. RECORD STAGE END as done
        stage_timing_repository.record_stage_end_sync(
            document_id, 'ocr', 'done'
        )
        
        # 5. Mark worker as completed
        worker_repository.update_worker_status_sync(
            worker_id, document_id, 'ocr', 'completed'
        )
        
    except Exception as e:
        # RECORD STAGE END with error
        stage_timing_repository.record_stage_end_sync(
            document_id, 'ocr', 'error', error_message=str(e)
        )
        # ... handle error ...
```

**Workers actualizados**:
- ✅ `_ocr_worker_task` (stage='ocr')
- ✅ `_chunking_worker_task` (stage='chunking')
- ✅ `_indexing_worker_task` (stage='indexing')
- ⚠️ `_insights_worker_task` (stage='insights' - registra inicio, pero end se marca cuando TODOS los news_items terminan)

---

## 📈 Análisis de Performance Habilitado

Con este sistema, puedes responder preguntas como:

1. **¿Qué stage es el más lento?**
   ```sql
   SELECT stage, AVG(...duration...) FROM document_stage_timing ...
   ```

2. **¿Cuánto tiempo tomó procesar el documento X?**
   ```sql
   SELECT SUM(EXTRACT(EPOCH FROM (updated_at - created_at)))
   FROM document_stage_timing WHERE document_id = 'doc-X' AND status = 'done'
   ```

3. **¿Qué documentos están atascados?**
   ```sql
   SELECT * FROM document_stage_timing 
   WHERE status = 'processing' AND NOW() - created_at > INTERVAL '1 hour'
   ```

4. **¿Cuál es la tasa de error por stage?**
   ```sql
   SELECT stage, 
          SUM(CASE WHEN status='error' THEN 1 ELSE 0 END)::float / COUNT(*) as error_rate
   FROM document_stage_timing GROUP BY stage
   ```

---

## 🎯 Estándar Aplicado a Otras Tablas

Este mismo patrón se aplica a **todas las tablas**:

| Tabla | `created_at` | `updated_at` | Trigger |
|-------|-------------|--------------|---------|
| `document_status` | ✅ | ✅ | ✅ |
| `document_stage_timing` | ✅ | ✅ | ✅ |
| `users` | ✅ (ya existía) | ✅ (nuevo) | ✅ |
| `pipeline_runtime_kv` | ✅ (nuevo) | ✅ (ya existía) | ❌ (manual) |
| `news_items` | ✅ (ya existía) | ✅ (ya existía) | ✅ (nuevo) |
| `news_item_insights` | ✅ (ya existía) | ✅ (ya existía) | ✅ (nuevo) |
| `document_insights` | ✅ (ya existía) | ✅ (ya existía) | ✅ (nuevo) |
| `daily_reports` | ✅ (ya existía) | ✅ (ya existía) | ✅ (nuevo) |
| `weekly_reports` | ✅ (ya existía) | ✅ (ya existía) | ✅ (nuevo) |

---

## 🔧 Migración: `018_standardize_timestamps.py`

**Cambios aplicados**:

1. **`document_status`**: Agrega `created_at`, `updated_at`
2. **`document_stage_timing`**: Nueva tabla (estructura completa arriba)
3. **`users`**: Agrega `updated_at`
4. **`pipeline_runtime_kv`**: Agrega `created_at`
5. **Triggers**: Auto-update de `updated_at` en todas las tablas
6. **Backfill**: Migra datos existentes:
   - `upload_updated_at = ingested_at`
   - `indexing_updated_at = indexed_at`

**Índices de performance**:
- `idx_document_status_created/updated`
- `idx_document_stage_timing_doc` (document_id, stage)
- `idx_document_stage_timing_stage` (stage, status, created_at)
- `idx_document_stage_timing_performance` (para calcular duraciones)

---

## 📝 Resumen de Cambios

| Componente | Cambios |
|-----------|---------|
| **Migration 018** | Nueva tabla `document_stage_timing` + timestamps en otras tablas |
| **Domain Entity** | `StageTimingRecord` (nueva) |
| **Repository Port** | `StageTimingRepository` (nueva) |
| **Repository Impl** | `PostgresStageTimingRepository` (nueva) |
| **Document Entity** | Simplificada (removidos 10 campos de stage timing) |
| **DocumentRepository** | SELECTs simplificados (16 campos en vez de 26) |
| **Workers** | Llamadas a `record_stage_start/end` en inicio/fin de cada stage |

---

## 🎯 Estado Final del Sistema

### ✅ Completado:

1. ✅ Nueva tabla `document_stage_timing` (escalable, flexible)
2. ✅ Entity + Repository para stage timing
3. ✅ Document entity simplificada (solo document-level timestamps)
4. ✅ DocumentRepository actualizado (mapeo correcto)
5. ✅ Workers OCR, Chunking, Indexing actualizados
6. ✅ Triggers automáticos para `updated_at`
7. ✅ Índices de performance
8. ✅ Backfill de datos existentes

### ⚠️ Pendiente:

- [ ] Verificar insights worker (complejo: procesa news_items no documents)
- [ ] Testing completo (migration + endpoints)
- [ ] Documentación en CONSOLIDATED_STATUS

---

## 🔍 Verificación de Integridad

Comparación con versión original:

| Aspecto | Original | Nuevo | Estado |
|---------|----------|-------|--------|
| Campos en `save()` UPDATE | 9 | 12 | ✅ +3 campos |
| Campos en `save()` INSERT | 12 | 16 | ✅ +4 campos |
| SELECTs (columnas) | 12 | 16 | ✅ +4 campos |
| Stage timing tracking | ❌ No | ✅ Sí (tabla separada) | ✅ Nueva funcionalidad |
| Compilación | ✅ | ✅ | ✅ OK |

**Conclusión**: ✅ NO se perdieron campos, se AGREGÓ funcionalidad escalable.
