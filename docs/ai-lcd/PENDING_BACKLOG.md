# Backlog Pendiente - NewsAnalyzer-RAG

> **Fuente única** de pendientes técnicos (mejoras, fixes menores).
> **Última actualización**: 2026-04-07

---

## 🎨 NUEVO: Mejoras de Dashboards (2026-04-07)

### PEND-022: Mejoras Pipeline Dashboard - Aplicar Design System Profesional ✨
**Prioridad**: COMPLETADO ✅  
**Fecha completado**: 2026-04-07  
**Estimación**: 6-8 horas (actual: ~5 horas)  
**Tipo**: UX/UI Improvement

**Descripción completada**:
✅ CSS variables consistentes (paleta de VISUAL_ANALYTICS_GUIDELINES.md)
✅ Tipografía profesional (Fira Code + Fira Sans)
✅ Iconos SVG (Heroicons, no emojis)
✅ Jerarquía visual clara (KPIs destacados)
✅ Accesibilidad WCAG AA
✅ Export functions (CSV/JSON/PNG)
✅ Componente KPICard reutilizable
✅ Progress bar stacked con legend

**Documentación**: 
- `docs/ai-lcd/DASHBOARD_VISUAL_IMPROVEMENTS_PLAN.md`
- `docs/ai-lcd/PEND-022_IMPLEMENTATION_PLAN.md`

**Archivos implementados**:
- ✅ `app/frontend/src/styles/design-tokens.css` (nuevo)
- ✅ `app/frontend/src/components/dashboard/KPICard.jsx` (nuevo)
- ✅ `app/frontend/src/components/dashboard/ExportMenu.jsx` (nuevo)
- ✅ `app/frontend/src/components/PipelineSummaryCard.jsx` (refactorizado)
- ✅ `app/frontend/src/components/dashboard/CollapsibleSection.jsx` (mejorado)
- ✅ `app/frontend/src/components/dashboard/WorkerLoadCard.jsx` (optimizado)
- ✅ `app/frontend/src/components/PipelineDashboard.jsx` (iconos Heroicons)

**Dependencias añadidas**:
- ✅ `@heroicons/react` (2.1.x)
- ✅ `html2canvas` (1.4.x)

**Verificación completada**:
- [x] Contraste mínimo 4.5:1 (WCAG AA)
- [x] Design tokens aplicados consistentemente
- [x] Heroicons SVG instalados y funcionando
- [x] KPICard funcional con hover states
- [x] Export menu operativo (CSV/JSON/PNG)
- [x] Frontend build exitoso (301.61 kB gzip: 99.44 kB)
- [x] Responsive mobile/tablet/desktop
- [x] Keyboard navigation funcional

**Estado**: ESTABLE ✅ - No modificar sin razón crítica

---

### PEND-023: News Analytics Dashboards - Facts + Insights 📰
**Prioridad**: MEDIA  
**Estimación**: 12-16 horas  
**Tipo**: New Feature (Dashboard separado)

**Descripción**:
Crear dos dashboards nuevos para análisis de contenido de noticias (separados del monitoreo de pipeline):

**1. Dashboard Facts** (Documentos indexados):
- KPI Cards: Docs indexados, News extraídas, Chunks, Tiempo avg
- Timeline de ingestión (D3 Area Chart + Brush)
- Treemap por fuente (El Pais, ABC, etc.)
- Tabla de documentos con filtros y sorting
- Performance Heatmap (opcional)

**2. Dashboard Insights** (Análisis IA):
- KPI Cards: Insights totales, Done, Pending, Cost estimado
- Insights Timeline (Multi-line chart)
- Word Cloud de keywords (requiere procesamiento backend)
- Tabla de insights con expandable rows
- Quality Metrics Gauges (opcional)

**Arquitectura**:
```
App.jsx
├── 📊 Pipeline (actual - monitoreo)
├── 📰 News Analytics (NUEVO)
│   ├── Facts (documentos indexados)
│   └── Insights (análisis IA)
├── 🔍 Query
└── 📁 Documents
```

**Documentación**: `docs/ai-lcd/NEWS_ANALYTICS_DASHBOARDS_PROPOSAL.md`

**Backend necesario**:
- Nuevos endpoints `/api/analytics/facts/*` y `/api/analytics/insights/*`
- Procesamiento de keywords para Word Cloud
- Queries optimizadas con filtros y paginación

**Archivos a crear**:
- `app/frontend/src/components/news-analytics/` (carpeta nueva)
- `app/backend/adapters/driving/api/v1/routers/news_analytics.py`

**Verificación**:
- [ ] Separación clara Facts vs Insights
- [ ] Brushing & linking entre visualizaciones
- [ ] Design system consistente con Pipeline Dashboard
- [ ] Responsive en mobile/tablet/desktop
- [ ] Performance <2s render inicial

**Esfuerzo**: Alto  
**Fecha propuesta**: 2026-04-07

---

## 📍 Fuentes de pendientes (consolidado)

| Fuente | Contenido | Ubicación |
|--------|-----------|-----------|
| **Este archivo** | Mejoras técnicas (PEND-XXX) | PENDING_BACKLOG.md |
| **REQUESTS_REGISTRY** | Peticiones usuario (REQ-XXX) | REQUESTS_REGISTRY.md § REQ-014, REQ-021 |

**Peticiones usuario pendientes**: 
- REQ-014 — Mejoras UX Dashboard (4 sub-peticiones). Ver `REQUESTS_REGISTRY.md`
- **REQ-021 — Refactor Backend SOLID + Hexagonal + LangChain** (EN PROGRESO). Ver `REQUESTS_REGISTRY.md`

**No hay listas paralelas**: PLAN_AND_NEXT_STEP.md § Improvements solo referencia este archivo.

---

## Prioridad: Alta

### PEND-018: Estandarizar estados de Insights con prefijo de pipeline
**Descripción**: `document_status` usa canon prefijado por etapa (`ocr_pending`, `indexing_done`, etc.), pero `news_item_insights.status` sigue con estados genéricos (`pending`, `queued`, `generating`, `done`, `error`). Esto complica trazabilidad, logs y representación consistente en dashboard.

**Evidencia (2026-04-07)**:
- En runtime hay mezcla de semánticas (document-level prefijado vs news-level no prefijado).
- El scheduler/worker de insights depende de estos estados para encolar y recuperar tareas en `processing_queue`.
- Durante debugging se observó riesgo operativo cuando la cola no refleja claramente “stage + estado” para insights.

**Canon objetivo (propuesto)**:
1. Definir estados canónicos de insights con prefijo (`insights_pending`, `insights_generating`, `insights_done`, `insights_error`, etc.).
2. Migrar datos en parada controlada (sin requerimiento de zero-downtime).
3. Migrar primero escritura; después ampliar lecturas para contemplar transición corta si hiciera falta.
4. Eliminar estados legacy al confirmar estabilidad post-restart.

**Decisión de implementación**:
- ✅ Hacer migración integral con app detenida (downtime permitido).
- ✅ Evitar capa permanente de traducción old↔new en repositorios.
- ✅ Priorizar claridad operativa sobre compatibilidad prolongada con legacy.

**Ubicación**: `app/backend/app.py`, `app/backend/adapters/driven/persistence/postgres/news_item_repository_impl.py`, `app/backend/adapters/driven/persistence/postgres/dashboard_read_repository_impl.py`, `docs/ai-lcd/*`  
**Esfuerzo**: Medio-Alto  
**Fecha detección**: 2026-04-07

---

### ~~PEND-016: Ingesta fuera de Inbox reingresa errores legacy (estandarización de entradas)~~ ✅ IMPLEMENTADO (2026-04-07)
**Descripción**: Se detectó que un documento viejo (`test_upload.pdf`, `source='upload'`, ingestado 2026-04-02) reaparece en workers OCR durante pruebas de hoy, aunque los 6 archivos de hoy entraron por inbox correctamente. El flujo de retry/reprocess no distingue antiguedad ni canal y puede reactivar entradas legacy inválidas.

**Evidencia (2026-04-06)**:
- `document_status`: 6 registros de hoy (`source='inbox'`) + caso legacy `source='upload'` con `ingested_at=2026-04-02`.
- Archivo legacy: `uploads/a1fff0ff...dffae.pdf`, tamaño 13 bytes, tipo real `ASCII text` (no PDF).
- Logs: retries OCR repetidos para `test_upload.pdf` sin nuevo upload del usuario.

**Hipótesis principal**:
1. El documento inválido fue creado por un camino alterno de upload (API/manual) fuera de inbox.
2. `retry-errors` y/o cola de reproceso reactivan documentos `error` antiguos sin filtro por fecha/canal.
3. La ingesta por upload no deja evidencia en `inbox/processed` (prefijo corto), dificultando trazabilidad operacional.

**Alcance propuesto**:
1. Agregar auditoría de canal de ingesta (campo explícito + reason/event) en reintentos.
2. Filtrar `retry-errors` para excluir automáticamente errores legacy inválidos (o requerir confirmación explícita).
3. Estandarizar upload API al mismo lifecycle operativo de inbox (registro equivalente en processed/audit trail).
4. Definir política de cuarentena para archivos inválidos (no reintentar en loop).

**Mitigación inicial (2026-04-06)**:
- Limpieza puntual en BD del caso `test_upload.pdf` (`document_id=a1fff0ff...dffae`) en: `worker_tasks`, `processing_queue`, `document_stage_timing`, `document_status`, `ocr_performance_log`.
- Archivo movido a cuarentena: `app/local-data/uploads/PEND-016/test_upload__a1fff0ff...dffae.pdf`.
- Corrección puntual de symlink roto para `document_id=91fafac5...8423a` (`source='inbox'`): target actualizado a `91fafac5_23-03-26-El Periodico Catalunya.pdf` (sin sufijo ` 2`).
- Normalización del registro en BD para ese caso: `document_status.filename`, `processing_queue.filename` y `document_stage_timing.metadata.filename` alineados al nombre real del archivo.
- Script de diagnóstico agregado: `app/backend/scripts/check_upload_symlink_db_consistency.py` (read-only por defecto; fixes opcionales con flags explícitos).
- Ejecución global del script sobre 80 symlinks: 1 caso adicional detectado y corregido (`f14f2cf0...947b`, `El Pais 2.pdf` → `El Pais.pdf`) en symlink + BD.
- Estado: **parcialmente mitigado** (se elimina el caso puntual; falta estandarización estructural del canal upload/retry).

- **Trail equivalente a inbox**: cada upload API crea symlink en `uploads/processed/<hash>_archivo.pdf` y evento JSONL en `uploads/audit/ingestion_events.jsonl`.
- **Guardrails de retry/requeue**: `POST /api/documents/{id}/requeue` y `POST /api/workers/retry-errors` detectan automáticamente documentos legacy (`source` en `LEGACY_UPLOAD_CHANNELS` o antigüedad ≥ `LEGACY_UPLOAD_MAX_DAYS`) y bloquean el reintento salvo que se envíe `force_legacy=true` tras validación manual.
- **Auditoría**: los nuevos stage timing metadata incluyen `ingestion_channel` y `force_legacy` para facilitar el seguimiento operativo.

**Ubicación**: `app/backend/app.py`, `app/backend/file_ingestion_service.py`, `docs/ai-lcd/03-operations/*`  
**Esfuerzo**: Medio  
**Fecha detección**: 2026-04-06

---

### PEND-013: `PoolError` en repositorios PostgreSQL (`trying to put unkeyed connection`)
**Descripción**: Los workers OCR/Indexing fallan al iniciar `stage_timing_repository.record_stage_start_sync()` por error de pool al liberar conexión. Impacta procesamiento concurrente y deja tareas en error.

**Evidencia (logs 2026-04-06)**:
- `psycopg2.pool.PoolError: trying to put unkeyed connection`
- Stack: `app.py` (`_ocr_worker_task`, `_indexing_worker_task`) → `stage_timing_repository_impl.py` → `base.py:release_connection`

**Alcance propuesto**:
1. Endurecer `BasePostgresRepository.release_connection()` para manejar conexiones no registradas sin romper workers.
2. Revisar estrategia de pool en `BasePostgresRepository` (pool único compartido y lock de inicialización).
3. Validar en runtime: 0 errores `PoolError` en logs tras redeploy.

**Ubicación**: `app/backend/adapters/driven/persistence/postgres/base.py`, `stage_timing_repository_impl.py`  
**Esfuerzo**: Medio  
**Fecha detección**: 2026-04-06

---

### PEND-014: `pipeline_runtime_kv` rompe refresh por filas tipo tupla
**Descripción**: En startup, `insights_pipeline_control.refresh_from_db()` falla con `tuple indices must be integers or slices, not str` al leer snapshot runtime.

**Evidencia (logs 2026-04-06)**:
- `insights_pipeline_control - ERROR - refresh_from_db: failed to load pipeline_runtime_kv`
- Stack: `pipeline_runtime_store.py:load_full_snapshot` (`r["key"]`, `r["value"]`)

**Alcance propuesto**:
1. Hacer `pipeline_runtime_store.py` compatible con filas `dict` y `tuple`.
2. Validar que `load_full_snapshot()`, `get_pause()` y `get_insights_llm()` no dependan del tipo de cursor.
3. Confirmar en logs de arranque que desaparece el error.

**Ubicación**: `app/backend/pipeline_runtime_store.py`, `app/backend/insights_pipeline_control.py`  
**Esfuerzo**: Bajo  
**Fecha detección**: 2026-04-06

---

### PEND-015: OCR rechaza archivo no-PDF (`UnsupportedImageFormatError`)
**Descripción**: `ocr-service` devuelve 500 cuando recibe contenido que no es PDF aunque el nombre termine en `.pdf`, generando errores repetidos en workers OCR.

**Evidencia (logs 2026-04-06)**:
- `OCRmyPDF failed (500): Input file is not a PDF`
- `UnsupportedImageFormatError`

**Alcance propuesto**:
1. Validación temprana de tipo real de archivo antes de enviar a OCRmyPDF.
2. Clasificar error como permanente de input (sin retries agresivos).
3. Registrar mensaje claro para diagnóstico en dashboard.

**Ubicación**: `app/backend/ocr_service_ocrmypdf.py`, `app/backend/app.py`  
**Esfuerzo**: Medio  
**Fecha detección**: 2026-04-06

### ~~PEND-001: Insights vectorizados en Qdrant~~ ✅ IMPLEMENTADO (2026-03-16)
**Descripción**: Indexar los insights (resúmenes LLM) en Qdrant para mejorar preguntas de alto nivel.

**Implementación**:
- Tras generar insight → `_index_insight_in_qdrant()` → embed(content) → insert en Qdrant con metadata `content_type=insight`, `news_item_id`, `document_id`, `filename`, `text`, `title`
- Búsqueda RAG: chunks e insights en la misma colección; el search devuelve ambos por similitud
- Reindex-all: re-indexa insights existentes tras borrar vectores
- Delete document: borra chunks + insights (mismo `document_id`)

**Archivos**: `app.py` (_index_insight_in_qdrant, _handle_insights_task, _insights_worker_task, run_news_item_insights_queue_job, _run_reindex_all), `qdrant_connector.py` (insert_insight_vector, delete_insight_by_news_item)

---

## Prioridad: Media

### ~~PEND-009: Refactor Backend — SOLID y Single Responsibility~~ ✅ EN PROGRESO (REQ-021)
**Descripción**: Hacer el backend más manejable. `app.py` tiene ~6,700 líneas y mezcla endpoints, lógica de negocio, workers, scheduler y utils. No sigue Single Responsibility ni principios SOLID.

**Estado**: ✅ **Movido a REQ-021** — Refactor Hexagonal + DDD + LangChain/LangGraph  
**Fecha inicio**: 2026-03-31  
**Ver**: `REQUESTS_REGISTRY.md § REQ-021`  
**Documentación**: `02-construction/HEXAGONAL_ARCHITECTURE.md`

---

### PEND-006: Coherencia totales Dashboard — Stage Insights
**Descripción**: En el stage Insights, `total_documents` incluye insights en estado `error`, pero el frontend solo muestra pending/processing/completed. Resultado: `total ≠ pending + processing + completed` (ej.: total 18.834, suma 18.784 → 50 en error).

**Propuesta**:
- **Opción A**: Añadir `error_tasks` al stage y mostrarlo en la UI (pendientes/procesando/completados/errores).
- **Opción B**: Excluir errores del total: `total = pending + processing + completed` (errores aparte).

**Ubicación**: `app.py` § dashboard analysis (query Insights), `PipelineAnalysisPanel.jsx`  
**Esfuerzo**: Bajo  
**Fecha detección**: 2026-03-17

---

### PEND-007: Coherencia totales Dashboard — Stage Upload
**Descripción**: En Upload, `total_documents = max(upload_total, total_documents, inbox_count)` representa "documentos en el sistema", no tareas en la etapa. Resultado: total 251 vs suma 1 (pending+processing+completed).

**Propuesta**:
- **Opción A**: Cambiar semántica: `total_documents` = tareas en la etapa (pending+processing+completed+paused) para consistencia con otros stages.
- **Opción B**: Mantener total = docs en sistema pero añadir label/tooltip "Total documentos" vs "Tareas en etapa".

**Ubicación**: `app.py` § dashboard analysis (Upload Stage)  
**Esfuerzo**: Bajo  
**Fecha detección**: 2026-03-17

---

### ~~PEND-008: Workers vs Processing — Indexing Insights~~ ✅ IMPLEMENTADO (2026-03-17)
**Descripción**: Gráfica de workers mostraba menos que "en progreso" en pipeline. Causa: insert en `worker_tasks` era non-fatal.

**Solución aplicada**:
1. **indexing_insights**: claim (UPDATE) + insert worker_tasks en misma transacción (mismo conn). Si insert falla → rollback, no hay insight huérfano.
2. **insights**: mismo patrón — insert antes de commit; si falla → rollback.
3. **Recovery**: detect_crashed_workers resetea insights con status='indexing' sin worker_tasks → 'done' (retry).

**Ubicación**: `worker_pool.py`, `app.py` § detect_crashed_workers

---

### PEND-002: Botón Reindex en Dashboard
**Descripción**: Añadir botón en la UI para reindexar todos los documentos (actualmente solo vía API).

**Beneficio**: Tras cambiar `EMBEDDING_MODEL` o prefijo de instrucción, el usuario puede reindexar sin usar curl/Swagger.

**Dependencias**:
- [x] Endpoint `POST /api/admin/reindex-all` implementado
- [ ] Componente frontend (Admin panel o DatabaseStatusPanel)

**Esfuerzo**: Bajo  
**Referencia**: `app.py` línea ~4279

---

### PEND-010: Routers admin/dashboard sin repositorios hexagonales
**Descripción**: `adapters/driving/api/v1/routers/admin.py` y `dashboard.py` siguen importando `document_status_store`, `news_item_store` y helpers legacy de `app.py`. Esto impide eliminar el store y duplica la lógica de integridad, totales e insights que ya exponen `DocumentRepository`, `StageTimingRepository`, `NewsItemRepository` y `WorkerRepository`.

**Alcance**:
- Reemplazar conexiones directas (`document_status_store.get_connection()`, `news_item_insights_store`) por puertos hexagonales.
- Extraer cálculos de métricas (totales por etapa, integridad de archivos/insights, inbox stats) a servicios reutilizables para que los routers se limiten a orquestar.
- Ajustar imports/DI para que los routers no requieran `import app as app_module` salvo para caches globales inevitables.

**Actualización 2026-04-06**: Se creó `ReportService` y se migraron `generate_daily_report_for_date`, `generate_weekly_report_for_week` y `check_workers_script.py` a los puertos hexagonales (`DocumentRepository`, `PostgresWorkerRepository`, `PostgresNewsItemRepository`). Los jobs y utilidades de reportes ya no dependen de `document_status_store`, lo que reduce el alcance de legacy pendiente en este item.
**Actualización 2026-04-07**:
- Se retiraron rutas `"/api/legacy/dashboard/*"` y `"/api/legacy/workers/status"` de `app.py` (ya no quedan endpoints legacy publicados).
- `dashboard.py` ya opera vía `DashboardMetricsService` + `DashboardReadRepository` (hexagonal).
- `documents.py`, `workers.py` y `news_items.py` dejaron de importar stores legacy y ahora consumen `news_item_repository` para métricas/estado de insights y listados.
- **Gap restante**: `reports.py`, `notifications.py`, `auth.py` siguen usando capas legacy (`daily_report_store`, `weekly_report_store`, `notification_store`, `db`) y deben migrarse a puertos/adapters equivalentes para cerrar 100% hexagonal.

**Prioridad**: Media (bloquea el objetivo AI-LCD de “fuente única”).  
**Archivos**: `routers/admin.py:1-320`, `routers/dashboard.py:1-520`.  
**Dependencia**: Ninguna (repos nuevos ya disponibles).

---

### ~~PEND-011: Auditoría de datos para admin/dashboard antes de migrar~~ ✅ IMPLEMENTADO (2026-04-07)
**Resultado**:
- `docs/ai-lcd/DASHBOARD_REFACTOR_PLAN.md` §5 documenta la matriz completa “métrica → fuente → puerto” para summary/analysis/integrity/pipeline.
- Se agregó checklist en `TESTING_DASHBOARD_INTERACTIVE.md` para comparar snapshots y se dejó constancia de que el snapshot “after” (2026-04-07) es la referencia oficial aceptada.
- `PLAN_AND_NEXT_STEP.md` y `CONSOLIDATED_STATUS.md` referencian esta auditoría como cerrada, dejando PEND-010 como único pendiente de la línea.

**Notas**:
- No se capturó snapshot “before” porque el equipo acordó que bastaba con documentar el “after” válido una vez que los routers hexagonales estuvieran en uso estable.
- El entregable sirve como baseline para futuras migraciones en `admin.py`/`dashboard.py`.

---

### ~~PEND-012: Ejecutar lote de pruebas tras migraciones API~~ ✅ IMPLEMENTADO (2026-04-07)
**Resultado**:
- Smoke suite ejecutado vía `TOKEN=<jwt admin> ./scripts/run_api_smoke.sh`; log completo en `smoke_1.log`.
- Snapshot estructurado `docs/ai-lcd/artifacts/dashboard_2026-04-07_after.json` con respuestas 200 de `/api/documents`, `/api/workers/status`, `/api/dashboard/{summary,analysis}`, `/api/admin/data-integrity`.
- `docs/ai-lcd/TESTING_DASHBOARD_INTERACTIVE.md` documenta los valores clave y enlaza tanto el log como el JSON.
- PEND-010 mantiene prioridad, pero ya no bloquea evidencia: los routers v2 quedaron validados contra producción local.

**Notas**:
- El equipo aceptó omitir el snapshot “before” porque los endpoints legacy ya no estaban publicados; el “after” sirve como única fuente de verdad.
- Próximos cambios mayores deberán generar un nuevo snapshot siguiendo el mismo formato.

---

### PEND-017: Endpoints legacy duplicados en `app.py` tras migrar routers
**Descripción**: Aunque `/api/documents/*` y `/api/workers/*` ya se sirven a través de los routers (`adapters/driving/api/v1/routers/*.py`), los handlers originales siguen definidos en `app/backend/app.py` (`@app.post("/api/documents/{document_id}/requeue")`, `@app.post("/api/workers/retry-errors")`, etc.) y continúan importando `document_status_store`. FastAPI registra ambos para la misma ruta y solo el último declarado responde, lo que genera divergencias silenciosas (el router usa repositorios hexagonales mientras que el handler legacy sigue tocando SQL directo y no escribe en `document_stage_timing`).

**Evidencia (2026-04-06)**:
- `app/backend/app.py:3481-4088` mantiene los endpoints de requeue/retry/delete y 24 referencias activas a `document_status_store` (`rg -c "document_status_store" app/backend/app.py` → 24).
- Los routers equivalentes (`adapters/driving/api/v1/routers/documents.py` y `workers.py`) ya usan `DocumentRepository`, `StageTimingRepository` y `WorkerRepository`.
- No existe nota en la doc AI-LCD que marque los handlers legacy como “solo referencia” ni una lista de rutas que deben deshabilitarse.
- **Seguimiento 2026-04-07**: el smoke script (`scripts/run_api_smoke.sh`) devolvió `404 Not Found` en `GET /api/documents` a pesar de usar un token válido porque FastAPI siguió registrando solo los handlers legacy (los routers v2 no cargaron al arrancar, ver logs `⚠️ Could not load modular routers: cannot import name 'TaskType'...`). Tras exportar `TaskType` en `core/domain/value_objects/__init__.py`, es necesario reiniciar el backend para que los routers v2 tomen control y el 404 desaparezca.

**Alcance propuesto**:
1. Deshabilitar o renombrar los endpoints legacy (ej. moverlos a `/legacy/*`) una vez que el smoke suite confirme que las versiones nuevas funcionan.
2. Revisar `app/backend/app.py` para eliminar dependencias residuales de `document_status_store` en rutas públicas.
3. Actualizar la doc AI-LCD (PLAN y BACKLOG) para indicar explícitamente qué rutas quedan “solo legacy” antes de borrar el store.

**Prioridad**: Media (bloquea la eliminación del store y puede ocultar bugs, porque las rutas legacy ignoran `StageTimingRepository`).  
**Dependencia**: PEND-012 — cumplida el 2026-04-07 con `smoke_1.log` + `dashboard_2026-04-07_after.json`; ya se puede proceder a retirar los handlers legacy.

## Prioridad: Baja

### PEND-004: Qdrant healthcheck
**Descripción**: Healthcheck fiable para el contenedor Qdrant (imagen mínima sin curl/wget).

**Dependencias**: Ninguna  
**Esfuerzo**: Bajo  
**Referencia**: PLAN_AND_NEXT_STEP.md § Improvements Pendientes #5

---

### PEND-005: Exponer llm_source en API de insights
**Descripción**: Asegurar que `llm_source` (openai/perplexity/ollama) se devuelva en todos los endpoints que listan o devuelven insights.

**Estado**: Parcialmente hecho — `get_by_news_item_id` y `list_by_document_id` ya incluyen `llm_source`. Verificar endpoints REST que consumen estos datos.

**Esfuerzo**: Muy bajo

---

## Resumen por prioridad

| Prioridad | Items | Esfuerzo total |
|-----------|-------|----------------|
| Alta      | 4     | Medio          |
| Media     | 3     | Bajo-Medio     |
| Baja      | 2     | Muy bajo       |

---

## Dependencias entre items

```
PEND-001 ✅ Completado

PEND-002 (Botón Reindex)
  └── Requiere: endpoint reindex ✅

PEND-006 (Insights: total ≠ sum)
  └── Independiente — añadir error_tasks o ajustar total

PEND-007 (Upload: total = docs sistema)
  └── Independiente — clarificar semántica total_documents

PEND-008 ✅ (Workers vs processing) — claim+insert atómico

PEND-004 (Qdrant healthcheck)
  └── Independiente

PEND-005 (llm_source en API)
  └── Independiente (mayormente hecho)

PEND-009 (Backend refactor SOLID)
  └── Independiente — refactor incremental, no bloquea otras tareas

PEND-011 ✅ (Auditoría admin/dashboard, 2026-04-07)
  └── Proporciona la matriz “métrica → fuente → puerto” necesaria para PEND-010

PEND-010 (Migrar routers admin/dashboard)
  └── Desbloquea eliminación del store legacy; respaldado por PEND-011 (doc) y PEND-012 (smoke)

PEND-012 ✅ (Ejecución de pruebas, 2026-04-07)
  └── Evidencia en `smoke_1.log` + `docs/ai-lcd/artifacts/dashboard_2026-04-07_after.json`
```

> **Nota**: No se incluyen providers de embeddings vía API (OpenAI, Perplexity) en el backlog.

---

## Referencias

- **Pipeline**: `PIPELINE_GLOSARIO.md`
- **LLM/Insights**: `02-construction/OPENAI_INTEGRATION.md`
- **Plan general**: `PLAN_AND_NEXT_STEP.md`
