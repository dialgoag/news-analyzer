# Visual Analytics Guidelines - NewsAnalyzer-RAG

> Lineamientos de diseño visual para dashboards, tablas y reportes siguiendo principios de analítica visual e información.

**Última actualización**: 2026-03-04  
**Fase AI-DLC**: 02-construction  
**Audiencia**: Frontend developers, UX/UI designers, product team  
**Objetivo**: Garantizar coherencia visual, usabilidad y accesibilidad en todos los dashboards del sistema

---

## 1. Principios Fundamentales

### 1.1 Claridad visual
- **Una acción = una reacción visual clara**
- Los usuarios deben saber siempre qué está seleccionado, hovered, o activo
- El feedback visual debe ser **inmediato** (transiciones 0.2-0.3s)

### 1.2 Jerarquía de información
- **Información crítica**: colores vivos, tamaño mayor, contraste alto
- **Información secundaria**: colores suaves, tamaño menor, contraste moderado
- **Información terciaria**: mínimo resaltado, fácil de ignorar

### 1.3 Consistencia
- Los mismos patrones visuales se usan en todos los dashboards
- Colores y significados son predefinidos (no varían por componente)
- Transiciones y animaciones son uniformes

### 1.4 Accesibilidad
- Relación de contraste WCAG AA mínimo (4.5:1 para texto)
- No usar solo color para transmitir información (usar también iconos, bordes, patrones)
- Todos los elementos interactivos deben ser accesibles vía teclado

---

## 2. Paleta de Colores y Semántica

### 2.1 Estados de datos

| Estado | Color primario | Color de fondo | Caso de uso |
|--------|---|---|---|
| **Activo/Procesando** | `#4caf50` (verde) | `rgba(76, 175, 80, 0.1)` | Worker procesando, documento en proceso |
| **En espera** | `#ff9800` (naranja) | `rgba(255, 152, 0, 0.1)` | Worker ocioso, tarea pendiente |
| **Completado** | `#2196f3` (azul) | `rgba(33, 150, 243, 0.1)` | Documento indexado, tarea terminada |
| **Error** | `#f44336` (rojo) | `rgba(244, 67, 54, 0.1)` | Error en procesamiento, fallo en conexión |
| **Advertencia** | `#ff5722` (rojo-naranja) | `rgba(255, 87, 34, 0.1)` | Revisar manualmente, requiere atención |
| **Info/Neutral** | `#4dd0e1` (cyan) | `rgba(77, 208, 225, 0.1)` | Información general, resaltado neutro |

### 2.2 Elementos de interfaz

| Elemento | Color | Uso |
|---|---|---|
| **Fondo base** | `#0f172a` (gris-azul muy oscuro) | Fondo principal del dashboard |
| **Panel** | `#1e1e2e` (gris-azul oscuro) | Contenedores, tarjetas |
| **Borde** | `#334155` (gris-azul) | Separadores, bordes de elementos |
| **Texto principal** | `#f1f5f9` (blanco-gris) | Títulos, contenido importante |
| **Texto secundario** | `#cbd5e1` (gris claro) | Etiquetas, información secundaria |
| **Texto deshabilitado** | `#64748b` (gris) | Elementos deshabilitados, no interactivos |

---

## 3. Componentes Interactivos

### 3.1 Tablas y listas

**Selección de filas:**
```
Estado: No seleccionado
- Fondo: `#1a1a2e`
- Borde: `#334155` (1px)
- Efecto hover: Fondo -> `#334155`, cursor pointer

Estado: Seleccionado
- Fondo: `rgba(77, 208, 225, 0.15)` (cyan tenue)
- Borde izquierdo: `3px solid #4dd0e1` (cyan)
- Sombra: inset 0 0 10px rgba(77, 208, 225, 0.1)

Transición: todas 0.2s ease
```

**Headers sticky:**
```
Posición: sticky top-0 z-10
Fondo: `#2d2d44` (más oscuro que panel)
Borde inferior: 2px solid #4dd0e1
Sombra: 0 2px 4px rgba(0, 0, 0, 0.3)
```

**Filas con estado:**
```
Cada fila debe indicar visualmente su estado:

Procesando: borde izquierdo 2px verde, fondo rgba(76, 175, 80, 0.05)
En espera: borde izquierdo 2px naranja, fondo rgba(255, 152, 0, 0.05)
Completado: borde izquierdo 2px azul, fondo rgba(33, 150, 243, 0.05)
Error: borde izquierdo 2px rojo, fondo rgba(244, 67, 54, 0.05)
```

### 3.2 Botones y controles

**Estados del botón:**

```
Hover: 
  - Fondo brilla (+ 10% opacidad)
  - Sombra: 0 4px 12px rgba(77, 208, 225, 0.3)
  - Transformación: scale(1.02)

Activo (click):
  - Sombra: inset 0 2px 4px rgba(0, 0, 0, 0.3)
  - Transformación: scale(0.98)

Deshabilitado:
  - Opacidad: 0.5
  - Cursor: not-allowed
  - Sin hover effects
```

### 3.3 Badges y indicadores

**Worker status badges:**
```
Active: 
  - Fondo: #4caf50
  - Texto: blanco
  - Sombra: 0 0 10px rgba(76, 175, 80, 0.5)
  - Animación: pulse suave (0.5s)

Idle:
  - Fondo: #ff9800
  - Texto: blanco
  - Sin sombra

Completed:
  - Fondo: #2196f3
  - Texto: blanco

Error:
  - Fondo: #f44336
  - Texto: blanco
  - Animación: parpadeo suave (0.3s)
```

---

## 4. Patrones de Interacción

### 4.1 Selección múltiple en tablas

**Comportamiento esperado:**
```
✓ Checkbox en header -> selecciona todas las filas visibles
✓ Checkbox en fila -> selecciona solo esa fila
✓ Row click (con Ctrl/Cmd) -> multiseleccionar
✓ Row click (sin Ctrl/Cmd) -> seleccionar solo esa
✓ Selected rows se resaltan con:
  - Fondo: rgba(77, 208, 225, 0.15)
  - Borde izquierdo: 3px solid #4dd0e1
✓ Action bar aparece cuando hay selección (en la parte superior)
```

### 4.2 Expansión/Colapso

**Comportamiento esperado:**
```
✓ Indicador visual: triángulo rotativo (▼)
✓ Rotación: 180° cuando expandido, 0° cuando colapsado
✓ Transición: 0.3s ease
✓ Cursor: pointer en todo el área
✓ Tooltip: "Expandir" / "Contraer"
✓ Contador de items: mostrado siempre (ej: "5 reportes")
```

### 4.3 Acciones contextuales

**Botones de acción en filas:**
```
Mostrar solo en hover de la fila (no siempre visible)
Estar agrupados a la derecha
Iconos con tooltips claros:
  - Ver: 👁️ "Ver detalles"
  - Editar: ✏️ "Editar"
  - Descargar: ⬇️ "Descargar"
  - Eliminar: 🗑️ "Eliminar"
Confirmación requerida para acciones destructivas
```

---

## 5. Tipografía y Tamaños

| Elemento | Tamaño | Peso | Espaciado |
|---|---|---|---|
| **Título principal** | 1.875rem (30px) | 700 (bold) | 0 |
| **Título secundario** | 1.125rem (18px) | 600 (semibold) | 0 |
| **Encabezado tabla** | 0.875rem (14px) | 600 (semibold) | -0.5px |
| **Contenido** | 0.875rem (14px) | 400 (normal) | 0 |
| **Pequeño/Help** | 0.75rem (12px) | 400 (normal) | 0.5px |

---

## 6. Espaciado y Layout

### 6.1 Márgenes y padding

```
Panel principal: px-6 py-6 (24px)
Encabezado panel: p-4 (16px)
Fila tabla: px-4 py-3 (16px horizontal, 12px vertical)
Gap entre elementos: gap-4 (16px)
Borde: border (1px)
Radio: rounded-lg (8px)
```

### 6.2 Scroll areas

**Para tablas grandes:**
```
Contenedor padre: flex-1 overflow-auto
Encabezado: sticky top-0 z-10
Max-height si es necesario: max-h-[600px]
Scroll bar personalizada (webkit):
  - Ancho: 8px
  - Color: rgba(77, 208, 225, 0.6)
  - Hover: rgba(77, 208, 225, 0.8)
```

---

## 7. Animaciones y Transiciones

### 7.1 Duraciones estándar

- **Hover/focus**: 0.2s ease
- **Expansión/colapso**: 0.3s ease
- **Cambio de estado**: 0.3s ease
- **Entrada**: 0.4s ease-out

### 7.2 Animaciones específicas

```
Pulse (para activos):
  @keyframes pulse {
    0%, 100% { opacity: 1 }
    50% { opacity: 0.7 }
  }
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite

Parpadeo (para errores):
  @keyframes blink {
    0%, 49%, 100% { opacity: 1 }
    50%, 99% { opacity: 0.5 }
  }
  animation: blink 0.3s infinite
```

---

## 8. Dashboard - Layout estándar

### 8.1 Estructura visual

```
┌─────────────────────────────────────────────────────┐
│ [▼ Título colapsable]                               │
│ └─ Contenido (cuando expandido)                     │
├─────────────────────────────────────────────────────┤
│ [Columna 1]                    │ [Columna 2]        │
│ (30-40% ancho)                 │ (60-70% ancho)     │
│                                │                    │
│ - Header sticky                │ - Tabla scrollable │
│ - Elementos con estado         │ - Seleccionar filas│
│ - Badges coloridas             │ - Acciones hover   │
└─────────────────────────────────────────────────────┘
```

### 8.2 Reglas de color por contexto

**Workers:**
- Activo: verde (#4caf50)
- Ocioso: naranja (#ff9800)
- Error: rojo (#f44336)

**Documentos:**
- Pendiente: naranja (#ff9800)
- Procesando: verde (#4caf50)
- Indexado: azul (#2196f3)
- Error: rojo (#f44336)

**Reportes:**
- Generado: verde (#4caf50)
- Actualizado: cyan (#4dd0e1)
- Fallo: rojo (#f44336)

---

## 9. Implementación en Componentes React

### 9.1 Table row with selection

```jsx
<tr 
  onClick={handleSelect}
  className={`
    cursor-pointer transition-all
    ${isSelected 
      ? 'bg-cyan-900/15 border-l-4 border-l-cyan-400 shadow-inner' 
      : 'bg-slate-800 border-l-4 border-l-transparent'
    }
    ${status === 'active' && 'bg-green-900/5'}
    ${status === 'error' && 'bg-red-900/5'}
    hover:bg-slate-700/50
  `}
>
  {/* Row content */}
</tr>
```

### 9.2 Status badge

```jsx
<span className={`
  inline-block px-3 py-1 rounded text-white text-sm font-semibold
  ${status === 'active' && 'bg-green-500 shadow-lg shadow-green-500/50 animate-pulse'}
  ${status === 'idle' && 'bg-yellow-600'}
  ${status === 'error' && 'bg-red-500 animate-blink'}
`}>
  {status}
</span>
```

### 9.3 Expandible section

```jsx
<button 
  onClick={() => setExpanded(!expanded)}
  className="w-full flex items-center gap-2 hover:opacity-80 transition"
>
  <span className={`transform transition-transform ${expanded ? 'rotate-180' : ''}`}>
    ▼
  </span>
  <h3 className="font-bold text-white">📊 Title</h3>
  <span className="text-sm text-slate-400">{count} items</span>
</button>
{expanded && (
  <div className="mt-3 animate-in fade-in duration-300">
    {/* Content */}
  </div>
)}
```

---

## 10. Checklist de implementación

- [ ] Todos los estados tienen color semántico definido
- [ ] Tabla: headers sticky, selectable, resaltable
- [ ] Tabla: filas tienen indicador visual de estado (borde izquierdo)
- [ ] Botones: hover, active, disabled states claros
- [ ] Badges: animación para estados activos
- [ ] Expansibles: triángulo rotativo, contador visible
- [ ] Scroll: personalizado, visible
- [ ] Transiciones: suave (0.2-0.3s)
- [ ] Contraste: mínimo WCAG AA (4.5:1)
- [ ] Tooltips: en todos los iconos
- [ ] Acciones: requieren confirmación si destructivas
- [ ] Responsivo: funciona en móvil (stack vertical)

---

## 11. Próximos pasos

### Para Dashboard de Insights
Seguir los mismos lineamientos:
- Tabla de insights con selección
- Código de color por tipo de insight
- Expandibles para resúmenes
- Badges para métricas
- Gráficos pequeños con colores semánticos

### Para Reportes
- Usar paleta consistente
- Headers sticky en reportes largos
- Expandibles para secciones
- Código de color para temas/patrones

---

## 12. D3.js Advanced Patterns (NUEVO - 2026-03-13)

### 12.1 Brushing & Linking (Interconexión)

**Concepto**: Click/select en una visualización filtra automáticamente las demás.

**Ejemplo**:
```javascript
// Timeline con brush
const brush = d3.brushX()
  .extent([[0, 0], [width, height]])
  .on('end', (event) => {
    if (!event.selection) return;
    const [x0, x1] = event.selection;
    const timeRange = [xScale.invert(x0), xScale.invert(x1)];
    
    // Actualizar filtro global → afecta todas las visualizaciones
    updateFilter('timeRange', timeRange);
  });
```

**Resultado**: Seleccionar rango de tiempo en timeline automáticamente filtra Sankey, Heatmap, y otras visualizaciones.

### 12.2 Coordinated Multiple Views

**Patrón**: Varias visualizaciones muestran mismos datos desde diferentes perspectivas, coordinadas por estado compartido.

```
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  Sankey Flow    │  │   Timeline      │  │  Heatmap        │
│  (por stage)    │  │   (temporal)    │  │  (workers)      │
└─────────────────┘  └─────────────────┘  └─────────────────┘
         ↓                    ↓                     ↓
         └──────────── Filters State ───────────────┘
                    (stage, timeRange, workerId)
```

**Implementación**:
```javascript
const DashboardContext = createContext();

// Provider envuelve todas las visualizaciones
<DashboardProvider>
  <SankeyChart />
  <Timeline />
  <Heatmap />
</DashboardProvider>

// Cada visualización usa el mismo hook
const { filters, updateFilter } = useDashboardFilters();
```

### 12.3 Enter/Update/Exit Pattern

**Patrón fundamental** para transiciones suaves:

```javascript
// DATA JOIN
const bars = svg.selectAll('.bar').data(data, d => d.id);

// EXIT: elementos que ya no tienen datos
bars.exit()
  .transition().duration(300)
  .attr('opacity', 0)
  .remove();

// ENTER: elementos nuevos
const enter = bars.enter()
  .append('rect')
  .attr('class', 'bar')
  .attr('opacity', 0);

// UPDATE: todos los elementos (existentes + nuevos)
bars.merge(enter)
  .transition().duration(300)
  .attr('x', d => xScale(d.category))
  .attr('y', d => yScale(d.value))
  .attr('opacity', 1);
```

**Sin esto**: Elementos aparecen/desaparecen bruscamente.  
**Con esto**: Transiciones suaves, mejor UX.

### 12.4 React + D3 Integration

**REGLA CRÍTICA**: React maneja el DOM, D3 maneja cálculos y atributos.

```javascript
// ❌ MAL: D3 crea elementos DOM
d3.select(ref).append('div').attr('class', 'chart');

// ✅ BIEN: React crea, D3 actualiza
<svg ref={svgRef}>
  <g className="chart-group"></g>
</svg>

useEffect(() => {
  const g = d3.select(svgRef.current).select('.chart-group');
  // D3 solo actualiza atributos existentes
  g.selectAll('.bar').data(data).join('rect')...
}, [data]);
```

### 12.5 Performance con D3

**Optimizaciones clave**:

1. **Memoizar layouts costosos**:
```javascript
const sankeyData = useMemo(() => {
  return d3Sankey.sankey()(graphData);
}, [graphData]);
```

2. **Debounce filtros**:
```javascript
const handleFilterChange = useMemo(
  () => debounce((value) => updateFilter('search', value), 300),
  []
);
```

3. **Lazy load visualizaciones pesadas**:
```javascript
const ForceGraph = lazy(() => import('./ForceGraph'));

<Suspense fallback={<div>Loading...</div>}>
  <ForceGraph nodes={nodes} links={links} />
</Suspense>
```

### 12.6 Visualizaciones Avanzadas

#### Sankey Diagram
**Uso**: Flujo de datos entre stages del pipeline.  
**Librería**: `d3-sankey@0.12.3` (plugin separado, NO parte de d3 core)  
**API clave**: `d3.sankey()`, `d3.sankeyLinkHorizontal()`, `d3.sankeyJustify`  
**Best Practice**: Click en node/link para filtrar. Gradiente `source-target` para links. `mix-blend-mode: "screen"` en fondos oscuros.  
**Referencia completa**: Ver [`02-construction/D3_SANKEY_REFERENCE.md`](./D3_SANKEY_REFERENCE.md) — API completa, código de referencia de Observable (Mike Bostock), patrones de D3 Graph Gallery, y análisis de gaps con nuestra implementación.

#### Force-Directed Graph
**Uso**: Relaciones entre entidades/topics.  
**API**: `d3.forceSimulation()`, `d3.forceLink()`, `d3.forceManyBody()`  
**Best Practice**: Drag para reorganizar, zoom para explorar.

#### Heatmap
**Uso**: Carga de workers por tiempo.  
**Color**: `d3.scaleSequential(d3.interpolateRdYlGn)`  
**Best Practice**: Tooltip con métricas exactas.

#### Word Cloud
**Uso**: Keywords de insights.  
**Librería**: `d3-cloud`  
**Best Practice**: Tamaño = frecuencia, click para filtrar.

### 12.7 Accessibility en D3

**Siempre incluir**:

```javascript
<svg
  role="img"
  aria-label="Descriptive chart title"
>
  <title>Chart Title</title>
  <desc>Detailed description for screen readers</desc>
  
  <rect
    tabIndex={0}
    role="button"
    aria-label={`${d.category}: ${d.value}`}
    onKeyDown={(e) => {
      if (e.key === 'Enter') handleClick(d);
    }}
  />
</svg>
```

**No solo color**:
```javascript
// Color + patrón para errores
<rect
  fill={colorScale(d.status)}
  stroke={d.status === 'error' ? '#f44336' : 'none'}
  strokeWidth={d.status === 'error' ? 3 : 0}
  strokeDasharray={d.status === 'error' ? '5,5' : 'none'}
/>
```

---

## 13. Dashboard Interactivo: Checklist Completo

Antes de dar por terminado un dashboard, verificar:

### Funcionalidad:
- [ ] Click en visualización A filtra visualización B
- [ ] Brush en timeline filtra todas las vistas
- [ ] Hover muestra tooltips informativos
- [ ] Filtros tienen reset button visible
- [ ] Estado de filtros se muestra claramente

### Performance:
- [ ] Render inicial < 1 segundo
- [ ] Transiciones a 60fps
- [ ] Sin re-renders innecesarios (React.memo, useMemo)
- [ ] Lazy loading en visualizaciones pesadas

### Accesibilidad:
- [ ] Navegable completamente por teclado
- [ ] ARIA labels en SVG elements
- [ ] Contraste WCAG AA (4.5:1)
- [ ] No solo color para información crítica

### Código:
- [ ] React maneja DOM, D3 solo atributos
- [ ] Enter/Update/Exit usado correctamente
- [ ] State management centralizado
- [ ] Componentes reutilizables

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-04 | 1.0 | Creación: lineamientos visuales para dashboards analíticos | AI-DLC |
| 2026-03-13 | 1.1 | Agregado: D3.js Advanced Patterns (§12), Dashboard Checklist (§13) | AI-DLC |
| 2026-03-16 | 1.2 | Ampliado: §12.6 Sankey Diagram con referencia a D3_SANKEY_REFERENCE.md | AI-DLC |
