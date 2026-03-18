# Dashboard Analysis — Inconsistencias conocidas

> **Fecha**: 2026-03-17  
> **Propósito**: Documentar incoherencias en totales del pipeline. Fuente única para dashboard analysis.

**Resuelto**: §4 Workers vs Processing (PEND-008), §5 Bloqueos falsos, §6 Indexing pendientes, §7 Pending falso, §8 error_tasks por etapa, §9 Retry UI, §10 Errores de Insights  
**Pendiente**: §1 Insights (PEND-006), §2 Upload (PEND-007)

---

## 1. Stage Insights — total ≠ suma

| Campo | Valor ejemplo | Explicación |
|-------|---------------|-------------|
| total_documents | 18.834 | COUNT(*) de news_item_insights |
| pending + processing + completed | 18.784 | No incluye `error` |
| Diferencia | 50 | Insights en status `error` |

**Causa**: La query cuenta `error` en total pero el API no expone `error_tasks`. El frontend solo muestra P/P/C.

**Fix propuesto**: PEND-006 — Añadir `error_tasks` al stage o excluir errores del total.

---

## 2. Stage Upload — total ≠ tareas en etapa

| Campo | Valor ejemplo | Explicación |
|-------|---------------|-------------|
| total_documents | 251 | max(upload_total, total_documents, inbox_count) = docs en sistema |
| pending + processing + completed | 1 | Tareas reales en etapa Upload |
| Diferencia | 250 | total = "documentos totales", no "tareas en Upload" |

**Causa**: `upload_total_docs` usa `max(..., total_documents, ...)` para nunca mostrar 0 si hay docs. Semántica distinta al resto de stages.

**Fix propuesto**: PEND-007 — Unificar semántica o añadir aclaración en UI.

---

## 3. Workers — verificación

| Métrica | Valor | Estado |
|---------|-------|--------|
| Workers activos (worker_tasks) | 15 | OK |
| Por tipo | 6 Indexing, 6 Indexing Insights, 3 Insights | OK |
| Stuck | 0 | OK |
| Health check | 20/20 alive | OK |

**Límites vs activos** (ejemplo con env: INDEXING=6, INDEXING_INSIGHTS=6, INSIGHTS=3):
- indexing: 6 activos ≤ 6 ✓
- indexing_insights: 6 activos ≤ 6 ✓
- insights: 3 activos ≤ 3 ✓

**Nota**: Los límites vienen de `*_PARALLEL_WORKERS` en `.env`. `PIPELINE_WORKERS_COUNT` = tamaño del pool; activos = workers con tarea asignada; el resto idle.

---

## 5. Bloqueos falsos (OCR/Chunking/Indexing) ✅ RESUELTO (2026-03-18)

**Problema**: Dashboard mostraba "3 Bloqueos Detectados" cuando las etapas estaban completas (257 OCR, 251 chunking/indexing). Mensajes: "No hay documentos con ocr_done", "No hay documentos con chunking_done", etc.

**Causa**: La lógica añadía blocker siempre que `ready_for_next=0`, sin verificar si la etapa siguiente necesitaba input. Con pipeline fluyendo, `ready_for_next=0` es normal (todo ya pasó a la siguiente etapa).

**Solución**: Solo añadir blocker cuando la etapa siguiente tiene tareas pending/processing Y la actual no produce. Ver CONSOLIDATED_STATUS §91.

---

## 6. Indexing tasks pendientes no creadas ✅ RESUELTO (2026-03-18)

**Problema**: 7 documentos mostraban "pending" en Indexing pero no se procesaban. processing_queue tenía 0 pending para indexing.

**Causa**: El scheduler (PASO 3) solo buscaba docs con `processing_stage='chunking'` Y `status='chunking_done'`. Docs con `status=indexing_pending` (recovery) o con `processing_stage` NULL/inconsistente nunca recibían tarea en processing_queue.

**Solución**: Query ampliada a `status IN (chunking_done, indexing_pending)` sin exigir processing_stage. Ver CONSOLIDATED_STATUS §91.

---

## 8. error_tasks por etapa ✅ RESUELTO (2026-03-18)

**Problema**: Totales no cuadraban; docs en error no visibles por etapa.

**Solución**: Añadir `error_tasks` a cada stage (Upload, OCR, Chunking, Indexing, Insights, Indexing Insights). Contar por processing_stage. Ver CONSOLIDATED_STATUS §92.

---

## 9. Retry UI 422 + botones ✅ RESUELTO (2026-03-18)

**Problema**: Botón retry daba 422; sección Errores colapsada; algunos errores sin botón.

**Solución**: Endpoint usa Request + request.json(); sección expandida; can_auto_fix para Server disconnected; botón "Reintentar todos" visible. Ver CONSOLIDATED_STATUS §92.

---

## 10. Errores de Insights no visibles ni reintentables ✅ RESUELTO (2026-03-18)

**Problema**: Errores de Insights (news_item_insights status='error') no aparecían en "Análisis de Errores"; no había botón para reintentar.

**Causa**: El análisis solo consultaba document_status; retry solo manejaba document_ids.

**Solución**: Query adicional a news_item_insights; grupos con stage="insights"; retry acepta IDs insight_*; set_status(news_item_id, pending). Ver CONSOLIDATED_STATUS §94.

---

## 7. Pending falso (incluye docs en error) ✅ RESUELTO (2026-03-18)

**Problema**: Dashboard mostraba "7 pending" en Indexing cuando no había tareas reales. Los 8 docs "pendientes" eran en realidad **docs en status ERROR** (OCR failed, etc).

**Causa**: Fórmula `pending = total_documents - completed - processing` contaba cualquier doc no completado, incluyendo errores.

**Solución**: Usar `processing_queue.pending` (cola real) como fuente de verdad para OCR, Chunking, Indexing. Ver CONSOLIDATED_STATUS §91.

---

## 4. Workers vs Processing — Indexing Insights ✅ RESUELTO (2026-03-17)

**Problema**: Gráfica subcontaba workers porque el insert en `worker_tasks` era non-fatal.

**Solución**:
- Claim (UPDATE) + insert worker_tasks en **misma transacción**. Si insert falla → rollback completo.
- Recovery: insights con status='indexing' sin worker_tasks → reset a 'done'.

---

## Referencias

- **Status**: `CONSOLIDATED_STATUS.md` §89 (worker_tasks atómico), §88 (Indexing Insights)
- **Backlog pendiente**: `PENDING_BACKLOG.md` § PEND-006, PEND-007
- **API contract**: `FRONTEND_DASHBOARD_API.md`
- **Backend**: `app.py` § `/api/dashboard/analysis`
