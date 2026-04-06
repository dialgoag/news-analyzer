# 📝 PLAN: REFACTORIZAR INBOX SCAN A EVENT-DRIVEN

**Objetivo**: Hacer que `run_inbox_scan()` siga el patrón event-driven como OCR + Insights.

**Fecha**: 2026-03-03  
**Complejidad**: MEDIA (2-3 horas)  
**Impacto**: ALTO (elimina competencia por Tika, mejora estabilidad)

---

## PROBLEMA ACTUAL

```
run_inbox_scan() (cada 5 min)
  ├─ Escanea inbox/
  ├─ ThreadPoolExecutor.submit(_process_document_sync) x N  ❌ PROBLEMA
  │  └─ OCR INLINE en threads de ThreadPoolExecutor
  │  └─ Usa Tika DIRECTAMENTE (sin semáforo)
  │  └─ Puede saturar Tika simultáneamente con OCR workers
  │  └─ NO respeta MAX_OCR_WORKERS
  └─ Mueve a processed/ cuando termina
```

**Impacto en Tika**:
- Inbox Scan: hasta 4 threads haciendo OCR
- OCR workers: hasta 4 workers haciendo OCR
- **Total posible**: 8 threads en Tika simultáneamente ❌

---

## SOLUCIÓN: EVENT-DRIVEN PATTERN

```
run_inbox_scan() (cada 5 min) - RÁPIDO
  ├─ Escanea inbox/
  ├─ Para cada archivo válido:
  │  ├─ Generar document_id = timestamp_filename
  │  ├─ Copiar a UPLOAD_DIR
  │  ├─ INSERT en processing_queue:
  │  │  └─ (task_id='ocr_{doc_id}', task_type='ocr', document_id=doc_id, status='pending')
  │  ├─ INSERT en document_status:
  │  │  └─ (doc_id, filename, status='queued', source='inbox', news_date=...)
  │  └─ NO llamar _process_document_sync
  └─ Return (scheduler no bloquea)

Resultado en DB:
  - processing_queue tiene N pendientes con task_type='ocr'
  - OCR scheduler ya existente las procesa
  - OCR workers respetan semáforo (máx 4 simultáneos)
```

---

## CAMBIOS NECESARIOS

### 1. Nueva función auxiliar: `_inbox_file_to_queue()`

```python
def _inbox_file_to_queue(path: str, filename: str) -> bool:
    """
    Move inbox file to UPLOAD_DIR and queue for OCR processing.
    Returns document_id if queued, None if duplicate, raises on error.
    """
    try:
        document_id = ingest_from_inbox(
            inbox_path=path,
            filename=filename,
            upload_dir=UPLOAD_DIR,
            processed_dir=PROCESSED_DIR,
        )
        if not document_id:
            return None  # duplicate handled by service

        stage_timing_repository.record_stage_start_sync(
            document_id=document_id,
            stage='upload',
            metadata={'source': 'inbox', 'filename': filename}
        )
        logger.info(f"Inbox: queued {filename} as {document_id}")
        return document_id

    except Exception as e:
        logger.error(f"Inbox queue failed for {filename}: {e}", exc_info=True)
        raise
```

### 2. Refactorizar `run_inbox_scan()`

```python
def run_inbox_scan():
    """
    Scan INBOX_DIR for new files and queue them for OCR processing.
    Does NOT perform OCR inline - lets OCR scheduler handle it.
    """
    if not INBOX_DIR or not os.path.isdir(INBOX_DIR):
        return
    
    processed_dir = os.path.join(INBOX_DIR, "processed")
    os.makedirs(processed_dir, exist_ok=True)
    max_bytes = MAX_UPLOAD_SIZE_MB * 1024 * 1024

    # Find valid files
    files_to_queue = []
    for name in os.listdir(INBOX_DIR):
        if name == "processed":
            continue
        path = os.path.join(INBOX_DIR, name)
        if not os.path.isfile(path):
            continue
        ext = Path(name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            continue
        try:
            if os.path.getsize(path) > max_bytes:
                logger.warning(f"Inbox: skip {name} (>{MAX_UPLOAD_SIZE_MB}MB)")
                continue
        except OSError:
            continue
        files_to_queue.append((path, name))

    if not files_to_queue:
        return

    logger.info(f"Inbox: found {len(files_to_queue)} file(s) to queue")

    queued = 0
    for path, name in files_to_queue:
        document_id = _inbox_file_to_queue(path, name)
        if document_id:
            queued += 1
        # ingest_from_inbox already moves the file into processed_dir (symlink target)
        # so no manual shutil.move is required here.

    logger.info(f"Inbox: queued {queued}/{len(files_to_queue)} files for OCR via file_ingestion_service")
```

### 3. DocumentRepository como única fuente de verdad

- `file_ingestion_service.ingest_from_inbox` crea/actualiza documentos mediante `document_repository.save_sync()` concluyendo en `document_stage_timing`.
- No se expone más `document_status_store.insert`. Toda la metadata (`source`, `status`, `news_date`, hashes) se setea en el `Document` domain object antes de persistirlo.
- Los encolados OCR los realiza `worker_repository.enqueue_task_sync`, por lo que no hay API separada para `processing_queue_store`.

---

## VERIFICACIONES

### Antes de cambiar

1. ✅ OCR pattern está correcto (HECHO)
2. ✅ Insights pattern está correcto (HECHO)
3. ✅ Legacy Insights eliminado (HECHO)
4. ✅ `processing_queue_store.insert()` puede recibir source (VERIFICAR)

### Después de cambiar

1. ⏳ Inbox Scan NO llama OCR inline
2. ⏳ OCR scheduler procesa archivos inbox
3. ⏳ Dashboard muestra documentos "queued" en inbox
4. ⏳ 50 archivos en inbox → OCR workers uno a uno (máx 4 simultáneos)
5. ⏳ Tika NO saturado (máx 4 conexiones)
6. ⏳ Log: sin "too many open connections to Tika"

---

## CAMBIOS A `database.py`

### ProcessingQueueStore.insert()

Verificar que acepte `source`:

```python
def insert(self, task_id: str, task_type: str, document_id: str, 
           filename: str, status: str = "pending", source: str = None):
    """Insert task into queue."""
    # ...
```

### DocumentStatusStore.insert()

Verificar que tenga `source` como parámetro:

```python
def insert(self, document_id: str, filename: str, source: str = "upload", 
           status: str = "processing", ...):
    """Insert document."""
    # ...
```

---

## SCHEDULER CHANGE

**Antes**:
```python
backup_scheduler.add_interval_job(run_inbox_scan, 5*60, "inbox_scan_job", "Inbox folder scan (with OCR)")
```

**Después** (sin cambio en scheduler, pero en la función):
```python
backup_scheduler.add_interval_job(run_inbox_scan, 5*60, "inbox_scan_job", "Inbox folder scan (queue only)")
```

---

## TIMELINE

- **Fase 1**: Verificar que `processing_queue_store.insert()` soporta `source` (30 min)
- **Fase 2**: Implementar `_inbox_file_to_queue()` (45 min)
- **Fase 3**: Refactorizar `run_inbox_scan()` (45 min)
- **Fase 4**: Testear con 50 archivos (60 min)
- **Total**: ~3 horas

---

## TESTING PLAN

1. Compilar backend con cambios
2. Agregar 50 PDFs a `inbox/`
3. Verificar dashboard:
   - Muestra 50 documentos "queued"
   - Inbox files se procesan uno a uno
   - OCR workers máx 4 simultáneos
4. Verificar logs:
   - `Inbox: queued N files for OCR`
   - `[ocr_worker_1] Processing doc_id...`
   - Sin errores de Tika
5. Verificar DB:
   - 50 filas en `processing_queue` con `task_type='ocr'`
   - 50 filas en `document_status` con `source='inbox'`

---

## ROLLBACK PLAN

Si hay problemas:
1. Reverter cambios a `run_inbox_scan()`
2. Restaurar `_process_document_sync()` call
3. Backend ya tiene ThreadPoolExecutor como fallback

---

## NOTAS

- ✅ No elimina `_process_document_sync()` (usado por upload API)
- ✅ Inbox Scan solo cambia para queue en lugar de OCR inline
- ✅ OCR scheduler ya existente maneja el resto
- ✅ Recovery automático si worker crashes (status='started')

---

**Autor**: AI Assistant  
**Próximo Paso**: Revisar `database.py` para confirmar signatures
