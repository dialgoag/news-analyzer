# Fase 5E Testing Checklist - ANTES DE COMMIT

## ⚠️ ESTADO ACTUAL: TESTING EN PROGRESO

**Docker build**: ⏳ En progreso (descargando dependencias)  
**Backend running**: ❌ No (esperando build)  
**Tests ejecutados**: ❌ Ninguno aún

---

## 🐛 Bugs Encontrados y Corregidos (SIN COMMIT):

### 1. Dockerfile.cpu y Dockerfile
**Problema**: Intentaban copiar `worker_pool.py` (eliminado en Fase 5C)  
**Solución**: Comentada línea `COPY backend/worker_pool.py .`  
**Archivos**: 
- `app/backend/Dockerfile.cpu` línea 53
- `app/backend/docker/cuda/Dockerfile` línea 44

### 2. GET /api/documents/{id}/download
**Problema**: Usaba `document_status_store.get()` en lugar del migrado `document_repository.get_by_id_sync()`  
**Solución**: Migrado a repository  
**Archivo**: `app/backend/app.py` línea 3605

### 3. POST /api/workers/retry-errors  
**Problema**: Usaba `document_status_store.get()` en lugar del migrado  
**Solución**: Migrado a repository  
**Archivo**: `app/backend/app.py` línea 3856

---

## ✅ Tests a Ejecutar (EN ESTE ORDEN):

### 1. Verificación de Compilación
```bash
cd app/backend
python3 -m py_compile app.py
```
**Estado**: ✅ PASÓ (ya verificado)

### 2. Docker Build
```bash
cd app
docker-compose build backend
```
**Estado**: ⏳ EN PROGRESO

### 3. Levantar Backend
```bash
cd app
docker-compose up -d
sleep 10
curl http://localhost:8000/api/health
```
**Estado**: ❌ PENDIENTE

### 4. Test de Endpoints (Repository Migration)
```bash
cd app
python3 test_endpoints_fase5e.py
```
**Tests**:
- [ ] GET /api/documents/metadata
- [ ] GET /api/documents/{id}/segmentation-diagnostic
- [ ] GET /api/documents/{id}/download (🐛 corregido)
- [ ] POST /api/documents/{id}/requeue
- [ ] GET /api/workers/status

**Estado**: ❌ PENDIENTE

### 5. Test End-to-End (Pipeline Completo)
**Pipeline a validar**:
1. UPLOAD → pending → processing → done
2. OCR → pending → processing → done
3. CHUNKING → pending → processing → done
4. INDEXING (chunks) → pending → processing → done
5. INSIGHTS (LLM) → pending → processing → done
6. INDEXING_INSIGHTS (indexar insights) → pending → processing → done
7. COMPLETED (terminal)

**Estado**: ❌ PENDIENTE

---

## 📊 Cambios Totales Fase 5E:

### Part 1 (YA COMMITEADO - commit 97becaa):
- ✅ Agregados métodos al DocumentRepository
- ✅ Migrados async workers
- ✅ Reducido de 55 a 48 usos

### Part 2 (YA COMMITEADO - commit a39cf73):
- ✅ Agregados get_by_id_sync, list_all_sync
- ✅ Migrados 4 endpoints GET
- ✅ Reducido de 48 a 45 usos (incorrecto - tenía 2 bugs)

### Part 3 (SIN COMMIT - TESTING AHORA):
- 🐛 Corregidos 2 bugs encontrados durante testing
- 🐛 Corregidos Dockerfiles
- ✅ Reducido de 45 a 43 usos (después de correcciones)
- ❌ Test de endpoints PENDIENTE
- ❌ Test E2E PENDIENTE

---

## 🚫 REGLA CRÍTICA:

**NO HACER COMMIT HASTA QUE:**
1. ✅ Docker build complete
2. ✅ Backend levante sin errores
3. ✅ Todos los tests de endpoints pasen
4. ✅ Test E2E pase (al menos hasta indexing)

---

## 📝 Commit Message (CUANDO TESTS PASEN):

```
fix(REQ-021): Fase 5E Part 3 - Fix bugs + Dockerfile corrections

BUG FIXES:
- Fixed GET /api/documents/{id}/download using old document_status_store.get()
- Fixed POST /api/workers/retry-errors using old document_status_store.get()
- Fixed Dockerfile.cpu and Dockerfile trying to copy removed worker_pool.py

CHANGES:
- Reduced document_status_store usage from 45 to 43 occurrences
- All migrated endpoints now use document_repository correctly

TESTING:
- ✅ Docker build successful
- ✅ Backend starts without errors  
- ✅ All endpoint tests pass
- ✅ E2E test validates pipeline flow

Refs: REQ-021 Fase 5E (Part 3/3 - Bug Fixes)
```

---

**Última actualización**: 2026-04-01 12:49
**Build en progreso**: docker-compose build backend (PID 77879)
