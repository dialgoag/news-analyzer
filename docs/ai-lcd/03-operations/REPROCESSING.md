# 🔄 Reprocesamiento de Documentos (OCR → Insights)

> Procedimiento oficial para volver a procesar documentos completos sin perder noticias ni insights existentes.

## 1. Objetivo y alcance
- **Cuándo usarlo**: PDFs con OCR deficiente, segmentación incompleta, noticias nuevas detectadas en fuentes externas o tras ajustes de pipeline.
- **Qué cubre**: Vuelve a ejecutar todas las etapas document-level (OCR, chunking, indexing) y actualiza news-level (segmentación, insights) solo cuando el contenido realmente cambia.

## 2. Qué se preserva vs. qué se recalcula
| Preservado | Motivo |
|------------|--------|
| `news_items` e `news_item_insights` existentes cuyo `text_hash` no cambia | Evitar duplicados y mantener trazabilidad de IDs/notas previas |
| `document_stage_timing` histórico de etapas ya completadas | Auditoría; se añaden nuevos registros para la corrida actual |
| Evidencia de ingesta (`uploads/*`, `document_id`, `source`) | Conserva contexto operativo |

| Recalculado | Motivo |
|--------------|--------|
| Texto OCR (`document_status.ocr_text`) | Obtener texto limpio/correcciones |
| Segmentación y noticias nuevas | Descubrir notas faltantes tras mejoras |
| Chunks y vectores en Qdrant | Mantener índice alineado al nuevo texto |
| Insights solo para noticias nuevas | Ahorra tokens y mantiene insights confirmados |

## 3. Flujo end-to-end
```
Usuario marca documento → flag persistente → scheduler → cola OCR → workers OCR → chunking → indexing → insights
```
1. **Marcado**: `POST /api/documents/{id}/requeue` o botón 🔄 del dashboard ejecuta
   - `reprocess_requested = 1`
   - `status = processing:ocr`
   - `ocr_text = NULL`
   - se encola tarea OCR (`priority=10`)
2. **Scheduler** (cada 10 s) revisa `document_repository.list_pending_reprocess_sync()` y re-encola si no está en cola activa.
3. **Workers** ejecutan OCR → chunking → indexing. Al cerrar indexing:
   - `document_repository.mark_for_reprocessing_sync(document_id, requested=False)`
   - Nuevas noticias se insertan; existentes se reconcilian por `text_hash`.
4. **Insights**: si `INSIGHTS_QUEUE_ENABLED`, sólo noticias nuevas pasan a la cola de insights; las existentes conservan su `news_item_insights` previo.

## 4. Guardrails y trazabilidad
- **Persistencia**: Columna `reprocess_requested` (INTEGER) + índice `idx_document_status_reprocess` garantiza que las solicitudes sobreviven reinicios.
- **Deduplicación**: `segment_news_items_from_text` calcula `text_hash` y reutiliza IDs cuando coincide; `news_item_repository` opera el merge.
- **Stage timing**: cada worker llama a `StageTimingRepository.record_stage_start/end`, por lo que el timeline refleja la corrida nueva.
- **Retry legacy**: `file_ingestion_service` y endpoints de retry detectan documentos legacy y bloquean la operación salvo `force_legacy=true`.

## 5. Cómo ejecutarlo
### Dashboard (recomendado)
1. Ir a **Documents** → localizar el PDF.
2. Click en 🔄 `Requeue` → confirmar.
3. Seguir progreso en Dashboard > Upload/OCR/Chunking stages o en `/api/workers/status`.

### API directa
```bash
TOKEN=...  # JWT admin o super_user
DOC_ID=...
curl -X POST \
  -H "Authorization: Bearer $TOKEN" \
  http://localhost:8000/api/documents/$DOC_ID/requeue
```

### Scripts útiles
- `scripts/run_api_smoke.sh` → confirma que `/api/documents` refleja el nuevo estado.
- `app/backend/scripts/check_upload_symlink_db_consistency.py` → verificar integridad antes/después de reprocesar lotes grandes.

## 6. Verificación post-reproceso
Checklist recomendado:
- `docker compose logs backend | grep requeue` → ver confirmaciones ✅/errores.
- `GET /api/documents/{id}` → campos `status`, `num_chunks`, `ingested_at` actualizados.
- `GET /api/documents/{id}/segmentation-diagnostic` → validar número de noticias detectadas.
- `GET /api/workers/status` → sin tareas stuck en `processing`.
- Qdrant: `scripts/qdrant_check_vectors.py` (si aplica) para confirmar que la colección coincide con los nuevos chunks.

## 7. Troubleshooting rápido
| Síntoma | Acción |
|---------|--------|
| Flag no se limpia (`reprocess_requested=1` permanente) | Revisar logs de indexing; puede haber error antes de marcar done. Ejecutar `mark_for_reprocessing_sync(document_id, requested=False)` manualmente solo tras solucionar el error. |
| Documento vuelve a cola legacy | Verifica que `force_legacy=true` no esté habilitado y que la fuente sea `inbox`. |
| Poco OCR tras reprocess | Validar PDF fuente; si es corrupto, moverlo a `app/local-data/uploads/PEND-016/` y documentar en backlog. |

## 8. Referencias relacionadas
- `app/backend/file_ingestion_service.py` — trail físico + guardrails `force_legacy`.
- `app/backend/app.py` — endpoints `requeue`/`retry-errors`, scheduler y workers.
- `app/backend/core/ports/repositories/document_repository.py` — API utilizada para marcar/desmarcar.
- `docs/ai-lcd/03-operations/SEGMENTATION_DIAGNOSTIC_GUIDE.md` — diagnóstico detallado post-OCR.
- Históricos completos del incidente en `docs/archive/2026-03-recovery/`.
