# 📊 Plan de Refactorización Completa del Dashboard

> **Objetivo**: Rehacer dashboard con D3.js avanzado + Principios SOLID + Dashboard de Insights separado

**Fecha**: 2026-03-13  
**Prioridad**: 🟡 ALTA  
**Versión planeada**: v1.3  
**Estimación**: 8-12 horas (múltiples sesiones)

---

## 1. CONTEXTO Y MOTIVACIÓN

### 1.1 Estado Actual
- ✅ `PipelineDashboard.jsx`: Usa D3.js para gráficos de barras simples
- ✅ `DashboardSummaryRow.jsx`: Resumen en fila sticky
- ✅ Guidelines de visual analytics documentadas
- ❌ Visualizaciones NO interconectadas (filtros no afectan todo)
- ❌ Sin dashboard de insights separado
- ❌ Código backend `app.py` 4600+ líneas (monolito, NO SOLID)

### 1.2 Objetivos del Refactor
1. **Dashboard interactivo**: Visualizaciones D3.js interconectadas (brushing & linking)
2. **SOLID obligatorio**: Refactorizar backend siguiendo principios SOLID
3. **Dashboard Insights**: Vista separada con análisis de contenido de noticias
4. **Buenas prácticas**: Código limpio, modular, testeable, documentado

---

## 2. FASES DE IMPLEMENTACIÓN

### FASE 1: Reglas y Documentación (30-45 min)
**Objetivo**: Establecer reglas y arquitectura antes de codear

#### Tareas:
1. ✅ Crear `.cursor/rules/solid-principles.mdc`
   - Single Responsibility Principle (SRP)
   - Open/Closed Principle (OCP)
   - Liskov Substitution Principle (LSP)
   - Interface Segregation Principle (ISP)
   - Dependency Inversion Principle (DIP)
   - Ejemplos en Python y React

2. ✅ Crear `.cursor/rules/dashboard-best-practices.mdc`
   - D3.js patterns (enter/update/exit)
   - React + D3 integration
   - Interconexión de visualizaciones
   - State management para dashboards
   - Performance optimization

3. ✅ Actualizar `VISUAL_ANALYTICS_GUIDELINES.md`
   - Sección nueva: "D3.js Advanced Patterns"
   - Brushing & Linking
   - Coordinated Multiple Views
   - Interactive filtering

4. ✅ Crear `DASHBOARD_ARCHITECTURE.md`
   - Estructura de carpetas frontend
   - Arquitectura backend (servicios, controladores, repositorios)
   - Flujo de datos entre visualizaciones
   - API endpoints necesarios

---

### FASE 2: Backend SOLID Refactor (4-6 horas)
**Objetivo**: Refactorizar backend aplicando SOLID

#### Antes (app.py monolito - 4600 líneas):
```
app.py
├─ Endpoints FastAPI (200+ líneas)
├─ OCR logic inline (300+ líneas)
├─ Insights logic inline (400+ líneas)
├─ Scheduler jobs (500+ líneas)
├─ Database queries inline (1000+ líneas)
├─ Auth logic (200+ líneas)
└─ Utils (resto)
```

#### Después (estructura SOLID):
```
backend/
├─ app.py (FastAPI app + routes, <200 líneas)
├─ controllers/
│   ├─ document_controller.py (endpoints /api/documents/*)
│   ├─ insights_controller.py (endpoints /api/insights/*)
│   ├─ dashboard_controller.py (endpoints /api/dashboard/*)
│   ├─ workers_controller.py (endpoints /api/workers/*)
│   └─ auth_controller.py (endpoints /api/auth/*)
├─ services/
│   ├─ ocr_service.py (ya existe, mejorar con SRP)
│   ├─ insights_service.py (lógica de negocio insights)
│   ├─ dashboard_service.py (agregaciones para dashboard)
│   ├─ worker_pool_service.py (ya existe como worker_pool.py)
│   └─ notification_service.py
├─ repositories/
│   ├─ document_repository.py (queries documentos)
│   ├─ insights_repository.py (queries insights)
│   ├─ worker_repository.py (queries worker_tasks)
│   └─ user_repository.py (queries usuarios)
├─ models/ (ya existe auth_models.py, backup_models.py)
│   ├─ document_models.py
│   ├─ insight_models.py
│   └─ worker_models.py
├─ schedulers/
│   ├─ master_pipeline_scheduler.py (extraer de app.py)
│   └─ backup_scheduler.py (ya existe)
└─ utils/
    ├─ validators.py
    └─ formatters.py
```

#### Estrategia de Refactor:
1. **NO romper funcionalidad**: Refactor incremental
2. **Tests primero**: Crear tests para funcionalidad existente
3. **Extraer por capas**: Repositories → Services → Controllers
4. **Verificar en cada paso**: Levantar backend, testear endpoints

#### Pasos Detallados:
1. Crear estructura de carpetas
2. Extraer `repositories/` (queries de database.py)
3. Extraer `services/` (lógica de negocio de app.py)
4. Extraer `controllers/` (endpoints de app.py)
5. Actualizar `app.py` para importar controllers
6. Verificar: levantar backend, testear todos los endpoints
7. Cleanup: remover código duplicado

---

### FASE 3: Dashboard Pipeline Mejorado (2-3 horas)
**Objetivo**: Mejorar visualización pipeline con D3.js interconectado

#### Mejoras a `PipelineDashboard.jsx`:

1. **Gráfico Sankey Flow** (en lugar de barras):
   - Flujo desde "Pending" → "OCR" → "Chunking" → "Indexing" → "Insights" → "Completed"
   - Ancho de flujo = cantidad de documentos
   - Hover: muestra detalles de stage
   - Click: filtra documentos en ese stage

2. **Timeline de Procesamiento**:
   - Eje X: tiempo (últimas 24h, 7 días, 30 días)
   - Eje Y: cantidad de documentos procesados
   - Líneas por stage (OCR, Indexing, Insights)
   - Brush para zoom temporal
   - Click en punto: filtra documentos de ese momento

3. **Heatmap de Workers**:
   - Eje X: hora del día (00:00 - 23:59)
   - Eje Y: workers (OCR, Insights)
   - Color: carga (verde = bajo, rojo = saturado)
   - Hover: muestra métricas de worker

4. **Interconexión**:
   - Seleccionar stage en Sankey → filtra Timeline y Heatmap
   - Brush en Timeline → filtra Sankey y Heatmap
   - Click en Heatmap → muestra documentos procesados en esa hora

#### Nuevos Componentes:
```
frontend/src/components/dashboard/
├─ PipelineSankeyChart.jsx (Sankey flow)
├─ ProcessingTimeline.jsx (timeline con brush)
├─ WorkersHeatmap.jsx (heatmap carga)
├─ DashboardFilters.jsx (filtros globales)
└─ useCoordinatedFilters.js (hook para estado compartido)
```

#### State Management:
```javascript
// Contexto para filtros coordinados
const DashboardContext = React.createContext();

const useDashboardFilters = () => {
  const [filters, setFilters] = useState({
    stage: null,      // 'ocr', 'indexing', etc.
    timeRange: null,  // [startDate, endDate]
    workerId: null,   // worker específico
    status: null      // 'active', 'error', 'completed'
  });
  
  const updateFilter = (key, value) => {
    setFilters(prev => ({ ...prev, [key]: value }));
  };
  
  const clearFilters = () => {
    setFilters({ stage: null, timeRange: null, workerId: null, status: null });
  };
  
  return { filters, updateFilter, clearFilters };
};
```

---

### FASE 4: Dashboard de Insights (3-4 horas)
**Objetivo**: Crear dashboard separado para análisis de insights

#### Visualizaciones:

1. **Word Cloud Interactivo**:
   - Palabras clave extraídas de insights
   - Tamaño = frecuencia
   - Color = categoría (política, economía, etc.)
   - Click en palabra → filtra insights relacionados

2. **Sentiment Analysis Timeline**:
   - Eje X: tiempo
   - Eje Y: sentimiento promedio (-1 a +1)
   - Línea de tendencia con banda de confianza
   - Click en punto → muestra insights de ese día

3. **Topic Clustering (Force Graph)**:
   - Nodos = topics detectados
   - Tamaño = cantidad de noticias
   - Edges = similaridad entre topics
   - Click en nodo → zoom + detalles del topic

4. **Entities Network**:
   - Nodos = entidades (personas, organizaciones)
   - Edges = co-ocurrencia
   - Grosor edge = frecuencia
   - Click → expande conexiones

5. **Geographic Map** (si hay ubicaciones):
   - Mapa con puntos donde ocurren noticias
   - Color = tipo de evento
   - Tamaño = cantidad de menciones

#### Nuevos Componentes:
```
frontend/src/components/insights/
├─ InsightsDashboard.jsx (contenedor principal)
├─ WordCloudViz.jsx (D3 word cloud)
├─ SentimentTimeline.jsx (D3 line chart con brush)
├─ TopicForceGraph.jsx (D3 force simulation)
├─ EntitiesNetwork.jsx (D3 network graph)
├─ GeographicMap.jsx (D3 map con proyección)
└─ InsightsFilters.jsx (filtros específicos)
```

#### Backend Endpoints Necesarios:
```python
# En dashboard_controller.py
GET /api/insights/keywords         # Word cloud data
GET /api/insights/sentiment        # Sentiment timeline
GET /api/insights/topics           # Topic clustering
GET /api/insights/entities         # Entities network
GET /api/insights/geographic       # Geographic data
GET /api/insights/summary          # Resumen general
```

#### D3.js Patterns Usados:
- **Word Cloud**: `d3-cloud` library
- **Force Graph**: `d3.forceSimulation()`
- **Network**: `d3.forceLink()` + `d3.forceManyBody()`
- **Map**: `d3.geoMercator()` + `d3.geoPath()`

---

### FASE 5: Testing y Optimización (1-2 horas)

#### Tests Frontend:
```javascript
// PipelineSankeyChart.test.jsx
test('renders Sankey with correct data', () => { ... });
test('click on stage filters other charts', () => { ... });

// useCoordinatedFilters.test.js
test('updates filters correctly', () => { ... });
test('clears all filters', () => { ... });
```

#### Tests Backend:
```python
# test_dashboard_service.py
def test_get_pipeline_data():
    data = dashboard_service.get_pipeline_data()
    assert 'files' in data
    assert 'ocr' in data

# test_insights_repository.py
def test_get_keywords():
    keywords = insights_repo.get_keywords(limit=50)
    assert len(keywords) <= 50
```

#### Performance:
- Lazy loading de visualizaciones pesadas
- Virtualization para listas grandes
- Debounce en filtros interactivos
- Memoization de cálculos D3.js

---

## 3. VERIFICACIÓN

### Checklist Backend SOLID:
- [ ] Cada servicio tiene SRP (una responsabilidad)
- [ ] Controllers NO tienen lógica de negocio
- [ ] Repositories solo hacen queries (NO lógica)
- [ ] Interfaces/Protocols definidos (Python typing)
- [ ] Dependency injection en servicios
- [ ] Tests unitarios para cada servicio
- [ ] Backend levanta sin errores
- [ ] Todos los endpoints funcionan

### Checklist Dashboard Pipeline:
- [ ] Sankey flow renderiza correctamente
- [ ] Timeline con brush funcional
- [ ] Heatmap muestra carga correcta
- [ ] Filtros coordinados (click en uno afecta los demás)
- [ ] Performance < 1s render inicial
- [ ] Responsive en móvil

### Checklist Dashboard Insights:
- [ ] Word cloud interactivo
- [ ] Sentiment timeline con tendencia
- [ ] Topic force graph navegable
- [ ] Entities network expandible
- [ ] Filtros específicos funcionan
- [ ] Endpoints backend retornan datos correctos

---

## 4. RIESGOS Y MITIGACIONES

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Romper funcionalidad existente | ALTA | CRÍTICO | Tests antes de refactor, refactor incremental |
| Backend demasiado complejo | MEDIA | ALTO | Empezar simple, iterar, documentar bien |
| Performance D3.js lento | MEDIA | MEDIO | Lazy loading, virtualization, debounce |
| Data no disponible para insights | BAJA | MEDIO | Mockear datos si no hay suficientes insights |
| Tiempo excede estimación | ALTA | MEDIO | Priorizar fases, marcar opcional lo avanzado |

---

## 5. DEPENDENCIAS

### Librerías Adicionales:
```bash
# Frontend
npm install d3-cloud d3-sankey d3-geo d3-hierarchy

# Backend (si necesario)
pip install pydantic typing-extensions
```

### Pre-requisitos:
- ✅ Sistema operativo (v1.0 ESTABLE)
- ✅ Event-driven architecture funcionando
- ✅ Dashboard actual como baseline
- ✅ Visual analytics guidelines

---

## 6. TIMELINE ESTIMADO

| Fase | Duración | Dependencias | Prioridad |
|------|----------|--------------|-----------|
| 1. Reglas y Docs | 30-45 min | Ninguna | 🔴 CRÍTICA |
| 2. Backend SOLID | 4-6 horas | Fase 1 | 🔴 CRÍTICA |
| 3. Dashboard Pipeline | 2-3 horas | Fase 2 | 🟡 ALTA |
| 4. Dashboard Insights | 3-4 horas | Fase 2, 3 | 🟡 ALTA |
| 5. Testing | 1-2 horas | Todas | 🟢 MEDIA |

**Total estimado**: 8-12 horas (2-3 sesiones de trabajo)

---

## 7. RESULTADO ESPERADO

### Frontend:
```
frontend/src/
├─ components/
│   ├─ dashboard/
│   │   ├─ PipelineSankeyChart.jsx ✨ NUEVO
│   │   ├─ ProcessingTimeline.jsx ✨ NUEVO
│   │   ├─ WorkersHeatmap.jsx ✨ NUEVO
│   │   ├─ DashboardFilters.jsx ✨ NUEVO
│   │   └─ useCoordinatedFilters.js ✨ NUEVO
│   ├─ insights/
│   │   ├─ InsightsDashboard.jsx ✨ NUEVO
│   │   ├─ WordCloudViz.jsx ✨ NUEVO
│   │   ├─ SentimentTimeline.jsx ✨ NUEVO
│   │   ├─ TopicForceGraph.jsx ✨ NUEVO
│   │   ├─ EntitiesNetwork.jsx ✨ NUEVO
│   │   ├─ GeographicMap.jsx ✨ NUEVO
│   │   └─ InsightsFilters.jsx ✨ NUEVO
│   ├─ PipelineDashboard.jsx (mejorado)
│   └─ DashboardSummaryRow.jsx (sin cambios)
```

### Backend:
```
backend/
├─ app.py (refactorizado, <200 líneas)
├─ controllers/ ✨ NUEVO
├─ services/ ✨ NUEVO
├─ repositories/ ✨ NUEVO
├─ models/ (expandido)
└─ schedulers/ ✨ NUEVO
```

### Documentación:
```
.cursor/rules/
├─ solid-principles.mdc ✨ NUEVO
└─ dashboard-best-practices.mdc ✨ NUEVO

docs/ai-lcd/
├─ VISUAL_ANALYTICS_GUIDELINES.md (actualizado)
├─ DASHBOARD_ARCHITECTURE.md ✨ NUEVO
└─ DASHBOARD_REFACTOR_PLAN.md (este archivo)
```

---

## 8. PRÓXIMOS PASOS (POST-IMPLEMENTACIÓN)

1. **Dashboard de Reportes**: Visualizaciones para reportes diarios/semanales
2. **Alertas en Dashboard**: Notificaciones visuales de errores/anomalías
3. **Export de Visualizaciones**: Descargar gráficos como PNG/SVG
4. **Dashboard Mobile**: Versión optimizada para móvil
5. **Real-time Updates**: WebSocket para actualizaciones sin polling

---

**Status**: 📋 PLAN CREADO, esperando aprobación del usuario

**Próximo paso**: Solicitar aprobación y comenzar Fase 1 (Reglas y Docs)
