# Plan del Proyecto y Siguiente Paso

> Plan detallado, timeline, checklist de verificación
> 
> **⚠️ NOTA IMPORTANTE**: Ver `CONSOLIDATED_STATUS.md` para el estatus completo.
>
> **📋 ÚLTIMO**: Fix #112 — Sistema Unificado de Timestamps ✅ (Migration 018). REQ-021 Fase 5 COMPLETA.

**Última actualización**: 2026-04-06  
**Versión**: 3.0.17 (Hexagonal Architecture + backlog memoria post-insights)

---

## 🎯 REQ-021: Backend Refactor - FASE 5 COMPLETA ✅

### [x] Fix #112: Sistema Unificado de Timestamps ✅ (2026-04-01)
**Estado**: ESTABLE ✅  
**Migration**: 018 aplicada

**Implementación completada**:
- ✅ Tabla `document_stage_timing` (document-level + news-level)
- ✅ Entidad `StageTimingRecord` con `news_item_id` support
- ✅ Repository `PostgresStageTimingRepository` (async + sync)
- ✅ 4 workers integrados (OCR, Chunking, Indexing, Insights)
- ✅ Backfill de 620 registros (320 upload + 300 indexing)
- ✅ Triggers `updated_at` en 7 tablas
- ✅ Fix `DocumentType` enum (CONTRACT + GENERIC_DOCUMENT)

**Archivos modificados**:
- `migrations/018_standardize_timestamps.py` (+360 líneas)
- `core/domain/entities/stage_timing.py` (nueva entidad, +150)
- `core/ports/repositories/stage_timing_repository.py` (nuevo port, +180)
- `adapters/.../stage_timing_repository_impl.py` (implementación, +330)
- `core/domain/entities/document.py` (enum DocumentType +2 valores)
- `app.py` (4 workers integrados, ~40 líneas)

**Queries habilitadas**:
- Timeline completo por documento
- Performance stats por stage (avg/min/max duration)
- Detección de bottlenecks (stages atascados)
- Tracking granular de insights (por news_item_id)

Ver: CONSOLIDATED_STATUS.md § Fix #112, SESSION_LOG.md § Sesión 50

### [x] Fase 5E: DocumentStatusStore → Repository ✅ (2026-04-01)
**Estado**: ESTABLE
**Fix**: #111

**Migración completada**:
- ✅ 9 endpoints/workers migrados a `DocumentRepository`
- ✅ Eliminada referencia `generic_worker_pool`
- ✅ Fixes SQL: `TRUE→1`, `created_at→ingested_at`
- ✅ 5/5 tests E2E pasan
- ✅ Backend healthy sin spam de errores

**Archivos afectados**:
- `app/backend/app.py` (L794, L2789, L2998, L3469, L3605, L3676, L3729, L3856, L3875, L5147-5230)
- `app/backend/core/ports/repositories/document_repository.py`
- `app/backend/adapters/driven/persistence/postgres/document_repository_impl.py`
- `app/backend/Dockerfile.cpu`, `app/backend/docker/cuda/Dockerfile`

Ver: CONSOLIDATED_STATUS.md § Fix #111, SESSION_LOG.md § 2026-04-01

### ✅ Fase 0-5: COMPLETADAS

| Fase | Estado | Fecha | Descripción |
|------|--------|-------|-------------|
| **0** | ✅ | 2026-03-31 | Documentación arquitectura hexagonal |
| **1** | ✅ | 2026-03-31 | Domain Model (Entities + Value Objects) |
| **2** | ✅ | 2026-03-31 | Repositories (Ports + Adapters) |
| **3** | ✅ | Previo | LLM Infrastructure (LangChain/Graph/Mem) |
| **5A-5E** | ✅ | 2026-04-01 | Workers + Scheduler (repositories) |

### 🚀 SIGUIENTE: Fase 6 - API Routers

**Objetivo**: Extraer endpoints de `app.py` a routers modulares

**Plan**:
1. Documents Router (`/api/documents/*`)
2. Workers Router (`/api/workers/*`)
3. Dashboard Router (`/api/dashboard/*`)
4. Auth Router (`/api/auth/*`)

**Impacto**: Separación completa presentación ↔ dominio

## 🟥 Auditoría 2026-04-06 – Brechas vs. AI-LCD

| # | Brecha detectada | Prioridad | Archivos/Líneas | Detalle y siguiente paso |
|---|-----------------|-----------|-----------------|---------------------------|
| 1 | (Resuelto 2026-04-06) Endpoints de documentos usan `DocumentRepository`/`StageTimingRepository` | ✅ | `adapters/driving/api/v1/routers/documents.py:24-247, 632`, `app/backend/app.py:3820-3895` | Actualizados para consumir `list_all_sync(..., status, source)`, `delete_sync` y `StageTimingRepository.delete_for_document_sync`. |
| 2 | (Resuelto 2026-04-06) API de workers usa `WorkerRepository`/`pipeline_runtime_store` | ✅ | `adapters/driving/api/v1/routers/workers.py` | Nuevos métodos (`list_active_with_documents`, `reset_processing_tasks`, etc.) reemplazan `_pg_conn` y toda la lógica de SQL directo. `set_all_pauses()` sustituye las escrituras manuales en `pipeline_runtime_kv`. |
| 3 | Routers `admin.py` y `dashboard.py` aún usan `document_status_store` | **Media** | `adapters/driving/api/v1/routers/admin.py:20-320`, `dashboard.py:14-520` | Estas rutas duplican lógica de `app.py` y bloquean la eliminación del store legacy. Necesitan migrarse a los puertos hexagonales (`DocumentRepository`, `StageTimingRepository`, `NewsItemRepository`, `WorkerRepository`). Ver **PEND-010** y la auditoría previa de métricas en **PEND-011**. |
| 4 | (Resuelto 2026-04-06) Eliminación limpia `document_stage_timing` e índices derivados | ✅ | `adapters/driving/api/v1/routers/documents.py:611-635`, `app/backend/app.py:3842-3865` | `StageTimingRepository.delete_for_document_sync` + `document_repository.delete_sync` se ejecutan antes de remover insights y news items. |
| 5 | (Resuelto 2026-04-06) Reportes diario/semanal usan `ReportService` | ✅ | `core/application/services/report_service.py`, `app/backend/app.py:1455-1535` | Se creó `ReportService` (puertos `DocumentRepository` + Qdrant/RAG) y se actualizó `generate_daily_report_for_date` / `generate_weekly_report_for_week` para usarlo. `check_workers_script.py` ahora consume `PostgresWorkerRepository`/`PostgresNewsItemRepository`, sin SQL directo ni `document_status_store`. |

> _Notas_: Las brechas 3–5 siguen bloqueando el objetivo AI-LCD de “Centralizar ingesta y estados en puertos hexagonales”. Antes de ampliar cobertura de pruebas debemos cerrar estas migraciones; después se puede abordar la limpieza del store legacy restante en `app.py`.

---

## 🚨 Incidentes runtime activos (2026-04-06)

- **PEND-016** (ingesta fuera de inbox + retries legacy) — En progreso: limpieza puntual del caso `test_upload` + cuarentena física en `uploads/PEND-016`; symlink/registro específico `91fafac5...` corregido; script de sanity check agregado para detección temprana (`check_upload_symlink_db_consistency.py`); pendiente estandarización estructural de upload/retry.
- **PEND-013** (`PoolError unkeyed connection`) — En progreso: hardening aplicado en `BasePostgresRepository` y redeploy ejecutado; validar estabilidad en carga.
- **PEND-014** (`pipeline_runtime_kv` tuple/dict mismatch) — En progreso: `pipeline_runtime_store` tolera filas tuple/dict; startup sin error tras rebuild.
- **PEND-015** (`UnsupportedImageFormatError` en OCR) — Pendiente: falta validación temprana de tipo real de archivo + clasificación de error permanente.

Ver fuente única de detalles en `PENDING_BACKLOG.md` (§ Prioridad Alta, PEND-016/013/014/015).

---

### 📌 Backlog priorizado (orden de ataque)

1. **Document endpoints → repositorios** ✅ (2026-04-06)  
   - `DocumentRepository.list_all_sync(..., status, source)` y `delete_sync` + `StageTimingRepository.delete_for_document_sync` implementados.  
   - `GET /api/documents`, `GET /api/documents/status`, `GET /api/documents/{id}/segmentation-diagnostic` y `DELETE /api/documents/{id}` ahora consumen únicamente los puertos hexagonales.  
   - `document_status_store` se conserva solo en `app.py` legacy y jobs heredados.

2. **Worker API → `WorkerRepository` / `PipelineRuntimeStore`** ✅ (2026-04-06)  
   - Nuevos métodos (`list_active_with_documents`, `list_recent_errors_with_documents`, `reset_processing_tasks`, `delete_active_worker_tasks`, `get_pending_task_counts`).  
   - `routers/workers.py` usa exclusivamente los puertos hexagonales y `pipeline_runtime_store.set_all_pauses`.  
   - Resultado: ninguna consulta SQL directa en el router; todo pasa por adaptadores hexagonales.

3. **Routers admin/dashboard sin legacy store**  
   - Diagnóstico previo de métricas/datos requeridos (matriz “métrica → fuente → puerto”).  
   - Sustituir `document_status_store`, `news_item_store` y SQL sueltos por métodos de `DocumentRepository`, `StageTimingRepository`, `NewsItemRepository` y `WorkerRepository`.  
   - Objetivo: los routers solo orquestan, sin conexiones directas a la BD. (Ver **PEND-010** y **PEND-011**).

4. **Eliminar cascadas en stage timing / fuentes derivadas** ✅ (2026-04-06)  
   - `StageTimingRepository.delete_for_document_sync` + borrado coordinado en insights/news items al eliminar documentos.  
   - Falta documentar el comportamiento final de auditoría en la guía operativa.

5. **Reportes diarios/semanales**  
   - Decidir si se mantienen solo en `app.py` legacy (documentarlo explícitamente) o se migra la lógica a un servicio basado en repositorios.  
   - Si se migra, crear puerto dedicado (p.ej. `ReportService`) que reutilice los métodos nuevos de `DocumentRepository`.

6. **Lote de pruebas pendientes (cuando finalice la migración)**  
   - Ejecutar suite disponible (`cd app/backend && pytest`) + smoke manual sobre `/api/documents`, `/api/workers`, `/api/dashboard`.  
   - Registrar resultados y comandos en `docs/ai-lcd/TESTING_DASHBOARD_INTERACTIVE.md` o nuevo checklist.  
   - Sin esta evidencia no se considera cerrada la Fase 6. (Ver **PEND-012**).

7. **Memoria analítica post-insights y reportes (brecha vs. visión híbrida)** — *pendiente, no iniciado*  
   **Contexto**: El pipeline ya es híbrido (OCR/chunking/indexing sin LLM; insights con LangGraph + `InsightMemory`). Tras generar insights, solo se persiste en `news_item_insights` el campo `content` (+ `llm_source`); `extracted_data` / `analysis` viven en caché `InsightMemory`, no como ciudadanos de primer nivel para agregaciones. Los reportes diario/semanal (`app.py` ~1464–1552) arman contexto desde **chunks en Qdrant** y vuelven a llamar al LLM, en lugar de apoyarse en insights ya materializados por noticia.  
   **Pasos futuros (orden sugerido)**:
   - [ ] **Esquema**: Añadir columnas JSONB (o tabla derivada `news_item_insight_artifacts`) para `extracted_data`, `analysis` y/o un schema versionado; mantener `content` como vista o concatenación estable para el API actual.
   - [ ] **Escritura**: En `_insights_worker_task` / `InsightsWorkerService`, tras éxito, persistir estructura además del texto; invalidar o versionar si se reprocesa el documento.
   - [ ] **Reportes**: Refactor de `generate_daily_report_for_date` / `generate_weekly_report_for_week` para que el prompt use **insights agregados por rango de fechas** (vía `DocumentRepository` + consulta por `news_date` / joins a `news_item_insights`), con chunks solo como fallback si falta insight.
   - [ ] **Servicio**: Opcional `ReportService` (puerto) que centralice la composición del contexto de reporte y métricas de tokens antes/después.
   - [ ] **Clarificación de producto**: Documentar diferencia entre memoria conversacional de usuario (`/api/.../memory`) y memoria analítica del corpus (insights persistidos).
   - [ ] **Verificación**: Tests de integración ligera y comparativa de coste/tokens en reportes piloto.

> Cada paso desencadena el siguiente; no avanzar con #2 hasta cerrar #1, etc. Este orden alimenta el roadmap de Fase 6 y asegura que la documentación refleje fielmente el estado real de la app. El ítem **7** puede avanzar en paralelo a migraciones admin/dashboard si hay capacidad; conviene cerrar **#3–5** antes de invertir fuerte en nuevos esquemas de reporte.

## 🔥 PRIORIDADES ACTUALES (2026-03-16)

### PRIORIDAD 1: REQ-017 — Rate Limit OpenAI (Fix #63) ✅
**Estado**: IMPLEMENTADO — Pendiente deploy + reset de 392 items
**Solución aplicada** (Enfoque C):
1. ✅ `RateLimitError` + quick retry (2s) en `rag_pipeline.py`
2. ✅ `_handle_insights_task` re-encola 429 como `pending` (no `error`)
3. ✅ `worker_pool.py` limita insights a `INSIGHTS_PARALLEL_WORKERS` (default 3)
4. ⏳ Post-deploy: `UPDATE news_item_insights SET status='pending', error_message=NULL WHERE status='error' AND error_message LIKE '%429%'`

### PRIORIDAD 2: REQ-018 — Crashed Workers Loop (Fix #64) ✅
**Estado**: IMPLEMENTADO + VERIFICADO — Deploy exitoso
**Solución aplicada**:
1. ✅ Startup: DELETE ALL worker_tasks (todos huérfanos tras restart)
2. ✅ PASO 0: limpia completed >1h, skip si task_type=None
3. ✅ Verificado: 63 worker_tasks + 14 queue + 6 insights limpiados, 0 loops fantasma

### PRIORIDAD 3: REQ-015 — Dashboard Performance (Fix #65) ✅
**Estado**: IMPLEMENTADO + VERIFICADO — Cache TTL 10-15s, sin Qdrant scroll, CORS 500, polling/timeouts 15-20s. Rebuild + up; logs OK.

### PRIORIDAD 4: REQ-014 — UX Dashboard 🔵
**Estado**: EN PROGRESO — Fix #76–83 aplicados (Upload/OCR, requeue, scheduler, Zoom Sankey, Upload inbox, colapsables)  
**Doc frontend**: `docs/ai-lcd/02-construction/FRONTEND_DASHBOARD_API.md` (API contract, granularidad, IDs)  
**Aplicar**: `cd app && docker compose build --no-cache backend frontend && docker compose up -d`

### PRIORIDAD 5: Coherencia + Indexing (Fix #66, #67, #68) ✅
**Estado**: IMPLEMENTADO + VERIFICADO (2026-03-17)
- Fix #66: Huérfanos — startup recovery verificado
- Fix #67: Coherencia totales dashboard (document_status fuente)
- Fix #68: Indexing performance (batch 4, workers 8)

### PRIORIDAD 6: Huérfanos runtime (Fix #69) ✅
**Estado**: IMPLEMENTADO (2026-03-17)
- Excluir insights del reset (document_id mismatch)
- Guardia orphans > 20 → log ERROR

### PRIORIDAD 7: REQ-014.5 Insights pipeline (Fix #70) ✅
**Estado**: IMPLEMENTADO (2026-03-17)
- Revisión pipeline + INSIGHTS_PIPELINE_REVIEW.md
- Dashboard: summary + analysis con INNER JOIN news_items
- Workers insights: filename desde news_item_insights

### PRIORIDAD 8: Pipeline completa + doc frontend (Fix #71) ✅
**Estado**: IMPLEMENTADO (2026-03-17)
- PASO 0: crashed insights → news_item_insights generating→pending
- PIPELINE_FULL_AUDIT.md
- **FRONTEND_DASHBOARD_API.md** — API contract, granularidad, IDs para REQ-014

### PRIORIDAD 9: Qdrant Docker (Fix #74) ✅
**Estado**: IMPLEMENTADO (2026-03-17)
- Límites memoria 4G; MAX_SEARCH_REQUESTS=100
- Healthcheck omitido (imagen mínima sin wget/curl)

---

## 📋 IMPROVEMENTS PENDIENTES

> **Fuente única**: `PENDING_BACKLOG.md` (no hay listas paralelas)

| # | Mejora | Prioridad | Esfuerzo |
|---|--------|-----------|----------|
| 1 | ~~Cache/batch chunks~~ → **scroll_filter** ✅ — Qdrant Filter+MatchAny server-side (Fix #75) | — | — |
| 2 | ~~Recovery para insights~~ ✅ — Inferir task_type=insights cuando doc_id=insight_* (Fix #75) | — | — |
| 3 | ~~GPU para embeddings~~ ✅ — `backend/docker/cuda/Dockerfile` + EMBEDDING_DEVICE (Fix #75) | — | — |
| 4 | ~~**REQ-014.4 Zoom semántico**~~ ✅ — 3 niveles drill-down en Sankey (Fix #82) | — | — |
| 5 | ~~**PEND-001**~~ — Insights vectorizados en Qdrant ✅ (2026-03-16) | — | — |
| 6 | ~~**PEND-008**~~ — Workers vs processing (worker_tasks atómico) ✅ (2026-03-17) | — | — |
| 7 | **PEND-002** — Botón Reindex en Dashboard | Media | Bajo |
| 8 | **PEND-006** — Coherencia totales Insights (error_tasks) | Media | Bajo |
| 9 | **PEND-007** — Coherencia totales Upload (semántica total) | Media | Bajo |
| 10 | **PEND-004** — Qdrant healthcheck | Baja | Bajo |
| 11 | **PEND-005** — Verificar llm_source en endpoints insights | Baja | Muy bajo |
| 12 | **PEND-009** — Refactor Backend SOLID / Single Responsibility | Media | Alto |

---

## 🔄 REBUILD Y VERIFICACIÓN (2026-03-27)

```bash
# Opcional primero: shutdown ordenado (ver docs/ai-lcd/03-operations/ORDERLY_SHUTDOWN_AND_REBUILD.md)
# Requiere token ADMIN (ej. export TOKEN=$(... login ... | jq -r .access_token))
curl -sS -X POST http://localhost:8000/api/workers/shutdown \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"

cd app && docker compose build backend frontend && docker compose up -d backend frontend
```

**Última versión**: 3.0.12 (Fix #96–97 + migración 015)

**Documentación operativa**: `docs/ai-lcd/03-operations/ORDERLY_SHUTDOWN_AND_REBUILD.md`

**Checklist post-rebuild**:
- [x] Backend build exitoso (~9 segundos)
- [x] Backend levantado sin errores
- [x] Migración ejecutada: 258 symlinks + 7 migrados
- [x] Archivo problemático procesado: 302K chars OCR, 187 chunks
- [x] Logs limpios: sin "Only PDF files are supported"
- [x] `resolve_file_path` funciona correctamente
- [x] Dashboard carga sin errores
- [x] Sección Errores expandida por defecto; muestra grupos de error (incl. stage="insights")
- [x] Errores de Insights visibles cuando news_item_insights tiene status='error'
- [x] Botón "Reintentar todos los errores" visible cuando hay errores
- [x] Botón "Reintentar este grupo" por cada grupo (excepto Shutdown ordenado)
- [x] Click retry → 200 OK (no 422); alert con retried_count
- [x] Pipeline: cada etapa muestra fila "Errores" (❌ N)
- [x] Totales cuadran: pending + processing + completed + error por etapa
- [x] Bloqueos: 0 cuando etapas completas (no falsos positivos)
- [x] Pending: cola real (0 si no hay tareas en processing_queue)

---

## ✅ COMPLETADO RECIENTEMENTE

### 🎯 Sesión 43: Fix file naming + OCR symlink (2026-03-19) - ESTABLE
**Fix #95**: File naming con hash prefix + extensión en symlinks

**Completado**:
- ✅ Processed files: `{short_hash}_{filename}` (8 chars SHA256 + nombre original)
- ✅ Symlinks: `{document_id}.pdf` (SHA completo + extensión)
- ✅ `resolve_file_path`: Backward compatible (intenta .pdf primero, luego legacy)
- ✅ Migración legacy: 258 symlinks con .pdf, 292 archivos con prefijo hash
- ✅ 4 endpoints actualizados en `app.py` para usar `resolve_file_path`
- ✅ Script `migrate_file_naming.py` ejecutado exitosamente (0 errores, 12 segundos)
- ✅ Archivo problemático (`28-03-26-ABC.pdf`) procesado: 302,152 chars OCR, 187 chunks
- ✅ Logs sin errores "Only PDF files are supported" ni "File not found"

**Impacto**:
- No más sobrescrituras de archivos con mismo nombre
- OCR funcional para todos los archivos
- Trazabilidad completa por contenido único
- Sistema backward compatible con archivos legacy

### 🎯 Sesión 42: Errores de Insights en análisis y retry (2026-03-18) - ESTABLE
**Fix #94**: Insights visibles y reintentables desde dashboard

**Completado**:
- ✅ Análisis incluye `news_item_insights` con status='error'
- ✅ Retry soporte para IDs con prefijo `insight_`
- ✅ `can_auto_fix` para 429/rate limit, timeout, connection

### 🎯 Sesión 40: Dashboard errores + retry (2026-03-18)
- Fix #92: Retry desde document_status; retry por stage (OCR/Chunking/Indexing)
- error_tasks en todas las etapas; UI retry funcional; fix 422

### 🎯 Sesión 26: Documentación D3-Sankey Reference (2026-03-16)

#### [x] Referencia D3-Sankey extraída de fuentes oficiales (2026-03-16) - ESTABLE
**Ubicación**: `docs/ai-lcd/02-construction/D3_SANKEY_REFERENCE.md`

**Completado**:
- ✅ API completa d3-sankey (nodos, links, alineación, sorting, extent)
- ✅ Código `SankeyChart` component de Observable (Mike Bostock, 597 forks)
- ✅ Ejemplo simplificado @d3/sankey/2 (295 forks)
- ✅ Patrones D3 Graph Gallery (drag, CSS hover)
- ✅ Análisis de gaps vs `PipelineSankeyChartWithZoom.jsx`
- ✅ Checklist de mejoras aplicables
- ✅ VISUAL_ANALYTICS_GUIDELINES.md §12.6 actualizado

**Impacto**: Base técnica para REQ-014 (UX Dashboard)

---

### 🎯 Sesión 19-Tarde: Dashboard Data Layer + Restauración (2026-03-14 10:00-10:50)

#### [x] Servicio de Transformación de Datos (2026-03-14 10:43) - ESTABLE
**Ubicación**: `frontend/src/services/documentDataService.js`

**Completado**:
- ✅ `normalizeDocumentMetrics()`: Valores mínimos garantizados (0.5 MB, 1 news, 5 chunks, 1 insight)
- ✅ `calculateStrokeWidth()`: Lógica centralizada con escalas por stage
- ✅ `generateTooltipHTML()`: Tooltips consistentes
- ✅ `groupDocumentsByStage()`: Agrupación reutilizable
- ✅ `transformDocumentsForVisualization()`: Pipeline completo
- ✅ Componente Sankey refactorizado para usar servicio
- ✅ Frontend build exitoso (307.52 kB gzipped)

**Impacto**:
- Documentos en espera ahora VISIBLES (líneas delgadas)
- Separación de responsabilidades (servicios transforman, componentes pintan)
- Código testeable y reutilizable

#### [x] Fix Error 500 en Workers Status (2026-03-14 10:25) - ESTABLE
**Ubicación**: `backend/app.py` líneas 4675-4695

**Completado**:
- ✅ Verificación de tipo para `started_at` (datetime vs string)
- ✅ Backend reiniciado sin errores
- ✅ Endpoint retorna 200 OK
- ✅ WorkersTable carga correctamente

#### [x] Restauración de Insights desde Backup (2026-03-14 10:50) - ESTABLE
**Ubicación**: `/local-data/backups/`

**Completado**:
- ✅ Script `convert_insights.py` (SQLite → PostgreSQL)
- ✅ 1,543 insights importados (28 documentos)
- ✅ Backup del 13 de marzo restaurado
- ✅ Query verificada: 28 documentos únicos con insights

**Estado actual**: Dashboard tiene datos reales para visualizar

---

## 🚫 Congelado (No modificar sin razón crítica)

## 🔥 PRIORITARIO: REQ-012 (Migración OCR: Tika → OCRmyPDF)

### Estado Actual: FASE 2 COMPLETADA ✅

#### ✅ FASE 1: Setup New Service (COMPLETADA 2026-03-13)
- Dockerfile OCRmyPDF creado
- Service integrado en docker-compose
- Testing manual: 1:42 min/PDF (vs 3-5 min Tika)

#### ✅ FASE 2: Integración Backend (COMPLETADA 2026-03-14)
- `ocr_service_ocrmypdf.py` implementado con factory pattern
- Dual-engine architecture: `OCR_ENGINE=tika|ocrmypdf`
- Timeout conservador adaptativo: 20 min inicial
- **NUEVO**: Sistema de logging de errores completo

#### ✅ SESIÓN 18: Sistema de Logging OCR (COMPLETADA 2026-03-14 09:30)

**Implementado**:
1. **Tabla `ocr_performance_log`** en PostgreSQL
   - Registra TODOS los eventos: éxitos, timeouts, errores HTTP, excepciones
   - Índices: timestamp, success, error_type, file_size_mb
   - 2 registros ya capturados (HTTP_408 timeouts)

2. **Método `_log_to_db()`** en `ocr_service_ocrmypdf.py`
   - Conexión directa a PostgreSQL con psycopg2
   - No bloquea OCR si falla el logging
   - Registra: filename, file_size, success, processing_time, timeout_used, error_type, error_detail

3. **Fix crítico**: `migration_runner.py` (SQLite → PostgreSQL)
   - Todas las migraciones ahora funcionan correctamente
   - Yoyo-migrations conecta a PostgreSQL

4. **Timeout aumentado**:
   - INITIAL_TIMEOUT: 900s (15 min) → **1200s (20 min)**
   - MAX_TIMEOUT: 960s (16 min) → **1500s (25 min)**
   - Justificado por datos: PDFs de 15-17MB tardan >15 min

**Datos capturados**:
- 2 errores HTTP_408 registrados (timeouts en 15 min)
- PDFs afectados: 15.34MB y 17.17MB
- 5 tareas OCR en progreso con nuevo timeout (20 min)

**Queries de análisis**:
- Tasa de éxito por tamaño de archivo
- Errores más comunes
- Tiempo promedio de procesamiento

**Estado**: 
- ✅ Sistema de logging funcional
- ✅ Timeout aumentado a 20 min
- ⏳ Esperando resultados con nuevo timeout
- 📊 Listo para análisis post-mortem

#### ~~FASE 3: Testing Comparativo~~ CANCELADA ✅
**Razón**: OCRmyPDF demostró superioridad clara en producción (~1:42 min/PDF vs 3-5 min Tika). No se requiere testing comparativo formal.

#### ✅ FASE 4: Migración Completa - COMPLETADA (2026-03-14)
- [x] OCRmyPDF es el engine por defecto
- [x] Tika comentado en docker-compose.yml (preservado como fallback)
- [x] Recursos optimizados: 8 CPUs, 6GB RAM, 2 workers, 3 threads

#### ✅ FASE 5: Tika Deprecada - COMPLETADA (2026-03-14)
- [x] Tika comentado en docker-compose.yml
- [x] Código preservado para reactivación fácil si necesario
- [x] Recursos liberados (2 CPUs, 2GB RAM)

**Archivos críticos**:
- ✅ `ocr-service/app.py` (OCRmyPDF + subprocess)
- ✅ `backend/ocr_service_ocrmypdf.py` (adaptador + logging)
- ✅ `backend/ocr_service.py` (factory pattern)
- ✅ `backend/migrations/011_ocr_performance_log.py` (nueva tabla)
- ✅ `backend/migration_runner.py` (fix PostgreSQL)
- ✅ `docker-compose.yml` (service ocr-service)
- ✅ `.env.example` (vars OCR_ENGINE, OCR_SERVICE_*)

---

## 🚫 Congelado (No modificar sin razón crítica)

### ❌ Servicio de Datos (`documentDataService.js`) - 2026-03-14
**Razón**: Arquitectura fundamental para transformación de datos  
**Impacto**: Si lo cambias, Sankey deja de funcionar  
**Ver**: CONSOLIDATED_STATUS.md § Fix #28

### ❌ Workers Status Endpoint (`/api/workers/status`) - 2026-03-14
**Razón**: Fix de tipo para started_at (datetime/string)  
**Impacto**: Error 500 si se revierte  
**Ver**: CONSOLIDATED_STATUS.md § Fix #29

### ❌ Insights Restaurados (`news_item_insights` table) - 2026-03-14
**Razón**: 1,543 registros recuperados de backup del 13 de marzo  
**Impacto**: Pérdida de datos históricos si se trunca  
**Ver**: CONSOLIDATED_STATUS.md § Fix #30

---

## 🔎 NUEVO FEATURE: Semantic Zoom en Dashboard (Sesión 19 - 2026-03-14)

### Estado: IMPLEMENTADO ✅ | Testing Pendiente ⏳

**Problema resuelto**:
- Dashboard ilegible con >100 documentos
- Sankey con líneas superpuestas
- Tabla gigante sin patrones visibles

**Solución implementada**:
1. **Vista Colapsada** (auto si >100 docs):
   - Meta-grupos: 🟢 Activos (pending, ocr, chunking, indexing, insights)
   - Meta-grupos: ⚫ No Activos (completed, error)
   - Métricas agregadas por grupo
   - Líneas gruesas en Sankey proporcionales a volumen
   
2. **Vista Expandida** (toggle manual):
   - Todos los documentos individuales
   - Tabla con grupos plegables (auto-colapsa si >20 docs)
   - Conectores visuales (└─) para drill-down

**Archivos creados**:
- ✅ `frontend/src/services/semanticZoomService.js`
- ✅ `frontend/src/components/dashboard/PipelineSankeyChartWithZoom.jsx`
- ✅ `frontend/src/components/dashboard/DocumentsTableWithGrouping.jsx`
- ✅ `frontend/src/components/dashboard/SemanticZoom.css`
- ✅ `frontend/src/components/dashboard/DocumentsTableGrouping.css`
- ✅ `frontend/src/services/__tests__/semanticZoomService.test.js` (tests unitarios)

**Archivos modificados**:
- ✅ `frontend/src/components/PipelineDashboard.jsx`

**Build**:
- ✅ Build exitoso (`npm run build`)
- ✅ Documentación completa (SEMANTIC_ZOOM_GUIDE.md, SEMANTIC_ZOOM_INTEGRATION.md)

**Testing completado**:
- [x] Test dev environment (`npm run dev`) - ✅ Sin errores de compilación
- [x] Build de contenedor - ✅ Completado en 2.56s
- [x] Deploy a producción - ✅ Contenedor iniciado
- [ ] Verificación manual con >100 documentos (235 disponibles, pendiente usuario)
- [ ] Verificar toggle collapsed/expanded (pendiente usuario)
- [ ] Verificar tooltips y métricas (pendiente usuario)
- [ ] Tests unitarios (requiere configurar Jest)

**Deploy completado**:
- [x] Frontend containerizado reconstruido
- [x] Servicio iniciado en http://localhost:3000
- [x] Backend funcionando con 235 documentos
- [x] Distribución ideal para testing:
  - 🟢 Activos: 175 docs (pending: 3, processing: 1, queued: 171)
  - ⚫ No Activos: 60 docs (completed: 4, error: 56)

**Verificación manual requerida**:
Ver: `CONSOLIDATED_STATUS.md` § Fix #28b (Semantic Zoom) para detalles de verificación

---

## 1. Estado Actual del Plan

| Fase | Estado | Descripción |
|------|--------|-------------|
| **Fundación** | ✅ | RAG Enterprise base + docs AI-DLC |
| **OpenAI Integration** | ✅ | gpt-4o, rate limiting, retry backoff |
| **Despliegue Local** | ✅ | Docker Compose, Dockerfile.cpu, volúmenes |
| **Auth + Permisos** | ✅ | JWT, RBAC (Admin/SuperUser/User) |
| **Ingesta Masiva** | ✅ | bulk_upload.py + inbox folder |
| **Dashboard + Filtros** | ✅ | document_status, UI con 4 filtros |
| **Reportes Diarios** | ✅ | news_date, job 23:00, API, UI |
| **Reportes Semanales** | ✅ | weekly_reports, job lunes 6:00, API, UI |
| **Notificaciones** | ✅ | Bandeja, marcar leídas, fix JWT |
| **Persistencia Colas** | ✅ **COMPLETADA** | STATUS_GENERATING recuperado |
| **Paralelización OpenAI** | ✅ **COMPLETADA** | 4x workers, ThreadPoolExecutor |
| **Dashboard Summary** | ✅ **COMPLETADA** | Fila superior 8 métricas, sticky, responsive |
| **Dashboard Unificado** | 📋 | Combinar tabla + reportes (BR-11) |
| **Tema Recurrente** | 📋 | Detección automática (BR-12/13) |

---

## 2. Checklist de Verificación (Ahora)

### 2.1 Código (Static)
```
☐ database.py línea 868: STATUS_GENERATING presente
☐ database.py línea 1122: STATUS_GENERATING presente
☐ app.py línea 534: scheduler usa run_news_item_insights_queue_job_parallel
☐ app.py línea 1333: función paralela existe con ThreadPoolExecutor
☐ .env línea 196: INSIGHTS_PARALLEL_WORKERS=4
☐ app.jsx líneas 793, 803, 817: Authorization headers presentes
☐ DashboardSummaryRow.jsx: componente React creado
☐ DashboardSummaryRow.css: estilos incluyen sticky, gradient, responsive
```

Script rápido:
```bash
./verify_changes.sh  # Debería mostrar 7/7 ✅
```

### 2.2 Runtime (Después de docker-compose up)
```
☐ Backend arranca sin errores
☐ Frontend carga en http://localhost:3000
☐ API docs disponible en http://localhost:8000/docs
☐ GET /api/dashboard/summary retorna JSON válido
☐ Dashboard tab disponible
☐ Fila superior visible con 8 métricas
☐ Auto-refresh cada 5 segundos
☐ Subir PDFs y ver cambios en tiempo real
```

### 2.3 Funcionalidad (Con PDFs)
```
☐ Archivos: aumenta al subir
☐ Noticias: aumenta al procesar
☐ OCR: % éxito sube
☐ Chunking: chunks aparecen
☐ Indexación: items en Qdrant
☐ Insights: % done sube lentamente (paralelización en marcha)
☐ Logs muestran: "Processing 4 items in parallel"
☐ Items completados en ~15s (4 en paralelo)
☐ NO: "Processing 1 item" (significaría secuencial)
```

### 2.4 Recuperación (Crash Test)
```
☐ Subir PDFs
☐ Esperar a que haya items "generating" en logs
☐ docker-compose down (durante processing)
☐ docker-compose up -d (reiniciar)
☐ Verificar: items recuperados y completados
☐ Logs muestran: STATUS_GENERATING recuperados
```

---

## 3. Timeline Esperado

### Fase 1: Verificación (Ahora)
- **Duración**: 15-30 minutos
- **Pasos**: Static check + runtime check + 5-10 PDFs prueba
- **Éxito**: 7/7 verificaciones ✅

### Fase 2: Test de Carga (Opcional)
- **Duración**: 30-60 minutos
- **Pasos**: Subir 20-50 PDFs, medir velocidad, verificar paralelización
- **Éxito**: 4x velocidad confirmada, ETA preciso

### Fase 3: Recuperación (Opcional)
- **Duración**: 15-20 minutos
- **Pasos**: Crash test, verificar items recuperados
- **Éxito**: 100% recuperación sin pérdida

### Fase 4: Dashboard Unificado (Siguiente)
- **Duración**: 2-3 horas
- **Pasos**: Combinar tabla documentos + reportes diarios/semanales en 1 vista
- **Éxito**: Vista única sin necesidad de tabs

---

## 4. Problemas Comunes & Soluciones

### ❌ Error: "STATUS_GENERATING not found"
```
Causa: Cambio en database.py no aplicado
Solución: Verificar líneas 868 y 1122, reiniciar backend
```

### ❌ Error: 403 en notificaciones
```
Causa: Anteriormente JWT no se enviaba
Solución: Ya arreglado. Si persiste, verificar líneas 793, 803, 817 en App.jsx
```

### ❌ Ver "Processing 1 item" en logs
```
Causa: Función paralela no se está usando (scheduler viejo)
Solución: Verificar línea 534 en app.py, reiniciar backend
```

### ❌ Dashboard Summary no aparece
```
Causa: Componente no integrado o CSS no cargando
Solución: 
  1. Verificar import en App.jsx línea 4
  2. Verificar componente renderizado en Dashboard
  3. Abrir DevTools → Console/Network para errores
```

### ❌ Tempo lento (~60s por insight)
```
Causa: Paralelización no activada
Solución: 
  1. Verificar logs: debe ver "Processing 4 items"
  2. docker-compose logs backend | grep parallel
  3. Si no aparece, reconstruir backend: docker-compose build --no-cache backend
```

---

## 5. Beneficios de la Implementación

### Velocidad
- ⚡ **4x más rápido**: ~15s (4 items paralelo) vs. ~60s (1 secuencial)
- ⚡ **ETA inteligente**: Calcula tiempo faltante basado en items pending
- ⚡ **Batch processing**: Múltiples items a la vez

### Confiabilidad
- 🛡️ **100% recuperable**: Items en "generating" se recuperan al restart
- 🛡️ **Retry automático**: Backoff exponencial en errores 429
- 🛡️ **Sin pérdida de datos**: PostgreSQL persistente

### Visibilidad
- 👁️ **360° vista**: Todas métricas sin scroll en 1 fila
- 👁️ **Real-time**: Auto-refresh cada 5 segundos
- 👁️ **Indicadores visuales**: Barras, porcentajes, colores claros

### Costo
- 💰 **Sin cambios**: gpt-4o sin downgrade, mismo precio/insight
- 💰 **Optimizado**: 4x velocidad sin incremento costo

---

## 6. Pasos Inmediatos (Ahora)

### 1. Dashboard UX Fixes (HECHO ✅)
```bash
# Frontend changes made:
# - Fixed height container (600px)
# - Sticky headers
# - Fixed column widths
# - Intelligent sorting (active → idle → error)

# Rebuild frontend
cd frontend && npm run build
docker-compose build --no-cache frontend
docker-compose up frontend
```

### 2. Test Dashboard
```
# Visually verify:
- No flashing/jumping
- Headers stay at top when scrolling
- Workers ordered: active first, then idle, then others
- Consistent column widths
```

### 3. Backend Rebuild
```bash
# OCR + Insights event-driven is ready
docker-compose build --no-cache backend
docker-compose up -d

# Verify logs
docker-compose logs -f backend | grep -E "\[ocr_|insights_" | head -20
```

### 4. System Test
```bash
# Upload 10 files
# Expect:
# - Max 2 OCR workers simultaneously
# - Max 4 Insights workers simultaneously
# - Logs with [worker_id] prefix
# - No saturation after 1 hour
```

---

## 7. 📦 VERSIONES CONSOLIDADAS (Estables)

> Agrupamiento de peticiones relacionadas (REQ-XXX) y sus cambios (Fix #X) en versiones atómicas

### **v1.0 - Event-Driven Base + Dashboard Confiable** ✅
**Fecha consolidada**: 2026-03-05 14:00  
**Status**: 🟢 ESTABLE (Congelada, no modificar sin justificación crítica)

**Peticiones incluidas**:
- [REQ-001](REQUESTS_REGISTRY.md#req-001-hacer-ocr-más-rápido-event-driven) - "Hacer OCR más rápido (event-driven)"
- [REQ-002](REQUESTS_REGISTRY.md#req-002-dashboard-sin-saturación-tika) - "Dashboard sin saturación Tika"

**Cambios agrupados** (6 total):
- Fix #5: OCR Timeout 600s → 120s
- Fix #6: ThreadPoolExecutor → Event-driven OCR
- Fix #8: Optimizar health check (cache 3s + timeout 0.5s)
- Fix #9: Async workers dispatch (asyncio.run_coroutine_threadsafe)
- Fix #10: Dashboard sticky header + 8 métricas
- Fix #11: Inbox refactor event-driven

**Verificaciones completadas** ✅:
- [x] OCR workers ejecutándose (<= 2)
- [x] Insights workers ejecutándose (<= 4)
- [x] Dashboard muestra worker status correcto en tiempo real
- [x] Health check no bloquea dashboard (< 1s)
- [x] Sin "coroutine never awaited" en logs
- [x] Recovery en crash funciona (detecta worker caído → re-enqueue)

**Documentación de referencia**:
- `CONSOLIDATED_STATUS.md` § Fixes #5-11
- `SESSION_LOG.md` § Sesión 10
- `EVENT_DRIVEN_ARCHITECTURE.md` § Patrón OCR + Insights

**Rollback (si necesario)**:
```bash
# Esta versión está congelada. Para revertir (RARO):
# 1. Identificar commits asociados (ver git log --grep="Event-driven")
# 2. git revert <commit-hash1> <commit-hash2> ... <commit-hash6>
# 3. Reconstruir backend: docker-compose build --no-cache backend
# ⚠️ CUIDADO: v1.1 depende de esta versión
```

**⚠️ CRÍTICO - NO TOCAR**:
- `backend/app.py` § 1496-1593: _ocr_worker_task (semáforo OCR)
- `backend/app.py` § 1398-1587: _insights_worker_task (semáforo Insights)
- `backend/database.py` § worker_tasks schema (semáforo persistencia)
- Health check caching logic (linha 279-287)

**Próxima versión**: v1.1 (Indexing Refactor + Deduplication)

---

### **v1.1 - Indexing Refactor + Deduplication** ✅
**Fecha**: 2026-03-05 → 2026-03-15  
**Status**: 🟢 COMPLETADA (dedup via PostgreSQL ON CONFLICT + SHA256)

**Peticiones incluidas**:
- [REQ-003](REQUESTS_REGISTRY.md#req-003-verificar-si-hay-duplicados-en-dedup-logic) - "Verificar si hay duplicados"

**Cambios aplicados**:
- Fix #4: assign_worker() verifica antes de asignar
- Fix #46: Dedup SHA256 en Insights Workers (3 handlers)
- Fix #51: Indexing worker real con index_chunk_records()
- Migración PostgreSQL (REQ-008) con ON CONFLICT DO NOTHING

**Link a REQUESTS_REGISTRY**: 
- [REQ-003 detallada](REQUESTS_REGISTRY.md#req-003-verificar-si-hay-duplicados-en-dedup-logic)

---

### **Futuras Versiones**

#### v1.2 - Master Pipeline Scheduler ✅ COMPLETADA
**Fecha**: 2026-03-05 → 2026-03-13  
**Scope**: REQ-004 — Scheduler único que orquesta Inbox → OCR → Chunking → Indexing → Insights

#### v1.3 - Dashboard D3.js Interactivo ✅ COMPLETADA
**Fecha**: 2026-03-13  
**Scope**: REQ-007 — Sankey + Timeline + Tablas con Brushing & Linking

#### v2.0 - PostgreSQL + Frontend Resiliente ✅ COMPLETADA
**Fecha**: 2026-03-13  
**Scope**: REQ-008 + REQ-009 — Migración SQLite → PostgreSQL, frontend con degradación graciosa

#### v2.5 - Semantic Zoom + Data Service ✅ COMPLETADA
**Fecha**: 2026-03-14  
**Scope**: REQ-013 — Sankey con zoom semántico, servicio de transformación de datos

#### v3.0 - OCRmyPDF + Docker Unificado + Recovery ✅ COMPLETADA
**Fecha**: 2026-03-14 → 2026-03-15  
**Scope**: REQ-012 — Migración Tika → OCRmyPDF, compose unificado, startup recovery

#### v3.0.1 - Dashboard Performance (PENDIENTE)
**Scope**: REQ-015 — Fix timeouts, CORS, Qdrant saturation

#### v3.1 - Dashboard UX Improvements (PENDIENTE)
**Scope**: REQ-014 — Upload stage, secciones colapsables, zoom multinivel

---

## 7b. Siguiente Paso

### ⏳ PENDIENTE AHORA
**REQ-015: Fix Dashboard Performance** (v3.0.1 hotfix)
- PRIORIDAD 1: Caché + connection pooling + eliminar Qdrant scroll
- PRIORIDAD 2: CORS headers en respuestas 500
- PRIORIDAD 3: Rate limiting en workers insights
- Ver: `REQUESTS_REGISTRY.md` § REQ-015

### Después de REQ-015
**REQ-014: Mejoras UX Dashboard** (v3.1)
- Secciones colapsables, header compacto, zoom multinivel
- Ver: `REQUESTS_REGISTRY.md` § REQ-014

### Si Hay ❌ Problemas
1. Revisar los logs: `docker compose logs backend --tail 100`
2. Ejecutar PROTOCOLO DE RECOVERY POST-RESTART (§ más abajo)
3. Consultar `REQUESTS_REGISTRY.md` para peticiones relacionadas

---

## 8. Configuración Avanzada (Opcional)

### Cambiar Velocidad Paralelización
```env
# .env
INSIGHTS_PARALLEL_WORKERS=4    # Cambiar a 2-6 según necesidad (capped a 4)
INSIGHTS_THROTTLE_SECONDS=60   # Base para retry exponencial
INSIGHTS_MAX_RETRIES=5         # Reintentos en 429
```

### Cambiar Refresh del Dashboard
```javascript
// DashboardSummaryRow.jsx línea ~30
const interval = setInterval(fetchSummary, 5000);  // 5000ms = 5s
// Cambiar a: 3000 (3s), 10000 (10s), etc.
```

---

## 9. Referencias Rápidas

| Documento | Uso |
|-----------|-----|
| README.md | Visión general, stack, cómo comenzar |
| CONSOLIDATED_STATUS.md | Estado actual, cambios completados, verificación |
| SESSION_LOG.md | Decisiones, contexto, sesiones previas |
| **REQUESTS_REGISTRY.md** | **Rastreo de peticiones del usuario + contradicciones** |
| 03-operations/DEPLOYMENT_GUIDE.md | Despliegue a producción |
| 03-operations/TROUBLESHOOTING_GUIDE.md | Problemas y soluciones |

---

## 10. Métricas a Monitorear

| Métrica | Normal | Alarma |
|---------|--------|--------|
| Items/paralelo | 4 | <2 |
| Tiempo/batch | 15s | >30s |
| % Éxito OCR | >95% | <90% |
| Error 429 | <5% | >10% |
| Recuperación | 100% | <95% |
| Uptime | 99%+ | <95% |

---

| Fecha | Versión | Cambios |
|-------|---------|---------|
| 2026-02-xx | 1.0 | Plan inicial (sesiones 1-7) |
| 2026-03-03 | **2.0** | **CONSOLIDACIÓN**: Todos cambios implementados, checklist completo, timeline claro, verificación paso a paso. |
| 2026-03-13 | **3.0** | **DASHBOARD REFACTOR**: D3.js interactivo, Brushing & Linking, responsive design, stageColors fix aplicado (3 archivos). FASE 3 completada. |

---

**Status**: 🟡 **FRONTEND RECUPERADO — PENDIENTE: REQ-015 (Dashboard Performance)**

**Última actualización**: 2026-03-15
**Frontend modular**: 17 archivos JS/JSX + 11 archivos CSS recuperados desde source map
**Backend**: Idéntico entre imagen Docker y app/ (verificado)
**Dashboard desplegado**: http://localhost:3000
**Pipeline verificada**: 14/14 documentos completados con nuevos status
**221 documentos pausados**: Listos para despausar en lotes controlados
**Bloqueante**: REQ-015 (Dashboard inutilizable por timeouts 15-54s)

---

## 🔥 PRÓXIMOS PASOS — Priorizado por Contención de Bugs (2026-03-15)

> **Principio**: Arreglar bugs primero, luego procesar datos, luego features nuevas.
> 
> **Actualizado**: 2026-03-15 — Nuevos bugs PRIORIDAD 1-2 (REQ-015: Dashboard inutilizable)

---

### ⚠️ PROTOCOLO DE RECOVERY POST-RESTART (Aplicar en CADA rebuild/restart del backend)

Al reiniciar el backend, tareas que estaban a mitad de ejecución quedan en estados intermedios y no se completan. Hay recovery parcial automática pero con gaps.

**Recovery automática existente** (ya implementada en `app.py`):
- `_initialize_processing_queue()` (línea 491): Re-encola docs en `upload_pending`, `*_processing` → cola OCR
- `master_pipeline_scheduler` PASO 0 (línea 564): Detecta `worker_tasks` con status `started` > 5 min → re-encola y elimina worker
- `detect_crashed_workers()` (línea 3075): Similar al PASO 0, detecta workers stuck > 5 min

**Gaps de recovery NO cubiertos** (requieren intervención manual o fix):
1. **`processing_queue` con status `processing`**: Tareas marcadas como `processing` en la cola quedan huérfanas — ningún worker las retoma. El scheduler solo busca `pending`.
2. **`news_item_insights` con status `generating`**: Insights a mitad de generación quedan en `generating` para siempre — el scheduler solo encola `pending`/`queued`.
3. **`worker_tasks` con status `assigned`** (no `started`): El PASO 0 solo busca `started` > 5 min, no `assigned`.
4. **`document_status` con `*_processing`**: Se re-encolan para OCR (línea 507/531), pero si estaban en `chunking_processing` o `indexing_processing`, deberían re-encolarse para su stage correcto, no para OCR.

**Queries de recovery manual** (ejecutar post-restart si hay tareas atascadas):
```sql
-- 1. Resetear processing_queue huérfana
UPDATE processing_queue SET status = 'pending' WHERE status = 'processing';

-- 2. Resetear insights en generating → pending
UPDATE news_item_insights SET status = 'pending' WHERE status = 'generating';

-- 3. Limpiar worker_tasks huérfanos (assigned o started sin proceso)
DELETE FROM worker_tasks WHERE status IN ('assigned', 'started');

-- 4. Verificar docs en *_processing (la recovery automática los re-encola para OCR)
SELECT document_id, filename, status FROM document_status WHERE status LIKE '%_processing';
```

**IMPORTANTE**: Estas queries deben ejecutarse DESPUÉS de cada `docker compose up` si hubo restart forzado. La recovery automática cubre parte pero no todo.

---

### 🔴 PRIORIDAD 1: BUG — Dashboard inutilizable: endpoints 15-54s (REQ-015.1)
**Severidad**: CRÍTICA — Dashboard completamente roto, ningún panel carga  
**Afecta**: Todos los paneles del dashboard (summary, analysis, documents, workers)  
**Error**: `AxiosError: timeout of 5000ms exceeded` en PipelineDashboard, DocumentsTable, DatabaseStatusPanel, WorkersTable, ErrorAnalysisPanel, PipelineAnalysisPanel, StuckWorkersPanel

**Causa raíz**:
- Queries sync bloquean event loop de uvicorn (20+ queries secuenciales)
- Sin connection pooling (nuevo `psycopg2.connect()` por cada llamada)
- Qdrant full collection scroll en `/api/documents` (itera miles de chunks)
- Sin caché (dashboard recalcula todo desde cero cada request)

**Tiempos medidos**:
| Endpoint | Tiempo | Timeout frontend |
|---|---|---|
| `/api/dashboard/summary` | ~54s | 5s |
| `/api/dashboard/analysis` | ~51s | 10s |
| `/api/documents` | ~15s | 5s |
| `/api/documents/status` | ~16s | 5s |

**Fix propuesto**:
1. Caché en memoria con TTL (30s dashboard, 15s documents)
2. `run_in_executor()` para queries sync en handlers async
3. Eliminar Qdrant scroll del hot path de `/api/documents`
4. Connection pooling (`psycopg2.pool.ThreadedConnectionPool`)
5. Aumentar timeouts frontend (5s→30s) + reducir polling (5s→30s)

**Archivos**: `backend/app.py`, `backend/database.py`, `backend/qdrant_connector.py`, `frontend/src/components/dashboard/*.jsx`

**🔄 Requiere rebuild backend**: Sí → aplicar PROTOCOLO DE RECOVERY POST-RESTART

---

### 🔴 PRIORIDAD 2: BUG — CORS headers ausentes en respuestas 500 (REQ-015.2)
**Severidad**: ALTA — Errores 500 se ven como "CORS blocked", confunde diagnóstico  
**Afecta**: Cualquier endpoint que lance excepción no manejada  
**Error**: `Access-Control-Allow-Origin header is not present on the requested resource`

**Causa raíz**: Excepciones no manejadas generan respuesta 500 que no pasa por CORSMiddleware de FastAPI.

**Fix propuesto**: Exception handler global que incluya CORS headers en respuestas de error.

**Archivos**: `backend/app.py` (exception handler)

**🔄 Requiere rebuild backend**: Sí → aplicar PROTOCOLO DE RECOVERY POST-RESTART (puede combinarse con PRIORIDAD 1 en un solo rebuild)

---

### 🔴 PRIORIDAD 3: BUG — Remanentes SQLite en database.py (migración incompleta)
**Severidad**: ALTA — Métodos explotan en runtime con `'NoneType' object has no attribute 'fetchone'`  
**Afecta**: `list_users`, `get_by_document_id`, `DocumentInsightsStore.get_by_document_id`, `get_done_by_content_hash`, `NewsItemInsightsStore.get_by_news_item_id`  
**Error**: `cursor.execute(...).fetchone()` retorna `None` en psycopg2 (patrón SQLite, no PostgreSQL)

**Causa raíz**: La migración SQLite → PostgreSQL cambió el driver a `psycopg2` y los placeholders (`?` → `%s`), pero no corrigió patrones de API incompatibles:
1. **`cursor.execute().fetchone()`** (5 instancias) — En SQLite `execute()` retorna el cursor; en psycopg2 retorna `None`
2. **`cursor.lastrowid`** (2 instancias, líneas 157, 865) — No funciona en psycopg2; requiere `RETURNING id`
3. **`is_active = 1` / `= 0`** (menor) — Funciona pero debería ser `BOOLEAN` en PostgreSQL

**Instancias a corregir**:
| Línea | Método | Patrón roto |
|---|---|---|
| 232 | `UserDatabase.list_users()` | `.execute(...).fetchall()` |
| 463 | `DocumentStatusStore.get_by_document_id()` | `.execute(...).fetchone()` |
| 1044 | `DocumentInsightsStore.get_by_document_id()` | `.execute(...).fetchone()` |
| 1084 | `DocumentInsightsStore.get_done_by_content_hash()` | `.execute(...).fetchone()` |
| 1307 | `NewsItemInsightsStore.get_by_news_item_id()` | `.execute(...).fetchone()` |
| 157 | `UserDatabase.create_user()` | `cursor.lastrowid` |
| 865 | `NotificationStore.insert()` | `cursor.lastrowid` |

**Fix**: Separar `execute()` de `fetchone()`/`fetchall()`, reemplazar `lastrowid` por `RETURNING id`.

**Archivos**: `backend/database.py`

**🔄 Requiere rebuild backend**: Sí

---

### ✅ PRIORIDAD 0: BUG — Inbox "File not found" + Centralizar ingesta (REQ-016, Fix #56, #57) — COMPLETADO
**Fecha completado**: 2026-03-15
**Solución implementada**: `file_ingestion_service.py` creado + 3 paths refactorizados + `_handle_ocr_task` fix
**Resultado**: 4/4 docs procesados end-to-end (OCR→chunking→indexing→Qdrant)
**Estado**: ESTABLE, no modificar

---

### 🟡 PRIORIDAD 4: BUG — Workers saturan Qdrant en loop de fallos (REQ-015.3)
**Severidad**: MEDIA — Degrada performance de todo el backend  
**Afecta**: Workers de insights + Qdrant  
**Error**: Cientos de `scroll` requests/segundo, workers fallan con "No chunks found" y reintentan

**Causa raíz**: News items sin chunks se encolan para insights, fallan, y se re-encolan en loop.

**Fix propuesto**: Marcar news items sin chunks como error permanente o verificar chunks antes de encolar.

**Archivos**: `backend/app.py` (insights worker + scheduler), `backend/worker_pool.py`

**🔄 Requiere rebuild backend**: Sí → aplicar PROTOCOLO DE RECOVERY POST-RESTART (puede combinarse con PRIORIDAD 1-2 en un solo rebuild)

---

### ~~🔴 PRIORIDAD 5 (antes 4/1): BUG — `LIMIT ?` (SQLite residual en PostgreSQL)~~ ✅ COMPLETADO (2026-03-15)
**Severidad**: ALTA — Bloquea indexing y insights de documentos  
**Afecta**: 2 docs en `error` + cualquier doc que pase por `list_by_document_id`  
**Error**: `not all arguments converted during string formatting`

**Causa raíz**: 5 queries en `database.py` usan `LIMIT ?` (sintaxis SQLite) en vez de `LIMIT %s` (PostgreSQL). psycopg2 no reconoce `?`, deja parámetros sin consumir y lanza el error.

**Fix aplicado**: Cambiado `LIMIT ?` → `LIMIT %s` en las 5 líneas (database.py 515, 997, 1154, 1256, 1312).

**Verificación**:
- [x] 5 `LIMIT ?` reemplazados por `LIMIT %s`
- [x] Backend reconstruido y desplegado
- [x] 0 ocurrencias de `LIMIT ?` en contenedor

---

### ~~🔴 PRIORIDAD 6 (antes 5/2): BUG — Indexing worker NO indexa chunks en Qdrant~~ ✅ COMPLETADO (2026-03-15)
**Severidad**: ALTA — Causa 557 insights "No chunks found" en 13 docs  
**Afecta**: Todos los docs procesados por pipeline async (no sync)  
**Error**: `No chunks found` en insights worker

**Causa raíz**: Las funciones `_handle_indexing_task` (línea 2570) y `_indexing_worker_task` (línea 2863) en `app.py` **nunca llaman a `rag_pipeline.index_chunk_records()`**. Solo marcan el doc como `INDEXING_DONE` y encolan insights, pero los chunks nunca se escriben en Qdrant.

**Flujo roto**:
```
OCR ✅ → Chunking ✅ (crea chunk_records en memoria) → Indexing ❌ (NO escribe a Qdrant) → Insights ❌ ("No chunks found")
```

**Flujo correcto** (solo funciona en `_process_document_sync`, línea 2024):
```
OCR ✅ → Chunking ✅ → Indexing ✅ (rag_pipeline.index_chunk_records()) → Insights ✅
```

**Fix necesario**: El indexing worker debe:
1. Leer `ocr_text` de `document_status`
2. Re-ejecutar chunking (o leer chunks de una tabla staging)
3. Llamar a `rag_pipeline.index_chunk_records(chunk_records)`
4. Solo entonces marcar como `INDEXING_DONE` y encolar insights

**Alternativa más simple**: Re-chunking + indexing desde `ocr_text` guardado en BD (los 13 docs tienen `ocr_text` de 252K-514K chars).

**Fix aplicado**: Indexing worker reconstruye chunks desde ocr_text y llama `rag_pipeline.index_chunk_records()`.

**Verificación**:
- [x] Indexing worker llama a `rag_pipeline.index_chunk_records()`
- [x] Qdrant: 17519 puntos (antes 10053)
- [x] Insights encuentran chunks

---

### ~~Startup Recovery + Protocolo Despliegue~~ ✅ COMPLETADO (2026-03-15)
- [x] `detect_crashed_workers` reescrito: limpia huérfanos, rollback document_status e insights
- [x] PASO 0 scheduler: rollback runtime para workers >5min
- [x] `_initialize_processing_queue` simplificada: solo seed `upload_pending`
- [x] Protocolo documentado en DEPLOYMENT_GUIDE.md (stop → clean DB → rebuild)
- [x] Constantes pipeline_states en handlers, bug fix línea 4956

---

### 🟡 PRIORIDAD 7 (antes 6/3): Reprocesar 2 docs en `error` (post-fix LIMIT)
**Severidad**: MEDIA — Datos perdidos recuperables  
**Afecta**: 2 docs (06-02-26-El Pais, 03-03-26-El Pais) con 86 noticias

**Procedimiento** (después de fix PRIORIDAD 4):
1. Resetear status: `UPDATE document_status SET status='indexing_done', error_message=NULL WHERE status='error'`
2. Re-encolar tareas de indexing en `processing_queue`
3. Verificar que completan sin error

**🔄 Requiere rebuild**: No (solo SQL), pero requiere que PRIORIDAD 5 esté aplicada y backend corriendo

---

### 🟡 PRIORIDAD 8 (antes 7/4): Reprocesar 557 insights con error (post-fix indexing)
**Severidad**: MEDIA — Insights generables una vez chunks existan en Qdrant  
**Afecta**: 13 docs en `indexing_done` con 557 insights "No chunks found"

**Procedimiento** (después de fix PRIORIDAD 5):
1. Re-indexar los 13 docs (chunks → Qdrant)
2. Resetear insights: `UPDATE news_item_insights SET status='pending', error_message=NULL WHERE status='error' AND error_message LIKE '%No chunks%'`
3. Scheduler reconcilia automáticamente (PASO 3.5)
4. Verificar que insights se generan correctamente

**🔄 Requiere rebuild**: No (solo SQL + re-enqueue), pero requiere que PRIORIDAD 6 esté aplicada y backend corriendo
**⚠️ Post-restart**: Si el backend se reinicia mientras insights están `generating`, ejecutar: `UPDATE news_item_insights SET status='pending' WHERE status='generating'`

---

### 🟢 PRIORIDAD 9 (antes 8/5): Despausar documentos en lotes controlados
**Severidad**: BAJA — Feature, no bug  
**Afecta**: 186 docs pausados

**Procedimiento**:
1. Despausar lote de 20-30 docs → `UPDATE document_status SET status = 'upload_pending' WHERE status = 'paused' LIMIT 30`
2. Monitorear pipeline: OCR → Chunking → Indexing → Insights
3. Verificar que dedup por SHA256 funciona (logs: "Reusing insight from text_hash")
4. Si OK, despausar siguiente lote
5. Repetir hasta completar los 186
**Estimación**: ~7-8 lotes, ~2-3 horas total (depende de OCR)

**IMPORTANTE**: Solo ejecutar DESPUÉS de fixes PRIORIDAD 1-6, para que los docs nuevos no caigan en los mismos bugs.

**🔄 Requiere rebuild**: No (solo SQL), pero requiere PRIORIDAD 1-6 aplicadas
**⚠️ Post-restart entre lotes**: Si el backend se reinicia mientras un lote está procesándose, ejecutar PROTOCOLO DE RECOVERY antes de despausar el siguiente lote

---

### 🟢 PRIORIDAD 10 (antes 9/6): Documentar resultados finales
**Objetivo**: Actualizar docs con métricas finales post-procesamiento
- Total noticias extraídas
- Total insights generados vs reutilizados (ahorro de costes)
- Tasa de éxito OCR
- Tiempo total de procesamiento

---

### 🔵 PRIORIDAD 11 (antes 10/7): Features pendientes (post-estabilización)

#### 7a. REQ-014: Mejoras UX Dashboard (v3.1) — 4 sub-peticiones
1. **REQ-014.1**: Agregar stage "Upload" al PipelineAnalysisPanel + estado "paused" visible
2. **REQ-014.2**: Eliminar filtros + secciones colapsables (accordion pattern)
3. **REQ-014.3**: Unificar header duplicado → 1 línea compacta — **avance 2026-03-20**: toolbar único + franja diagnóstico con scroll acotado + tablas en flex restante (ver CONSOLIDATED_STATUS §58)
4. **REQ-014.4**: Zoom semántico multinivel (3 niveles de drill-down en Sankey)

#### 7b. Otros features pendientes
1. **Dashboard Unificado** (BR-11) — Combinar tabla docs + reportes en 1 vista
2. **Dashboard Insights** (FASE 4) — Word cloud, sentiment, topics
3. **Extraer vistas del monolito** — QueryView, DocumentsView, AdminPanel
4. **Testing unitario** — Configurar Jest para frontend

---

## ~~Pasos anteriores~~ (Completados)

### ~~PASO 1: Rebuild y deploy del backend~~ ✅ COMPLETADO
- Reconciliación: 461 registros creados (5 ciclos: 100+100+100+100+61)

### ~~PASO 2: Verificar dedup por SHA256~~ ✅ COMPLETADO
- Dedup implementado en 3 handlers
- Fix psycopg2 en `get_done_by_text_hash()` (database.py)

---

## 🐛 PRIORIDAD ALTA — Pendiente

### BUG: Workers insights sin rate limiting (Fix #55)
- **Problema**: 25 workers llaman a OpenAI sin backoff → 2230+ errores 429 → saturan backend → dashboard inutilizable
- **Solución**: Exponential backoff + jitter + limitar concurrencia insights a 3-5 workers
- **Impacto**: Sin fix, cada vez que hay insights pendientes el dashboard se cae
- **Archivos**: `backend/app.py` (insights handlers), `backend/worker_pool.py`
- [ ] Implementar exponential backoff en llamadas OpenAI
- [ ] Limitar concurrencia de insights workers (max 3-5)
- [ ] Verificar que dashboard responde <2s con insights en proceso

---

## ✅ Completado (2026-03-14/15)
- [x] Frontend modular recuperado: 17 JS/JSX desde source map + 11 CSS desde bundle (2026-03-15) - ESTABLE
- [x] Docker Compose unificado: CPU por defecto, GPU opt-in (Fix #56, 2026-03-15) - ESTABLE
- [x] Refactor submodule → app/ (Fix #55, 2026-03-15) - ESTABLE
- [x] Startup Recovery + Crash Recovery (Fix #52, 2026-03-15) - ESTABLE
- [x] Protocolo de Despliegue Seguro (Fix #53, 2026-03-15) - ESTABLE
- [x] Fix LIMIT ? → LIMIT %s (PRIORIDAD 4, Fix #50) - ESTABLE
- [x] Fix Indexing worker real: index_chunk_records() (PRIORIDAD 5, Fix #51) - ESTABLE
- [x] Startup Recovery + Runtime Crash Recovery (Fix #52) - ESTABLE
- [x] Protocolo de Despliegue Seguro (Fix #53) - ESTABLE
- [x] Constantes pipeline_states + bug fix worker_tasks (Fix #54) - ESTABLE
- [x] Investigación workers: 25 pool, 0-2 útiles, guía diagnóstico documentada (Fix #47) - ESTABLE
- [x] Fix chunk_count bug en indexing worker - ESTABLE
- [x] SOLID Refactor: pipeline_states.py con convención {stage}_{state} - ESTABLE
- [x] Migración BD: todos status convertidos al nuevo esquema - ESTABLE
- [x] Dashboard: scroll fix + nuevos paneles diagnóstico - ESTABLE
- [x] Pipeline verificada end-to-end: 14/14 docs completed - ESTABLE
- [x] 221 documentos pausados para procesamiento controlado - ESTABLE
- [x] Reconciliación insights: PASO 3.5 en scheduler (Fix #44) - ESTABLE
- [x] Inventario BD: 1,987 news items, 1,264 huérfanos, 461 sin insight (Fix #45) - ESTABLE
- [x] Fix login 422 React crash - useAuth.js normaliza detail a string (Fix #46) - ESTABLE
- [x] Fix volumenes Docker apuntando a ruta incorrecta (2026-03-15) - ESTABLE

## 🚫 Congelado (No modificar sin razón crítica)
- ❌ pipeline_states.py - Source of truth para todos los estados
- ❌ Event-Driven OCR Pipeline + Master Scheduler - Corazón del sistema
- ❌ Graceful Shutdown endpoint - Testeado y funcional
- ❌ Convención {stage}_{state} - Estándar adoptado en todo el codebase
- ❌ PASO 3.5 Reconciliación - Idempotente, no requiere cambios
