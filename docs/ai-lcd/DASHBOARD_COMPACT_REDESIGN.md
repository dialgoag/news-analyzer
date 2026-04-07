# 🎨 Plan: Dashboard Compacto + Coordenadas Paralelas Mejoradas

**Fecha**: 2026-04-07  
**Objetivo**: Combinar Opción A (Arreglar Coordenadas Paralelas) + Opción C (Rediseño compacto)  
**Resultado esperado**: Dashboard de ~1200px (vs 2500px actual) con visualización clara de bifurcación

---

## 📐 Layout Propuesto

```
┌───────────────────────────────────────────────┐
│ 🎯 KPIs Inline (Compactos)                    │ ← 60px
│ 20 docs | 45 news | 38 insights | 2 errores   │
├───────────────────────────────────────────────┤
│ 📊 Pipeline Status Table (Compacta)           │ ← 200px
│ Stage | Pending | Processing | Done | Errors  │
├───────────────────────────────────────────────┤
│ 👥 Workers (Compacto) | ⚠️ Errors (si hay)   │ ← 150px
│ 3 active, 2 idle      | 2 upload_failed      │
├───────────────────────────────────────────────┤
│ 🌊 Coordenadas Paralelas MEJORADAS            │ ← 450px
│ (Bifurcación visual + ancho proporcional)     │
│                                               │
│ [Sankey-style: doc grueso → bifurca → news]  │
└───────────────────────────────────────────────┘
Total: ~860px + padding = ~1000px
```

---

## 🔧 Cambios Específicos por Componente

### 1. **KPIs Inline** (Nuevo componente compacto)

**Antes**: 3 KPICards grandes (200px total)  
**Después**: Badges inline horizontales (60px total)

```jsx
// KPIsInline.jsx
<div className="kpis-inline">
  <KPIBadge 
    icon={<DocumentTextIcon />}
    label="Documentos"
    value={stats.total_docs}
    status={stats.docs_status} // 'ok' | 'warning' | 'error'
  />
  <KPIBadge 
    icon={<NewspaperIcon />}
    label="News Items"
    value={stats.total_news}
    status={stats.news_status}
  />
  <KPIBadge 
    icon={<SparklesIcon />}
    label="Insights"
    value={stats.total_insights}
    status={stats.insights_status}
  />
  <KPIBadge 
    icon={<ExclamationCircleIcon />}
    label="Errores"
    value={stats.total_errors}
    status="error"
    highlight={stats.total_errors > 0}
  />
</div>
```

**CSS**:
```css
.kpis-inline {
  display: flex;
  gap: var(--space-2);
  padding: var(--space-3);
  background: var(--bg-panel);
  border-radius: var(--radius-lg);
  flex-wrap: wrap;
}

.kpi-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-2) var(--space-3);
  background: var(--bg-elevated);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  font-size: var(--text-sm);
  font-family: var(--font-body);
  transition: all var(--transition-fast);
}

.kpi-badge--highlight {
  border-color: var(--color-error);
  background: var(--color-error-bg);
  animation: pulse 2s infinite;
}

.kpi-badge__icon {
  width: 18px;
  height: 18px;
}

.kpi-badge__value {
  font-weight: var(--weight-bold);
  font-family: var(--font-heading);
  font-size: var(--text-md);
}
```

**Ganancia**: -140px vertical 📉

---

### 2. **Pipeline Status Table** (Rediseño PipelineAnalysisPanel)

**Antes**: Grid de cards (~1000px)  
**Después**: Tabla horizontal compacta (200px)

```jsx
// PipelineStatusTable.jsx
<table className="pipeline-table">
  <thead>
    <tr>
      <th>Stage</th>
      <th>⏳ Pending</th>
      <th>🔄 Processing</th>
      <th>✓ Done</th>
      <th>❌ Errors</th>
      <th>Status</th>
      <th>Actions</th>
    </tr>
  </thead>
  <tbody>
    {stages.map(stage => (
      <tr key={stage.name} className={getRowClass(stage)}>
        <td className="stage-name">
          <span className="stage-icon" style={{background: stageColors[stage.name]}}>
            {stage.name[0]}
          </span>
          {stage.name}
        </td>
        <td className="stat-cell">{stage.pending}</td>
        <td className="stat-cell stat-cell--processing">{stage.processing}</td>
        <td className="stat-cell stat-cell--done">{stage.done}</td>
        <td className="stat-cell stat-cell--error">{stage.errors}</td>
        <td className="status-cell">
          <StatusBadge stage={stage} />
        </td>
        <td className="actions-cell">
          {isAdmin && <PauseToggle stage={stage} />}
        </td>
      </tr>
    ))}
  </tbody>
</table>
```

**CSS**:
```css
.pipeline-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-sm);
  font-family: var(--font-body);
}

.pipeline-table thead {
  background: var(--bg-elevated);
  border-bottom: 2px solid var(--border-color);
}

.pipeline-table th {
  padding: var(--space-2) var(--space-3);
  text-align: left;
  font-weight: var(--weight-semibold);
  font-size: var(--text-xs);
  color: var(--text-secondary);
  text-transform: uppercase;
}

.pipeline-table tbody tr {
  border-bottom: 1px solid var(--border-light);
  transition: background var(--transition-fast);
}

.pipeline-table tbody tr:hover {
  background: var(--bg-hover);
}

.pipeline-table tbody tr.has-bottleneck {
  border-left: 3px solid var(--color-warning);
}

.pipeline-table tbody tr.has-errors {
  border-left: 3px solid var(--color-error);
}

.stat-cell {
  padding: var(--space-2) var(--space-3);
  text-align: center;
  font-family: var(--font-heading);
  font-weight: var(--weight-semibold);
}

.stat-cell--processing {
  color: var(--color-pending);
}

.stat-cell--done {
  color: var(--color-active);
}

.stat-cell--error {
  color: var(--color-error);
}
```

**Ganancia**: -800px vertical 📉

---

### 3. **Workers + Errors Inline** (Mini widgets lado a lado)

**Antes**: WorkerLoadCard (300px) + ErrorPanel separados  
**Después**: Mini widgets horizontales (150px)

```jsx
// WorkersErrorsInline.jsx
<div className="workers-errors-inline">
  <div className="mini-widget workers-widget">
    <div className="mini-widget-header">
      <UsersIcon className="widget-icon" />
      <h4>Workers</h4>
      <RefreshButton onClick={refresh} />
    </div>
    <div className="mini-widget-content">
      <div className="worker-summary">
        <span className="worker-badge worker-badge--active">
          {activeWorkers} activos
        </span>
        <span className="worker-badge worker-badge--idle">
          {idleWorkers} idle
        </span>
      </div>
      <MiniBarChart data={workerLoadData} height={60} />
    </div>
  </div>

  <div className="mini-widget errors-widget">
    <div className="mini-widget-header">
      <ExclamationTriangleIcon className="widget-icon" />
      <h4>Errores Activos</h4>
      <span className="error-count">{errorCount}</span>
    </div>
    <div className="mini-widget-content">
      {errorCount === 0 ? (
        <div className="no-errors">✓ Sin errores</div>
      ) : (
        <div className="error-summary">
          {errorGroups.slice(0, 3).map(group => (
            <div key={group.id} className="error-item-mini">
              <span className="error-count-badge">{group.count}</span>
              <span className="error-message">{group.message}</span>
            </div>
          ))}
          {errorGroups.length > 3 && (
            <button onClick={expandErrors}>
              Ver todos ({errorGroups.length})
            </button>
          )}
        </div>
      )}
    </div>
  </div>
</div>
```

**CSS**:
```css
.workers-errors-inline {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.mini-widget {
  background: var(--bg-panel);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-3);
  min-height: 150px;
}

.mini-widget-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-light);
}

.mini-widget-header h4 {
  flex: 1;
  margin: 0;
  font-size: var(--text-sm);
  font-weight: var(--weight-semibold);
}

.worker-summary {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.worker-badge {
  font-size: var(--text-xs);
  padding: var(--space-1) var(--space-2);
  border-radius: var(--radius-sm);
}

.worker-badge--active {
  background: var(--color-active-bg);
  color: var(--color-active);
}

.worker-badge--idle {
  background: var(--color-pending-bg);
  color: var(--color-pending);
}
```

**Ganancia**: -150px vertical 📉

---

### 4. **Coordenadas Paralelas MEJORADAS** 🌊

**Cambios clave**:

#### A. Aumentar rango de ancho significativamente

```javascript
// ANTES (imperceptible)
const widthFromNews = 1.2 + Math.min(4.5, targetNewsCount * 0.35);
// Rango: 1.55px - 5.7px (diferencia de 4px)

// DESPUÉS (visible)
const MIN_LINE_WIDTH = 2;
const MAX_LINE_WIDTH = 20;
const widthFromNews = MIN_LINE_WIDTH + Math.min(
  MAX_LINE_WIDTH - MIN_LINE_WIDTH, 
  targetNewsCount * 1.5
);
// Rango: 2px - 20px (diferencia de 18px)
// 1 news = 3.5px, 5 news = 9.5px, 10 news = 17px
```

#### B. Bifurcación visual estilo Sankey

```javascript
// Concepto: En los ejes 1-4 (nivel documento), dibujar UNA línea gruesa
// En el eje 5 (News), dividir en N líneas delgadas

// Nuevo cálculo de posiciones Y con offset de bifurcación
const getBifurcationOffset = (newsIndex, totalNews, docY) => {
  if (totalNews === 1) return docY;
  
  const spreadRange = Math.min(50, totalNews * 3); // Max 50px de spread
  const step = spreadRange / (totalNews - 1);
  const offset = (newsIndex - (totalNews - 1) / 2) * step;
  
  return docY + offset;
};

// En el rendering de segmentos:
segments.forEach((segment, i) => {
  if (segment.toKey === 'news') {
    // Este es el punto de bifurcación
    const newsIndex = line.newsMeta.item_index || 0;
    const totalNews = line.docNewsCount || 1;
    
    // Ancho cambia gradualmente
    const widthStart = line.docWidth; // Ancho del documento
    const widthEnd = 2; // Ancho de una news individual
    
    // Crear gradiente de ancho usando path en vez de line
    const path = d3.path();
    path.moveTo(segment.fromX, segment.fromY);
    // ... bezier curve que adelgaza el trazo
    path.bezierCurveTo(...);
    path.lineTo(
      segment.toX, 
      getBifurcationOffset(newsIndex, totalNews, segment.toY)
    );
    
    // Dibujar como path con stroke-width variable
  } else if (segment.fromKey === 'news') {
    // Después de news, todas las líneas son delgadas (2px)
    strokeWidth = 2;
  } else {
    // Antes de news, línea gruesa
    strokeWidth = line.docWidth;
  }
});
```

#### C. Encoding de color por tipo de línea

```javascript
// Nuevo esquema de colores
function getSegmentColor(segment, line) {
  // Si hay error en este segmento, rojo
  if (segment.state === 'error') return '#f44336';
  
  // Si es bifurcación (hacia news), color especial
  if (segment.toKey === 'news') {
    return line.topicColor || '#4dd0e1'; // Color del tema
  }
  
  // Si es post-bifurcación (después de news)
  if (['insights', 'indexInsights'].includes(segment.toKey)) {
    return getStateColor(segment.state); // Verde/naranja según estado
  }
  
  // Pre-bifurcación (documento)
  return '#2196f3'; // Azul para documento
}
```

#### D. Leyenda visual de la bifurcación

```jsx
<div className="parallel-bifurcation-legend">
  <div className="legend-item">
    <svg width="60" height="30">
      <line x1="0" y1="15" x2="30" y2="15" stroke="#2196f3" strokeWidth="8" />
    </svg>
    <span>Nivel Documento (ancho proporcional a # news)</span>
  </div>
  <div className="legend-item">
    <svg width="60" height="30">
      <line x1="0" y1="10" x2="20" y2="10" stroke="#4dd0e1" strokeWidth="8" />
      <line x1="20" y1="10" x2="40" y2="5" stroke="#4dd0e1" strokeWidth="3" />
      <line x1="20" y1="10" x2="40" y2="15" stroke="#4dd0e1" strokeWidth="3" />
      <line x1="20" y1="10" x2="40" y2="20" stroke="#4dd0e1" strokeWidth="3" />
    </svg>
    <span>Bifurcación en News Items</span>
  </div>
  <div className="legend-item">
    <svg width="60" height="30">
      <line x1="0" y1="15" x2="30" y2="15" stroke="#4caf50" strokeWidth="2" />
    </svg>
    <span>Nivel News Item (1 línea = 1 noticia)</span>
  </div>
</div>
```

#### E. Reducir altura y mejorar scroll

```javascript
// Antes: chartHeight depende de documentos (puede ser 2000px+)
const chartHeight = useMemo(() => {
  const rowHeight = 28 * density;
  const rows = Math.max(docPositions.count, 1);
  return Math.max(520, rows * rowHeight + 240);
}, [docPositions.count, density]);

// Después: Altura fija máxima con scroll interno optimizado
const MAX_CHART_HEIGHT = 450;
const chartHeight = useMemo(() => {
  const rowHeight = 18 * density; // Reducido de 28 a 18
  const rows = Math.max(docPositions.count, 1);
  return Math.min(MAX_CHART_HEIGHT, rows * rowHeight + 180);
}, [docPositions.count, density]);
```

**Ganancia**: -150px vertical promedio 📉

---

## 📊 Comparación Visual

### Antes
```
┌────────────────────┐
│ KPI Card 1         │ 70px
├────────────────────┤
│ KPI Card 2         │ 70px
├────────────────────┤
│ KPI Card 3         │ 70px
├────────────────────┤
│ Pipeline Card 1    │ 200px
│ (Upload)           │
├────────────────────┤
│ Pipeline Card 2    │ 200px
│ (OCR)              │
├────────────────────┤
│ ... 5 más cards    │ 1000px
├────────────────────┤
│ Worker Load Chart  │ 300px
├────────────────────┤
│ Parallel Coords    │ 600px
└────────────────────┘
Total: ~2500px
```

### Después
```
┌────────────────────┐
│ KPIs Inline        │ 60px
├────────────────────┤
│ Pipeline Table     │ 200px
├────────────────────┤
│ Workers | Errors   │ 150px
├────────────────────┤
│ Parallel Coords    │ 450px
│ (Mejoradas)        │
└────────────────────┘
Total: ~860px
```

**Reducción**: -65% de altura 🎉

---

## 🎯 Plan de Implementación

### Fase 1: Componentes Compactos (4-5 horas)
1. ✅ Crear `KPIsInline.jsx` + CSS
2. ✅ Crear `PipelineStatusTable.jsx` (reemplaza PipelineAnalysisPanel cards)
3. ✅ Crear `WorkersErrorsInline.jsx` (mini widgets)
4. ✅ Actualizar layout en `PipelineDashboard.jsx`

### Fase 2: Coordenadas Paralelas Mejoradas (6-8 horas)
1. ✅ Aumentar rango de ancho (2px - 20px)
2. ✅ Implementar bifurcación visual con offset
3. ✅ Cambiar de `<line>` a `<path>` para gradiente de ancho
4. ✅ Nuevo esquema de colores por tipo
5. ✅ Reducir altura máxima a 450px
6. ✅ Agregar leyenda visual de bifurcación

### Fase 3: Testing y Refinamiento (2-3 horas)
1. ✅ Verificar con diferentes cantidades de docs (1, 10, 50)
2. ✅ Ajustar colores para contraste WCAG AA
3. ✅ Optimizar performance (memoization, debounce)
4. ✅ Responsive design para móvil

---

## 🎨 Mockup ASCII del Resultado Final

```
╔═══════════════════════════════════════════════════════════╗
║ 📄 20 docs │ 📰 45 news │ ✨ 38 insights │ ⚠️ 2 errores  ║ 60px
╠═══════════════════════════════════════════════════════════╣
║ Stage    │ ⏳ Pend │ 🔄 Proc │ ✓ Done │ ❌ Err │ Status  ║
║──────────┼─────────┼─────────┼────────┼────────┼─────────║
║ 📤 Upload│    0    │    2    │   18   │   0    │ ✓ OK   ║
║ 👁️ OCR   │    2    │    1    │   17   │   0    │ 🔄 Work║
║ ✂️ Chunk │    3    │    0    │   17   │   0    │ ⏳ Queue║
║ 🔍 Index │    5    │    2    │   13   │   0    │ 🔄 Work║
║ 💡 Insig │   12    │    3    │   30   │   0    │ 🔄 Work║ 200px
╠══════════════════════════╤════════════════════════════════╣
║ 👥 Workers               │ ⚠️ Errores                    ║
║ ─────────────────────────│────────────────────────────────║
║ 3 activos, 2 idle        │ 2 upload_failed               ║
║ [████████░░] 80%         │ 1 ocr_timeout                 ║ 150px
╠══════════════════════════╧════════════════════════════════╣
║ 🌊 Coordenadas Paralelas (Bifurcación Visual)             ║
║                                                            ║
║  Upload   OCR  Chunk Index  News  Insig  IdxIns           ║
║    │      │     │     │      │      │      │               ║
║ ═══╪══════╪═════╪═════╪══════╪══════╪══════╪═══            ║
║    │      │     │     │    ╱ │      │      │               ║
║ ━━━●━━━━━━●━━━━━●━━━━━●━━━┼━━●━━━━━━●━━━━━━●━━━ Doc1(3)   ║
║    │      │     │     │  ╲│  │      │      │               ║
║    │      │     │     │   ●  │      │      │               ║
║    │      │     │     │   │╲ │      │      │               ║
║ ━━━●━━━━━━●━━━━━●━━━━━●━━━┼─●━━━━━━●━━━━━━●━━━ Doc2(5)   ║
║    │      │     │     │   │╱ │      │      │               ║
║    │      │     │     │   ●  │      │      │               ║
║                                                            ║
║ [Leyenda: ══ Documento | ─ News Item | Ancho ∝ #news]    ║ 450px
╚═══════════════════════════════════════════════════════════╝
Total: ~900px
```

---

## ✅ Checklist de Implementación

- [ ] `KPIsInline.jsx` + CSS
- [ ] `PipelineStatusTable.jsx` + CSS  
- [ ] `WorkersErrorsInline.jsx` + CSS
- [ ] Actualizar ancho de líneas (2-20px)
- [ ] Implementar bifurcación con offset
- [ ] Path con gradiente de ancho
- [ ] Colores por tipo de línea
- [ ] Leyenda visual de bifurcación
- [ ] Reducir altura máxima (450px)
- [ ] Testing con diferentes datasets
- [ ] Build y deploy

---

**¿Empezamos con la Fase 1 (componentes compactos)?**
