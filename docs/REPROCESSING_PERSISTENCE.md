# 🔄 Sistema de Reprocesamiento Persistente

## Fecha: 2026-03-05
## Versión: 2.1 - Reprocesamiento con persistencia

---

## 📋 Resumen de la Mejora

Se ha agregado **persistencia de solicitudes de reprocesamiento** para que los documentos marcados no se pierdan al reiniciar la aplicación.

---

## ✨ Características Nuevas

### 1. Flag Persistente en Base de Datos

Se agregó la columna `reprocess_requested` en la tabla `document_status`:

```sql
ALTER TABLE document_status ADD COLUMN reprocess_requested INTEGER DEFAULT 0
CREATE INDEX idx_document_status_reprocess ON document_status(reprocess_requested)
```

### 2. Master Scheduler Integrado

El Master Pipeline Scheduler ahora:
- ✅ Verifica documentos marcados para reprocesamiento cada 10 segundos
- ✅ Los agrega a la cola si no están ya procesándose
- ✅ Los desmarca automáticamente al completar el indexing
- ✅ Persiste el estado incluso si la app se reinicia

### 3. Flujo Completo

```
Usuario Click "🔄 Requeue"
    ↓
Endpoint /api/documents/{id}/requeue
    ↓
- Marca: reprocess_requested = 1
- Reset status: "processing:ocr"
- Clear ocr_text
- Enqueue task OCR
    ↓
Master Scheduler (cada 10s)
    ↓
- Detecta: reprocess_requested = 1
- Verifica si ya está en cola
- Si no → Enqueue task OCR (priority=10)
    ↓
Workers procesan: OCR → Chunking → Indexing
    ↓
Al completar Indexing
    ↓
Desmarca: reprocess_requested = 0
```

---

## 🔧 Implementación Técnica

### Migración: `014_add_reprocess_flag.py`

```python
"""
Migration 014: Add reprocess_requested column to document_status

Domain: Document Processing
Description: Add flag to persist reprocessing requests across app restarts
Depends on: 002_document_status_schema
"""

from yoyo import step

steps = [
    step(
        """
        ALTER TABLE document_status ADD COLUMN reprocess_requested INTEGER DEFAULT 0
        """,
        """
        ALTER TABLE document_status DROP COLUMN reprocess_requested
        """
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_document_status_reprocess ON document_status(reprocess_requested)",
        "DROP INDEX IF EXISTS idx_document_status_reprocess"
    ),
]
```

### Métodos en `database.py`

#### `mark_for_reprocessing(document_id, requested=True)`
```python
def mark_for_reprocessing(self, document_id: str, requested: bool = True) -> bool:
    """Mark a document for reprocessing (persists across app restarts)."""
    conn = self.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "UPDATE document_status SET reprocess_requested = ? WHERE document_id = ?",
            (1 if requested else 0, document_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
```

#### `get_documents_pending_reprocess()`
```python
def get_documents_pending_reprocess(self) -> List[Dict]:
    """Get all documents marked for reprocessing."""
    conn = self.get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM document_status WHERE reprocess_requested = 1 ORDER BY ingested_at DESC"
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()
```

### Lógica en Master Scheduler (`app.py`)

```python
# PASO 0: Documentos marcados para reprocesamiento
try:
    docs_to_reprocess = document_status_store.get_documents_pending_reprocess()
    if docs_to_reprocess:
        logger.info(f"🔄 Found {len(docs_to_reprocess)} documents marked for reprocessing")
        for doc in docs_to_reprocess:
            doc_id = doc['document_id']
            filename = doc['filename']
            
            # Verificar si ya está en la cola de procesamiento
            conn_temp = processing_queue_store.get_connection()
            cursor_temp = conn_temp.cursor()
            cursor_temp.execute("""
                SELECT COUNT(*) FROM processing_queue
                WHERE document_id = ?
                AND task_type = 'ocr'
                AND status IN ('pending', 'processing')
            """, (doc_id,))
            in_queue = cursor_temp.fetchone()[0] > 0
            conn_temp.close()
            
            if not in_queue:
                # Agregar a la cola
                processing_queue_store.enqueue_task(doc_id, filename, 'ocr', priority=10)
                logger.info(f"   ✅ Enqueued {filename} for reprocessing")
            else:
                logger.debug(f"   ⏳ {filename} already in queue, skipping")
except Exception as e:
    logger.error(f"❌ Error checking reprocess queue: {e}")
```

### Desmarcado Automático

En `_handle_indexing_task()` (app.py):

```python
try:
    document_status_store.update_status(document_id, "indexed", processing_stage="indexing", indexed_at=datetime.utcnow().isoformat())
    
    # Desmarcar documento de reprocesamiento (ya completado)
    document_status_store.mark_for_reprocessing(document_id, requested=False)
    
    if INSIGHTS_QUEUE_ENABLED and rag_pipeline:
        # ... resto del código
```

---

## 📊 Ventajas del Nuevo Sistema

### Antes (Sin Persistencia)
```
Usuario marca documento → App reinicia
    ↓
❌ Se pierde la solicitud de reprocesamiento
❌ Usuario debe volver a marcar manualmente
❌ No hay tracking de estado
```

### Ahora (Con Persistencia)
```
Usuario marca documento → App reinicia
    ↓
✅ Solicitud persiste en DB
✅ Master Scheduler lo detecta automáticamente
✅ Se encola y procesa sin intervención
✅ Se desmarca automáticamente al completar
```

---

## 🔍 Monitoreo y Debugging

### Ver documentos marcados para reprocesamiento

```bash
# Desde el container del backend
docker compose exec backend python3 << 'EOF'
from database import DocumentStatusStore
store = DocumentStatusStore()
docs = store.get_documents_pending_reprocess()
print(f"Documentos marcados para reprocesamiento: {len(docs)}")
for doc in docs:
    print(f"  - {doc['filename']} ({doc['document_id']})")
EOF
```

### Logs del Master Scheduler

```bash
# Ver logs en tiempo real
docker compose logs -f backend | grep "Master Pipeline"

# Ejemplos de logs:
# 🔄 Found 2 documents marked for reprocessing
#    ✅ Enqueued 28-12-26-El Mundo.pdf for reprocessing
#    ⏳ 04-02-26-Expansion.pdf already in queue, skipping
```

### Estado de la cola de procesamiento

```bash
# Ver tareas OCR pendientes
docker compose exec backend python3 << 'EOF'
from database import ProcessingQueueStore
store = ProcessingQueueStore()
import sqlite3
conn = store.get_connection()
cursor = conn.cursor()
cursor.execute("""
    SELECT document_id, filename, task_type, status 
    FROM processing_queue 
    WHERE task_type = 'ocr' AND status IN ('pending', 'processing')
""")
for row in cursor.fetchall():
    print(f"  - {row[1]}: {row[2]} ({row[3]})")
conn.close()
EOF
```

---

## 🧪 Testing

### Test 1: Marcar para reprocesamiento

```bash
# 1. Marcar documento desde el dashboard
# Click en botón "🔄 Requeue" para documento "28-12-26-El Mundo.pdf"

# 2. Verificar que se marcó
docker compose exec backend python3 << 'EOF'
from database import DocumentStatusStore
store = DocumentStatusStore()
doc = store.get_by_document_id("1772479861.457278_28-12-26-El Mundo.pdf")
print(f"reprocess_requested: {doc['reprocess_requested']}")
EOF

# Esperado: reprocess_requested: 1
```

### Test 2: Persistencia tras reinicio

```bash
# 1. Marcar documento para reprocesamiento
# 2. Reiniciar backend
docker compose restart backend

# 3. Esperar 10 segundos (ciclo del Master Scheduler)
sleep 15

# 4. Ver logs del scheduler
docker compose logs backend --tail=50 | grep "reprocessing"

# Esperado:
# 🔄 Found 1 documents marked for reprocessing
#    ✅ Enqueued 28-12-26-El Mundo.pdf for reprocessing
```

### Test 3: Desmarcado automático

```bash
# 1. Marcar documento
# 2. Esperar a que complete el procesamiento (OCR → Chunking → Indexing)
# 3. Verificar que se desmarcó

docker compose exec backend python3 << 'EOF'
from database import DocumentStatusStore
store = DocumentStatusStore()
doc = store.get_by_document_id("1772479861.457278_28-12-26-El Mundo.pdf")
print(f"Status: {doc['status']}")
print(f"reprocess_requested: {doc['reprocess_requested']}")
EOF

# Esperado:
# Status: indexed
# reprocess_requested: 0
```

---

## 🚨 Troubleshooting

### Problema: Documento marcado pero no se procesa

**Diagnóstico:**
```bash
# Verificar si Master Scheduler está corriendo
docker compose logs backend | grep "Master Pipeline Scheduler"

# Debería aparecer:
# ✅ Master Pipeline Scheduler initialized
```

**Solución:**
- Verificar que el Master Scheduler esté registrado
- Revisar logs para errores de DB
- Reiniciar backend si es necesario

### Problema: Documento se marca y desmarca constantemente

**Diagnóstico:**
```bash
# Ver historial de cambios
docker compose logs backend | grep "mark_for_reprocessing"
```

**Posible causa:**
- Error en el proceso de indexing
- Worker crasheando antes de completar

**Solución:**
- Ver logs completos del worker
- Verificar errores en OCR/Tika
- Revisar integridad del PDF

### Problema: Documento no se desmarca tras completar

**Diagnóstico:**
```bash
# Verificar estado
docker compose exec backend python3 << 'EOF'
from database import DocumentStatusStore
store = DocumentStatusStore()
doc = store.get_by_document_id("DOCUMENT_ID_HERE")
print(f"Status: {doc['status']}")
print(f"Processing Stage: {doc['processing_stage']}")
print(f"Reprocess Requested: {doc['reprocess_requested']}")
EOF
```

**Solución:**
- Si `status = 'indexed'` pero `reprocess_requested = 1`:
  ```bash
  # Desmarcar manualmente
  docker compose exec backend python3 << 'EOF'
  from database import DocumentStatusStore
  store = DocumentStatusStore()
  store.mark_for_reprocessing("DOCUMENT_ID_HERE", requested=False)
  print("✅ Unmarked")
  EOF
  ```

---

## 📝 Notas Importantes

1. **Prioridad de cola**: Documentos marcados para reprocesamiento tienen prioridad 10 (alta)
2. **Frecuencia**: Master Scheduler revisa cada 10 segundos
3. **Idempotencia**: Si el documento ya está en cola, no se duplica
4. **Data safety**: News items e insights NUNCA se eliminan durante reprocesamiento
5. **Automatic cleanup**: Flag se desmarca automáticamente al completar

---

## 🔗 Archivos Relacionados

- **Migración**: `backend/migrations/014_add_reprocess_flag.py`
- **Database**: `backend/database.py` (métodos `mark_for_reprocessing`, `get_documents_pending_reprocess`)
- **Scheduler**: `backend/app.py` (función `master_pipeline_scheduler`)
- **Endpoint**: `backend/app.py` (endpoint `/api/documents/{document_id}/requeue`)
- **Frontend**: `frontend/src/App.jsx` (botón "🔄 Requeue")

---

## ✅ Checklist de Implementación

- [x] Migración 014 creada
- [x] Métodos en `DocumentStatusStore` agregados
- [x] Master Scheduler actualizado para detectar documentos marcados
- [x] Lógica de desmarcado en `_handle_indexing_task`
- [x] Endpoint `/requeue` actualizado para marcar flag
- [x] Documentación actualizada
- [x] Testing manual completado

---

**Implementado por:** AI Assistant  
**Fecha:** 2026-03-05  
**Estado:** ✅ Completado y en producción
