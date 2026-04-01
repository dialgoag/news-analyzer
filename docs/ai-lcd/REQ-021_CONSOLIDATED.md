# 🎯 REQ-021: Backend Refactor - Estado Consolidado

## Resumen Ejecutivo

**Objetivo**: Refactorizar backend monolítico (app.py 6,718 líneas) a **Hexagonal Architecture + DDD + LangChain/LangGraph/LangMem**

**Estado Global**: Fase 5 ✅ COMPLETADA + Fix #112 (Timestamps) ✅

---

## ✅ Fases Completadas

### Fase 0: Documentación ✅
- Arquitectura hexagonal diseñada
- DDD patterns definidos
- Event-driven integration planificada

### Fase 1: Domain Model ✅ (Fix #110)
**Entities**:
- `Document`: Aggregate root (lifecycle, validations)
- `NewsItem`: Child entity (content, embeddings)
- `Worker`: Worker lifecycle management

**Value Objects**:
- `DocumentId` / `NewsItemId`: Typed identifiers
- `TextHash`: SHA256 immutable hash
- `PipelineStatus`: Composable status (StageEnum + StateEnum + TerminalStateEnum)

### Fase 2: Repositories ✅ (Fix #110)
**Ports** (interfaces abstractas):
- `DocumentRepository`: Document CRUD
- `WorkerRepository`: Worker + task management
- `InsightsRepository`: Insights persistence
- `NewsItemRepository`: News CRUD (parcial)
- `StageTimingRepository`: Stage timing tracking

**Adapters** (implementaciones):
- `PostgresDocumentRepository`: 504 líneas
- `PostgresWorkerRepository`: 400+ líneas
- `PostgresStageTimingRepository`: 330 líneas

### Fase 3: LLM Infrastructure ✅ (Fix #109)
- LangChain integrado
- LangGraph para workflows
- LangMem para memory/history
- Testing suite completo (31/31 tests ✅)

### Fase 5: Workers + Scheduler ✅ (Fix #111 + #112)

**5A-5D**: Migración workers a repositories ✅

**5E**: DocumentStatusStore → DocumentRepository ✅ (Fix #111)
- 9 endpoints/workers migrados
- SQL fixes (TRUE→1, created_at→ingested_at)
- 5/5 tests E2E pasan

**Fix #112**: Sistema Unificado de Timestamps ✅
- Nueva tabla `document_stage_timing` (document-level + news-level)
- 4 workers integrados (OCR, Chunking, Indexing, Insights)
- Backfill 620 registros
- Triggers automáticos en 7 tablas
- Performance analytics habilitadas

---

## 🚀 Siguiente Paso: Fase 6 - API Routers

**Objetivo**: Extraer endpoints de `app.py` (~1,500 líneas REST) a routers modulares

### Estructura Propuesta

```
app/backend/adapters/driving/api/
├── routers/
│   ├── documents_router.py     # /api/documents/*
│   ├── workers_router.py        # /api/workers/*
│   ├── dashboard_router.py      # /api/dashboard/*
│   ├── insights_router.py       # /api/insights/*
│   └── admin_router.py          # /api/admin/*
└── dependencies.py              # Dependency injection
```

### Plan de Migración

**Paso 1**: Crear `DocumentsRouter`
- `GET /api/documents` → lista documentos
- `POST /api/documents/upload` → upload nuevo documento
- `GET /api/documents/{id}/download` → descarga PDF
- `POST /api/documents/{id}/reprocess` → marca para reprocesar
- `GET /api/documents/{id}/segmentation-diagnostic` → diagnóstico

**Paso 2**: Crear `WorkersRouter`
- `GET /api/workers/status` → estado de workers
- `GET /api/workers/{id}/logs` → logs de worker

**Paso 3**: Crear `DashboardRouter`
- `GET /api/dashboard/summary` → resumen
- `GET /api/dashboard/analysis` → análisis
- `GET /api/dashboard/parallel-data` → datos pipeline

**Paso 4**: Crear `AdminRouter`
- `POST /api/admin/insights-pipeline/pause` → pausar insights
- `POST /api/admin/insights-pipeline/resume` → resumir insights
- `PUT /api/admin/insights-pipeline/llm-source` → cambiar LLM

### Beneficios

- ✅ Separación clara de responsabilidades
- ✅ Dependency injection explícita
- ✅ Testing simplificado (mock repositories)
- ✅ app.py reducido de 6,718 → ~500 líneas
- ✅ Routers reutilizables

---

## 📊 Progreso REQ-021

| Fase | Estado | Fix | Líneas | Archivos |
|------|--------|-----|--------|----------|
| 0. Documentación | ✅ | - | +2,000 | 5 |
| 1. Domain Model | ✅ | #110 | +800 | 8 |
| 2. Repositories | ✅ | #110 | +2,500 | 10 |
| 3. LLM Infrastructure | ✅ | #109 | +3,000 | 15 |
| 5. Workers + Scheduler | ✅ | #111, #112 | +2,000 | 12 |
| **6. API Routers** | ⏳ | - | ~1,500 | 5 |
| 7. Testing + Deprecate | ⏳ | - | TBD | TBD |

**Completado**: ~10,300 líneas (60% del refactor)  
**Pendiente**: ~3,000 líneas (40% restante)

---

## 🔒 Congelado (No Modificar Sin Razón Crítica)

| Componente | Fix | Razón | Última Modificación |
|------------|-----|-------|---------------------|
| Event-Driven OCR Pipeline | #5, #6 | Corazón del sistema | 2026-03-03 |
| Master Pipeline Scheduler | #15, #32 | Orquesta todo | 2026-03-05 |
| PostgreSQL Migration | #22 | Migración sensible | 2026-03-13 |
| Deduplication Logic | #4, #46 | SHA256 dedup delicado | 2026-03-05 |
| Domain Entities | #110 | Base del refactor | 2026-03-31 |
| DocumentRepository | #111 | 9 endpoints dependen | 2026-04-01 |
| **StageTimingRepository** | **#112** | **Auditabilidad crítica** | **2026-04-01** |

---

## 📝 Documentación de Timestamp System

**Archivos de referencia**:
- `TIMESTAMP_SYSTEM_DESIGN.md` - Diseño técnico completo
- `UNIFIED_TIMESTAMP_SYSTEM_COMPLETE.md` - Resumen ejecutivo + queries
- `IMPACT_ANALYSIS_MIGRATION_018.md` - Análisis de impacto
- `validate_migration_018.py` - Script de validación

**Queries útiles**: Ver `UNIFIED_TIMESTAMP_SYSTEM_COMPLETE.md` § Queries Útiles

---

## ✅ Todos los TODOs Completados

- ✅ Auditar tablas para timestamps
- ✅ Diseñar estándar global
- ✅ Crear migration 018
- ✅ Actualizar repositories
- ✅ Actualizar Document entity
- ✅ Actualizar workers (4 workers)
- ✅ Testing completado
- ✅ Documentación actualizada

**Sistema funcionando en producción** sin errores ✅
