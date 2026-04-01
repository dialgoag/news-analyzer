# Análisis de Código Legacy - REQ-021

**Fecha**: 2026-03-31  
**Propósito**: Identificar y priorizar eliminación/refactor de código legacy tras Fase 5A

---

## 📊 Métricas Actuales

| Componente | Líneas | Uso en app.py | Estado |
|------------|--------|---------------|--------|
| `database.py` | 1,495 | Stores importados | 🔴 ALTO acoplamiento |
| `document_status_store.*` | - | 70 referencias | 🔴 CRÍTICO |
| `processing_queue_store.*` | - | 71 referencias | 🔴 CRÍTICO |
| `news_item_store.*` | - | 14 referencias | 🟡 MEDIO |
| SQL directo (`cursor.execute`) | - | 104 referencias | 🔴 CRÍTICO |
| Conexiones directas | - | 20+ `get_connection()` | 🔴 CRÍTICO |

---

## 🗂️ Categorías de Legacy Code

### 1️⃣ **STORES (database.py)** 🔴 CRÍTICO

**8 Stores activos**:
```python
DocumentStatusStore          # 70 usos → ✅ TIENE repository (PostgresDocumentRepository)
ProcessingQueueStore         # 71 usos → ❌ SIN repository
NewsItemStore                # 14 usos → ✅ TIENE repository (PostgresNewsItemRepository)
NewsItemInsightsStore        # ~30 usos → ❌ SIN repository (pero es específico)
DocumentInsightsStore        # ~10 usos → ❌ SIN repository (legacy, poco usado)
DailyReportStore             # ~15 usos → ❌ SIN repository (feature reports)
WeeklyReportStore            # ~10 usos → ❌ SIN repository (feature reports)
NotificationStore            # ~8 usos → ❌ SIN repository (feature notifications)
```

**Prioridad**:
1. 🔴 `DocumentStatusStore` → **YA TIENE** `DocumentRepository` (migrar usos restantes)
2. 🔴 `ProcessingQueueStore` → Necesita `WorkerRepository` + `QueueRepository`
3. 🟡 `NewsItemStore` → **YA TIENE** `NewsItemRepository` (migrar usos)
4. 🟢 Reports/Notifications → Mantener stores (son features específicas, no core pipeline)

---

### 2️⃣ **WORKERS (app.py)** 🟡 PARCIAL

**Estado actual - 2 SISTEMAS DE WORKERS COEXISTEN**:

**Sistema 1: Schedulers individuales** (NUEVO - Fase 5A ✅):
```python
✅ run_document_ocr_queue_job_parallel()     # Línea 3321 - Usa Thread + asyncio.run()
   └─> _ocr_worker_task()                    # Línea 3007 - ✅ REFACTORIZADO con repository
✅ run_document_chunking_queue_job()         # Similar pattern
   └─> _chunking_worker_task()               # Línea 3123 - ✅ REFACTORIZADO
✅ run_document_indexing_queue_job()         # Similar pattern
   └─> _indexing_worker_task()               # Línea 3223 - ✅ REFACTORIZADO
🟡 run_news_item_insights_queue_job()        # Línea 2603
   └─> _insights_worker_task()               # Línea 2445 - Usa service pero SQL en dedup
```

**Sistema 2: GenericWorkerPool** (LEGACY - worker_pool.py):
```python
⚠️ GenericWorkerPool                         # worker_pool.py - Pool genérico
   └─> generic_task_dispatcher()             # Línea 2986 - Dispatcher
       ├─> _handle_ocr_task()                # Línea 2740 - ❌ LEGACY (no usa repository)
       ├─> _handle_chunking_task()           # Línea 2778 - ❌ LEGACY
       └─> _handle_indexing_task()           # Línea 2812 - ❌ LEGACY
```

**Usado en**:
- `workers_health_check()` (línea 3605) - Auto-start pool si no existe
- `/api/workers/start` endpoint (línea 6567)

**PROBLEMA CRÍTICO**: 
- ✅ Sistema 1 (schedulers + Thread) usa repositories
- ❌ Sistema 2 (GenericWorkerPool) NO usa repositories
- ⚠️ **AMBOS SISTEMAS SE EJECUTAN SIMULTÁNEAMENTE**

**Prioridad**:
1. 🔴 **Decidir estrategia**:
   - **Opción A**: Eliminar GenericWorkerPool, usar solo schedulers individuales
   - **Opción B**: Refactorizar `_handle_*_task()` para usar repositories (como `_*_worker_task()`)
   - **Opción C**: Migrar schedulers a usar GenericWorkerPool refactorizado
2. 🔴 **Unificar sistemas** - No mantener 2 implementaciones paralelas

---

### 3️⃣ **SCHEDULER (app.py)** 🔴 CRÍTICO

**Funciones con SQL directo**:
```python
master_pipeline_scheduler()              # Línea 622 - Queries raw SQL
run_document_ocr_queue_job_parallel()   # Línea 3321 - SQL directo
run_news_item_insights_queue_job()      # Línea 2603 - SQL directo
detect_crashed_workers()                 # Línea 3432 - SQL queries
```

**Queries típicas**:
```sql
SELECT * FROM processing_queue WHERE status = 'pending' AND task_type = 'ocr'
SELECT COUNT(*) FROM worker_tasks WHERE status IN ('assigned', 'started')
```

**Prioridad**:
1. 🔴 Refactorizar `run_document_ocr_queue_job_parallel()` con `document_repository.list_by_status()`
2. 🔴 Usar `worker_repository` para worker assignment
3. 🟡 Refactorizar `detect_crashed_workers()` con repositories

---

### 4️⃣ **API ENDPOINTS (app.py)** 🟡 MEDIO

**Endpoints con SQL directo**:
```python
GET  /api/documents                    # Línea 3737 - SQL query
GET  /api/documents/status             # Línea 3839 - SQL query
GET  /api/documents/{id}/news-items    # Línea 4005 - SQL query
GET  /api/workers/status               # Línea 5597 - SQL query (20+ líneas)
GET  /api/dashboard/summary            # Línea 5243 - SQL query
GET  /api/dashboard/analysis           # Línea 5938 - SQL query
POST /api/documents/upload             # Línea 1862 - Usa store
POST /api/documents/{id}/requeue       # Línea 4097 - Usa store
```

**Total**: ~30-40 endpoints, mayoría usa stores o SQL directo

**Prioridad**:
1. 🟡 Migrar endpoints críticos del pipeline (upload, requeue, status)
2. 🟢 Dashboard endpoints pueden esperar (son read-only, menos crítico)

---

### 5️⃣ **FUNCIONES UTILITARIAS** 🟢 BAJO

**Funciones legacy pero útiles**:
```python
_initialize_processing_queue()          # Setup inicial
_process_document_sync()                # Legacy sync processing (¿se usa?)
_execute_restore()                      # Backup/restore
workers_health_check()                  # Health checks
```

**Prioridad**: 🟢 Mantener por ahora, refactorizar en Fase 6-7

---

## 🎯 PLAN DE ACCIÓN PRIORIZADO

### **FASE 5B: Scheduler + Queue Management** 🔴 CRÍTICA

**Objetivo**: Eliminar SQL directo en schedulers, usar repositories

**Tareas**:
1. **Refactorizar `run_document_ocr_queue_job_parallel()`**:
   ```python
   # ANTES (SQL directo)
   cursor.execute("SELECT * FROM processing_queue WHERE status='pending' AND task_type='ocr'")
   
   # DESPUÉS (repository)
   pending_tasks = await document_repository.list_by_status(
       PipelineStatus.create(StageEnum.OCR, StateEnum.PENDING)
   )
   ```

2. **Crear `QueueRepository` o usar `WorkerRepository`**:
   - Queries de `processing_queue` table
   - Worker assignment logic

3. **Migrar `detect_crashed_workers()`**:
   - Usar `worker_repository.list_stuck()`
   - Usar `document_repository.update_status()`

**Impacto**: 🔴 ALTO - Schedulers son el corazón del pipeline

**Tiempo estimado**: 3-4 horas

---

### **FASE 5C: Unificar Sistemas de Workers** 🔴 CRÍTICA

**Objetivo**: Resolver duplicación de 2 sistemas de workers coexistentes

**Situación actual**:
- **Sistema 1**: Schedulers individuales + Thread (usa repositories ✅)
- **Sistema 2**: GenericWorkerPool (NO usa repositories ❌)
- Ambos se ejecutan simultáneamente → **Confusión + doble procesamiento**

**Decisión requerida**:

#### **Opción A: Eliminar GenericWorkerPool** (RECOMENDADA 👍)
```python
# Eliminar:
- worker_pool.py (GenericWorkerPool)
- generic_task_dispatcher()
- _handle_ocr_task(), _handle_chunking_task(), _handle_indexing_task()

# Mantener:
- run_document_ocr_queue_job_parallel() + _ocr_worker_task()
- run_document_chunking_queue_job() + _chunking_worker_task()
- run_document_indexing_queue_job() + _indexing_worker_task()
```

**Pros**:
- ✅ Más simple (1 sistema en lugar de 2)
- ✅ Ya usa repositories (Fase 5A)
- ✅ Pattern probado (APScheduler + Thread)

**Contras**:
- ❌ Pierde "pool genérico" (pero puede no ser necesario)

#### **Opción B: Refactorizar GenericWorkerPool**
```python
# Refactorizar:
- _handle_ocr_task() → usar document_repository
- _handle_chunking_task() → usar document_repository
- _handle_indexing_task() → usar document_repository
- Eliminar schedulers individuales

# Mantener:
- GenericWorkerPool como único sistema
```

**Pros**:
- ✅ Pool genérico puede balancear carga entre task types

**Contras**:
- ❌ Más complejo (pool threads + asyncio + DB polling)
- ❌ Requiere refactorizar `_handle_*_task()` (similar a Fase 5A)
- ❌ Duplica lógica que ya funciona

**Recomendación**: **Opción A** - Eliminar GenericWorkerPool

**Impacto**: 🔴 CRÍTICO - 2 sistemas compitiendo por mismas tareas

**Tiempo estimado**: 2-3 horas (eliminar + testear)

---

### **FASE 5D: Cleanup Workers Duplicados** 🟢 BAJA
**(Se resuelve automáticamente con Fase 5C - Opción A)**

---

### **FASE 5E: Migrar usos restantes de DocumentStatusStore** 🟡 MEDIA

**Objetivo**: Reemplazar 70 usos de `document_status_store` por `document_repository`

**Categorías**:
1. **Status updates** (30+ usos):
   ```python
   # ANTES
   document_status_store.update_status(doc_id, DocStatus.ERROR, error_message="...")
   
   # DESPUÉS
   await document_repository.update_status(
       DocumentId(doc_id),
       PipelineStatus.terminal(TerminalStateEnum.ERROR),
       error_message="..."
   )
   ```

2. **OCR text storage** (5 usos):
   ```python
   # ANTES
   document_status_store.store_ocr_text(doc_id, text)
   
   # DESPUÉS
   document = await document_repository.get_by_id(DocumentId(doc_id))
   document.ocr_text = text  # (si agregamos campo mutable)
   await document_repository.save(document)
   ```

3. **Queries** (20+ usos):
   ```python
   # ANTES
   conn = document_status_store.get_connection()
   cursor.execute("SELECT * FROM document_status WHERE...")
   
   # DESPUÉS
   documents = await document_repository.list_by_status(status)
   ```

**Impacto**: 🟡 MEDIO - Reduce acoplamiento a database.py

**Tiempo estimado**: 4-6 horas (muchos call sites)

---

### **FASE 6: API Endpoints** 🟢 BAJA

**Objetivo**: Migrar endpoints a usar repositories

**Prioridad**:
1. 🟡 Upload/Requeue endpoints (core pipeline)
2. 🟢 Dashboard endpoints (read-only, menos crítico)
3. 🟢 Reports endpoints (feature específica, mantener stores)

**Impacto**: 🟢 BAJO - Son entry points, no afectan lógica core

**Tiempo estimado**: 6-8 horas

---

### **FASE 7: Eliminar database.py stores innecesarios** 🟢 BAJA

**Objetivo**: Una vez migrados todos los usos, eliminar stores legacy

**Stores a eliminar**:
- ❌ `DocumentStatusStore` → Reemplazado por `DocumentRepository`
- ❌ `NewsItemStore` → Reemplazado por `NewsItemRepository`
- ⚠️ `ProcessingQueueStore` → Refactorizar como `QueueRepository`

**Stores a mantener** (features específicas):
- ✅ `DailyReportStore` (reports son feature separada)
- ✅ `WeeklyReportStore`
- ✅ `NotificationStore`
- ✅ `NewsItemInsightsStore` (lógica compleja de insights)
- ✅ `DocumentInsightsStore` (legacy pero usado en reports)

**Impacto**: 🟢 BAJO - Limpieza final, no cambia funcionalidad

**Tiempo estimado**: 2-3 horas

---

## 📋 RESUMEN DE PRIORIDADES (ACTUALIZADO)

| Fase | Componente | Prioridad | Tiempo | Impacto |
|------|------------|-----------|--------|---------|
| **5B** | Scheduler queries → repositories | 🔴 CRÍTICA | 3-4h | 🔴 ALTO |
| **5C** | Unificar sistemas workers (eliminar pool) | 🔴 CRÍTICA | 2-3h | 🔴 ALTO |
| **5E** | Migrar DocumentStatusStore usos | 🟡 MEDIA | 4-6h | 🟡 MEDIO |
| **6** | API Endpoints → repositories | 🟢 BAJA | 6-8h | 🟢 BAJO |
| **7** | Eliminar stores legacy | 🟢 BAJA | 2-3h | 🟢 BAJO |

**Total estimado**: 17-24 horas

---

## 🚨 RIESGOS IDENTIFICADOS

1. **⚠️ 2 SISTEMAS DE WORKERS COMPITIENDO**: GenericWorkerPool + schedulers individuales procesan mismas tareas simultáneamente
2. **SQL directo masivo**: 104 `cursor.execute()` - difícil rastrear todos
3. **Coexistencia stores + repositories**: Puede causar inconsistencias
4. **Metadata legacy**: Campos como `processing_stage`, `num_chunks` siguen en DB pero no en entities
5. **GenericWorkerPool NO usa repositories**: Sistema legacy procesa con SQL directo

---

## ✅ RECOMENDACIÓN

**Orden sugerido**:

1. 🔴 **FASE 5C: Unificar workers** (CRÍTICO - eliminar GenericWorkerPool)
2. 🔴 **FASE 5B: Scheduler** (CRÍTICO - corazón del pipeline)
3. 🟡 **FASE 5E: Migrar DocumentStatusStore** (MEDIO - reduce acoplamiento)
4. 🟢 **FASE 6: API Endpoints** (BAJO - son entry points)
5. 🟢 **FASE 7: Cleanup stores** (BAJO - limpieza final)

**Siguiente paso inmediato**: **FASE 5C - Eliminar GenericWorkerPool** (resolver duplicación crítica)

**Alternativa si prefiere scheduler primero**: **FASE 5B - Refactorizar scheduler** (también crítico)

