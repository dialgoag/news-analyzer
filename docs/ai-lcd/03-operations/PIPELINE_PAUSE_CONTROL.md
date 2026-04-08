# Control de Pausas del Pipeline

> **Funcionalidad para controlar qué etapas del pipeline están activas**
> 
> Útil para ahorrar recursos cuando no necesitas procesar ciertas etapas

---

## 🎛️ Etapas Pausables

El sistema permite pausar individualmente o en conjunto las siguientes etapas:

| Etapa | ID | Descripción |
|-------|-----|-------------|
| **OCR** | `ocr` | Extracción de texto de PDFs |
| **Chunking** | `chunking` | División de texto en chunks |
| **Indexing** | `indexing` | Indexado de chunks en Qdrant |
| **Insights** | `insights` | Generación de insights con LLM |
| **Indexing Insights** | `indexing_insights` | Indexado de insights en Qdrant |

---

## 🔧 Cómo Pausar/Reanudar

### Opción 1: API (Recomendado)

#### Obtener Token de Admin

```bash
TOKEN=$(curl -sS http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"your_password"}' | jq -r .access_token)
```

#### Ver Estado Actual

```bash
curl -sS http://localhost:8000/api/admin/insights-pipeline \
  -H "Authorization: Bearer $TOKEN" | jq .
```

#### Pausar una Etapa Específica

```bash
# Pausar solo Insights (LLM)
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"pause_generation": true}'

# Pausar solo Indexing Insights
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"pause_indexing_insights": true}'

# Pausar múltiples etapas
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "pause_steps": {
      "ocr": false,
      "chunking": false,
      "indexing": false,
      "insights": true,
      "indexing_insights": true
    }
  }'
```

#### Pausar Todo el Pipeline

```bash
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"pause_all": true}'
```

#### Reanudar Todo el Pipeline

```bash
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"resume_all": true}'
```

---

### Opción 2: SQL Directo (Avanzado)

Si necesitas pausar sin usar la API:

#### Pausar una Etapa

```bash
# Pausar Insights
docker compose exec -T postgres psql -U rag-user -d rag-enterprise -c "
INSERT INTO pipeline_runtime_kv (key, value, updated_at)
VALUES ('pause.insights', '{\"paused\": true}'::jsonb, NOW())
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    updated_at = NOW();
"

# Pausar OCR
docker compose exec -T postgres psql -U rag-user -d rag-enterprise -c "
INSERT INTO pipeline_runtime_kv (key, value, updated_at)
VALUES ('pause.ocr', '{\"paused\": true}'::jsonb, NOW())
ON CONFLICT (key) DO UPDATE SET
    value = EXCLUDED.value,
    updated_at = NOW();
"
```

#### Ver Estado Actual

```bash
docker compose exec -T postgres psql -U rag-user -d rag-enterprise -c "
SELECT key, value FROM pipeline_runtime_kv WHERE key LIKE 'pause.%' ORDER BY key;
"
```

#### Reanudar una Etapa

```bash
docker compose exec -T postgres psql -U rag-user -d rag-enterprise -c "
UPDATE pipeline_runtime_kv 
SET value = '{\"paused\": false}'::jsonb, updated_at = NOW()
WHERE key = 'pause.insights';
"
```

---

## 🔍 Verificar que Pausó/Reanudó

### Logs del Backend

```bash
# Ver si workers están siendo dispatched
docker compose logs backend -f | grep -E "Generating insights|OCR worker|Chunking|Indexing"

# Si pausado correctamente, NO deberías ver logs de esa etapa
```

### Query de Workers Activos

```bash
docker compose exec -T postgres psql -U rag-user -d rag-enterprise -c "
SELECT task_type, COUNT(*) 
FROM worker_tasks 
WHERE status IN ('assigned', 'started') 
GROUP BY task_type;
"
```

Si una etapa está pausada, NO debe tener workers activos.

---

## 💡 Casos de Uso

### Caso 1: Ahorrar Recursos en Insights

**Problema**: Insights consume muchos recursos (LLM + API calls)

**Solución**:
```bash
# Pausar solo insights, dejar resto funcionando
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"pause_generation": true}'
```

**Resultado**: OCR, Chunking, Indexing siguen procesando. Insights quedan pendientes.

---

### Caso 2: Procesar Solo OCR/Indexing (Sin Insights)

**Problema**: Solo necesitas chunks indexados, no insights

**Solución**:
```bash
# Pausar insights + indexing_insights
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "pause_steps": {
      "insights": true,
      "indexing_insights": true
    }
  }'
```

**Resultado**: Documentos llegan hasta `indexing_done`, quedan ahí.

---

### Caso 3: Pausar Todo para Mantenimiento

**Problema**: Vas a hacer mantenimiento/debugging

**Solución**:
```bash
# 1. Shutdown ordenado (pausa todo + limpia workers)
curl -X POST http://localhost:8000/api/workers/shutdown \
  -H "Authorization: Bearer $TOKEN"

# 2. Hacer mantenimiento

# 3. Reanudar todo
curl -X PUT http://localhost:8000/api/admin/insights-pipeline \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"resume_all": true}'
```

---

## ⚠️ Notas Importantes

### Persistencia

✅ **Las pausas son persistentes** (PostgreSQL):
- Sobreviven a reinicios del backend
- Sobreviven a rebuilds
- Debes reanudar explícitamente cuando quieras procesar

### Shutdown Ordenado

El endpoint `POST /api/workers/shutdown` automáticamente:
1. Detiene workers activos
2. **Pausa TODOS los pasos** del pipeline
3. Marca tareas en progreso para retry

Después de shutdown, **DEBES reanudar** para que el pipeline vuelva a funcionar.

### Tareas Pendientes

Cuando pausas una etapa:
- ✅ Las tareas YA encoladas quedan en `processing_queue` con status `pending`
- ✅ NO se asignan a workers nuevos
- ✅ Cuando reanudes, se procesan automáticamente

### Sin Efecto en Otras Etapas

Pausar una etapa **NO afecta** a otras:
- Pausar Insights → OCR sigue funcionando
- Pausar OCR → Insights sigue procesando pendientes
- Cada etapa es independiente

---

## 📊 Monitoreo

### Dashboard (UI)

El dashboard muestra el estado de pausas en:
- Panel de administración (si eres admin)
- Estado de cada etapa del pipeline

### Logs

```bash
# Ver si una etapa específica está pausada
docker compose logs backend | grep "is_step_paused"

# Ver dispatch de workers (si pausado, no se asignan)
docker compose logs backend -f | grep "Dispatching worker"
```

---

## 🔧 Troubleshooting

### "Workers no procesan después de reanudar"

**Causa**: Cache no refrescado

**Solución**:
```bash
# Reiniciar backend para refrescar cache
docker compose restart backend
```

### "Pausas no persisten después de rebuild"

**Verificar migración 016**:
```bash
docker compose exec -T postgres psql -U rag-user -d rag-enterprise -c "
\d pipeline_runtime_kv
"
```

Si no existe, ejecutar migración:
```bash
docker compose exec backend python -m backend.migrations.migration_runner
```

### "No puedo pausar (403 Forbidden)"

**Causa**: Token no es de admin

**Solución**: Login con usuario que tenga rol `admin`:
```bash
# Ver roles de usuarios
docker compose exec -T postgres psql -U rag-user -d rag-enterprise -c "
SELECT username, role FROM users;
"
```

---

## 📚 Referencias

- **Implementación**: `app/backend/insights_pipeline_control.py`
- **Store**: `app/backend/pipeline_runtime_store.py`
- **API**: `app/backend/adapters/driving/api/v1/routers/admin.py`
- **Migración**: `app/backend/migrations/016_pipeline_runtime_kv.py`
- **Documentación relacionada**: `docs/ai-lcd/03-operations/ORDERLY_SHUTDOWN_AND_REBUILD.md`
