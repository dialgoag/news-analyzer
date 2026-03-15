# 📋 AUDITORÍA DE SCHEDULER JOBS Y WORKERS

**Fecha**: 2026-03-03  
**Objetivo**: Verificar que TODOS los scheduler jobs sigan el patrón event-driven con semáforos BD

## RESUMEN EJECUTIVO

| Job | Tipo | Pattern | Workers | Status | Acción |
|-----|------|---------|---------|--------|--------|
| **OCR** | Event-Driven | Semáforos BD ✅ | 4 | **CORRECTO** | ✅ Mantener |
| **Insights (News)** | Event-Driven | Semáforos BD ✅ | 4 | **CORRECTO** | ✅ Mantener |
| **Insights (Legacy)** | Scheduler | Single-threaded ❌ | 0 | **ELIMINADO** | ✅ HECHO |
| **Daily Report** | Scheduler | Inline (1/día) ✅ | 0 | **OK** | ✅ Mantener |
| **Weekly Report** | Scheduler | Inline (1/semana) ✅ | 0 | **OK** | ✅ Mantener |
| **Inbox Scan** | Parallel Pool | ThreadPoolExecutor ⚠️ | 1-4 | **NECESITA FIX** | ⏳ TODO |

---

## 1. ✅ OCR JOB (run_document_ocr_queue_job_parallel)

**Línea**: 1685 en `app.py`  
**Scheduler Interval**: 5 segundos  
**Workers Configurados**: 4 (env: `OCR_PARALLEL_WORKERS`)  

### Arquitectura

```
Scheduler (cada 5s)
  ├─ Revisa semáforo en worker_tasks
  │  └─ SELECT COUNT(*) FROM worker_tasks WHERE status IN ('assigned','started') AND worker_type='OCR'
  ├─ Si active < max_workers:
  │  └─ SELECT ONE pending task from processing_queue WHERE task_type='ocr' AND status='pending'
  ├─ Asigna con assign_worker() → worker_tasks INSERT
  └─ Spawn threading.Thread + asyncio.run(_ocr_worker_task)
     └─ Marca "started", procesa, marca "completed"
```

### Verificación

✅ **Correctas**:
- Semáforo en BD (worker_tasks) previene duplicación
- Dispatcher revisa semaforamente antes de asignar
- Worker async ejecuta en thread separado
- Marca "assigned" → "started" → "completed"
- Retry logic para recuperación de crashes

✅ **Status**: CORRECTO

---

## 2. ✅ INSIGHTS JOB (run_news_item_insights_queue_job_parallel)

**Línea**: 1509 en `app.py`  
**Scheduler Interval**: 2 segundos  
**Workers Configurados**: 4 (env: `INSIGHTS_PARALLEL_WORKERS`)  

### Arquitectura

**Idéntica a OCR**, pero procesa insights por noticia (`news_item_id`).

```
Scheduler (cada 2s)
  ├─ Revisa semáforo en worker_tasks
  ├─ Si active < max_workers:
  │  └─ SELECT ONE pending from processing_queue WHERE task_type='insights'
  ├─ Asigna con assign_worker()
  └─ Spawn threading.Thread + asyncio.run(_insights_worker_task)
```

✅ **Status**: CORRECTO

---

## 3. ❌ INSIGHTS LEGACY (run_insights_queue_job) - **ELIMINADO**

**Línea**: ELIMINADA (era 593 y 1313)  
**Tipo**: Scheduler inline, ejecuta LLM en thread del scheduler  

### Problema

- Procesaba por **documento** (no por noticia)
- **BLOQUEABA** scheduler thread si LLM tardaba
- NO usaba workers
- NO usaba event-driven
- **DUPLICADO** con el nuevo `run_news_item_insights_queue_job_parallel`

### Acción Tomada

✅ Eliminada línea 593 en scheduler init:
```python
# ELIMINADO:
# backup_scheduler.add_interval_job(run_insights_queue_job, 2, "insights_queue_job", ...)
```

✅ **Status**: ELIMINADO

---

## 4. ✅ DAILY REPORT JOB (run_daily_report_job)

**Línea**: 629 en `app.py`  
**Schedule**: Diariamente a las 23:00  
**Workers**: NINGUNO (inlined, pero OK)  

### Arquitectura

```
Scheduler (1 vez/día a las 23:00)
  └─ Genera reporte LLM en thread scheduler (ACEPTABLE por baja frecuencia)
     └─ Ejecuta generate_report_from_context() inline
        └─ Guarda en daily_report_store
```

### Verificación

✅ Frecuencia muy baja (1 vez/día) → no satura scheduler  
✅ No compite con OCR/Insights workers  
✅ Ejecuta LLM inline pero es aceptable  

✅ **Status**: ACEPTABLE - NO CAMBIAR

---

## 5. ✅ WEEKLY REPORT JOB (run_weekly_report_job)

**Línea**: 676 en `app.py`  
**Schedule**: Lunes a las 6:00  
**Workers**: NINGUNO (inlined, pero OK)  

### Arquitectura

Similar a Daily Report, pero generar reporte de 7 días.

✅ Frecuencia muy baja (1 vez/semana) → no satura scheduler  
✅ **Status**: ACEPTABLE - NO CAMBIAR

---

## 6. ⏳ INBOX SCAN JOB (run_inbox_scan) - **NECESITA REFACTORIZACIÓN**

**Línea**: 1872 en `app.py`  
**Scheduler Interval**: 5 minutos  
**Workers**: 1-4 inline (ThreadPoolExecutor)  

### Problema CRÍTICO

```
Scheduler (cada 5 min)
  ├─ Escanea inbox/
  ├─ Crea document_id en BD
  ├─ Copia archivo a UPLOAD_DIR
  └─ Llama _process_document_sync(path, doc_id, name)  ❌ PROBLEMA
     └─ Ejecuta OCR DIRECTAMENTE sin pasar por processing_queue
        └─ USA TIKA INLINE (compite con OCR workers)
        └─ Puede saturar Tika con múltiples threads
        └─ NO respeta semáforo de OCR workers
        └─ NO pasa por event-driven system
```

### Impacto

- ⚠️ Compite con OCR workers por Tika
- ⚠️ Puede saturar Tika simultáneamente
- ⚠️ NO coordina con BD semaphore
- ⚠️ ThreadPoolExecutor inline no respeta límite de workers

### Solución Propuesta

Refactorizar para seguir el patrón event-driven:

```
Scheduler (cada 5 min)
  ├─ Escanea inbox/
  ├─ Para cada archivo válido:
  │  └─ Crea document_id = timestamp_filename
  │  └─ Copia a UPLOAD_DIR
  │  └─ INSERT en processing_queue (task_type='ocr', status='pending')
  │  └─ INSERT en document_status (status='queued')
  │  └─ Mueve a processed/ SOLO cuando estado='completed' en processing_queue
  └─ Return (scheduler no bloquea)

Luego OCR Job ya existente lo procesa normalmente:
  └─ OCR scheduler revisa semáforo
  └─ Asigna worker
  └─ Worker procesa
```

### Ventajas

✅ **Elimina competencia** por Tika  
✅ **Respeta semáforo** de OCR workers  
✅ **Coordina en BD** como el resto  
✅ **Recuperable** si worker crash  
✅ **Escalable** con múltiples workers  
✅ **Consistente** con OCR/Insights pattern  

---

## RESUMEN DE CAMBIOS

### ✅ COMPLETADO ESTA SESIÓN

1. ✅ Eliminado `run_insights_queue_job` del scheduler (línea 593)
   - Legacy job de insights por documento
   - Reemplazado por `run_news_item_insights_queue_job_parallel`
   - Commit: Removed legacy Insights job

### ⏳ TODO EN PRÓXIMA SESIÓN

1. ⏳ Refactorizar `run_inbox_scan` a event-driven
   - Cambiar para que agregue a processing_queue en lugar de OCR inline
   - Remover ThreadPoolExecutor
   - Integrar con semáforo BD
   - Estimar: 2-3 horas

2. ⏳ Testear que Inbox Scan no satura Tika
   - Agregar 50+ archivos a inbox/
   - Verificar dashboard: OCR workers uno a uno
   - Verificar logs: sin "Tika timeout"

---

## VERIFICACIÓN FINAL

### Pattern Event-Driven Correcto

✅ **OCR + Insights siguen el patrón correcto**:

```python
# El patrón correcto es:
1. Scheduler revisa semáforo cada N segundos
2. Si hay espacio: assign_worker() marca "assigned"
3. Spawn async worker en thread separado
4. Worker marca "started"
5. Worker procesa
6. Worker marca "completed"
7. Scheduler verifica en próximo ciclo y asigna siguiente tarea
```

✅ **Ambos implementados correctamente**:
- OCR: cada 5s, máx 4 workers
- Insights: cada 2s, máx 4 workers

### Next Steps

1. Compilar backend (OCR + Insights pattern correcto)
2. Testear: OCR workers procesando uno a uno
3. Refactorizar Inbox Scan
4. Testear: Inbox files procesados sin saturar Tika

---

## NOTAS TÉCNICAS

### Database Semaphore Pattern

```sql
-- Verificar workers activos
SELECT COUNT(*) FROM worker_tasks 
WHERE status IN ('assigned', 'started') 
AND worker_type = 'OCR'
AND updated_at > datetime('now', '-1 minute')

-- Asignar nuevo worker (con validación de no-duplicados)
INSERT INTO worker_tasks (worker_id, worker_type, document_id, task_type, status, assigned_at)
VALUES (?, ?, ?, ?, 'assigned', ?)

-- Worker inicia procesamiento
UPDATE worker_tasks SET status = 'started', started_at = ? WHERE id = ?

-- Worker completa
UPDATE worker_tasks SET status = 'completed', completed_at = ? WHERE id = ?
```

### Event-Driven Benefits

✅ **Recuperación de crashes**: Si worker muere con estado='started', scheduler puede reassignar  
✅ **Escalable**: Agregar más workers = solo cambiar env var  
✅ **Coordinated**: Todos respetan el mismo semáforo BD  
✅ **Observable**: Estado en BD = fácil de debuggear  
✅ **Fair**: No satura servicio externo (Tika, OpenAI)  

---

**Autor**: AI Assistant  
**Conclusión**: Patrón OCR + Insights ✅ CORRECTO. Inbox Scan ⏳ PRÓXIMO.
