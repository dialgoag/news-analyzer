# Backlog Pendiente - NewsAnalyzer-RAG

> **Fuente única** de pendientes técnicos (mejoras, fixes menores).
> **Última actualización**: 2026-03-31

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

_(ninguna pendiente)_

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
| Alta      | 0     | —              |
| Media     | 5     | Bajo + Alto    |
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
```

> **Nota**: No se incluyen providers de embeddings vía API (OpenAI, Perplexity) en el backlog.

---

## Referencias

- **Pipeline**: `PIPELINE_GLOSARIO.md`
- **LLM/Insights**: `02-construction/OPENAI_INTEGRATION.md`
- **Plan general**: `PLAN_AND_NEXT_STEP.md`
