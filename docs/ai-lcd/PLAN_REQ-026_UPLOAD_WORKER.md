# REQ-026: Upload como Worker Stage Completo

**Fecha**: 2026-04-08  
**Autor**: AI Assistant  
**Estado**: 📋 PLANIFICADO (no ejecutado)

## 🎯 Objetivo

Transformar Upload en una **etapa completa del pipeline** con worker asíncrono, pausable, con estadísticas y manejo de errores, igual que OCR, Segmentation, Chunking, etc.

## ❌ Problema Actual

Upload es **síncrono** dentro del HTTP request:
```
POST /upload → guarda archivo → crea DB record → responde 202
              ↓ (background task blocking)
              _process_document_sync (hace TODO: OCR+Seg+Chunk+Index...)
```

**Limitaciones**:
- ❌ No hay worker pool para upload
- ❌ No se puede pausar
- ❌ Estadísticas incorrectas (completed_tasks=0)
- ❌ No hay retry mechanism
- ❌ No hay observabilidad de sub-etapas
- ❌ Bloquea HTTP request durante guardado

## ✅ Solución Propuesta

### **Sistema de Prefijos para Estados**

**Convención de nombres** (todos en `/uploads/`):
```
pending_{hash}_{filename}.pdf       → Uploaded, awaiting validation
processing_{hash}_{filename}.pdf    → Worker validating
{hash}_{filename}.pdf               → Validated, ready for OCR
error_{hash}_{filename}.pdf         → Failed validation (debug)
```

**Flujo**:
1. POST `/upload` → Guarda como `pending_{hash}_{filename}`
2. Upload worker → Rename a `processing_{hash}_{filename}`
3. Worker valida → Rename a `{hash}_{filename}` (SIN prefijo = done)
4. Si falla → Rename a `error_{hash}_{filename}`

**Ventajas**:
- ✅ Todo en mismo directorio
- ✅ Operación atomic (rename)
- ✅ Visual (`ls` muestra estado)
- ✅ Compatible con código existente
- ✅ Recuperación de crashes (detectar `processing_*` stuck)

---

## 📐 Arquitectura

### **FASE 1: Backend Core**

#### 1.1. Upload Utils (✅ HECHO)
- ✅ Archivo: `upload_utils.py`
- ✅ Functions: `build_upload_filename()`, `parse_upload_filename()`, `transition_file_state()`
- ✅ Helpers: `list_files_by_state()`, `cleanup_error_files()`

#### 1.2. TaskType.UPLOAD
**Archivo**: `pipeline_states.py`
```python
class TaskType:
    UPLOAD = "upload"        # ← NUEVO
    OCR = "ocr"
    SEGMENTATION = "segmentation"
    CHUNKING = "chunking"
    INDEXING = "indexing"
    INSIGHTS = "insights"
    INDEXING_INSIGHTS = "indexing_insights"
    
    ALL = [UPLOAD, OCR, SEGMENTATION, ...]  # ← Agregar UPLOAD
```

#### 1.3. Upload Worker Function
**Archivo**: `app.py` (nuevo)
```python
async def _upload_worker_task(document_id: str, filename: str, worker_id: str):
    """
    Worker: Validar archivo + Verificar integridad + Transition to validated
    
    Sub-etapas:
    1. Transition: pending → processing
    2. Validar formato (extension check)
    3. Validar tamaño (MAX_UPLOAD_SIZE_MB)
    4. Re-compute hash (integrity check)
    5. Verificar legibilidad (file not corrupted)
    6. Transition: processing → validated (sin prefijo)
    7. Record stage timing
    
    Si falla:
    - Transition: processing → error
    - Mark document status=error, processing_stage=upload
    - Log error details
    """
    try:
        # 1. RECORD STAGE START
        stage_timing_repository.record_stage_start_sync(
            document_id, 'upload',
            metadata={'worker_id': worker_id, 'filename': filename}
        )
        
        # 2. Mark as started
        worker_repository.update_worker_status_sync(
            worker_id, document_id, TaskType.UPLOAD, WorkerStatus.STARTED
        )
        
        # 3. Get current file path (pending_*)
        pending_files = list_files_by_state(UPLOAD_DIR, UploadFileState.PENDING)
        current_file = next((f for f in pending_files if document_id in f), None)
        
        if not current_file:
            raise ValueError(f"File not found in pending state: {document_id}")
        
        # 4. Transition: pending → processing
        current_file = transition_file_state(
            UPLOAD_DIR, current_file, UploadFileState.PROCESSING
        )
        
        # 5. Validate file
        file_path = Path(UPLOAD_DIR) / current_file
        
        # 5a. Format validation
        ext = file_path.suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Invalid format: {ext}")
        
        # 5b. Size validation
        file_size_mb = file_path.stat().st_size / (1024 * 1024)
        if file_size_mb > MAX_UPLOAD_SIZE_MB:
            raise ValueError(f"File too large: {file_size_mb:.1f}MB")
        
        # 5c. Integrity check (re-compute hash)
        with open(file_path, 'rb') as f:
            content = f.read()
        actual_hash = hashlib.sha256(content).hexdigest()
        
        _, expected_hash, _ = parse_upload_filename(current_file)
        if not actual_hash.startswith(expected_hash):
            raise ValueError("Hash mismatch - file corrupted")
        
        # 5d. Readability check (try to open with appropriate tool)
        # For PDFs: try PyMuPDF
        if ext == '.pdf':
            import fitz
            doc = fitz.open(file_path)
            if doc.page_count == 0:
                raise ValueError("PDF has 0 pages")
            doc.close()
        
        # 6. Transition: processing → validated (no prefix)
        validated_file = transition_file_state(
            UPLOAD_DIR, current_file, UploadFileState.VALIDATED
        )
        
        # 7. Update document status
        doc_id = DocumentId(document_id)
        await document_repository.update_status(
            doc_id,
            PipelineStatus.create(StageEnum.UPLOAD, StateEnum.DONE),
            processing_stage=Stage.UPLOAD
        )
        
        # 8. RECORD STAGE END
        stage_timing_repository.record_stage_end_sync(
            document_id, 'upload', 'done',
            metadata={
                'file_size_mb': file_size_mb,
                'validated_file': validated_file
            }
        )
        
        # 9. Mark completed
        worker_repository.update_worker_status_sync(
            worker_id, document_id, TaskType.UPLOAD, WorkerStatus.COMPLETED
        )
        worker_repository.mark_task_completed_sync(document_id, TaskType.UPLOAD)
        
        logger.info(f"[{worker_id}] ✅ Upload validation completed: {validated_file}")
        
    except Exception as e:
        logger.error(f"[{worker_id}] Upload validation failed: {e}", exc_info=True)
        
        try:
            # Transition: processing → error
            if current_file:
                error_file = transition_file_state(
                    UPLOAD_DIR, current_file, UploadFileState.ERROR
                )
                logger.info(f"[{worker_id}] Moved to error state: {error_file}")
            
            # Record error
            err_msg = str(e)[:200]
            stage_timing_repository.record_stage_end_sync(
                document_id, 'upload', 'error', error_message=err_msg
            )
            
            error_status = PipelineStatus.terminal(TerminalStateEnum.ERROR)
            doc_id = DocumentId(document_id)
            await document_repository.update_status(
                doc_id, error_status,
                error_message=err_msg,
                processing_stage=Stage.UPLOAD
            )
            
            worker_repository.update_worker_status_sync(
                worker_id, document_id, TaskType.UPLOAD, WorkerStatus.ERROR,
                error_message=err_msg
            )
            worker_repository.mark_task_completed_sync(document_id, TaskType.UPLOAD)
            
        except Exception as e2:
            logger.error(f"[{worker_id}] Failed to mark upload error: {e2}")
```

#### 1.4. Master Scheduler Update
**Archivo**: `app.py` → `master_pipeline_scheduler()`

**Agregar PASO 0 (antes de OCR)**:
```python
# PASO 0: Documentos upload_pending sin Upload task → Crear Upload tasks
ready_for_upload_validation = []
for row in document_repository.list_all_sync(limit=None, status=DocStatus.UPLOAD_PENDING):
    doc_id = row["document_id"]
    filename = row.get("filename") or f"{doc_id}.pdf"
    
    # Skip if already in queue
    if worker_repository.has_queue_task_sync(doc_id, TaskType.UPLOAD):
        continue
    
    ready_for_upload_validation.append((doc_id, filename))
    
    if len(ready_for_upload_validation) >= 50:
        break

if ready_for_upload_validation:
    for doc_id, filename in ready_for_upload_validation:
        worker_repository.enqueue_task_sync(doc_id, filename, TaskType.UPLOAD, priority=0)
    logger.info(f"✅ Created {len(ready_for_upload_validation)} Upload validation tasks")
```

**Modificar PASO 1 (OCR)**:
```python
# PASO 1: Documentos upload_done sin OCR task → Crear OCR tasks
# (ya existe, sin cambios)
```

**Agregar Upload al worker pool**:
```python
worker_pool = {
    TaskType.UPLOAD: max(1, min(2, TOTAL_WORKERS)),       # ← NUEVO: 2 upload workers
    TaskType.OCR: max(1, min(5, TOTAL_WORKERS)),
    TaskType.SEGMENTATION: max(1, min(2, TOTAL_WORKERS)),
    ...
}

worker_tasks = {
    TaskType.UPLOAD: lambda: asyncio.run(_upload_worker_task(doc_id, filename, worker_id)),  # ← NUEVO
    TaskType.OCR: lambda: asyncio.run(_ocr_worker_task(doc_id, filename, worker_id)),
    ...
}
```

#### 1.5. Pause Control
**Archivo**: `pipeline_runtime_store.py`
```python
KNOWN_PAUSE_STEPS: List[Tuple[str, str]] = [
    ("upload", "Upload/Ingesta"),               # ← NUEVO
    ("ocr", "OCR"),
    ("segmentation", "Segmentación (LLM)"),
    ("chunking", "Chunking"),
    ("indexing", "Indexado documentos (vectores)"),
    ("insights", "Insights (LLM)"),
    ("indexing_insights", "Indexado insights en Qdrant"),
]
```

**Verificar pause en scheduler**:
```python
import insights_pipeline_control as _ipc

# En PASO 0 (Upload)
if _ipc.is_step_paused("upload"):
    logger.debug("⏸️  Upload paused, skipping upload task creation")
    # No crear upload tasks
else:
    # Crear upload tasks (código ya mostrado)
```

#### 1.6. Endpoint `/upload` Refactor
**Archivo**: `adapters/driving/api/v1/routers/documents.py`

```python
@router.post("/upload")
async def upload_document(
    file: UploadFile = File(...),
    current_user: CurrentUser = Depends(require_upload_permission)
):
    """
    Upload a document - saves with 'pending_' prefix for worker validation.
    
    New flow:
    1. Receive file
    2. Compute hash
    3. Check duplicate
    4. Save as pending_{hash}_{filename}
    5. Create DB record: status=upload_pending
    6. Upload worker will validate and transition to validated state
    """
    import app as app_module
    from upload_utils import build_upload_filename, UploadFileState
    
    # Check if upload is paused
    import insights_pipeline_control as _ipc
    if _ipc.is_step_paused("upload"):
        raise HTTPException(
            status_code=503,
            detail="Upload is currently paused. Please try again later."
        )
    
    # ... (validación formato/tamaño igual que antes)
    
    try:
        # Compute hash
        content = await file.read()
        file_hash = compute_sha256(data=content)
        
        # Check duplicate
        existing = check_duplicate(file_hash)
        if existing:
            logger.info(f"📋 Duplicate: '{file.filename}' exists as '{existing['filename']}'")
            return JSONResponse(
                status_code=200,
                content={
                    "message": "Duplicate file detected",
                    "status": "duplicate",
                    "existing_document_id": existing['document_id'],
                    "existing_filename": existing['filename']
                }
            )
        
        # Generate document_id
        document_id = str(uuid.uuid4())
        upload_dir = _upload_dir()
        
        # Build filename with PENDING prefix
        pending_filename = build_upload_filename(
            UploadFileState.PENDING,
            file_hash[:16],  # Usar primeros 16 chars del hash
            file.filename
        )
        
        file_path = Path(upload_dir) / pending_filename
        
        # Save file with pending prefix
        with open(file_path, 'wb') as f:
            f.write(content)
        
        logger.info(f"📄 File saved (pending validation): {pending_filename}")
        
        # Create DB record: status=upload_pending
        doc_id = DocumentId(document_id)
        await document_repository.create(
            doc_id=doc_id,
            filename=file.filename,
            status=PipelineStatus.create(StageEnum.UPLOAD, StateEnum.PENDING),
            file_hash=file_hash,
            processing_stage=Stage.UPLOAD,
            metadata={
                'size_bytes': len(content),
                'original_filename': file.filename,
                'pending_file': pending_filename
            }
        )
        
        # Record stage timing (upload received)
        stage_timing_repository.record_stage_start_sync(
            document_id, 'upload',
            metadata={'pending_file': pending_filename, 'size_bytes': len(content)}
        )
        
        return JSONResponse(
            status_code=202,
            content={
                "message": "Document received, queued for validation",
                "document_id": document_id,
                "filename": file.filename,
                "status": "upload_pending",
                "size_bytes": len(content)
            }
        )
        
    except Exception as e:
        logger.error(f"❌ Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

### **FASE 2: Frontend Integration**

#### 2.1. Dashboard Data Hook
**Archivo**: `app/frontend/src/hooks/useDashboardData.jsx`

```javascript
const STAGE_PAUSE_KEY = {
  'Upload': 'upload',          // ← NUEVO
  'OCR': 'ocr',
  'Segmentation': 'segmentation',
  'Chunking': 'chunking',
  'Indexing': 'indexing',
  'Insights': 'insights',
  'Indexing Insights': 'indexing_insights'
};
```

#### 2.2. Dashboard Backend
**Archivo**: `adapters/driven/persistence/postgres/dashboard_read_repository_impl.py`

Upload stage ya existe (líneas 336-349), solo necesita agregar `pauseKey`:

```python
stages.append(
    {
        "name": "Upload",
        "pauseKey": "upload",                           # ← NUEVO
        "paused": pause_states.get("upload", False),   # ← NUEVO
        "total_documents": upload_pending + upload_processing + upload_completed + ...,
        "pending_tasks": upload_pending,
        "processing_tasks": upload_processing,
        "completed_tasks": upload_completed,
        "error_tasks": upload_errors,  # ← Cambiar de ocr_errors
        "paused_tasks": upload_paused,
        "ready_for_next": upload_completed,
        "inbox_documents": inbox_count,
        "blockers": [],
    }
)
```

**Fix estadísticas** (ya implementado en Fix #156):
```python
# Count ALL documents that passed upload (not in pending/processing)
cursor.execute(
    """
    SELECT COUNT(*) as total FROM document_status
    WHERE status NOT IN (%s, %s)
    """,
    (DocStatus.UPLOAD_PENDING, DocStatus.UPLOAD_PROCESSING)
)
upload_completed = cursor.fetchone()["total"] or 0
```

---

### **FASE 3: Database Schema**

#### 3.1. Stage Enum (ya existe)
- ✅ `Stage.UPLOAD` ya definido en `pipeline_states.py`

#### 3.2. Estados (ya existen)
- ✅ `upload_pending`
- ✅ `upload_processing`
- ✅ `upload_done`

#### 3.3. Stage Timing (ya existe)
- ✅ `document_stage_timing` ya soporta `stage='upload'`

#### 3.4. Migration (NO necesaria)
- ✅ Todo el schema necesario ya existe

---

### **FASE 4: Error Handling & Retry**

#### 4.1. Error Types
```python
class UploadError:
    INVALID_FORMAT = "invalid_format"
    FILE_TOO_LARGE = "file_too_large"
    DUPLICATE_HASH = "duplicate_hash"
    DISK_FULL = "disk_full"
    CORRUPTION = "file_corrupted"
    UNREADABLE = "file_unreadable"
```

#### 4.2. Retry Mechanism
**Endpoint existente** `/documents/{doc_id}/requeue` ya funciona:
```python
# Si status=error y processing_stage=upload:
# → Crea nueva upload task
# → Worker reintenta validación
```

#### 4.3. Error File Cleanup
**Agregar a scheduler** (ejecutar cada 6 horas):
```python
# En master_pipeline_scheduler(), agregar:
if iteration_count % 360 == 0:  # Cada 6h (si cycle=60s)
    from upload_utils import cleanup_error_files
    deleted = cleanup_error_files(UPLOAD_DIR, max_age_hours=24)
    if deleted:
        logger.info(f"🧹 Cleaned {deleted} error upload files (>24h old)")
```

---

### **FASE 5: Testing & Validation**

#### 5.1. Unit Tests (nuevo archivo `test_upload_worker.py`)
```python
def test_upload_filename_building():
    filename = build_upload_filename(UploadFileState.PENDING, "abc123", "doc.pdf")
    assert filename == "pending_abc123_doc.pdf"

def test_upload_filename_parsing():
    prefix, hash, name = parse_upload_filename("pending_abc123_doc.pdf")
    assert prefix == "pending_"
    assert hash == "abc123"
    assert name == "doc.pdf"

def test_upload_state_transition():
    # Test que rename funciona correctamente
    pass

def test_upload_worker_validation():
    # Test worker con archivo válido
    pass

def test_upload_worker_invalid_format():
    # Test worker con formato inválido
    pass

def test_upload_worker_corrupted_file():
    # Test worker con hash mismatch
    pass
```

#### 5.2. Integration Tests
1. Upload → Validación → OCR (flujo completo)
2. Upload → Error → Retry → Success
3. Pause upload → Intentar upload → Rechazado 503
4. Resume upload → Upload exitoso

#### 5.3. Manual Testing Checklist
- [ ] Upload archivo válido → Ver en dashboard pending → processing → done
- [ ] Upload archivo grande → Rechazado con error
- [ ] Upload formato inválido → Error en worker
- [ ] Pausar upload → Intentar upload → 503
- [ ] Reanudar upload → Upload funciona
- [ ] Verificar estadísticas correctas en dashboard
- [ ] Retry de upload fallido

---

## 📊 Métricas de Éxito

### Antes (Actual)
- Upload síncrono en HTTP request
- No pausable
- completed_tasks = 0 (incorrecto)
- No retry
- No observabilidad

### Después (Objetivo)
- ✅ Upload asíncrono con worker pool
- ✅ Pausable desde dashboard
- ✅ Estadísticas correctas (pending/processing/completed)
- ✅ Retry automático de errores
- ✅ Sub-etapas observables (validation, integrity check)
- ✅ Control de pauseKey en dashboard
- ✅ Manejo robusto de errores

---

## ⚠️ Riesgos y Mitigaciones

### Riesgo 1: Race Condition en Rename
**Mitigación**: `Path.rename()` es operación atómica en sistemas POSIX

### Riesgo 2: Worker Crash Mid-Validation
**Mitigación**: 
- Archivo queda en estado `processing_*`
- Scheduler detecta workers stuck (>10min)
- Revierte a `pending_*` para retry

### Riesgo 3: Archivos Existentes Sin Prefijo
**Mitigación**:
- Código existente sigue funcionando (busca `{hash}_{filename}`)
- Nuevos uploads usan prefijo
- Migration opcional para agregar prefijo a existentes

### Riesgo 4: Disk Space
**Mitigación**:
- Worker valida espacio disponible antes de procesar
- Cleanup automático de archivos `error_*` viejos

---

## 🚀 Plan de Despliegue

### Orden de Implementación
1. ✅ **FASE 0**: Upload utils (`upload_utils.py`) → HECHO
2. **FASE 1**: Backend core (TaskType, worker, scheduler, pause)
3. **FASE 2**: Frontend (STAGE_PAUSE_KEY, dashboard)
4. **FASE 3**: Testing (unit + integration)
5. **FASE 4**: Deploy + monitoreo

### Rollback Plan
Si algo falla:
1. Revertir cambios en `/upload` endpoint (volver a síncrono)
2. Remover `TaskType.UPLOAD` de scheduler
3. Archivos `pending_*` existentes se pueden procesar manualmente

---

## 📝 Documentación Pendiente

Después de implementar, actualizar:
- [ ] `CONSOLIDATED_STATUS.md` con Fix #157
- [ ] `SESSION_LOG.md` con decisiones
- [ ] `REQUESTS_REGISTRY.md` con REQ-026
- [ ] `PLAN_AND_NEXT_STEP.md` con progreso
- [ ] README backend con nueva arquitectura upload

---

## ✅ Aprobación

**Usuario**: Aprobó Opción C con prefijos  
**Próximo paso**: Ejecutar implementación en orden:
1. Backend core (TaskType + Worker + Scheduler)
2. Frontend integration
3. Testing

**Estimación**: ~4-6 horas implementación + 2h testing
