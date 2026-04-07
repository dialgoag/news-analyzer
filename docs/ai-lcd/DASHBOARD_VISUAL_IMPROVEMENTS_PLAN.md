# 🎨 Mejoras del Pipeline Dashboard - Aplicando Design System Profesional

**Fecha**: 2026-04-07  
**Objetivo**: Mejorar dashboard actual de monitoreo aplicando Visual Analytics best practices  
**Prioridad**: ALTA  
**Estimación**: 6-8 horas

---

## 📊 Estado Actual

### Componentes Existentes
```
PipelineDashboard.jsx
├── ErrorAnalysisPanel (colapsable)
├── PipelineAnalysisPanel (colapsable)
├── StuckWorkersPanel (colapsable)
├── DatabaseStatusPanel (colapsable)
├── PipelineSummaryCard
├── WorkerLoadCard
└── ParallelPipelineCoordinates
```

### Fortalezas ✅
- Arquitectura modular (componentes separados)
- Collapsible sections para optimizar espacio
- Auto-refresh cada 20s
- Manejo de errores gracioso
- Responsive design básico

### Problemas Identificados ❌

#### 1. **Design System Inconsistente**
- Colores mezclados (algunos hexagonales, otros CSS vars)
- Tipografía sin sistema claro (sin Fira Code/Fira Sans)
- Espaciado irregular (8px, 10px, 12px sin patrón)
- No sigue paleta de Visual Analytics Guidelines

#### 2. **Jerarquía Visual Pobre**
- KPI Cards no destacan suficiente
- Secciones colapsables con misma importancia visual
- Sin diferenciación clara crítico/secundario/terciario

#### 3. **Accesibilidad**
- Algunos textos sin contraste WCAG AA (4.5:1)
- Emojis como iconos (no SVG profesionales)
- Focus states no visibles en algunos elementos
- Sin keyboard navigation clara

#### 4. **Interactividad Limitada**
- No hay brushing & linking entre visualizaciones
- Filtros no coordinan todas las vistas
- Sin export functions (CSV, JSON, PNG)
- Tooltips básicos (falta contexto)

#### 5. **Performance**
- Auto-refresh cada 20s sin debounce
- Sin lazy loading para datos pesados
- Charts re-renderizan completamente (no optimizados)

---

## 🎨 Design System a Aplicar

### Paleta de Colores (de VISUAL_ANALYTICS_GUIDELINES.md)

#### Estados de Datos
| Estado | Color | Uso | Variable CSS |
|--------|-------|-----|--------------|
| **Activo/Procesando** | `#4caf50` | Workers activos, docs procesando | `--color-active` |
| **En espera** | `#ff9800` | Pending tasks, idle workers | `--color-pending` |
| **Completado** | `#2196f3` | Docs completed, tasks done | `--color-completed` |
| **Error** | `#f44336` | Errores, fallos | `--color-error` |
| **Advertencia** | `#ff5722` | Warnings, requiere atención | `--color-warning` |
| **Info/Neutral** | `#4dd0e1` | Info general, resaltados | `--color-info` |

#### Elementos de Interfaz
| Elemento | Color | Variable CSS |
|----------|-------|--------------|
| **Fondo base** | `#0f172a` | `--bg-base` |
| **Panel** | `#1e1e2e` | `--bg-panel` |
| **Borde** | `#334155` | `--border-color` |
| **Texto principal** | `#f1f5f9` | `--text-primary` |
| **Texto secundario** | `#cbd5e1` | `--text-secondary` |
| **Texto deshabilitado** | `#64748b` | `--text-disabled` |

### Tipografía

```css
@import url('https://fonts.googleapis.com/css2?family=Fira+Code:wght@400;500;600;700&family=Fira+Sans:wght@300;400;500;600;700&display=swap');

:root {
  --font-heading: 'Fira Code', monospace;
  --font-body: 'Fira Sans', sans-serif;
  
  /* Tamaños */
  --text-xl: 1.875rem;  /* 30px - Título principal */
  --text-lg: 1.125rem;  /* 18px - Título secundario */
  --text-md: 0.875rem;  /* 14px - Headers tabla */
  --text-sm: 0.875rem;  /* 14px - Contenido */
  --text-xs: 0.75rem;   /* 12px - Pequeño/Help */
}
```

### Espaciado (Sistema de 4px)

```css
:root {
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 20px;
  --space-6: 24px;
  --space-8: 32px;
}
```

### Transiciones

```css
:root {
  --transition-fast: 150ms ease;
  --transition-normal: 200ms ease;
  --transition-slow: 300ms ease;
}
```

---

## 🔧 Mejoras Concretas

### 1. **PipelineSummaryCard** (Prioridad ALTA)

#### Problemas Actuales
- Métricas sin jerarquía clara
- Barra de progreso sin color semántico
- Tipografía genérica
- Sin hover states

#### Mejoras Propuestas

```jsx
// PipelineSummaryCard.jsx (mejorado)
<div className="pipeline-summary-card">
  {/* KPI Cards con jerarquía */}
  <div className="kpi-grid">
    <KPICard
      icon={<DocumentIcon />} // SVG, no emoji
      label="Docs Procesados"
      value={completedDocs}
      total={totalDocs}
      percentage={files?.percentage_done}
      status="completed" // Color azul
      trend="+5% vs ayer" // Opcional
    />
    <KPICard
      icon={<BrainIcon />}
      label="Insights Listos"
      value={insightsDone}
      total={insightsTotal}
      percentage={insights?.percentage_done}
      status="active" // Color verde
    />
    <KPICard
      icon={<ClockIcon />}
      label="News Pendientes"
      value={newsPending}
      status="pending" // Color naranja
    />
  </div>
  
  {/* Progress bar con estados */}
  <div className="progress-bar-stack">
    <div className="progress-segment progress-segment--completed" style={{ width: `${completed}%` }} />
    <div className="progress-segment progress-segment--processing" style={{ width: `${processing}%` }} />
    <div className="progress-segment progress-segment--pending" style={{ width: `${pending}%` }} />
  </div>
  
  {/* Legend */}
  <div className="progress-legend">
    <span><span className="dot dot--completed"></span> Completado ({completed}%)</span>
    <span><span className="dot dot--processing"></span> Procesando ({processing}%)</span>
    <span><span className="dot dot--pending"></span> Pendiente ({pending}%)</span>
  </div>
</div>
```

#### CSS Mejorado

```css
.pipeline-summary-card {
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: 8px;
  padding: var(--space-4);
}

.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.kpi-card {
  background: rgba(255, 255, 255, 0.02);
  border: 1px solid var(--border-color);
  border-radius: 6px;
  padding: var(--space-3);
  transition: var(--transition-normal);
  cursor: pointer;
}

.kpi-card:hover {
  background: rgba(255, 255, 255, 0.05);
  border-color: var(--color-info);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(77, 208, 225, 0.15);
}

.kpi-card__icon {
  width: 24px;
  height: 24px;
  margin-bottom: var(--space-2);
  color: var(--color-info);
}

.kpi-card__label {
  font-family: var(--font-body);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.kpi-card__value {
  font-family: var(--font-heading); /* Fira Code para números */
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.kpi-card__percentage {
  font-size: var(--text-sm);
  color: var(--text-secondary);
}

/* Progress bar stacked */
.progress-bar-stack {
  height: 8px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 4px;
  overflow: hidden;
  display: flex;
  margin-bottom: var(--space-2);
}

.progress-segment {
  height: 100%;
  transition: width var(--transition-slow);
}

.progress-segment--completed {
  background: var(--color-completed);
}

.progress-segment--processing {
  background: var(--color-active);
}

.progress-segment--pending {
  background: var(--color-pending);
}

.progress-legend {
  display: flex;
  gap: var(--space-4);
  font-size: var(--text-xs);
  color: var(--text-secondary);
}

.dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: var(--space-1);
}

.dot--completed { background: var(--color-completed); }
.dot--processing { background: var(--color-active); }
.dot--pending { background: var(--color-pending); }
```

---

### 2. **CollapsibleSection** (Mejorar Jerarquía)

#### Problemas Actuales
- Todas las secciones tienen misma importancia visual
- Iconos emoji (no profesionales)
- Sin indicador de contenido dentro

#### Mejoras Propuestas

```jsx
// CollapsibleSection.jsx (mejorado)
<div className={`collapsible-section collapsible-section--${priority}`}>
  <button
    className="collapsible-section__header"
    onClick={toggle}
    aria-expanded={!collapsed}
  >
    <div className="collapsible-section__left">
      <ChevronIcon className={`chevron ${!collapsed ? 'chevron--open' : ''}`} />
      <IconComponent className="section-icon" /> {/* SVG, no emoji */}
      <h3 className="section-title">{title}</h3>
      {badge && <span className="section-badge">{badge}</span>}
    </div>
    <div className="collapsible-section__right">
      {summary && <span className="section-summary">{summary}</span>}
    </div>
  </button>
  
  {!collapsed && (
    <div className="collapsible-section__content">
      {children}
    </div>
  )}
</div>
```

#### CSS con Prioridades

```css
/* Prioridad ALTA (errores, crítico) */
.collapsible-section--high {
  border: 2px solid var(--color-error);
  background: rgba(244, 67, 54, 0.05);
}

.collapsible-section--high .section-icon {
  color: var(--color-error);
}

/* Prioridad MEDIA (análisis, status) */
.collapsible-section--medium {
  border: 1px solid var(--border-color);
}

/* Prioridad BAJA (database status) */
.collapsible-section--low {
  border: 1px solid rgba(255, 255, 255, 0.05);
  opacity: 0.8;
}

.collapsible-section__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-3) var(--space-4);
  cursor: pointer;
  transition: var(--transition-fast);
}

.collapsible-section__header:hover {
  background: rgba(255, 255, 255, 0.03);
}

.collapsible-section__header:focus-visible {
  outline: 2px solid var(--color-info);
  outline-offset: 2px;
}

.chevron {
  width: 16px;
  height: 16px;
  transition: transform var(--transition-normal);
}

.chevron--open {
  transform: rotate(90deg);
}

.section-title {
  font-family: var(--font-heading);
  font-size: var(--text-md);
  font-weight: 600;
  color: var(--text-primary);
  margin: 0;
}

.section-badge {
  font-size: var(--text-xs);
  padding: 2px 8px;
  border-radius: 12px;
  background: var(--color-info);
  color: var(--bg-base);
  font-weight: 600;
}

.section-summary {
  font-size: var(--text-xs);
  color: var(--text-secondary);
}
```

---

### 3. **ErrorAnalysisPanel** (Visualización Mejorada)

#### Mejoras Propuestas

```jsx
// ErrorCard para cada tipo de error
<div className="error-card">
  <div className="error-card__header">
    <AlertIcon className="error-card__icon" />
    <div className="error-card__info">
      <h4 className="error-card__title">{errorType}</h4>
      <p className="error-card__message">{errorMessage}</p>
    </div>
    <span className="error-card__count">{count}</span>
  </div>
  
  {/* Barra de severidad */}
  <div className="error-card__severity">
    <div className="severity-bar" style={{ width: `${(count / totalErrors) * 100}%` }} />
  </div>
  
  {/* Acciones */}
  <div className="error-card__actions">
    <button className="btn-ghost btn-sm">
      <EyeIcon /> Ver docs ({count})
    </button>
    {canAutoFix && (
      <button className="btn-primary btn-sm">
        <RefreshIcon /> Reintentar
      </button>
    )}
  </div>
</div>
```

---

### 4. **WorkerLoadCard** (Chart Mejorado)

#### Mejoras Propuestas

- Usar D3.js con mejor layout
- Hover tooltips informativos
- Color coding por estado (activo/idle/error)
- Animaciones smooth (transitions)

```jsx
// D3 Worker Load Chart
const WorkerLoadChart = ({ workers }) => {
  useEffect(() => {
    const svg = d3.select(svgRef.current);
    
    // Escala de colores por estado
    const colorScale = d3.scaleOrdinal()
      .domain(['active', 'idle', 'error'])
      .range([
        'var(--color-active)',
        'var(--color-pending)',
        'var(--color-error)'
      ]);
    
    // Tooltip
    const tooltip = d3.select('body').append('div')
      .attr('class', 'worker-tooltip')
      .style('opacity', 0);
    
    // Bars with transition
    svg.selectAll('.worker-bar')
      .data(workers)
      .join(
        enter => enter.append('rect')
          .attr('class', 'worker-bar')
          .attr('y', (d, i) => i * 30)
          .attr('height', 24)
          .attr('width', 0)
          .attr('fill', d => colorScale(d.status))
          .call(enter => enter.transition()
            .duration(500)
            .attr('width', d => d.load * 100)
          ),
        update => update
          .call(update => update.transition()
            .duration(300)
            .attr('width', d => d.load * 100)
            .attr('fill', d => colorScale(d.status))
          )
      )
      .on('mouseover', (event, d) => {
        tooltip.transition().duration(200).style('opacity', 1);
        tooltip.html(`
          <strong>${d.worker_id}</strong><br/>
          Status: ${d.status}<br/>
          Load: ${(d.load * 100).toFixed(1)}%<br/>
          Docs: ${d.documents_processed}
        `)
          .style('left', (event.pageX + 10) + 'px')
          .style('top', (event.pageY - 28) + 'px');
      })
      .on('mouseout', () => {
        tooltip.transition().duration(200).style('opacity', 0);
      });
  }, [workers]);
  
  return <svg ref={svgRef} width={400} height={workers.length * 30} />;
};
```

---

### 5. **Iconos Profesionales** (Heroicons)

Reemplazar emojis por SVG:

```bash
npm install @heroicons/react
```

```jsx
import {
  DocumentTextIcon,
  CpuChipIcon,
  ClockIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  XCircleIcon,
  ArrowPathIcon,
  ChartBarIcon,
  ServerIcon,
  LightBulbIcon
} from '@heroicons/react/24/outline';

// Uso
<DocumentTextIcon className="icon-md text-info" />
```

---

### 6. **Export Functions** (Nuevo Feature)

```jsx
// ExportMenu.jsx (nuevo componente)
<div className="export-menu">
  <button className="btn-ghost" onClick={toggleMenu}>
    <ArrowDownTrayIcon /> Export
  </button>
  
  {menuOpen && (
    <div className="export-dropdown">
      <button onClick={() => exportData('csv')}>
        <DocumentIcon /> CSV
      </button>
      <button onClick={() => exportData('json')}>
        <CodeBracketIcon /> JSON
      </button>
      <button onClick={() => exportScreenshot()}>
        <CameraIcon /> Screenshot (PNG)
      </button>
    </div>
  )}
</div>
```

---

### 7. **Brushing & Linking** (Coordinar Visualizaciones)

```jsx
// useDashboardState.jsx (hook compartido)
const DashboardContext = createContext();

export function DashboardProvider({ children }) {
  const [selectedTimeRange, setSelectedTimeRange] = useState(null);
  const [selectedStatus, setSelectedStatus] = useState(null);
  const [selectedWorkers, setSelectedWorkers] = useState([]);
  
  const value = {
    filters: { selectedTimeRange, selectedStatus, selectedWorkers },
    setTimeRange: setSelectedTimeRange,
    setStatus: setSelectedStatus,
    setWorkers: setSelectedWorkers,
    clearFilters: () => {
      setSelectedTimeRange(null);
      setSelectedStatus(null);
      setSelectedWorkers([]);
    }
  };
  
  return (
    <DashboardContext.Provider value={value}>
      {children}
    </DashboardContext.Provider>
  );
}

// En cualquier componente
const { filters, setTimeRange } = useDashboard();

// Cuando usuario selecciona rango en timeline
onBrushEnd={(range) => setTimeRange(range)} // Propaga a todos los componentes
```

---

## 📋 Plan de Implementación

### Fase 1: Design System Base (2h)
- [ ] Crear `design-tokens.css` con variables CSS
- [ ] Importar Fira Code + Fira Sans
- [ ] Aplicar sistema de espaciado (4px grid)
- [ ] Actualizar `PipelineDashboard.css` con tokens

### Fase 2: Componentes Core (2-3h)
- [ ] Refactorizar `PipelineSummaryCard` con KPICard
- [ ] Mejorar `CollapsibleSection` con prioridades
- [ ] Instalar y configurar Heroicons
- [ ] Reemplazar emojis por SVG icons

### Fase 3: Visualizaciones (2h)
- [ ] Mejorar `WorkerLoadCard` con D3.js
- [ ] Optimizar `ErrorAnalysisPanel` con error cards
- [ ] Agregar tooltips informativos a todos los charts

### Fase 4: Features + Polish (1-2h)
- [ ] Implementar `ExportMenu` component
- [ ] Mejorar `useDashboardFilters` para brushing & linking
- [ ] Agregar keyboard navigation
- [ ] Testing accesibilidad (WCAG AA)
- [ ] Responsive testing (mobile, tablet, desktop)

---

## ✅ Checklist Pre-Delivery

### Design System
- [ ] CSS variables definidas y usadas consistentemente
- [ ] Fira Code para números/código, Fira Sans para texto
- [ ] Espaciado en múltiplos de 4px
- [ ] Transiciones 150-300ms en todos los interactivos

### Accesibilidad
- [ ] Contraste mínimo 4.5:1 en todos los textos
- [ ] Focus states visibles (outline 2px)
- [ ] Keyboard navigation funciona en todos los componentes
- [ ] ARIA labels en iconos y botones
- [ ] prefers-reduced-motion respetado

### Performance
- [ ] Charts optimizados (max 1000 datapoints)
- [ ] Debounce en auto-refresh (20s + exponential backoff)
- [ ] Lazy loading para paneles colapsados
- [ ] D3 cleanup en useEffect return

### Funcionalidad
- [ ] Brushing & linking funciona entre visualizaciones
- [ ] Export CSV/JSON/PNG funcional
- [ ] Tooltips informativos en todos los charts
- [ ] Loading states + error handling gracioso

---

## 📊 Métricas de Éxito

| Métrica | Antes | Objetivo | Validación |
|---------|-------|----------|------------|
| **Contraste mínimo** | 3.5:1 | 4.5:1 | WCAG AA checker |
| **Render inicial** | 3-4s | <2s | Performance profiler |
| **Consistencia CSS** | 60% | 95% | Audit de variables |
| **Accesibilidad** | No verificada | WCAG AA | axe DevTools |
| **Export functions** | 0 | 3 (CSV/JSON/PNG) | Manual testing |

---

## 📚 Referencias

- `VISUAL_ANALYTICS_GUIDELINES.md` - Paleta y principios
- `D3_SANKEY_REFERENCE.md` - Patrones D3.js
- UI/UX Pro Max - Data-Dense Dashboard pattern
- Heroicons - https://heroicons.com/
- WCAG 2.1 AA - https://www.w3.org/WAI/WCAG21/quickref/

---

**Última actualización**: 2026-04-07  
**Estado**: PROPUESTA - Listo para implementar
