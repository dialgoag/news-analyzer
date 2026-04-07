# 📊 Propuesta: Dashboards de Análisis de Noticias

**Fecha**: 2026-04-07  
**Objetivo**: Crear dashboards profesionales para análisis de noticias (Facts + Insights) separados del dashboard de monitoreo de pipeline  
**Prioridad**: ALTA  
**Estimación**: 12-16 horas (diseño + implementación)

---

## 🎯 Problema Identificado

### Dashboard Actual (Monitoreo de Pipeline)
El dashboard actual (`PipelineDashboard.jsx`) está diseñado para **monitoreo de infraestructura**:

**Qué muestra**:
- ✅ Workers status (OCR, Chunking, Indexing, Insights)
- ✅ Pipeline stages (pending, processing, completed, error)
- ✅ Errores de procesamiento y workers stuck
- ✅ Estado de base de datos y colas
- ✅ Métricas de performance (tiempos, throughput)

**Qué NO muestra**:
- ❌ Contenido de las noticias indexadas
- ❌ Análisis de insights generados
- ❌ Tendencias temporales de noticias
- ❌ Comparación entre documentos/fuentes
- ❌ Visualización de entidades, temas o sentimientos
- ❌ Búsqueda y filtrado por contenido

### Necesidad Real
Los usuarios necesitan **dos dashboards separados**:

1. **Dashboard de Monitoreo** (ya existe) → Para DevOps/Admin
2. **Dashboard de Análisis de Noticias** (NUEVO) → Para analistas/usuarios finales

---

## 📋 Solución Propuesta

### Arquitectura de Navegación

```
App.jsx
├── 📊 Pipeline (Dashboard actual - monitoreo)
├── 📰 News Analytics (NUEVO - análisis de noticias)
│   ├── Facts (documentos indexados)
│   └── Insights (análisis generados)
├── 🔍 Query (búsqueda RAG)
└── 📁 Documents (gestión de archivos)
```

---

## 🎨 Design System Generado

Basado en **UI/UX Pro Max** para dashboards de analytics de noticias:

### Pattern
**AI Personalization Landing** adaptado a **Data-Dense Dashboard**
- Conversion focus: Analytics-driven (no marketing)
- Layout: Grid compacto con múltiples widgets
- CTA: Context-aware (filtros, exportar, compartir)

### Style
**Data-Dense Dashboard**
- **Mode Support**: Light ✓ Full | Dark ✓ Full
- **Keywords**: Multiple charts/widgets, data tables, KPI cards, minimal padding, grid layout, maximum data visibility
- **Best For**: Business intelligence, financial analytics, enterprise reporting, data warehousing
- **Performance**: ⚡ Excellent | **Accessibility**: ✓ WCAG AA

### Colors
| Role | Hex | CSS Variable | Uso |
|------|-----|--------------|-----|
| Primary | `#1E40AF` | `--color-primary` | Headers, títulos principales |
| Secondary | `#3B82F6` | `--color-secondary` | Elementos interactivos |
| Accent/CTA | `#D97706` | `--color-accent` | Highlights, CTAs (ajustado WCAG 3:1) |
| Background | `#F8FAFC` | `--color-background` | Fondo principal |
| Foreground | `#1E3A8A` | `--color-foreground` | Texto principal |
| Muted | `#E9EEF6` | `--color-muted` | Texto secundario |
| Border | `#DBEAFE` | `--color-border` | Separadores |
| Destructive | `#DC2626` | `--color-destructive` | Errores, eliminar |

**Nota**: Blue data + amber highlights para máxima legibilidad en contexto analítico

### Typography
- **Heading**: **Fira Code** (dashboard, data, analytics, technical, precise)
- **Body**: **Fira Sans** (clean, professional, highly readable)
- **Google Fonts**: https://fonts.google.com/share?selection.family=Fira+Code:wght@400;500;600;700|Fira+Sans:wght@300;400;500;600;700

```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

:root {
  --font-heading: 'Fira Code', monospace;
  --font-body: 'Fira Sans', sans-serif;
}
```

### Key Effects
- Hover tooltips
- Chart zoom on click
- Row highlighting on hover
- Smooth filter animations (200-300ms)
- Data loading spinners

### Avoid (Anti-patterns)
- ❌ Ornate design
- ❌ No filtering
- ❌ Emojis as icons (usar SVG: Heroicons/Lucide)
- ❌ Bright neon colors
- ❌ Harsh animations

---

## 📰 Dashboard 1: News Facts (Documentos Indexados)

### Propósito
Visualizar y analizar documentos indexados (PDFs de noticias procesados)

### Datos Disponibles (Backend)

**Tabla**: `document_status`, `news_items`, `document_stage_timing`

```sql
-- Métricas disponibles
document_id, filename, source, status, ingested_at, indexed_at
num_chunks, news_date, error_message
-- Timing por stage
upload_time, ocr_time, chunking_time, indexing_time
```

### Visualizaciones Propuestas

#### 1. KPI Cards (Top Row)
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ 📄 Docs     │ 📰 News     │ 📊 Chunks   │ ⏱️ Avg Time │
│ Indexados   │ Extraídas   │ Totales     │ Pipeline    │
│ 1,234       │ 4,567       │ 45,678      │ 2.3 min     │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

**Tipo**: Bullet Charts (compact KPI)
- **Library**: D3.js
- **Interactive**: Hover tooltips
- **Data**: `COUNT(document_status)`, `COUNT(news_items)`, `SUM(num_chunks)`, `AVG(processing_time)`

#### 2. Timeline de Ingestión (Main Visual)
```
Timeline + Heatmap
├── X-axis: Tiempo (últimos 30 días)
├── Y-axis: Número de documentos
├── Color: source (El Pais, ABC, etc.)
└── Brushing: Seleccionar rango temporal
```

**Tipo**: Area Chart + Time Brush
- **Library**: D3.js + Brushing
- **Interactive**: Click para drill-down, brush para filtrar
- **Data**: `GROUP BY DATE(ingested_at), source`

#### 3. Distribución por Fuente
```
Treemap o Sunburst
├── Level 1: source (El Pais, ABC, etc.)
├── Level 2: status (completed, error, pending)
└── Size: número de documentos
```

**Tipo**: Treemap (mejor para muchas fuentes)
- **Library**: D3.js Hierarchy
- **Interactive**: Click para filtrar tabla
- **Data**: `GROUP BY source, status`

#### 4. Tabla de Documentos (Bottom)
```
DataTable con filtros y sorting
├── Columns: filename, source, news_count, chunks, date, status
├── Filters: source, status, date range
├── Actions: ver detalles, download, reprocess
└── Pagination: 25/50/100 por página
```

**Tipo**: Data Table
- **Library**: React Table (TanStack Table)
- **Features**: Sorting, filtering, pagination, row selection
- **Data**: `SELECT * FROM document_status JOIN news_items`

#### 5. Performance Heatmap (Opcional)
```
Heatmap de tiempos por stage
├── Y-axis: Stages (OCR, Chunking, Indexing)
├── X-axis: Tiempo (días)
├── Color: Avg processing time
└── Hover: Show bottlenecks
```

**Tipo**: Calendar Heatmap
- **Library**: D3.js
- **Data**: `document_stage_timing` table

---

## 🧠 Dashboard 2: Insights Analytics (Análisis Generados)

### Propósito
Visualizar y analizar insights generados por IA sobre las noticias

### Datos Disponibles (Backend)

**Tabla**: `news_item_insights`, `news_items`

```sql
-- Métricas disponibles
news_item_id, document_id, title, status, content, text_hash
created_at, updated_at, error_message, llm_source
```

### Visualizaciones Propuestas

#### 1. KPI Cards (Top Row)
```
┌─────────────┬─────────────┬─────────────┬─────────────┐
│ 🧠 Insights │ ✅ Done     │ ⏳ Pending  │ 💰 Cost Est │
│ Totales     │ Completados │ En cola     │ (tokens)    │
│ 4,567       │ 4,200       │ 367         │ $45.67      │
└─────────────┴─────────────┴─────────────┴─────────────┘
```

**Tipo**: Bullet Charts
- **Data**: `COUNT(*) GROUP BY status`, costo estimado por tokens

#### 2. Insights Timeline (Main Visual)
```
Line Chart + Area
├── X-axis: Tiempo (últimos 30 días)
├── Y-axis: Número de insights generados
├── Lines: done, pending, error
└── Brushing: Seleccionar rango temporal
```

**Tipo**: Multi-line Time Series
- **Library**: D3.js
- **Interactive**: Hover tooltips, brush filter
- **Data**: `GROUP BY DATE(created_at), status`

#### 3. Word Cloud / Topics (Análisis de Contenido)
```
Word Cloud (requiere procesamiento adicional)
├── Extracción: Top palabras clave de insights.content
├── Size: Frecuencia
├── Color: Categoría (entities, topics, sentiments)
└── Click: Filtrar insights por palabra
```

**Tipo**: Word Cloud
- **Library**: D3-cloud
- **Processing**: Backend debe analizar `content` field y extraer keywords
- **Note**: Requiere endpoint `/api/insights/keywords`

#### 4. Tabla de Insights (Bottom)
```
DataTable con búsqueda y filtros
├── Columns: title, document, date, status, preview
├── Search: Full-text search en content
├── Filters: status, date range, document source
├── Actions: ver completo, editar, regenerar
└── Expandable rows: Mostrar content completo
```

**Tipo**: Data Table + Expandable Rows
- **Library**: React Table
- **Features**: Full-text search, sorting, filtering, expandable

#### 5. Insights Quality Metrics (Opcional)
```
Gauge Charts
├── Avg length (words)
├── Avg confidence (si disponible)
├── Error rate (%)
└── LLM provider distribution
```

**Tipo**: Gauge / Bullet Charts
- **Data**: Métricas calculadas de `news_item_insights`

---

## 🔗 Separación Facts vs Insights

### Criterio de Diferenciación

| Aspecto | Facts Dashboard | Insights Dashboard |
|---------|----------------|-------------------|
| **Datos** | Documentos crudos indexados | Análisis generados por IA |
| **Tabla Principal** | `document_status` + `news_items` | `news_item_insights` |
| **Propósito** | Ver QUÉ se indexó | Ver QUÉ se analizó |
| **Audiencia** | Analistas de datos, editores | Decisores, analistas de negocio |
| **Métricas** | Cantidad, velocidad, fuentes | Calidad, temas, tendencias |
| **Visualizaciones** | Timeline, distribución, tabla | Word cloud, sentimientos, tabla |

### Navegación

```jsx
// En App.jsx
<button onClick={() => setCurrentView('news-facts')}>
  📰 News Facts
</button>
<button onClick={() => setCurrentView('insights')}>
  🧠 Insights
</button>
```

---

## 📊 Mejores Prácticas de Visual Analytics Aplicadas

### Principios (de VISUAL_ANALYTICS_GUIDELINES.md)

#### 1. Claridad Visual ✅
- Una acción = una reacción visual clara
- Feedback inmediato (transiciones 0.2-0.3s)
- Hover states en todos los elementos interactivos

#### 2. Jerarquía de Información ✅
- **Crítica**: KPI cards arriba, colores vivos, tamaño mayor
- **Secundaria**: Visualizaciones main (charts), colores moderados
- **Terciaria**: Tablas abajo, fácil de scroll

#### 3. Consistencia ✅
- Misma paleta de colores en ambos dashboards
- Mismos patrones de interacción (brushing & linking)
- Transiciones uniformes

#### 4. Accesibilidad ✅
- WCAG AA mínimo (contraste 4.5:1)
- No solo color (iconos + bordes + patterns)
- Keyboard navigation en todos los elementos

### Paleta de Colores (de guideline)

| Estado | Color | Uso |
|--------|-------|-----|
| **Activo/Procesando** | `#4caf50` (verde) | Insights generándose |
| **En espera** | `#ff9800` (naranja) | Pending insights |
| **Completado** | `#2196f3` (azul) | Done |
| **Error** | `#f44336` (rojo) | Errores |
| **Info/Neutral** | `#4dd0e1` (cyan) | Resaltados |

### Componentes Interactivos

#### Brushing & Linking (Ya implementado en Pipeline Dashboard)
```
Usuario selecciona rango en Timeline
  → Filtra automáticamente:
    - KPI Cards
    - Tabla de documentos/insights
    - Treemap/Word Cloud
```

#### Hover Tooltips
```
Hover en chart
  → Muestra:
    - Valor exacto
    - Porcentaje del total
    - Fecha/hora
    - Acción disponible (click para filtrar)
```

#### Expandable Rows (Nuevo para Insights)
```
Click en fila de tabla
  → Expande mostrando:
    - Full content del insight
    - Metadata (LLM source, tokens, tiempo)
    - Acciones (regenerar, editar, copiar)
```

---

## 🏗️ Arquitectura de Componentes

### Estructura de Archivos

```
app/frontend/src/
├── components/
│   ├── news-analytics/              # NUEVO
│   │   ├── NewsAnalyticsView.jsx    # Container principal
│   │   ├── facts/                   # Dashboard Facts
│   │   │   ├── FactsDashboard.jsx
│   │   │   ├── FactsKPICards.jsx
│   │   │   ├── FactsTimeline.jsx    # D3 Area Chart + Brush
│   │   │   ├── FactsTreemap.jsx     # D3 Treemap (sources)
│   │   │   ├── FactsTable.jsx       # React Table
│   │   │   └── FactsPerformanceHeatmap.jsx
│   │   ├── insights/                # Dashboard Insights
│   │   │   ├── InsightsDashboard.jsx
│   │   │   ├── InsightsKPICards.jsx
│   │   │   ├── InsightsTimeline.jsx # D3 Multi-line
│   │   │   ├── InsightsWordCloud.jsx # D3-cloud
│   │   │   ├── InsightsTable.jsx     # React Table + Expandable
│   │   │   └── InsightsQualityGauges.jsx
│   │   └── shared/                  # Componentes reutilizables
│   │       ├── KPICard.jsx
│   │       ├── TimeRangeFilter.jsx
│   │       ├── ExportButton.jsx
│   │       └── LoadingSpinner.jsx
│   └── dashboard/                   # Existente (Pipeline monitoreo)
│       └── ... (no modificar)
├── services/
│   ├── newsAnalyticsService.js      # NUEVO - Transformaciones de datos
│   └── documentDataService.js       # Existente
├── hooks/
│   ├── useNewsAnalytics.js          # NUEVO - Fetching + state
│   └── useDashboardFilters.jsx      # Existente
└── styles/
    └── news-analytics/              # NUEVO
        ├── facts.css
        ├── insights.css
        └── shared.css
```

### Backend - Nuevos Endpoints Necesarios

```
app/backend/adapters/driving/api/v1/routers/
├── news_analytics.py  # NUEVO
│   ├── GET /api/analytics/facts/kpis
│   ├── GET /api/analytics/facts/timeline
│   ├── GET /api/analytics/facts/sources
│   ├── GET /api/analytics/facts/documents (con filtros)
│   ├── GET /api/analytics/insights/kpis
│   ├── GET /api/analytics/insights/timeline
│   ├── GET /api/analytics/insights/keywords  # Word cloud
│   └── GET /api/analytics/insights/list (con búsqueda)
```

---

## 📋 Plan de Implementación

### Fase 1: Setup Base (2-3h)
- [ ] Crear estructura de carpetas `news-analytics/`
- [ ] Setup navegación en `App.jsx` (agregar tabs)
- [ ] Crear componentes container vacíos
- [ ] Configurar rutas y estados

### Fase 2: Dashboard Facts (4-5h)
- [ ] Backend: Endpoints `/api/analytics/facts/*`
- [ ] Frontend: KPI Cards
- [ ] Frontend: Timeline (D3 + Brush)
- [ ] Frontend: Treemap (sources)
- [ ] Frontend: Tabla documentos (React Table)
- [ ] Integración: Brushing & Linking
- [ ] Testing: Verificar con datos reales

### Fase 3: Dashboard Insights (4-5h)
- [ ] Backend: Endpoints `/api/analytics/insights/*`
- [ ] Backend: Procesamiento keywords (Word Cloud)
- [ ] Frontend: KPI Cards
- [ ] Frontend: Timeline
- [ ] Frontend: Word Cloud (D3-cloud)
- [ ] Frontend: Tabla insights (expandable rows)
- [ ] Integración: Brushing & Linking
- [ ] Testing: Verificar con datos reales

### Fase 4: Polish + Responsive (2-3h)
- [ ] Responsive design (mobile, tablet, desktop)
- [ ] Dark mode (opcional)
- [ ] Accesibilidad (keyboard nav, ARIA labels)
- [ ] Loading states y error handling
- [ ] Export functions (CSV, JSON)
- [ ] Documentación: USAGE_GUIDE.md

---

## ✅ Checklist Pre-Delivery

### Design System
- [ ] No emojis as icons (usar Heroicons/Lucide)
- [ ] cursor-pointer en clickables
- [ ] Hover states (150-300ms transitions)
- [ ] Light mode: contraste 4.5:1 mínimo
- [ ] Focus states visibles (keyboard nav)
- [ ] prefers-reduced-motion respetado
- [ ] Responsive: 375px, 768px, 1024px, 1440px

### Funcionalidad
- [ ] Brushing & Linking funciona
- [ ] Filtros aplican a todas visualizaciones
- [ ] Tablas con sorting y search
- [ ] Export buttons funcionan
- [ ] No hay memory leaks (D3 cleanup)

### Performance
- [ ] Render inicial < 2s
- [ ] Charts optimizados (max 1000 datapoints)
- [ ] Lazy loading para tablas grandes
- [ ] Debounce en búsqueda (300ms)

### Backend
- [ ] Endpoints con caché (15-30s TTL)
- [ ] Paginación en tablas
- [ ] Filtros eficientes (SQL indexes)
- [ ] Error handling gracioso

---

## 📚 Referencias

### Documentación Existente
- `VISUAL_ANALYTICS_GUIDELINES.md` - Principios y paleta de colores
- `D3_SANKEY_REFERENCE.md` - Patrones D3.js
- `DASHBOARD_IMPROVEMENTS_PROPOSAL.md` - Mejoras pipeline dashboard
- `CONSOLIDATED_STATUS.md` - Estado actual del proyecto

### Librerías Recomendadas
- **D3.js** - Visualizaciones custom (timeline, treemap, word cloud)
- **React Table** (TanStack Table) - Tablas con filtros y sorting
- **D3-cloud** - Word cloud
- **Heroicons** - Iconos SVG profesionales
- **Tailwind CSS** - Styling (ya en uso)

### Diseño de Referencia
- UI/UX Pro Max: Data-Dense Dashboard pattern
- Google Fonts: Fira Code + Fira Sans
- Color palette: Blue data + amber highlights

---

## 🎯 Próximos Pasos

1. **Revisar y aprobar** esta propuesta
2. **Priorizar** Facts vs Insights (¿cuál primero?)
3. **Crear endpoints backend** para analytics
4. **Implementar Fase 1** (setup base)
5. **Iterar** por fases con feedback

---

**Última actualización**: 2026-04-07  
**Autor**: AI Assistant (siguiendo workflow obligatorio)  
**Estado**: PROPUESTA - Pendiente aprobación
