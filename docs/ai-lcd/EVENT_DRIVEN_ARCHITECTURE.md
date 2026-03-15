# Event-Driven Architecture con Semáforos en BD

> Plan detallado para unificar OCR, Insights, Indexing bajo un patrón event-driven robusto

**Versión**: 1.0  
**Fecha**: 2026-03-03  
**Estado**: En Implementación

---

## 1. Principios Fundamentales

### 1.1 Problema Original
- **OCR scheduler**: Cada 15s se crea ThreadPoolExecutor → múltiples threads idle
- **Insights scheduler**: Cada 2s se crea ThreadPoolExecutor → saturación
- **Indexing**: Acoplado a _process_document_sync → No es independiente
- **Resultado**: Tika/OpenAI saturados, memoria alta, difícil de debuggear

### 1.2 Solución: Event-Driven + DB Semaphores
```
Scheduler (cada 15s) → Revisa BD: ¿hay slot libre?
                           ↓ SI
                      Get 1 task de queue
                           ↓
                      Create worker_id
                           ↓
                      Mark en worker_tasks
                           ↓
                      Spawn background worker (async)
                           ↓
                      Return inmediatamente
                      
Worker (async, independiente)
  - Lee su worker_id en worker_tasks
  - Si worker cae: worker_id queda marcado
  - Al restart: sistema detecta "started" sin señal de vida → Recupera
```

### 1.3 Ventajas
- ✅ **Sin threads idle**: Solo un worker por slot actual
- ✅ **Escalable**: Cambiar `OCR_PARALLEL_WORKERS=2` → automático
- ✅ **Recuperable**: Worker_id persiste en BD
- ✅ **Debuggeable**: Logs claros con [worker_id]
- ✅ **No conflictos**: Cada worker tiene ID único, no hay race conditions

---

## 2. Arquitectura de Colas (Todo Unificado)

### 2.1 Base de Datos: Tablas Existentes

```sql
-- Queue central: todas las tareas
CREATE TABLE processing_queue (
    id INTEGER PRIMARY KEY,
    document_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    task_type TEXT NOT NULL,          -- 'ocr', 'indexing', 'insights'
    priority INTEGER DEFAULT 0,       -- Mayor = urgente
    created_at TEXT NOT NULL,
    processed_at TEXT,
    status TEXT NOT NULL              -- 'pending', 'processing', 'completed', 'failed'
);

-- Semáforo: cuántos workers activos
CREATE TABLE worker_tasks (
    id INTEGER PRIMARY KEY,
    worker_id TEXT NOT NULL,          -- "ocr_12345_67890"
    worker_type TEXT NOT NULL,        -- 'OCR', 'Insights', 'Indexing'
    document_id TEXT NOT NULL,
    task_type TEXT NOT NULL,
    status TEXT NOT NULL,             -- 'assigned', 'started', 'completed', 'error'
    assigned_at TEXT NOT NULL,
    started_at TEXT,                  -- NULL hasta que realmente inicia
    completed_at TEXT,
    error_message TEXT
);
```

### 2.2 Task Types (Unificados)

| Task Type | Queue | Max Workers | Interval | Backend |
|-----------|-------|-------------|----------|---------|
| `ocr` | processing_queue | 2 (configurable) | 15s | Tika/PyMuPDF |
| `indexing` | processing_queue | 4 (configurable) | 5s | Qdrant |
| `insights` | processing_queue | 4 (configurable) | 2s | OpenAI |

---

## 3. Patrones de Implementación

### 3.1 Patrón Scheduler (Genérico)

```python
def run_{task_type}_queue_job():
    """
    Scheduler job: checks semaphore, dispatches ONE worker if slot available.
    """
    if not services_ready:
        return
    
    try:
        max_workers = get_config(f"{TASK_TYPE}_PARALLEL_WORKERS")
        
        # Check semaphore
        active = count_active_workers(task_type)
        if active >= max_workers:
            return  # No slot available
        
        # Get pending task
        task = get_pending_task(task_type)
        if not task:
            return  # No pending tasks
        
        # Create worker
        worker_id = f"{task_type}_{pid}_{timestamp}"
        assign_worker(worker_id, task)
        
        # Spawn background worker
        asyncio.create_task(
            _worker_task(task_type, worker_id, task)
        )
        
    except Exception as e:
        logger.error(f"{task_type} scheduler error: {e}")
```

### 3.2 Patrón Worker (Genérico)

```python
async def _worker_task(task_type: str, worker_id: str, task: dict):
    """
    Background worker: processes ONE task independently.
    """
    try:
        # Mark started
        update_worker_status(worker_id, 'started')
        
        # Process (specific logic per task_type)
        result = await process_task(task_type, task, worker_id)
        
        # Mark completed
        update_worker_status(worker_id, 'completed')
        mark_task_completed(task)
        
    except Exception as e:
        logger.error(f"[{worker_id}] Error: {e}")
        update_worker_status(worker_id, 'error', str(e))
        mark_task_failed(task)
```

---

## 4. Implementación por Task Type

### 4.1 OCR (Ya Refactorizado)

✅ **Status**: COMPLETADO

- Scheduler: `run_document_ocr_queue_job_parallel()` (cada 15s)
- Worker: `_ocr_worker_task()` (async, background)
- Max workers: 2 (configurable via `OCR_PARALLEL_WORKERS`)
- Queue: processing_queue con task_type='ocr'

### 4.2 Insights (Por Refactorizar)

**Cambios necesarios**:

1. Cambiar de `news_item_insights_store.get_next_pending()` a `processing_queue`
2. Crear task_type='insights' en queue al generar insights
3. Refactorizar scheduler a solo 1 worker dispatch
4. Crear `_insights_worker_task()` async

```python
# ANTES: ThreadPoolExecutor de 4 workers
def run_news_item_insights_queue_job_parallel():
    pending = news_item_insights_store.get_next_pending(limit=4)
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(process_single_item, row) for row in pending]
        # ...

# DESPUÉS: Solo 1 dispatch, worker independiente
def run_news_item_insights_queue_job_parallel():
    active = count_active_workers('insights')  # From worker_tasks
    if active >= 4:
        return
    
    task = get_pending_task('insights')
    if not task:
        return
    
    worker_id = f"insights_{pid}_{timestamp}"
    assign_worker(worker_id, task)
    asyncio.create_task(_insights_worker_task(worker_id, task))
```

### 4.3 Indexing (Por Crear)

**Cambios necesarios**:

1. Extraer lógica de indexing de `_process_document_sync()`
2. Crear endpoint `/api/documents/{id}/index` para solicitar
3. Crear task_type='indexing' en queue
4. Crear scheduler + worker independientes

```python
# Después de OCR, documentos quedan con status='processing'
# En lugar de indexar INMEDIATAMENTE, agregamos tarea a queue:

def enqueue_indexing_task(document_id: str, filename: str):
    processing_queue_store.enqueue_task(
        document_id, filename, 'indexing', priority=0
    )

# Scheduler (cada 5s) dispara 1 worker si hay slot
def run_document_indexing_queue_job():
    # Same pattern: check semaphore, dispatch 1 worker

# Worker procesa: chunking + embedding + Qdrant insert
async def _indexing_worker_task(worker_id: str, task: dict):
    # Chunking + embedding + Qdrant upsert
```

---

## 5. Recovery & Resilience

### 5.1 Crash Detection

```python
def detect_crashed_workers():
    """
    Run at startup or periodically:
    - Find workers with status='started' pero older than 5 minutes
    - Assume crashed, re-enqueue task, clear worker_id
    """
    conn = get_connection()
    cursor = conn.cursor()
    
    # Workers que empezaron hace más de 5 min
    cursor.execute("""
        SELECT * FROM worker_tasks
        WHERE status = 'started'
        AND datetime(started_at) < datetime('now', '-5 minutes')
    """)
    
    crashed = cursor.fetchall()
    for worker in crashed:
        logger.warning(f"Detected crashed worker: {worker['worker_id']}")
        
        # Re-enqueue
        processing_queue_store.enqueue_task(
            worker['document_id'],
            worker['filename'],
            worker['task_type'],
            priority=10  # Boost priority
        )
        
        # Clear worker
        cursor.execute(
            "DELETE FROM worker_tasks WHERE worker_id = ?",
            (worker['worker_id'],)
        )
    
    conn.commit()
    conn.close()
```

### 5.2 Startup Recovery

```python
# In app startup
async def startup_event():
    # ... existing code ...
    
    # Detect and recover crashed workers
    detect_crashed_workers()
    
    logger.info("✅ System ready with event-driven architecture")
```

---

## 6. Timeline de Implementación

### Fase 1: OCR (COMPLETADA)
- ✅ Refactorizar OCR a event-driven
- ✅ Crear `_ocr_worker_task()` async
- ✅ Cambiar scheduler a single dispatch

### Fase 2: Insights (HOY)
- ⏳ Refactorizar insights a event-driven
- ⏳ Cambiar de `get_next_pending()` a `processing_queue`
- ⏳ Crear `_insights_worker_task()` async

### Fase 3: Indexing (HOY)
- ⏳ Extraer lógica de indexing
- ⏳ Crear scheduler + worker para indexing
- ⏳ Crear task_type='indexing' en queue

### Fase 4: Testing & Recovery
- ⏳ Test: spawn múltiples workers, verificar semáforo
- ⏳ Test: crash un worker, verificar recuperación
- ⏳ Test: escalabilidad con mucha carga

### Fase 5: Documentación & Monitoring
- ⏳ Actualizar STATUS_AND_HISTORY.md
- ⏳ Agregar métricas: workers activos, tasks pending, % utilización
- ⏳ Dashboard: mostrar estado de workers en tiempo real

---

## 7. Métricas & Monitoreo

### 7.1 Métricas a Trackear

```python
class WorkerMetrics:
    total_tasks_assigned: int
    total_tasks_completed: int
    total_tasks_failed: int
    total_crashed_workers: int
    current_active_workers: int
    avg_task_duration: float
    peak_concurrent_workers: int
    
    # Por task_type
    ocr_tasks: int
    insights_tasks: int
    indexing_tasks: int
```

### 7.2 Alertas

- `active_workers > max_workers` → Bug (nunca debería pasar)
- `crashed_workers > 5` → Problema sistémico
- `tasks_failed > 10%` → Investigar errores
- `task_duration > 10x normal` → Tika/OpenAI lento

---

## 8. Referencias

| Documento | Sección |
|-----------|---------|
| STATUS_AND_HISTORY.md | §2.5 - Paralelización OCR (baseline) |
| PLAN_AND_NEXT_STEP.md | §6 - Pasos inmediatos |
| database.py | worker_tasks, processing_queue |
| app.py | run_*_queue_job_parallel(), _*_worker_task() |

---

## 9. Checklist de Implementación

### OCR ✅
- [x] Refactorizar a event-driven
- [x] Crear worker_id único
- [x] Async worker task
- [x] DB semaphore

### Insights
- [ ] Cambiar a processing_queue
- [ ] Refactorizar scheduler
- [ ] Crear _insights_worker_task async
- [ ] Test con 4 workers

### Indexing
- [ ] Extraer lógica de _process_document_sync
- [ ] Crear scheduler + worker
- [ ] Agregar task_type='indexing'
- [ ] Test independiente

### Recovery
- [ ] detect_crashed_workers() en startup
- [ ] Timeout detection (5 min)
- [ ] Re-enqueue con boost priority
- [ ] Test: crash worker → restart → recupera

### Monitoring
- [ ] Métricas en /api/workers/status
- [ ] Dashboard: workers activos por tipo
- [ ] Alertas en logs
- [ ] Documentación actualizada

---

**Status**: 🟡 EN CONSTRUCCIÓN  
**Próximo paso**: Implementar Insights event-driven
