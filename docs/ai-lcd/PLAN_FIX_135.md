# Plan de Acción: Fix #135 - Detener Loop Infinito de Retries + Integrar UI de Pausas

## Contexto

**Bug**: Insights con error que exceden `MAX_INSIGHTS_RETRIES=3` son reintentados infinitamente por el scheduler PASO 4.

**Evidencia**:
- 2 insights con `retry_count` de 40 y 53
- Logs muestran mismo error repitiéndose cada 10 segundos (~6 intentos/minuto)
- **Consumo de recursos**: Llamadas OpenAI innecesarias, CPU wasted
- Worker incrementa correctamente `retry_count`
- Recovery (PASO 0) valida correctamente `retry_count`
- **PASO 4 (reconciliación) NO valida `retry_count`** ← Bug

## 💡 NOTA: Control de Recursos con Pausas

**El sistema YA tiene funcionalidad para pausar cualquier etapa del pipeline.**

Ver documentación completa: `docs/ai-lcd/03-operations/PIPELINE_PAUSE_CONTROL.md`

**Resumen rápido**:
```bash
# Pausar insights (LLM) para ahorrar recursos
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"pause_generation": true}'

# Pausar TODO el pipeline
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"pause_all": true}'

# Reanudar todo
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"resume_all": true}'
```

**Etapas pausables**:
- `ocr`: OCR de PDFs
- `chunking`: División en chunks
- `indexing`: Indexado en Qdrant
- `insights`: Generación LLM (consume recursos)
- `indexing_insights`: Indexado de insights

**Beneficios**:
- ✅ Control granular por etapa
- ✅ Persistente (sobrevive a rebuilds)
- ✅ No afecta otras etapas
- ✅ Útil para ahorrar recursos cuando no necesitas procesar

---

## 🎯 PROBLEMA ADICIONAL: UI de Pausas No Integrado

**Descubierto**: El componente `PipelineAnalysisPanel.jsx` YA EXISTE con UI completo para pausar etapas, PERO no está integrado en ninguno de los dos dashboards (v1 ni v2).

**Estado actual**:
- ✅ Backend funciona (API `/api/admin/insights-pipeline`)
- ✅ Componente UI existe (`PipelineAnalysisPanel.jsx`)
- ❌ **NO está en el dashboard** (usuario no puede pausar desde UI)

**Solución**: Integrar `PipelineAnalysisPanel` en Dashboard v1 (o v2)

---

## Cambios en Código

### PARTE 1: Backend - Fix Retry Loop

#### Archivo: `app/backend/app.py`

**Ubicación**: Líneas 965-1010 (PASO 4: Reconciliación de insights)

**Cambio**:

```python
# PASO 4: News items sin Insights task → Marcar como pending para workers
MAX_INSIGHTS_RETRIES = 3  # ← NUEVO: Definir constante

ready_for_insights = []
seen_news = set()
for doc in document_repository.list_all_sync(limit=None):
    doc_id = doc["document_id"]
    for insight in news_item_repository.list_insights_by_document_id_sync(doc_id):
        news_item_id = insight.get("news_item_id")
        if not news_item_id or news_item_id in seen_news:
            continue
        status = insight.get("status")
        retry_count = insight.get("retry_count", 0)  # ← NUEVO: Obtener retry_count
        
        if status in (InsightStatus.DONE, InsightStatus.GENERATING):
            continue
        
        # ← NUEVO: Skip insights que excedieron max retries
        if status == InsightStatus.ERROR and retry_count >= MAX_INSIGHTS_RETRIES:
            if debug_mode:
                logger.debug(
                    f"   ⏭ Skipping {news_item_id[:30]}... - "
                    f"max retries exceeded ({retry_count}/{MAX_INSIGHTS_RETRIES})"
                )
            continue
        
        seen_news.add(news_item_id)
        ready_for_insights.append(insight)
        if len(ready_for_insights) >= 100:
            break
    if len(ready_for_insights) >= 100:
        break
# ... resto del código sin cambios
```

**Líneas exactas a modificar**:
- **Línea ~973**: Agregar `retry_count = insight.get("retry_count", 0)`
- **Línea ~976**: Agregar bloque `if status == InsightStatus.ERROR and retry_count >= MAX_INSIGHTS_RETRIES:`

### PARTE 2: Frontend - Integrar UI de Pausas

#### Archivos a modificar:

1. **`app/frontend/src/components/PipelineDashboard.jsx`**
   - Importar `PipelineAnalysisPanel`
   - Agregar como sección colapsable

**Cambio propuesto**:

```jsx
// En imports (línea ~20)
import PipelineAnalysisPanel from './dashboard/PipelineAnalysisPanel';

// En el render, después de KPIsInline (línea ~250)
<CollapsibleSection title="Pipeline - Control de Etapas" defaultExpanded={true}>
  <PipelineAnalysisPanel 
    API_URL={API_URL}
    token={token}
    refreshTrigger={refreshTrigger}
    isAdmin={isAdmin}
  />
</CollapsibleSection>
```

**Beneficios**:
- ✅ Usuario admin puede pausar/reanudar etapas desde UI
- ✅ No necesita API calls manuales
- ✅ Botones "Todo activo" / "Pausar todo"
- ✅ Toggle individual por etapa (OCR, Chunking, Indexing, Insights, Indexing Insights)
- ✅ Persistente (sobrevive a rebuilds)

---

### 1. CONSOLIDATED_STATUS.md

Agregar al final:

```markdown
### 135. Fix Scheduler: Detener loop infinito de retries en insights ✅
**Fecha**: 2026-04-08
**Ubicación**: `app/backend/app.py` (líneas ~973-983, PASO 4 scheduler)

**Problema**: Insights con error permanente (retry_count >= 3) eran re-encolados infinitamente por el scheduler PASO 4. Evidencia: 2 insights con 40 y 53 reintentos fallando con "LLM refused to process (insufficient context)".

**Causa raíz**: 
- Worker incrementa correctamente `retry_count` y marca como ERROR
- Recovery (PASO 0) valida correctamente `retry_count` y no re-encola
- **PASO 4 (reconciliación) NO validaba `retry_count`** y re-encolaba cualquier insight con status != DONE/GENERATING

**Solución**: Agregada validación en PASO 4 para skip insights con `status=ERROR` y `retry_count >= MAX_INSIGHTS_RETRIES`.

**Impacto**: 
- Loop infinito detenido
- Insights con error permanente quedan en estado ERROR (no se reintentan)
- Scheduler ignora insights que ya agotaron intentos

**⚠️ NO rompe**:
- Worker retry logic ✅
- Recovery (PASO 0) ✅
- Insights válidos siguen procesándose ✅
- Reconciliación para insights sin error ✅

**Verificación**:
- [ ] Backend rebuild
- [ ] Logs muestran "Skipping ... max retries exceeded" para insights con retry_count >= 3
- [ ] Los 2 insights problemáticos (retry_count 40, 53) ya no se reintentan
- [ ] Insights nuevos con error se reintentan hasta 3 veces, luego quedan permanentes
```

### 2. SESSION_LOG.md

Agregar al final:

```markdown
## 2026-04-08 (Continuación - Sesión 58)

### Fix #135: Loop infinito de retries en insights

**Decisión**: Agregar validación `retry_count >= MAX_INSIGHTS_RETRIES` en PASO 4 del scheduler.

**Alternativas consideradas**:
1. ❌ Modificar worker para no marcar como ERROR → rechazado (worker está correcto)
2. ❌ Eliminar reconciliación PASO 4 → rechazado (necesaria para recovery legítimos)
3. ✅ **Agregar validación en PASO 4** → aceptado (quirúrgico, consistente con PASO 0)

**Impacto en roadmap**: Ninguno. Fix de bug no bloquea REQ-022 (Dashboard Redesign).

**Riesgo**: Bajo. Cambio localizado, no afecta flujo principal.

**Decisión de límite**: `MAX_INSIGHTS_RETRIES = 3` es consistente con:
- Recovery (PASO 0): línea 742
- Worker error handling: línea 2292
- LangGraph workflow: `max_attempts` default

**Cleanup necesario**: Los 2 insights actuales (retry_count 40, 53) quedarán en ERROR permanente. No se eliminarán automáticamente.
```

---

## Verificación

### Post-rebuild checks:

1. **Logs del scheduler**:
   ```bash
   docker compose logs backend -f | grep "Skipping.*max retries"
   ```
   Esperar ver mensajes para los 2 insights problemáticos.

2. **Query base de datos**:
   ```sql
   SELECT news_item_id, retry_count, updated_at::timestamp(0)
   FROM news_item_insights
   WHERE status = 'insights_error' AND retry_count >= 3
   ORDER BY updated_at DESC;
   ```
   Verificar que `updated_at` ya no cambia (no se reintentan).

3. **Contador de retries**:
   ```sql
   SELECT MAX(retry_count) as max_retries
   FROM news_item_insights
   WHERE status = 'insights_error';
   ```
   Verificar que el máximo se mantiene en 40/53 y no sigue creciendo.

4. **Insights nuevos**:
   - Subir documento que cause error de insights
   - Verificar que se reintenta máximo 3 veces
   - Verificar que queda en ERROR después del 3er intento

---

## Timeline Estimado

- **Backend fix (retry loop)**: 5 minutos
- **Frontend integration (UI pausas)**: 10 minutos
- **Rebuild backend**: ~15-20 segundos (Docker optimization activa)
- **Rebuild frontend**: ~30-40 segundos
- **Verificación**: 10-15 minutos (observar logs, query BD, test UI)
- **Documentación**: 10 minutos (CONSOLIDATED_STATUS + SESSION_LOG)

**Total**: ~45-55 minutos

---

## Rollback (si necesario)

Si el fix causa problemas:

```bash
# 1. Revertir cambio en app.py (remover validación retry_count)
git diff HEAD -- app/backend/app.py
git checkout HEAD -- app/backend/app.py

# 2. Rebuild
cd app && docker compose build backend && docker compose up -d backend

# 3. Observar comportamiento
docker compose logs backend -f
```

**Síntomas de problema** (poco probable):
- Insights válidos no se procesan
- Logs muestran "Skipping" para insights con retry_count < 3

---

## Notas Adicionales

**Comportamiento esperado después del fix**:

| Situación | retry_count | status | Comportamiento |
|-----------|-------------|--------|----------------|
| Worker falla 1era vez | 1 | ERROR | PASO 4 re-encola |
| Worker falla 2da vez | 2 | ERROR | PASO 4 re-encola |
| Worker falla 3era vez | 3 | ERROR | **PASO 4 NO re-encola** |
| Crashed worker recuperado | 0-2 | GENERATING | PASO 0 re-encola si < 3 |
| Crashed worker >3 retries | >= 3 | ERROR | PASO 0 NO re-encola |

**Constancia entre componentes**:
- PASO 0 (recovery): `MAX_INSIGHTS_RETRIES = 3` (línea 742)
- PASO 4 (reconciliación): `MAX_INSIGHTS_RETRIES = 3` (nuevo)
- Worker error handling: `MAX_INSIGHTS_RETRIES = 3` (línea 2292)

Todos usan la misma constante para consistencia.
