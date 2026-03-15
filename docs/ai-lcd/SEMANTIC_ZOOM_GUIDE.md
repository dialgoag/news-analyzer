# Zoom Semántico en Pipeline Sankey

> **Implementado**: 2026-03-14  
> **Componente**: `PipelineSankeyChartWithZoom.jsx`  
> **Servicio**: `semanticZoomService.js`

---

## 📊 ¿Qué es el Zoom Semántico?

**Zoom semántico** es una técnica de visualización que permite cambiar el **nivel de detalle** de la información mostrada sin perder el **contexto global**. A diferencia del zoom geométrico (que solo agranda), el zoom semántico **agrega o desagrega datos** según el nivel de detalle deseado.

### Ejemplo:
- **Zoom Out (Agrupado)**: "🟢 100 documentos activos" vs "⚫ 50 documentos no activos"
- **Zoom In (Detallado)**: "📄 20 en OCR, 30 en Chunking, 25 en Indexing, 15 en Insights, 10 en Completed"

---

## 🎯 Objetivos

### Problema
Con **muchos documentos** (100+), el diagrama Sankey se vuelve:
- **Visualmente saturado**: Demasiadas líneas superpuestas
- **Difícil de interpretar**: No se ve el panorama general
- **Lento de renderizar**: Muchos elementos DOM

### Solución
Implementar **zoom semántico jerárquico**:
1. **Nivel 1 (Agrupado)**: Mostrar meta-grupos (Activos vs No Activos)
2. **Nivel 2 (Detallado)**: Mostrar estados individuales (Pending, OCR, Chunking, etc)
3. **Transición interactiva**: Botón para alternar entre niveles
4. **Auto-colapso**: Automático cuando hay >100 documentos

---

## 🏗️ Arquitectura de Implementación

### Jerarquía de Agrupación

```javascript
GROUP_HIERARCHY = {
  active: {
    label: '🟢 Activos',
    color: '#10b981',
    stages: ['pending', 'ocr', 'chunking', 'indexing', 'insights'],
    description: 'Documentos en proceso'
  },
  inactive: {
    label: '⚫ No Activos',
    color: '#6b7280',
    stages: ['completed', 'error'],
    description: 'Documentos finalizados'
  }
}
```

### Estructura de Datos

#### Vista Colapsada (Level 1)
```javascript
{
  type: 'collapsed',
  groups: [
    {
      id: 'active',
      label: '🟢 Activos',
      color: '#10b981',
      metrics: {
        count: 85,              // Total documentos
        totalSize: 1250,        // MB totales
        totalChunks: 12500,     // Chunks totales
        totalNews: 3200,        // Noticias totales
        processing: 25,         // Actualmente procesando
        completed: 0,           // Completados
        error: 0                // Con error
      },
      documents: [...],         // Array de documentos (para drill-down)
      collapsed: true
    },
    {
      id: 'inactive',
      label: '⚫ No Activos',
      color: '#6b7280',
      metrics: { count: 15, ... },
      documents: [...],
      collapsed: true
    }
  ]
}
```

#### Vista Expandida (Level 2)
```javascript
{
  type: 'expanded',
  groups: [
    {
      id: 'active',
      label: '🟢 Activos',
      stages: [
        {
          id: 'pending',
          metaGroup: 'active',
          documents: [...],     // 10 documentos en pending
          metrics: { count: 10, ... }
        },
        {
          id: 'ocr',
          metaGroup: 'active',
          documents: [...],     // 20 documentos en OCR
          metrics: { count: 20, ... }
        },
        // ... más stages
      ],
      collapsed: false
    },
    // ... inactive group
  ]
}
```

---

## 🔧 Funciones Principales del Servicio

### 1. `transformForSemanticZoom(documents, mapStageToColumn, collapsed)`

Transforma documentos crudos a estructura jerárquica para visualización.

**Input**:
- `documents`: Array de documentos normalizados
- `mapStageToColumn`: Función que mapea documento a su stage actual
- `collapsed`: Boolean (true = vista agrupada, false = vista detallada)

**Output**:
- Objeto con estructura jerárquica lista para renderizar

**Ejemplo**:
```javascript
const vizData = transformForSemanticZoom(documents, mapStageToColumn, true);
// Returns: { type: 'collapsed', groups: [...] }
```

### 2. `aggregateGroupMetrics(documents)`

Calcula métricas agregadas para un grupo de documentos.

**Input**: Array de documentos

**Output**:
```javascript
{
  count: 85,
  totalSize: 1250.5,      // MB
  totalChunks: 12500,
  totalNews: 3200,
  totalInsights: 1850,
  processing: 25,
  completed: 0,
  error: 0
}
```

**Uso**: Mostrar totales en tooltips, calcular ancho de flujos agregados

### 3. `shouldAutoCollapse(documentCount, threshold = 100)`

Determina si debe auto-colapsar basándose en número de documentos.

**Ejemplo**:
```javascript
const collapsed = shouldAutoCollapse(150);  // true (>100 docs)
const collapsed = shouldAutoCollapse(50);   // false (<100 docs)
```

### 4. `calculateCollapsedStrokeWidth(metrics, metric, maxValue)`

Calcula ancho de línea de flujo para vista colapsada, basándose en métricas agregadas.

**Ejemplo**:
```javascript
const strokeWidth = calculateCollapsedStrokeWidth(
  { count: 50, totalSize: 750 },
  'count',    // Usar 'count' como métrica
  100         // Valor máximo para normalización
);
// Returns: ~27px (valor entre 2 y 50)
```

### 5. `generateCollapsedTooltipHTML(group)`

Genera HTML para tooltip de grupo colapsado.

**Output**:
```html
<div class="sankey-tooltip-collapsed">
  <div class="tooltip-header">
    <strong>🟢 Activos</strong>
    <span class="tooltip-badge">85 docs</span>
  </div>
  <div class="tooltip-body">
    <p>Documentos en proceso</p>
    <div class="tooltip-metrics">
      <div>📄 Total: 85</div>
      <div>💾 Tamaño: 1250.5 MB</div>
      <div>📰 Noticias: 3200</div>
      <div>🧩 Chunks: 12500</div>
      <div>🟢 Procesando: 25</div>
    </div>
    <p>💡 Click para expandir y ver detalle por estado</p>
  </div>
</div>
```

---

## 🎨 Renderizado Visual

### Vista Colapsada (Agrupada)

```
    🟢 Activos                  ⚫ No Activos
         85                           15
    ──────────────────────────────────────
         │                             │
         │────────── 15 docs ──────────►
         │                             │
         │         (flow line)         │
```

**Características**:
- 2 nodos grandes (círculos)
- 1 línea de flujo (con ancho proporcional)
- Tooltips con métricas agregadas
- Botón "🔍 Expandir" en top-right

### Vista Expandida (Detallada)

```
Upload  OCR  Chunking  Indexing  Insights  Done
  10     20     30        25        15      15
  ───────────────────────────────────────────
  ●─────●──────●─────────●─────────●────────●  Doc1
  ●─────●──────●─────────●─────────────────   Doc2
  ●─────●──────●────────────────────────────  Doc3
  ...
```

**Características**:
- Líneas individuales por documento
- Ancho variable por stage (representa volumen)
- Hover resalta documento individual
- Botón "📊 Agrupar" en top-right

---

## 🔄 Flujo de Interacción

### 1. Carga Inicial

```javascript
// Auto-determinar si colapsar
const [collapsed, setCollapsed] = useState(
  () => shouldAutoCollapse(documents.length)
);

// Si >100 docs: collapsed = true (vista agrupada)
// Si ≤100 docs: collapsed = false (vista detallada)
```

### 2. Transformación de Datos

```javascript
const visualizationData = useMemo(() => 
  transformForSemanticZoom(normalizedDocuments, mapStageToColumn, collapsed),
  [normalizedDocuments, collapsed]
);
```

### 3. Renderizado Condicional

```javascript
if (collapsed) {
  renderCollapsedView(g, visualizationData, ...);
} else {
  renderExpandedView(g, normalizedDocuments, ...);
}
```

### 4. Toggle Interactivo

```javascript
// Click en botón toggle
toggleButton.on('click', () => setCollapsed(!collapsed));

// Efecto: Re-render con nuevo nivel de detalle
// - collapsed: true → false (expandir)
// - collapsed: false → true (colapsar)
```

---

## 📊 Métricas y Agregación

### Cálculo de Valores Agregados

```javascript
// Ejemplo: Grupo "Activos" con 85 documentos
const activeGroup = {
  count: 85,
  totalSize: documents.reduce((sum, doc) => sum + doc.file_size, 0),
  totalChunks: documents.reduce((sum, doc) => sum + doc.chunks_count, 0),
  totalNews: documents.reduce((sum, doc) => sum + doc.news_count, 0),
  processing: documents.filter(doc => doc.status === 'processing').length
};
```

### Ancho de Flujo Proporcional

```javascript
// En vista colapsada, el ancho representa el volumen agregado
const flowValue = inactiveGroup.metrics.count;  // 15 docs completados
const maxFlow = normalizedDocuments.length;     // 100 docs totales
const strokeWidth = calculateCollapsedStrokeWidth(
  { count: flowValue },
  'count',
  maxFlow
);
// strokeWidth ≈ 2 + (50-2) * (15/100) = 9.2px
```

---

## 🎯 Ventajas del Zoom Semántico

### 1. **Escalabilidad**
- ✅ Funciona con 10 documentos
- ✅ Funciona con 1000 documentos
- ✅ Auto-ajusta nivel de detalle

### 2. **Claridad Visual**
- Vista agrupada: Panorama general claro
- Vista detallada: Seguimiento individual
- Transición suave entre niveles

### 3. **Performance**
- Vista colapsada: 2-10 elementos DOM
- Vista expandida: N*6 elementos (N = documentos)
- Auto-colapso previene lag en visualización

### 4. **Contexto Preservado**
- Métricas agregadas muestran totales
- No se pierde información al colapsar
- Drill-down disponible on-demand

---

## 🔧 Configuración y Personalización

### Cambiar Umbral de Auto-Colapso

```javascript
// Por defecto: 100 documentos
const collapsed = shouldAutoCollapse(documents.length, 100);

// Personalizado: 50 documentos
const collapsed = shouldAutoCollapse(documents.length, 50);
```

### Agregar Nuevo Meta-Grupo

```javascript
// En semanticZoomService.js
export const GROUP_HIERARCHY = {
  active: { ... },
  inactive: { ... },
  // Nuevo grupo:
  archived: {
    label: '📦 Archivados',
    color: '#64748b',
    stages: ['archived'],
    description: 'Documentos archivados'
  }
};
```

### Cambiar Métrica de Ancho de Flujo

```javascript
// Usar 'count' (número de documentos)
const strokeWidth = calculateCollapsedStrokeWidth(metrics, 'count', maxValue);

// Usar 'totalSize' (tamaño total en MB)
const strokeWidth = calculateCollapsedStrokeWidth(metrics, 'totalSize', maxSize);

// Usar 'totalNews' (noticias totales)
const strokeWidth = calculateCollapsedStrokeWidth(metrics, 'totalNews', maxNews);
```

---

## 🧪 Testing

### Test 1: Auto-Colapso
```javascript
// Pocos documentos → expandido
const docs = Array(50).fill({});
const collapsed = shouldAutoCollapse(docs.length);
expect(collapsed).toBe(false);

// Muchos documentos → colapsado
const docs = Array(150).fill({});
const collapsed = shouldAutoCollapse(docs.length);
expect(collapsed).toBe(true);
```

### Test 2: Agregación
```javascript
const docs = [
  { file_size: 10, chunks_count: 100, news_count: 5 },
  { file_size: 20, chunks_count: 200, news_count: 8 },
  { file_size: 15, chunks_count: 150, news_count: 6 }
];

const metrics = aggregateGroupMetrics(docs);
expect(metrics.count).toBe(3);
expect(metrics.totalSize).toBe(45);
expect(metrics.totalChunks).toBe(450);
expect(metrics.totalNews).toBe(19);
```

### Test 3: Transformación
```javascript
const docs = normalizedDocuments;
const collapsed = true;
const vizData = transformForSemanticZoom(docs, mapStageToColumn, collapsed);

expect(vizData.type).toBe('collapsed');
expect(vizData.groups).toHaveLength(2);  // active, inactive
expect(vizData.groups[0].metrics.count).toBeGreaterThan(0);
```

---

## 📚 Referencias

- **Componente principal**: `PipelineSankeyChartWithZoom.jsx`
- **Servicio de zoom**: `semanticZoomService.js`
- **Componente original**: `PipelineSankeyChart.jsx` (sin zoom)
- **Servicio de datos**: `documentDataService.js`

### Papers y Recursos
- [Semantic Zoom in Information Visualization](https://en.wikipedia.org/wiki/Semantic_zooming)
- [D3 Expandable Sankey](https://github.com/ricklupton/d3-expandable-sankey)
- [Hierarchical Edge Bundling (Similar Concept)](https://observablehq.com/@d3/hierarchical-edge-bundling)

---

## 🚀 Próximos Pasos

### Mejoras Potenciales

1. **Niveles Múltiples**
   - Nivel 1: Activos vs No Activos (2 grupos)
   - Nivel 2: Por tipo de estado (6 grupos)
   - Nivel 3: Documentos individuales (N grupos)

2. **Animaciones**
   - Transición suave entre niveles
   - Morph de nodos durante expand/collapse
   - Fade in/out de elementos

3. **Filtros en Vista Agrupada**
   - Click en grupo → Filtrar solo ese grupo
   - Drill-down: Click en grupo → Expandir solo ese grupo

4. **Métricas Alternativas**
   - Toggle entre diferentes métricas (count, size, news, chunks)
   - Visualización de múltiples métricas simultáneas

5. **Persistencia de Estado**
   - Guardar preferencia de usuario (collapsed/expanded)
   - localStorage o URL params

---

**Última actualización**: 2026-03-14  
**Versión**: 1.0  
**Autor**: Sistema NewsAnalyzer-RAG
