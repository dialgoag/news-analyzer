# Auditoría Completa Pipeline — Revisión Final

> **Fecha**: 2026-03-17  
> **Propósito**: Revisar toda la pipeline para evitar side effects y daño colateral.

---

## 1. Flujo por Etapa (Granularidad + IDs)

| Etapa | Granularidad | ID principal | Tabla fuente | Consumidor |
|-------|--------------|--------------|--------------|------------|
| Upload | documento | document_id | document_status | — |
| OCR | documento | document_id | processing_queue | Master scheduler → workers |
| Chunking | documento | document_id | processing_queue | Master scheduler → workers |
| Indexing | documento | document_id | processing_queue | Master scheduler → workers |
| **Insights** | **news_item** | **(document_id, news_item_id)** | **news_item_insights** | GenericWorkerPool |
| Completed | documento | document_id | document_status | Master PASO 5 |

---

## 2. PASO 0 — Runtime Crash Recovery

| Acción | OCR/Chunk/Index | Insights |
|--------|-----------------|----------|
| DELETE worker_tasks | ✅ doc_id real | ✅ insight_{id} |
| UPDATE processing_queue | ✅ doc_id match | ⚠️ N/A (no están) |
| UPDATE document_status | ✅ doc_id match | ❌ doc_id="insight_xxx" no matchea |
| **UPDATE news_item_insights** | N/A | **❌ FALTA** — generating→pending |

**Bug**: Crashed insights workers: se borra worker_tasks pero news_item_insights queda en "generating" → item bloqueado hasta restart.

**Fix aplicado**: Para task_type='insights' y doc_id.startswith("insight_"), extraer news_item_id y UPDATE news_item_insights SET status='pending' WHERE news_item_id=? AND status='generating'.

---

## 3. Orphan Reset (processing_queue)

- Excluye insights ✅ (Fix #69)
- Solo afecta ocr/chunking/indexing ✅

---

## 4. Startup Recovery (detect_crashed_workers)

- worker_tasks: DELETE all ✅
- processing_queue: processing→pending ✅
- document_status: *_processing→*_done ✅
- news_item_insights: generating→pending ✅

---

## 5. Dashboard — Consistencia

| Endpoint | Insights query | Filtro |
|----------|----------------|--------|
| **summary** | document_status filter | Puede ocultar datos |
| **analysis** | INNER JOIN news_items | Cadena doc→news→insight válida |

**Aplicado**: Summary e analysis usan INNER JOIN news_items (cadena doc→news→insight válida).

---

## 6. Workers Status

- insights: filename desde news_item_insights ✅
- analysis: subquery para insights filename ✅

---

## 7. Orphaned Tasks (analysis)

- Cuenta processing_queue sin worker ✅
- Insights no están en processing_queue → no afecta ✅
