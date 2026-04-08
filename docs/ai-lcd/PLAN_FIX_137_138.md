# Plan de Acción: Fix #137 (Insights Expirados UI) + Fix #138 (Simplificar Control Pausas)

## 🎯 Contexto

**Usuario solicita**:
1. Ver insights que excedieron `retry_count >= 3` con la razón de error en la UI
2. Simplificar control de pausas: remover `PipelineAnalysisPanel` completo, solo botones de pausa (TODO + individuales)

**Estado actual**:
- Fix #135 (retry loop) ya implementado ✅
- Fix #136 (integración PipelineAnalysisPanel) implementado pero usuario quiere versión simplificada
- Backend tiene API de pausas funcional: `/api/admin/insights-pipeline` (PUT)
- No existe endpoint para listar insights expirados

---

## 📋 PARTE 1: Fix #137 - Mostrar Insights Expirados con Razón de Error

### Backend

#### 1.1. Agregar método en `NewsItemRepository` (port)

**Archivo**: `app/backend/core/ports/repositories/news_item_repository.py`

```python
def list_expired_insights_sync(self, max_retries: int = 3) -> List[dict]:
    """SYNC: list insights that exceeded max retries (permanently failed)."""
    pass
```

#### 1.2. Implementar en `PostgresNewsItemRepository`

**Archivo**: `app/backend/adapters/driven/persistence/postgres/news_item_repository_impl.py`

```python
def list_expired_insights_sync(self, max_retries: int = 3) -> List[dict]:
    conn = self.get_connection_pool().getconn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT news_item_id, document_id, filename, item_index, title, 
                   status, error_message, retry_count, updated_at
            FROM news_item_insights
            WHERE retry_count >= %s
            ORDER BY updated_at DESC
            LIMIT 100
            """,
            (max_retries,),
        )
        rows = cursor.fetchall()
        return [self.map_row_to_dict(cursor, r) if isinstance(r, tuple) else dict(r) for r in rows]
    finally:
        self.get_connection_pool().putconn(conn)
```

#### 1.3. Crear endpoint en router dashboard

**Archivo**: `app/backend/adapters/driving/api/v1/routers/dashboard.py`

```python
@router.get("/expired-insights")
async def get_expired_insights(
    current_user: dict = Depends(auth.get_current_user),
    max_retries: int = 3
):
    """Get insights that exceeded max retries (permanently failed)."""
    news_item_repo = get_news_item_repository()
    expired = news_item_repo.list_expired_insights_sync(max_retries)
    return {
        "total": len(expired),
        "max_retries": max_retries,
        "insights": expired
    }
```

### Frontend

#### 1.4. Crear componente `ExpiredInsightsPanel`

**Archivo**: `app/frontend/src/components/dashboard/ExpiredInsightsPanel.jsx`

**Features**:
- Muestra lista de insights expirados
- Columnas: Documento, Item Index, Error Message, Retry Count, Last Update
- Botón "Limpiar insights expirados" (DELETE endpoint opcional)
- Collapsible por defecto

#### 1.5. Integrar en `PipelineDashboard.jsx`

Agregar después del panel de errores:

```jsx
<CollapsibleSection 
  title="Insights Expirados (Max Retries)" 
  icon={ExclamationTriangleIcon}
  priority="normal"
  defaultCollapsed={true}
>
  <ExpiredInsightsPanel 
    API_URL={API_URL}
    token={token}
    refreshTrigger={refreshTrigger}
  />
</CollapsibleSection>
```

---

## 📋 PARTE 2: Fix #138 - Activar Control de Pausas en Tabla Existente

**Descubrimiento**: `PipelineStatusTable` **YA TIENE** columna "Control" con botones Play/Pause (líneas 141-160), solo necesita activarse.

### Backend

#### 2.1. Enriquecer endpoint `/api/dashboard/analysis`

**Archivo**: Buscar endpoint que retorna `analysisData.pipeline.stages`

**Agregar a cada stage**:
```python
{
  "name": "OCR",
  "pauseKey": "ocr",  # NEW: key para API de pausas
  "paused": False,     # NEW: estado actual desde BD
  "pending_tasks": 10,
  # ... resto de campos existentes
}
```

**Fuente de datos**: Consultar `pipeline_runtime_kv` table para obtener estado de cada `pause_<step>`

### Frontend

#### 2.2. Implementar `onPauseToggle` en `PipelineDashboard.jsx`

**Archivo**: `app/frontend/src/components/PipelineDashboard.jsx`

**Cambios**:

1. **Remover integración de `PipelineAnalysisPanel`**:
   - Remover import (línea ~20)
   - Remover sección completa (líneas ~349-364)

2. **Implementar `onPauseToggle` funcional** (actualmente es solo console.log):

```jsx
const handlePauseToggle = async (stageKey, currentlyPaused) => {
  const newState = !currentlyPaused;
  const payload = { [`pause_${stageKey}`]: newState };
  
  try {
    await axios.put(
      `${API_URL}/api/admin/insights-pipeline`,
      payload,
      { headers: { Authorization: `Bearer ${token}` } }
    );
    // Refresh para obtener nuevo estado
    setRefreshTrigger(prev => prev + 1);
  } catch (err) {
    alert(`Error: ${err.response?.data?.detail || err.message}`);
  }
};
```

3. **Agregar botón "Pausar/Reanudar TODO"** arriba de la tabla:

```jsx
{isAdmin && (
  <div className="pipeline-global-controls">
    <button onClick={handlePauseAll} className="pause-all-button">
      {allPaused ? '▶️ Reanudar TODO' : '⏸️ Pausar TODO'}
    </button>
  </div>
)}
```

**Ubicación**: Justo antes de `<PipelineStatusTable />`

---

## 🔍 Verificación

### Backend
- [ ] Endpoint `/api/dashboard/expired-insights` retorna insights con retry_count >= 3
- [ ] Query incluye error_message correctamente
- [ ] Límite de 100 registros para performance

### Frontend - Expired Insights
- [ ] Panel muestra insights expirados
- [ ] Error messages visibles y legibles
- [ ] Collapsible funciona
- [ ] Refresh automático cada 30s

### Frontend - Pause Controls
- [ ] Botón "Pausar TODO" pausa todas las etapas
- [ ] Botón "Reanudar TODO" reactiva todas
- [ ] Botones individuales funcionan independientemente
- [ ] Estado visual claro (activo vs pausado)
- [ ] Solo visible para admin
- [ ] Logs backend confirman pausas aplicadas

---

## 📁 Archivos a Modificar/Crear

### Backend (4 archivos)
1. `app/backend/core/ports/repositories/news_item_repository.py` (agregar método port)
2. `app/backend/adapters/driven/persistence/postgres/news_item_repository_impl.py` (implementar)
3. `app/backend/adapters/driving/api/v1/routers/dashboard.py` (agregar endpoint expired-insights)
4. **Buscar endpoint que retorna `pipeline.stages`** y enriquecerlo con `pauseKey` + `paused`

### Frontend (3 archivos - SIMPLIFICADO)
1. `app/frontend/src/components/dashboard/ExpiredInsightsPanel.jsx` (NUEVO)
2. `app/frontend/src/components/dashboard/ExpiredInsightsPanel.css` (NUEVO)
3. `app/frontend/src/components/PipelineDashboard.jsx` (modificar: remover PipelineAnalysisPanel, implementar onPauseToggle, agregar botón "Pausar TODO")

---

## ⏱️ Timeline Estimado

- Backend (Parte 1): ~10 min
- Frontend ExpiredInsights (Parte 1): ~15 min
- Frontend PauseControls (Parte 2): ~20 min
- Testing + Rebuild: ~10 min
- **Total**: ~55 min

---

## 🚨 Riesgos

**Bajo riesgo**:
- Parte 1 es puramente aditiva (nuevo endpoint, nuevo componente)
- Parte 2 reemplaza integración pero API de pausas ya existe y funciona
- No afecta lógica del scheduler (ya fixed en #135)

**Mitigaciones**:
- Verificar que router dashboard tiene import correcto de `news_item_repository`
- CSS debe ser consistente con design system existente
- Testing manual en browser antes de commit
