# REQ-026: Comandos de Testing y Verificación

**Fecha**: 2026-04-08  
**Propósito**: Comandos útiles para verificar que Upload Worker funciona correctamente

---

## 🧪 Testing Manual

### 1. Verificar Estado de Pausa

```bash
# Ver estado de pausa de upload
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/insights-pipeline \
  | jq '.pause_steps[] | select(.id=="upload")'

# Resultado esperado:
# {
#   "id": "upload",
#   "label": "Upload/Ingesta",
#   "paused": false
# }
```

### 2. Pausar Upload

```bash
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pause_steps": {"upload": true}}' \
  http://localhost:8000/api/admin/insights-pipeline

# Verificar que pausó
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/insights-pipeline \
  | jq '.pause_steps[] | select(.id=="upload")'
```

### 3. Intentar Upload con Pausa Activa

```bash
# Debería retornar 503
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf" \
  http://localhost:8000/api/documents/upload

# Resultado esperado:
# {"detail": "Upload is currently paused. Please try again later."}
```

### 4. Reanudar Upload

```bash
curl -X PUT -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pause_steps": {"upload": false}}' \
  http://localhost:8000/api/admin/insights-pipeline
```

### 5. Upload Archivo Válido

```bash
# Upload PDF válido
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@documento.pdf" \
  http://localhost:8000/api/documents/upload

# Resultado esperado:
# {
#   "message": "Document received, queued for validation",
#   "document_id": "abc-123-...",
#   "filename": "documento.pdf",
#   "status": "upload_pending",
#   "size_bytes": 123456,
#   "file_hash": "a7f2b3c4..."
# }
```

### 6. Verificar Archivos en Disco

```bash
# Ver archivos pending
ls -lh app/local-data/uploads/pending_*

# Ver archivos processing
ls -lh app/local-data/uploads/processing_*

# Ver archivos validated (sin prefijo)
ls -lh app/local-data/uploads/ | grep -v "pending_\|processing_\|error_"

# Ver archivos error
ls -lh app/local-data/uploads/error_*
```

### 7. Monitorear Logs de Upload Worker

```bash
# Ver logs en tiempo real
docker logs -f rag-backend 2>&1 | grep -i "upload"

# Buscar validaciones exitosas
docker logs rag-backend 2>&1 | grep "✅ Upload validation completed"

# Buscar errores de validación
docker logs rag-backend 2>&1 | grep "Upload validation failed"
```

### 8. Verificar Estado en Dashboard

```bash
# Ver estadísticas de Upload stage
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/dashboard/analysis \
  | jq '.pipeline.stages[] | select(.name=="Upload")'

# Resultado esperado:
# {
#   "name": "Upload",
#   "pauseKey": "upload",
#   "paused": false,
#   "total_documents": 10,
#   "pending_tasks": 2,
#   "processing_tasks": 1,
#   "completed_tasks": 7,
#   "error_tasks": 0,
#   "paused_tasks": 0,
#   "ready_for_next": 7,
#   "inbox_documents": 0,
#   "blockers": []
# }
```

### 9. Verificar Worker Pool

```bash
# Ver workers activos
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/workers/status \
  | jq '.workers[] | select(.task_type=="upload")'

# Ver queue de upload
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/workers/status \
  | jq '.queues[] | select(.task_type=="upload")'
```

### 10. Testear Upload Archivo Grande

```bash
# Crear archivo de 100MB (debería rechazar si MAX_UPLOAD_SIZE_MB=50)
dd if=/dev/zero of=large.pdf bs=1M count=100

# Intentar upload
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@large.pdf" \
  http://localhost:8000/api/documents/upload

# Resultado esperado:
# {"detail": "File too large: 100.0MB. Maximum allowed: 50MB"}

# Limpiar
rm large.pdf
```

### 11. Testear Upload Formato Inválido

```bash
# Crear archivo .xyz (no soportado)
echo "test" > test.xyz

# Intentar upload
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.xyz" \
  http://localhost:8000/api/documents/upload

# Resultado esperado:
# {"detail": "Format '.xyz' not supported. Supported: ..."}

# Limpiar
rm test.xyz
```

### 12. Testear Retry de Upload Fallido

```bash
# 1. Subir archivo que fallará en validación
# (por ejemplo, PDF corrupto)

# 2. Ver en dashboard que está en error

# 3. Obtener document_id del error
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/dashboard/analysis \
  | jq '.pipeline.stages[] | select(.name=="Upload") | .error_tasks'

# 4. Retry
curl -X POST -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/documents/{DOCUMENT_ID}/requeue

# 5. Verificar que se creó nueva upload task
docker logs rag-backend 2>&1 | grep "Assigned Upload validation task"
```

---

## 🔍 Debugging

### Ver Estado de un Documento

```bash
# Obtener document_id del dashboard o logs
DOCUMENT_ID="abc-123-..."

# Ver estado en DB
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT document_id, filename, status, processing_stage FROM document_status WHERE document_id='$DOCUMENT_ID';"

# Ver stage timing
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT stage, status, started_at, completed_at, metadata FROM document_stage_timing WHERE document_id='$DOCUMENT_ID' ORDER BY started_at;"

# Ver worker tasks
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT id, task_type, status, error_message FROM processing_queue WHERE document_id='$DOCUMENT_ID';"
```

### Ver Processing Queue

```bash
# Ver todas las upload tasks
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT id, document_id, filename, status, priority, created_at FROM processing_queue WHERE task_type='upload' ORDER BY created_at DESC LIMIT 20;"

# Ver pending uploads
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT id, document_id, filename FROM processing_queue WHERE task_type='upload' AND status='pending';"

# Ver processing uploads
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT id, document_id, filename FROM processing_queue WHERE task_type='upload' AND status='processing';"
```

### Ver Worker Tasks

```bash
# Ver upload workers activos
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT worker_id, document_id, task_type, status, started_at FROM worker_tasks WHERE task_type='upload' AND status IN ('assigned', 'started') ORDER BY started_at DESC;"

# Ver upload workers completados recientemente
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT worker_id, document_id, status, error_message, started_at, completed_at FROM worker_tasks WHERE task_type='upload' ORDER BY completed_at DESC LIMIT 10;"
```

---

## 🐛 Troubleshooting

### Problema: Upload task creado pero no procesa

**Debug**:
```bash
# 1. Verificar que upload NO está pausado
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/admin/insights-pipeline \
  | jq '.pause_steps[] | select(.id=="upload")'

# 2. Verificar que hay workers disponibles
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/workers/status \
  | jq '.summary.total_workers, .summary.active_workers'

# 3. Ver logs del scheduler
docker logs rag-backend 2>&1 | grep "Master Pipeline" | tail -20

# 4. Ver si archivo pending existe
ls -lh app/local-data/uploads/pending_*
```

### Problema: Worker falla con "File not found"

**Debug**:
```bash
# 1. Ver estado del archivo
DOCUMENT_ID="abc-123"
ls -lh app/local-data/uploads/ | grep "$DOCUMENT_ID"

# 2. Ver logs del worker
docker logs rag-backend 2>&1 | grep "$DOCUMENT_ID" | tail -20

# 3. Verificar que document_id coincide con filename
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT document_id, filename, status FROM document_status WHERE document_id='$DOCUMENT_ID';"
```

### Problema: Hash mismatch durante validación

**Debug**:
```bash
# 1. Ver error exacto
docker logs rag-backend 2>&1 | grep "Hash mismatch"

# 2. Verificar integridad del archivo
FILE="app/local-data/uploads/processing_abc123_doc.pdf"
sha256sum "$FILE"

# 3. Comparar con hash esperado del filename
# processing_abc123_... → expected hash = abc123...

# 4. Si no coincide, archivo se corrompió durante escritura
# Worker lo marca como error_*
```

### Problema: Worker stuck en processing_*

**Debug**:
```bash
# 1. Ver workers stuck (>10 min)
curl -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/workers/status \
  | jq '.stuck_workers[] | select(.task_type=="upload")'

# 2. Master scheduler debería detectarlos y recuperar
docker logs rag-backend 2>&1 | grep "crashed workers"

# 3. Ver archivos stuck
ls -lh app/local-data/uploads/processing_* | awk '{print $6, $7, $8, $9}'
```

---

## 🎬 Flujo de Testing Completo

### Script de Testing End-to-End

```bash
#!/bin/bash
# test_upload_worker.sh

TOKEN="your_jwt_token"
API_URL="http://localhost:8000"

echo "🧪 Testing REQ-026: Upload Worker Stage"
echo "========================================"

# 1. Verificar estado inicial
echo ""
echo "1. Estado de pausa de upload:"
curl -s -H "Authorization: Bearer $TOKEN" \
  $API_URL/api/admin/insights-pipeline \
  | jq '.pause_steps[] | select(.id=="upload")'

# 2. Upload archivo de test
echo ""
echo "2. Uploading test file..."
RESPONSE=$(curl -s -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf" \
  $API_URL/api/documents/upload)

echo "$RESPONSE" | jq .
DOCUMENT_ID=$(echo "$RESPONSE" | jq -r '.document_id')

echo ""
echo "Document ID: $DOCUMENT_ID"

# 3. Esperar 5 segundos (upload worker procesa)
echo ""
echo "3. Esperando validación (5s)..."
sleep 5

# 4. Ver estado del documento
echo ""
echo "4. Estado del documento:"
curl -s -H "Authorization: Bearer $TOKEN" \
  "$API_URL/api/dashboard/analysis" \
  | jq '.pipeline.stages[] | select(.name=="Upload")'

# 5. Ver archivos en disco
echo ""
echo "5. Archivos en uploads/:"
ls -lh app/local-data/uploads/ | grep "$DOCUMENT_ID" || echo "Archivo ya validated (sin prefijo)"

# 6. Ver logs del worker
echo ""
echo "6. Logs del upload worker:"
docker logs rag-backend 2>&1 | grep "$DOCUMENT_ID" | tail -10

echo ""
echo "✅ Testing completado!"
```

---

## 📊 Métricas de Éxito

### Antes del Testing
- [ ] Upload worker puede procesar archivos
- [ ] Prefijos se aplican correctamente
- [ ] Validaciones funcionan
- [ ] Pause control funciona
- [ ] Estadísticas correctas en dashboard

### Después del Testing
- [ ] ✅ Upload válido → completed
- [ ] ✅ Upload grande → rechazado
- [ ] ✅ Upload inválido → error
- [ ] ✅ Pause → 503
- [ ] ✅ Resume → funciona
- [ ] ✅ Retry → re-procesa
- [ ] ✅ OCR toma validated file

---

## 🎯 Checklist de Verificación

### Backend
- [ ] `TaskType.UPLOAD` existe en `pipeline_states.py`
- [ ] `_upload_worker_task()` definido en `app.py`
- [ ] PASO 0 en scheduler crea upload tasks
- [ ] Upload en worker_pool con 2 workers
- [ ] `("upload", "Upload/Ingesta")` en KNOWN_PAUSE_STEPS
- [ ] Endpoint `/upload` verifica pause state
- [ ] Endpoint `/upload` guarda con prefijo `pending_*`
- [ ] Dashboard API retorna pauseKey para Upload

### Frontend
- [ ] `'Upload': 'upload'` en STAGE_PAUSE_KEY
- [ ] Dashboard muestra botón pause/play para Upload
- [ ] Estadísticas de Upload muestran valores correctos

### Database
- [ ] `document_status` tiene docs con `status=upload_pending`
- [ ] `processing_queue` tiene tasks con `task_type='upload'`
- [ ] `worker_tasks` tiene registros con `task_type='upload'`
- [ ] `document_stage_timing` tiene registros con `stage='upload'`
- [ ] `pipeline_runtime_kv` tiene `pause.upload` key

### Filesystem
- [ ] Archivos con prefijo `pending_*` se crean
- [ ] Archivos transition a `processing_*` cuando worker toma
- [ ] Archivos transition a sin prefijo cuando validated
- [ ] Archivos transition a `error_*` cuando fallan

---

## 🚨 Escenarios de Error

### Error 1: "File not found in pending state"
**Causa**: Archivo no tiene prefijo `pending_*` o document_id no coincide  
**Fix**: Verificar que endpoint `/upload` guardó con prefijo correcto

### Error 2: "Hash mismatch - file corrupted"
**Causa**: Archivo se corrompió durante escritura  
**Fix**: Worker marca como `error_*`, retry permitirá re-upload

### Error 3: "Invalid format"
**Causa**: Extensión no está en ALLOWED_EXTENSIONS  
**Fix**: Worker rechaza, marca como error

### Error 4: "File too large"
**Causa**: Excede MAX_UPLOAD_SIZE_MB  
**Fix**: Worker rechaza, marca como error

### Error 5: "PDF has 0 pages"
**Causa**: PDF corrupto o vacío  
**Fix**: Worker marca como `error_*`, permitir retry

---

## 📈 Monitoreo de Performance

### Métricas a Observar

```bash
# 1. Throughput de upload
# Cuántos uploads/minuto se procesan
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT COUNT(*) FROM document_stage_timing WHERE stage='upload' AND completed_at > NOW() - INTERVAL '1 minute';"

# 2. Tiempo promedio de validación
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_seconds FROM document_stage_timing WHERE stage='upload' AND status='done';"

# 3. Tasa de error
docker exec rag-postgres psql -d newsanalyzer_rag -c \
  "SELECT 
     COUNT(*) FILTER (WHERE status='done') as success,
     COUNT(*) FILTER (WHERE status='error') as errors,
     ROUND(100.0 * COUNT(*) FILTER (WHERE status='error') / COUNT(*), 2) as error_rate_percent
   FROM document_stage_timing 
   WHERE stage='upload';"

# 4. Workers utilization
# ¿Están los 2 workers upload siempre ocupados?
curl -H "Authorization: Bearer $TOKEN" \
  $API_URL/api/workers/status \
  | jq '.workers[] | select(.task_type=="upload") | .status'
```

---

## 🔧 Configuración Recomendada

### Variables de Entorno

```bash
# En app/.env

# Número de workers upload (default: 2)
# Aumentar si hay muchos uploads simultáneos
UPLOAD_PARALLEL_WORKERS=2

# Tamaño máximo de archivo (default: 50MB)
# Ajustar según capacidad de disco
MAX_UPLOAD_SIZE_MB=50

# Total workers del sistema (default: 25)
PIPELINE_WORKERS_COUNT=25
```

### Optimización

**Si uploads son lentos**:
- Aumentar `UPLOAD_PARALLEL_WORKERS` a 4
- Verificar disk I/O no es bottleneck

**Si validación toma mucho tiempo**:
- Considerar skip de readability check para non-PDF
- Optimizar hash computation (usar chunks)

**Si hay muchos errores**:
- Revisar logs: ¿Qué validación falla más?
- Ajustar MAX_UPLOAD_SIZE_MB si archivos legítimos son rechazados

---

## 📝 Notas de Implementación

### Sistema de Prefijos

**Ventajas**:
- Atomic operation (rename en mismo filesystem)
- Visual con `ls`
- No requiere tablas adicionales en DB
- Compatible con código legacy

**Limitaciones**:
- Requiere que `/uploads/` sea en mismo filesystem (no NFS remoto)
- Prefijos visibles en filesystem (no hidden)

### Recovery de Crashes

**Scheduler detecta**:
```python
# Si archivo processing_* > 10 minutos
# → Considera worker crashed
# → Puede revertir a pending_* para retry
```

**Implementación futura** (opcional):
```python
# En scheduler, agregar:
stuck_uploads = list_files_by_state(UPLOAD_DIR, UploadFileState.PROCESSING)
for f in stuck_uploads:
    file_age = time.time() - Path(f).stat().st_mtime
    if file_age > 600:  # 10 minutes
        transition_file_state(UPLOAD_DIR, f, UploadFileState.PENDING)
        logger.warning(f"🔧 Recovered stuck upload file: {f}")
```

---

## ✅ Sign-Off

**Implementación**: ✅ Completada  
**Build**: ✅ Exitoso  
**Deploy**: ✅ Exitoso  
**Testing manual**: ⏳ Pendiente (usuario debe ejecutar)

**Próxima acción**: Ejecutar tests manuales arriba y verificar que Upload worker funciona end-to-end.
