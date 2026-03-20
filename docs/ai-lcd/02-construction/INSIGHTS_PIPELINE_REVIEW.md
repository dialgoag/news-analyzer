# Revisión Pipeline Insights + Master Scheduler

> **Fecha**: 2026-03-17  
> **Propósito**: Verificar coherencia pipeline insights, IDs, y master scheduler antes de REQ-014.5.

---

## 1. Flujo de Insights (Diseño Actual)

| Fuente | Tabla | Consumidor |
|--------|-------|------------|
| Indexing completado | `news_item_insights` (enqueue) | GenericWorkerPool |
| Reconciliación (PASO 3.5) | `news_item_insights` (enqueue) | GenericWorkerPool |
| **processing_queue** | — | **No se usa para insights** |

**Conclusión**: Insights NO usan `processing_queue`. El master scheduler nunca encola insights ahí. Es correcto por diseño (ver DATABASE_DESIGN_REVIEW.md).

---

## 2. Master Scheduler

| PASO | Qué hace | Insights |
|------|----------|----------|
| 0 | Cleanup huérfanos | Excluye insights (Fix #69) ✅ |
| 2 | Encola OCR | — |
| 3 | Encola Chunking, Indexing | — |
| 3.5 | Reconciliación → news_item_insights | ✅ |
| 4 | Marca news_item_insights pending | ✅ |
| 5 | Documentos completed (all insights done) | ✅ |
| 6 | Despacha desde processing_queue | OCR, Chunking, Indexing; **insights nunca están** |

**Conclusión**: El master no encola insights en processing_queue. Los workers de insights los obtienen del GenericWorkerPool, que lee de `news_item_insights` directamente.

---

## 3. Consistencia de IDs

| Componente | document_id | Ejemplo |
|------------|-------------|---------|
| **processing_queue** (ocr/chunk/index) | doc_id real | `abc123` |
| **processing_queue** (insights) | — | No se usa |
| **worker_tasks** (ocr/chunk/index) | doc_id real | `abc123` |
| **worker_tasks** (insights) | `insight_{news_item_id}` | `insight_xyz789` |
| **news_item_insights** | document_id (doc padre) | `abc123` |

**Riesgo mitigado**: Fix #69 excluye insights del reset orphan porque `processing_queue.document_id` ≠ `worker_tasks.document_id` para insights.

---

## 4. Dashboard Insights

**Solución aplicada**: Summary y analysis usan `INNER JOIN news_items` (cadena doc→news→insight válida). Sin filtro document_status para no ocultar datos.

---

## 5. Workers Table — Insights con document_id

Para workers de tipo `insights`, `worker_tasks.document_id = "insight_{id}"`. El JOIN con `document_status` falla → filename = NULL.

**Solución**: Frontend o backend puede mostrar `document_id` cuando filename es NULL (para insights).

---

## 6. Checklist de Verificación

- [x] Insights no usan processing_queue (por diseño)
- [x] Master scheduler no encola insights (correcto)
- [x] GenericWorkerPool consume de news_item_insights
- [x] Fix #69 excluye insights del orphan reset
- [x] Dashboard: summary + analysis con INNER JOIN news_items
- [x] Workers: filename para insights vía news_item_insights (workers status + analysis)
- [x] PASO 0 crashed insights: news_item_insights generating→pending
