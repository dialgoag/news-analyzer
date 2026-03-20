# Análisis de brechas: Indexing Insights vs resto de etapas

> **Estado**: ✅ IMPLEMENTADO 2026-03-16  
> **Contexto**: PEND-001 implementó indexar insights en Qdrant como sub-paso. Este doc analizó brechas y la integración plena fue implementada.

**Referencias**: `CONSOLIDATED_STATUS.md §88` | `ENVIRONMENT_CONFIGURATION.md` (vars) | `PIPELINE_GLOSARIO.md` (§5 Indexing Insights)

---

## Comparativa: Etapas del pipeline

| Aspecto | OCR | Chunking | Indexing (chunks) | Insights (LLM) | **Indexing Insights** (actual) |
|---------|-----|----------|-------------------|---------------|--------------------------------|
| **Estados DocStatus** | ocr_pending, ocr_processing, ocr_done | chunking_* | indexing_* | insights_* | ❌ No existe |
| **TaskType** | ocr | chunking | indexing | insights | ❌ No existe |
| **processing_queue** | Sí | Sí | Sí | Sí (doc_id=insight_{id}) | ❌ No |
| **Master scheduler** | Crea tareas | Crea tareas | Crea tareas | Crea tareas | ❌ No |
| **Workers asignados** | Sí | Sí | Sí | Sí | ❌ Mismo worker que Insights |
| **worker_tasks** | Sí | Sí | Sí | Sí | ❌ No (se hace dentro de insights) |
| **Dashboard stage** | Sí | Sí | Sí | Sí | ❌ No |
| **Recovery crash** | Sí (rollback) | Sí | Sí | Sí | ❌ No |
| **Recovery orphan** | Sí | Sí | Sí | Sí | ❌ No |

---

## Comportamiento actual (PEND-001)

```
Insights worker:
  1. Genera insight (LLM)
  2. Guarda en news_item_insights (status=done)
  3. _index_insight_in_qdrant() ← sub-paso síncrono
  4. Marca task completed
```

**Problemas**:
- Si Qdrant falla en (3): log warning, insight en DB pero no en Qdrant. Sin retry.
- No hay visibilidad en dashboard de "insights indexados"
- No hay recovery si el worker muere entre (2) y (3)
- No consume workers del pool de forma explícita (es parte del mismo task insights)

---

## Integración plena propuesta (implementada)

Patrón coherente con **Insights**: worker pool obtiene tareas de `news_item_insights` (no processing_queue).

1. **news_item_insights**: columna `indexed_in_qdrant_at` (timestamp, nullable)
2. **TaskType.INDEXING_INSIGHTS**: nuevo tipo
3. **Worker pool**: prioridad indexing_insights (tras insights); claim desde news_item_insights WHERE status=done AND indexed_in_qdrant_at IS NULL
4. **Worker**: _indexing_insights_worker_task — lee content, embed, insert, set_indexed_in_qdrant
5. **Document completed**: solo cuando todos insights done Y indexed_in_qdrant_at IS NOT NULL
6. **Dashboard**: stage "Indexing Insights" con pending/processing/completed
7. **Recovery**: detect_crashed_workers para task_type=indexing_insights
8. **Insights task**: ya NO llama a _index_insight_in_qdrant (lo hace el worker indexing_insights)
