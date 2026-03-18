# API Dashboard — Referencia para Frontend

> **Fecha**: 2026-03-17  
> **Propósito**: Documentar contratos de API y estructura de datos para REQ-014 (UX Dashboard).

---

## 1. Endpoints Principales

| Endpoint | Cache TTL | Uso |
|----------|-----------|-----|
| `GET /api/dashboard/summary` | 15s | Resumen global (files, news, ocr, chunking, indexing, insights) |
| `GET /api/dashboard/analysis` | 15s | Pipeline detallado, workers, errores, BD |
| `GET /api/documents` | 10s | Lista documentos |
| `GET /api/workers/status` | 10s | Workers activos + pool |

---

## 2. Pipeline Analysis — `pipeline.stages`

Cada stage tiene:

```ts
interface PipelineStage {
  name: string;                    // "OCR" | "Chunking" | "Indexing" | "Insights"
  total_documents: number;         // Total unidades (docs o news_items según etapa)
  pending_tasks: number;
  processing_tasks: number;
  completed_tasks: number;
  ready_for_next: number;
  blockers: Array<{ reason: string; count: number; solution: string }>;
  // Solo Insights (opcional):
  granularity?: "news_item";       // Indica que la unidad es news_item, no documento
  docs_with_all_insights_done?: number;   // Docs con todos los insights completados
  docs_with_pending_insights?: number;     // Docs con al menos un insight pendiente
}
```

### Granularidad por etapa

| Stage | Granularidad | total_documents = | Campos adicionales |
|-------|--------------|-------------------|-------------------|
| OCR | documento | COUNT(document_status) | — |
| Chunking | documento | processing_queue (chunking) | `total_chunks`, `news_items_count` (chunks internos por news_item) |
| Indexing | documento | processing_queue (indexing) | `total_chunks`, `news_items_count` |
| **Insights** | **news_item** | COUNT(news_item_insights) | `docs_with_all_insights_done`, `docs_with_pending_insights` |

**Chunking/Indexing**: Procesamiento por documento; internamente los chunks se generan por news_item. `total_chunks` = SUM(num_chunks), `news_items_count` = COUNT(news_items).

**Insights**: `pending + processing + completed + error` = total news_items. Actualmente el API no expone `error_tasks`; si hay errores, `total ≠ pending + processing + completed`. Ver PEND-006.

**Indexing Insights**: `pending + processing + completed` = total (insights done/indexing con content). Coherente.

---

## 3. Workers — `workers.active_list` / `workers.stuck_list`

```ts
interface WorkerRow {
  worker_id: string;
  worker_type: string;
  task_type: "ocr" | "chunking" | "indexing" | "insights";
  document_id: string;    // Para insights: "insight_{news_item_id}"
  filename: string | null;  // Backend resuelve vía news_item_insights para insights
  status: string;
  started_at: string | null;
  execution_time_minutes: number;
  is_stuck: boolean;
  timeout_limit: number;
  progress_percent: number;
}
```

**Nota**: Para `task_type === "insights"`, `document_id` tiene formato `insight_{news_item_id}`. El backend ya resuelve `filename` desde `news_item_insights`; si viene null, mostrar `document_id` como fallback.

---

## 4. Dashboard Summary — `insights`

```ts
insights: {
  total: number;        // Estimado (expected_total_news)
  done: number;
  pending: number;
  errors: number;
  percentage_done: number;
  parallel_workers: number;
  eta_seconds: number;
}
```

Fuente: `news_item_insights` JOIN `news_items` (cadena doc→news→insight válida).

---

## 5. IDs Compuestos — Insights

| Contexto | ID | Ejemplo |
|----------|-----|---------|
| document_status | document_id | `abc123` |
| processing_queue | document_id | `abc123` |
| worker_tasks (ocr/chunk/index) | document_id | `abc123` |
| **worker_tasks (insights)** | **document_id = "insight_{news_item_id}"** | `insight_xyz789` |
| **errors.groups (insights)** | **document_ids = "insight_{news_item_id}"** | `insight_xyz789` |
| news_item_insights | news_item_id + document_id | `xyz789`, `abc123` |

---

## 5.5. Análisis de Errores — `analysis.errors`

```ts
errors: {
  real_errors: number;
  shutdown_errors: number;
  total_errors: number;
  groups: Array<{
    error_message: string;
    stage: string;           // "ocr" | "chunking" | "indexing" | "insights" | "upload" | "unknown"
    count: number;
    cause: string;
    can_auto_fix: boolean;
    document_ids: string[];  // Para insights: "insight_{news_item_id}"
    filenames: string[];
  }>;
}
```

**Fuentes**: `document_status` (OCR, Chunking, Indexing, Upload) + `news_item_insights` (stage="insights").  
**Retry**: `POST /api/workers/retry-errors` acepta `document_ids` con IDs de documento o `insight_{news_item_id}`. Ver CONSOLIDATED_STATUS §94.

---

## 6. Timeouts parametrizables

Para entornos lentos o con muchos datos, los timeouts de API se pueden aumentar vía variables de entorno:

| Variable | Default | Uso |
|----------|--------|-----|
| `VITE_API_TIMEOUT_MS` | 60000 (60s) | GET: summary, analysis, workers, documents |
| `VITE_API_TIMEOUT_ACTION_MS` | 90000 (90s) | POST: retry-errors, requeue |

Ejemplo `.env` (solo nombres, sin valores reales):
```
VITE_API_TIMEOUT_MS=120000
VITE_API_TIMEOUT_ACTION_MS=120000
```

El banner de error del dashboard incluye botón **Reintentar** y sugerencia de aumentar timeouts.

---

## 7. Referencias Técnicas

- `PIPELINE_FULL_AUDIT.md` — Auditoría completa pipeline
- `INSIGHTS_PIPELINE_REVIEW.md` — Flujo insights, IDs, master scheduler
- `DATABASE_DESIGN_REVIEW.md` — Diseño BD, convención estados
- `D3_SANKEY_REFERENCE.md` — Mejoras Sankey (REQ-014)
