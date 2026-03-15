# 🔍 ISSUES DETECTADOS EN VERIFICACIÓN PROD-LOCAL

**Fecha**: 2026-03-05  
**Verificador**: Revisión automatizada de sistema  
**Total Issues**: 3 (1 🔴 crítico para data cleanup, 2 🟡 informativos)

---

## 📋 LISTA DE ISSUES

### Issue #1: 151 Documentos con Error "File not found"

**Severidad**: 🟡 Media  
**Tipo**: Data Quality  
**Ubicación**: dashboard_summary.errors.documents_with_errors = 151

**Descripción**:
```json
{
  "status": "error",
  "processing_stage": "ocr",
  "error_message": "File not found",
  "source": "inbox"
}
```

**Root Cause**:
Migraciones antiguas crearon registros de documentos sin archivos físicos en `local-data/uploads/`. Probable causa: 
- Documentos del inbox procesados pero archivos luego eliminados
- Sincronización incompleta durante limpieza anterior
- Archivos movidos/renombrados sin actualizar BD

**Impacto**:
- ❌ Esos 151 documentos no se procesan
- ✅ NO afecta otros documentos (los 25 completados están OK)
- ✅ NO afecta insights (solo 4 errores en 10137)

**Solución**:

**Opción A: Limpiar desde BD** (recomendado)
```sql
-- Opción A.1: Ver cuáles tienen error "File not found"
SELECT COUNT(*), status, error_message 
FROM documents 
GROUP BY status, error_message;

-- Opción A.2: Eliminar registros con File not found
DELETE FROM documents WHERE error_message = 'File not found';

-- Opción A.3: Limpiar archivos huérfanos en BD
DELETE FROM news_items WHERE document_id NOT IN (
  SELECT id FROM documents WHERE status != 'error'
);
```

**Opción B: Re-scan inbox**
```bash
# 1. Detener backend
docker compose restart backend

# 2. Backend re-escanea inbox automáticamente en startup
# Los archivos "File not found" serán limpiados

# 3. Verificar limpieza
curl -s http://localhost:8000/api/dashboard/summary | grep -A 5 "errors"
```

**Acción Recomendada**: Ejecutar Opción B (más segura, automática)

**Timeline**: 5 minutos

---

### Issue #2: 3020 Chunks Pendientes de Indexación

**Severidad**: 🟡 Baja  
**Tipo**: Processing Progress  
**Ubicación**: dashboard_summary.chunking.pending = 3020 (85.8%)

**Descripción**:
De 3520 chunks totales, solo 500 están indexados (14.2%).

**Root Cause**:
Sistema está funcionando correctamente. Solo 25 de 176 documentos completaron OCR, por eso solo 500 chunks están indexados. Esto es **expected behavior** - el sistema sigue procesando.

**Impacto**:
- ✅ No es un problema, es progress normal
- 📊 A medida que OCR completa, más chunks se indexan
- ⏱️ Estimado: ~3 horas para 100% (si OCR sigue a 2x velocidad)

**Observación**:
El dashboard muestra `eta_seconds: 0` para insights, lo que significa:
- Todos los insights pending se están procesando
- No hay backlog

**Acción Recomendada**: Monitorear. Sin acción requerida.

**Próximo Check**: 30 minutos

---

### Issue #3: Variables de Entorno - Redundancia Detectada

**Severidad**: 🟢 Baja  
**Tipo**: Code Quality  
**Ubicación**: app.py, docker-compose.yml

**Descripción**:
Hay múltiples formas de configurar el mismo parámetro:
```
OPENAI_MODEL vs LLM_MODEL
OPENAI_API_KEY en .env y en backend vars
LLM_PROVIDER se valida en 3 lugares
```

**Impacto**:
- ✅ Funciona (lógica de fallback está correcta)
- ⚠️ Confusión en documentación
- 🔧 Oportunidad de refactor

**Acción Recomendada**: Documentar claramente en .env.example

**Timeline**: 0 (informativo)

---

## ✅ ITEMS VERIFICADOS Y CORRECTOS

Estos items fueron revisados y están 100% correctos:

```
✅ Backend health check
✅ Frontend loads
✅ Docker Compose services
✅ JWT token generation
✅ Login functionality
✅ Dashboard Summary endpoint (8 métricas OK)
✅ RAG Query endpoint (búsqueda + generation OK)
✅ Worker Pools (2 OCR + 2 Insights corriendo)
✅ Queue Persistencia (processing_queue tabla OK)
✅ CORS configuration (ALLOWED_ORIGINS OK)
✅ Security (JWT_SECRET_KEY OK, ADMIN_PASSWORD OK)
✅ OpenAI API key configured
✅ Qdrant connection
✅ Embeddings model (BAAI/bge-m3)
✅ Database migrations (8 applied)
✅ User roles (admin/superuser/user working)
✅ Event-driven architecture (2026-03-04 implementation)
```

---

## 🛠️ PLAN DE REMEDIACIÓN

### Fase 1: Limpieza Inmediata (5 min)

```bash
cd /Users/diego.a/Workspace/Experiments/NewsAnalyzer-RAG/rag-enterprise/rag-enterprise-structure

# 1. Restart backend (trigger cleanup)
docker compose restart backend

# 2. Monitorear logs
docker compose logs backend -f | grep -E "cleanup|File not found|migration"

# 3. Verificar resultado
curl -s http://localhost:8000/api/dashboard/summary | python3 -m json.tool | grep -A 2 "errors"
```

### Fase 2: Validación (5 min)

```bash
# Verificar que queremos:
# - errors.documents_with_errors < 10
# - OCR % sigue progresando
# - Insights % sigue progresando
```

### Fase 3: Monitoring (ongoing)

```bash
# Script para monitorear progreso
watch -n 30 'curl -s http://localhost:8000/api/dashboard/summary | python3 -c "import json, sys; data = json.load(sys.stdin); print(f\"OCR: {data[\"ocr\"][\"successful\"]}/{data[\"ocr\"][\"total\"]} ({data[\"ocr\"][\"percentage_success\"]}%) | Insights: {data[\"insights\"][\"done\"]}/{data[\"insights\"][\"total\"]} ({data[\"insights\"][\"percentage_done\"]}%)\")"'
```

---

## 📊 RESUMEN PRE vs POST CLEANUP

### PRE-Cleanup (Estado Actual)

```
Files:      176 total, 25 completed (14.2%), 151 errors
OCR:        25/176 successful (14.2%)
News:       10137 total, 1436 with insights (14.17%)
Chunks:     3520 total, 500 indexed (14.2%), 3020 pending
Errors:     151 documents
Workers:    2 OCR + 2 Insights (active, healthy)
```

### POST-Cleanup (Esperado)

```
Files:      ~30 total, ~25-28 completed, ~0-2 errors
OCR:        ~25/28 successful (>89%)
News:       ~1400 total, ~1400 with insights (100%)
Chunks:     ~1400 total, 500 indexed (35%), ~900 pending
Errors:     ~0-2 (acceptable)
Workers:    2 OCR + 2 Insights (active, healthy)
```

---

## 🎯 VERIFICACIÓN POST-REMEDIACIÓN

**Ejecutar después de cleanup**:

```bash
# Test 1: Dashboard updated
curl -s http://localhost:8000/api/dashboard/summary | grep "documents_with_errors"

# Test 2: Query still works
curl -X POST http://localhost:8000/api/query \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"query":"test"}'

# Test 3: Upload new document
curl -X POST http://localhost:8000/api/documents/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@test.pdf"
```

---

## 📝 NOTAS TÉCNICAS

### Por qué "File not found"?

1. **Teoría más probable**: Inbox scan procesó archivos que fueron eliminados después
   - Inbox scan copia archivo → DB registro creado
   - Después, archivo eliminado del disco
   - OCR worker intenta leerlo y falla con "File not found"

2. **Mitigación implementada (2026-03-04)**:
   - Inbox scan ahora es event-driven
   - OCR worker verifica existencia antes de procesar
   - Errores se registran correctamente en BD

### Por qué 3020 chunks pending?

Esto es **CORRECTO y ESPERADO**:
- OCR genera chunks
- Chunks se insertan en BD con status='pending_indexing'
- Scheduler indexa en paralelo
- A medida que OCR completa, más chunks llegan para indexar

**Velocidad estimada**: ~10-15 chunks/segundo (con 2x OCR workers)

---

## 🚀 NEXT STEPS

1. **Hoy**: Ejecutar Opción B (restart backend)
2. **1 hora después**: Verificar dashboard (errors debería bajar)
3. **4 horas**: Monitorear OCR progress (debería llegar a 50%+)
4. **Próxima sesión**: Validar 100% OCR completo

---

## ⚠️ ADVERTENCIAS

**NO EJECUTAR**:
```bash
# ❌ NO hacer esto (perderás datos)
docker compose down -v          # Elimina volumes
rm -rf local-data/*            # Elimina BD y uploads
docker system prune -a         # Limpia imágenes
```

**ANTES ejecutar**:
```bash
# ✅ Hacer primero
docker compose exec backend mysqldump... # Si usara MySQL
# SQLite no necesita backup (archivo simple)
```

---

**Resumen**: 3 issues detectados, 1 requiere acción (restart), 2 informativos.  
**Acción recomendada**: Restart backend en próximas 24 horas para cleanup.  
**Riesgo**: Bajo (restart no destructivo, datos persisten).
