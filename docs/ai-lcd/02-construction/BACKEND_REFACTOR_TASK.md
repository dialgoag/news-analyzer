# PEND-009: Refactor Backend — SOLID y Single Responsibility

> **Objetivo**: Hacer el backend más manejable, reduciendo archivos monolíticos y aplicando principios SOLID.
>
> **Estado**: Pendiente  
> **Prioridad**: Media  
> **Esfuerzo**: Alto (4-8 horas, múltiples sesiones)  
> **Última actualización**: 2026-03-18

---

## 1. Análisis del estado actual

### 1.1 Métricas de tamaño

| Archivo | Líneas | Problema |
|---------|--------|----------|
| `app.py` | **6,485** | Monolito: endpoints, lógica de negocio, workers, scheduler, utils |
| `database.py` | **1,480** | 10+ stores en un solo archivo |
| `rag_pipeline.py` | 809 | Aceptable |
| `worker_pool.py` | 447 | Aceptable |

**Total backend**: ~20,859 líneas. `app.py` concentra ~31% del código.

### 1.2 Responsabilidades mezcladas en `app.py`

| Responsabilidad | Líneas aprox. | Funciones/Clases |
|-----------------|----------------|------------------|
| **Parsing/Utils** | ~300 | `parse_news_date_from_filename`, `_normalize_text_for_hash`, `segment_news_items_from_text`, `detect_document_type`, `extract_*_fields` |
| **OCR pipeline** | ~400 | `_extract_ocr_only`, `_handle_ocr_task`, `_ocr_worker_task` |
| **Chunking** | ~150 | `_perform_chunking`, `_handle_chunking_task`, `_chunking_worker_task` |
| **Indexing** | ~200 | `_perform_indexing`, `_handle_indexing_task`, `_indexing_worker_task` |
| **Insights** | ~500 | `_insights_worker_task`, `_handle_insights_task`, `_index_insight_in_qdrant`, `_handle_indexing_insights_task` |
| **Master scheduler** | ~600 | `master_pipeline_scheduler`, PASO 0-6 |
| **Queue/Recovery** | ~200 | `_initialize_processing_queue`, `detect_crashed_workers` |
| **API Auth** | ~150 | `login`, `get_current_user_info`, `list_users`, `create_user`, etc. |
| **API Documents** | ~400 | `upload_document`, `list_documents`, `get_documents_status`, `requeue_document`, `delete_document` |
| **API Dashboard** | ~600 | `get_dashboard_summary`, `get_dashboard_analysis` (queries inline) |
| **API Workers** | ~300 | `workers_health_check`, `retry_error_workers`, `get_workers_status` |
| **API Reports/Notifications** | ~400 | `list_daily_reports`, `list_weekly_reports`, `list_notifications`, etc. |
| **API Backup** | ~100 | `get_backup_status`, `list_backup_providers` |
| **Cache** | ~50 | `_cache_get`, `_cache_set` |
| **Startup/Shutdown** | ~100 | `startup_event`, `shutdown_event` |

### 1.3 Violaciones SOLID identificadas

| Principio | Violación |
|-----------|-----------|
| **SRP (Single Responsibility)** | `app.py` hace: routing, lógica de negocio, workers, scheduler, parsing, cache, recovery. |
| **OCP (Open/Closed)** | Añadir un nuevo stage al pipeline requiere modificar `master_pipeline_scheduler` y múltiples handlers. |
| **DIP (Dependency Inversion)** | Endpoints llaman directamente a stores y servicios concretos; no hay abstracciones. |
| **ISP (Interface Segregation)** | No aplica directamente; los stores están bien segregados. |

### 1.4 `database.py` — Stores consolidados

- `UserDatabase`, `DocumentStatusStore`, `ProcessingQueueStore`
- `DailyReportStore`, `WeeklyReportStore`, `NotificationStore`
- `DocumentInsightsStore`, `NewsItemStore`, `NewsItemInsightsStore`

**Problema**: Un solo archivo con 10+ clases. Mantenible pero podría dividirse por dominio.

---

## 2. Estructura objetivo (referencia)

> **Fuente**: `DASHBOARD_REFACTOR_PLAN.md` § FASE 2

```
backend/
├─ app.py (<200 líneas — solo FastAPI + mount de routers)
├─ controllers/
│   ├─ document_controller.py
│   ├─ insights_controller.py
│   ├─ dashboard_controller.py
│   ├─ workers_controller.py
│   └─ auth_controller.py
├─ services/
│   ├─ ocr_service.py (ya existe)
│   ├─ insights_service.py
│   ├─ dashboard_service.py
│   └─ notification_service.py
├─ repositories/
│   ├─ document_repository.py
│   ├─ insights_repository.py
│   └─ worker_repository.py
├─ schedulers/
│   ├─ master_pipeline_scheduler.py
│   └─ backup_scheduler.py (ya existe)
└─ utils/
    ├─ parsers.py (segment_news_items, detect_document_type, extract_*)
    └─ formatters.py
```

---

## 3. Estrategia de refactor (incremental)

1. **NO romper funcionalidad**: Refactor por capas, verificar en cada paso.
2. **Extraer primero lo más independiente**:
   - `utils/parsers.py` — funciones puras de parsing
   - `schedulers/master_pipeline_scheduler.py` — extraer de app.py
3. **Luego por dominio**:
   - `controllers/` + `services/` para dashboard (queries pesadas)
   - `controllers/` para documents, workers, auth
4. **database.py**: Opcional dividir por dominio (document_*, user_*, report_*).

---

## 4. Referencias cruzadas

| Documento | Sección |
|----------|---------|
| `DASHBOARD_REFACTOR_PLAN.md` | FASE 2: Backend SOLID Refactor |
| `REQUESTS_REGISTRY.md` | REQ-007: "Backend SOLID: POSPUESTO para otra sesión" |
| `SESSION_LOG.md` | Sesión 11: Arquitectura Modular (SOLID) — aplicado a frontend |
| `PENDING_BACKLOG.md` | PEND-009 |

---

## 5. Verificación post-refactor

- [ ] Backend levanta sin errores
- [ ] Todos los endpoints responden 200/201 según contrato
- [ ] Master pipeline scheduler ejecuta cada 10s
- [ ] Workers OCR/Chunking/Indexing/Insights operativos
- [ ] Dashboard carga summary y analysis
- [ ] Sin regresiones en tests manuales

---

## 6. Riesgos y mitigación

| Riesgo | Mitigación |
|--------|------------|
| Regresiones en pipeline | Refactor incremental; verificar cada extracción |
| Imports circulares | Estructura en capas: utils → repositories → services → controllers |
| Tiempo subestimado | Dividir en sub-tareas (PEND-009.1, PEND-009.2, etc.) |
