# Referencia D3-Sankey para NewsAnalyzer-RAG

> Documentación extraída de fuentes oficiales para mejorar el Sankey del dashboard.
>
> **Fecha**: 2026-03-16  
> **Fuentes**:
> - [D3 Graph Gallery - Sankey](https://d3-graph-gallery.com/sankey)
> - [Observable @d3/sankey-component](https://observablehq.com/@d3/sankey-component) (Mike Bostock, 597 forks)
> - [Observable @d3/sankey/2](https://observablehq.com/@d3/sankey/2) (ejemplo simplificado, 295 forks)
> - [d3-sankey GitHub README](https://github.com/d3/d3-sankey) (API Reference oficial)
>
> **Relación con nuestro proyecto**: `PipelineSankeyChartWithZoom.jsx` usa una implementación custom. Este documento recopila patrones oficiales, API completa del plugin, y código de referencia para alinear/mejorar nuestra implementación.

---

## 1. Instalación y Dependencias

### NPM (nuestro caso)
```bash
npm install d3-sankey
# Versión recomendada: d3-sankey@0.12.3
```

### CDN (standalone)
```html
<script src="https://unpkg.com/d3-array@1"></script>
<script src="https://unpkg.com/d3-collection@1"></script>
<script src="https://unpkg.com/d3-path@1"></script>
<script src="https://unpkg.com/d3-shape@1"></script>
<script src="https://unpkg.com/d3-sankey@0"></script>
```

**Nota**: `d3-sankey` NO es parte de d3 core; requiere import separado:
```javascript
import * as d3 from "d3";
import * as d3Sankey from "d3-sankey";
// O si usas require:
// require("d3@7", "d3-sankey@0.12")
```

---

## 2. API Reference Completa (d3-sankey)

### 2.1 Constructor y Layout

#### `d3.sankey()`
Crea un nuevo generador Sankey con settings por defecto.

#### `sankey(arguments…)`
Computa posiciones de nodos y links. Retorna un *graph* con:
- `graph.nodes` — array de nodos con posiciones calculadas
- `graph.links` — array de links con posiciones calculadas

#### `sankey.update(graph)`
Recalcula solo las posiciones de los links (útil tras drag interactivo). Actualiza:
- `link.y0` — posición vertical inicio (en nodo source)
- `link.y1` — posición vertical fin (en nodo target)

### 2.2 Configuración de Nodos

#### `sankey.nodes([nodes])`
Getter/setter del accessor de nodos. Default:
```javascript
function nodes(graph) {
  return graph.nodes;
}
```

**Propiedades asignadas por el layout a cada nodo**:

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `node.sourceLinks` | Array | Links salientes (este nodo es source) |
| `node.targetLinks` | Array | Links entrantes (este nodo es target) |
| `node.value` | Number | Suma de `link.value` de links entrantes (o `fixedValue` si definido) |
| `node.index` | Number | Índice del nodo en el array (zero-based) |
| `node.depth` | Number | Profundidad en el grafo (topología, zero-based) |
| `node.height` | Number | Altura en el grafo (topología, zero-based) |
| `node.layer` | Number | Índice de columna (posición horizontal, zero-based) |
| `node.x0` | Number | Posición horizontal mínima |
| `node.x1` | Number | Posición horizontal máxima (`x0 + nodeWidth`) |
| `node.y0` | Number | Posición vertical mínima |
| `node.y1` | Number | Posición vertical máxima (proporcional a `node.value`) |

#### `sankey.nodeId([id])`
Accessor de ID de nodo. Default: `d => d.index` (numérico).

Para IDs string (recomendado para JSON):
```javascript
sankey.nodeId(d => d.id);

// Permite links con source/target por nombre:
const links = [
  { source: "Upload", target: "OCR", value: 45 },
  { source: "OCR", target: "Chunking", value: 38 }
];
```

#### `sankey.nodeAlign([align])`
Alineación horizontal de nodos. Opciones:

| Función | Comportamiento | Uso |
|---------|---------------|-----|
| `d3.sankeyLeft` | Alinea a la izquierda (`node.depth`) | Flujos lineales |
| `d3.sankeyRight` | Alinea a la derecha (`n - 1 - node.height`) | Flujos inversos |
| `d3.sankeyCenter` | Centro (izquierda, pero nodos sin incoming se mueven a la derecha) | Balanced |
| `d3.sankeyJustify` | **Default**. Nodos sin outgoing se mueven al extremo derecho | **Recomendado para pipeline** |

#### `sankey.nodeSort([sort])`
Orden vertical de nodos dentro de cada columna:
- `undefined` (default): orden automático por layout
- `null`: orden fijo por input
- `function(a, b)`: comparador custom (< 0 = a arriba, > 0 = b arriba)

#### `sankey.nodeWidth([width])`
Ancho de los rectángulos de nodo. **Default: 24px**.

Valor recomendado por Observable: **15px**.

#### `sankey.nodePadding([padding])`
Separación vertical entre nodos adyacentes. **Default: 8px**.

Valor recomendado por Observable: **10px**.

### 2.3 Configuración de Links

#### `sankey.links([links])`
Getter/setter del accessor de links. Cada link requiere:

| Propiedad (input) | Tipo | Descripción |
|-----------|------|-------------|
| `link.source` | ID/Ref | Nodo origen (ID, índice, o referencia) |
| `link.target` | ID/Ref | Nodo destino (ID, índice, o referencia) |
| `link.value` | Number | Valor numérico del flujo |

**Propiedades asignadas por el layout**:

| Propiedad | Tipo | Descripción |
|-----------|------|-------------|
| `link.y0` | Number | Posición vertical inicio (en source) |
| `link.y1` | Number | Posición vertical fin (en target) |
| `link.width` | Number | Ancho del link (proporcional a `value`) |
| `link.index` | Number | Índice del link en el array |

#### `sankey.linkSort([sort])`
Orden vertical de links dentro de cada nodo:
- `undefined` (default): orden automático
- `null`: orden fijo por input
- `function(a, b)`: comparador custom

### 2.4 Extensión y Tamaño

#### `sankey.extent([[x0, y0], [x1, y1]])`
Bounds del layout. Default: `[[0, 0], [1, 1]]`.

```javascript
sankey.extent([[marginLeft, marginTop], [width - marginRight, height - marginBottom]]);
```

#### `sankey.size([width, height])`
Alias de `extent` con origen en `[0, 0]`:
```javascript
sankey.size([width, height]);
// Equivale a: sankey.extent([[0, 0], [width, height]]);
```

#### `sankey.iterations([iterations])`
Iteraciones de relajación del layout. **Default: 6**. Más iteraciones = mejor distribución pero más lento.

### 2.5 Link Path Generator

#### `d3.sankeyLinkHorizontal()`
Retorna un generador de path horizontal para links Sankey en SVG:

```javascript
// Source accessor interno:
function source(d) {
  return [d.source.x1, d.y0]; // sale del borde derecho del nodo source
}

// Target accessor interno:
function target(d) {
  return [d.target.x0, d.y1]; // llega al borde izquierdo del nodo target
}
```

**Uso en renderizado**:
```javascript
svg.append("g")
    .attr("fill", "none")
    .attr("stroke", "#000")
    .attr("stroke-opacity", 0.2)
  .selectAll("path")
  .data(graph.links)
  .join("path")
    .attr("d", d3.sankeyLinkHorizontal())
    .attr("stroke-width", d => d.width);
```

---

## 3. Código de Referencia: SankeyChart Component (Observable)

Componente reutilizable de Mike Bostock (597 forks). Adaptable a React.

### 3.1 Firma de la función

```javascript
function SankeyChart({
  nodes,  // iterable de {id, ...}; inferido de links si falta
  links   // iterable de {source, target, value}
}, {
  // --- Formato ---
  format = ",",                    // d3.format specifier o función
  
  // --- Nodos ---
  align = "justify",               // shorthand para nodeAlign
  nodeId = d => d.id,              // accessor de ID
  nodeGroup,                       // d => ordinalValue (para color)
  nodeGroups,                      // array de valores ordinales
  nodeLabel,                       // d => texto de label
  nodeTitle = d => `${d.id}\n${format(d.value)}`,
  nodeAlign = align,               // left, right, center, justify
  nodeSort,                        // comparador de orden
  nodeWidth = 15,                  // ancho en px
  nodePadding = 10,                // separación vertical en px
  nodeLabelPadding = 6,            // separación label-nodo en px
  nodeStroke = "currentColor",
  nodeStrokeWidth,
  nodeStrokeOpacity,
  nodeStrokeLinejoin,
  
  // --- Links ---
  linkSource = ({source}) => source,
  linkTarget = ({target}) => target,
  linkValue = ({value}) => value,
  linkPath = d3Sankey.sankeyLinkHorizontal(),
  linkTitle = d => `${d.source.id} → ${d.target.id}\n${format(d.value)}`,
  linkColor = "source-target",     // "source", "target", "source-target", o color estático
  linkStrokeOpacity = 0.5,
  linkMixBlendMode = "multiply",
  
  // --- Layout ---
  colors = d3.schemeTableau10,     // paleta de colores
  width = 640,
  height = 400,
  marginTop = 5,
  marginRight = 1,
  marginBottom = 5,
  marginLeft = 1,
} = {})
```

### 3.2 Implementación completa

```javascript
function SankeyChart({ nodes, links }, options = {}) {
  const {
    format = ",", align = "justify", nodeId = d => d.id,
    nodeGroup, nodeGroups, nodeLabel,
    nodeTitle = d => `${d.id}\n${fmt(d.value)}`,
    nodeAlign = align, nodeSort, nodeWidth = 15, nodePadding = 10,
    nodeLabelPadding = 6, nodeStroke = "currentColor",
    nodeStrokeWidth, nodeStrokeOpacity, nodeStrokeLinejoin,
    linkSource = ({source}) => source,
    linkTarget = ({target}) => target,
    linkValue = ({value}) => value,
    linkPath = d3Sankey.sankeyLinkHorizontal(),
    linkTitle = d => `${d.source.id} → ${d.target.id}\n${fmt(d.value)}`,
    linkColor = "source-target", linkStrokeOpacity = 0.5,
    linkMixBlendMode = "multiply",
    colors = d3.schemeTableau10,
    width = 640, height = 400,
    marginTop = 5, marginRight = 1, marginBottom = 5, marginLeft = 1,
  } = options;

  // 1. Convertir nodeAlign string → función
  if (typeof nodeAlign !== "function") nodeAlign = {
    left: d3Sankey.sankeyLeft,
    right: d3Sankey.sankeyRight,
    center: d3Sankey.sankeyCenter
  }[nodeAlign] ?? d3Sankey.sankeyJustify;

  // 2. Extraer arrays de source, target, value
  const LS = d3.map(links, linkSource).map(intern);
  const LT = d3.map(links, linkTarget).map(intern);
  const LV = d3.map(links, linkValue);

  // 3. Inferir nodos de links si no se proporcionaron
  if (nodes === undefined) nodes = Array.from(d3.union(LS, LT), id => ({id}));
  const N = d3.map(nodes, nodeId).map(intern);
  const G = nodeGroup == null ? null : d3.map(nodes, nodeGroup).map(intern);

  // 4. Crear copias mutables para la simulación
  nodes = d3.map(nodes, (_, i) => ({id: N[i]}));
  links = d3.map(links, (_, i) => ({source: LS[i], target: LT[i], value: LV[i]}));

  // 5. Fallback si no hay grupos
  if (!G && ["source", "target", "source-target"].includes(linkColor)) {
    linkColor = "currentColor";
  }
  if (G && nodeGroups === undefined) nodeGroups = G;

  // 6. Escala de color
  const color = nodeGroup == null ? null : d3.scaleOrdinal(nodeGroups, colors);

  // 7. Computar layout Sankey
  d3Sankey.sankey()
      .nodeId(({index: i}) => N[i])
      .nodeAlign(nodeAlign)
      .nodeWidth(nodeWidth)
      .nodePadding(nodePadding)
      .nodeSort(nodeSort)
      .extent([[marginLeft, marginTop], [width - marginRight, height - marginBottom]])
    ({nodes, links});

  // 8. Computar títulos y labels
  const fmt = typeof format !== "function" ? d3.format(format) : format;
  const Tl = nodeLabel === undefined ? N : nodeLabel == null ? null : d3.map(nodes, nodeLabel);
  const Tt = nodeTitle == null ? null : d3.map(nodes, nodeTitle);
  const Lt = linkTitle == null ? null : d3.map(links, linkTitle);

  // 9. UID para clip paths (evitar conflictos)
  const uid = `O-${Math.random().toString(16).slice(2)}`;

  // 10. Crear SVG
  const svg = d3.create("svg")
      .attr("width", width)
      .attr("height", height)
      .attr("viewBox", [0, 0, width, height])
      .attr("style", "max-width: 100%; height: auto; height: intrinsic;");

  // 11. Renderizar nodos (rectángulos)
  const node = svg.append("g")
      .attr("stroke", nodeStroke)
      .attr("stroke-width", nodeStrokeWidth)
      .attr("stroke-opacity", nodeStrokeOpacity)
      .attr("stroke-linejoin", nodeStrokeLinejoin)
    .selectAll("rect")
    .data(nodes)
    .join("rect")
      .attr("x", d => d.x0)
      .attr("y", d => d.y0)
      .attr("height", d => d.y1 - d.y0)
      .attr("width", d => d.x1 - d.x0);

  if (G) node.attr("fill", ({index: i}) => color(G[i]));
  if (Tt) node.append("title").text(({index: i}) => Tt[i]);

  // 12. Renderizar links
  const link = svg.append("g")
      .attr("fill", "none")
      .attr("stroke-opacity", linkStrokeOpacity)
    .selectAll("g")
    .data(links)
    .join("g")
      .style("mix-blend-mode", linkMixBlendMode);

  // 13. Gradientes source-target (si aplica)
  if (linkColor === "source-target") {
    link.append("linearGradient")
        .attr("id", d => `${uid}-link-${d.index}`)
        .attr("gradientUnits", "userSpaceOnUse")
        .attr("x1", d => d.source.x1)
        .attr("x2", d => d.target.x0)
        .call(gradient => gradient.append("stop")
            .attr("offset", "0%")
            .attr("stop-color", ({source: {index: i}}) => color(G[i])))
        .call(gradient => gradient.append("stop")
            .attr("offset", "100%")
            .attr("stop-color", ({target: {index: i}}) => color(G[i])));
  }

  // 14. Path de cada link
  link.append("path")
      .attr("d", linkPath)
      .attr("stroke", linkColor === "source-target"
          ? ({index: i}) => `url(#${uid}-link-${i})`
          : linkColor === "source"
          ? ({source: {index: i}}) => color(G[i])
          : linkColor === "target"
          ? ({target: {index: i}}) => color(G[i])
          : linkColor)
      .attr("stroke-width", ({width}) => Math.max(1, width))
      .call(Lt ? path => path.append("title").text(({index: i}) => Lt[i]) : () => {});

  // 15. Labels de nodos
  if (Tl) svg.append("g")
      .attr("font-family", "sans-serif")
      .attr("font-size", 10)
    .selectAll("text")
    .data(nodes)
    .join("text")
      .attr("x", d => d.x0 < width / 2 ? d.x1 + nodeLabelPadding : d.x0 - nodeLabelPadding)
      .attr("y", d => (d.y1 + d.y0) / 2)
      .attr("dy", "0.35em")
      .attr("text-anchor", d => d.x0 < width / 2 ? "start" : "end")
      .text(({index: i}) => Tl[i]);

  function intern(value) {
    return value !== null && typeof value === "object" ? value.valueOf() : value;
  }

  return Object.assign(svg.node(), {scales: {color}});
}
```

### 3.3 Uso del componente

```javascript
SankeyChart({
  links: csvData  // [{source, target, value}, ...]
}, {
  nodeGroup: d => d.id.split(/\W/)[0],  // primera palabra para color
  nodeAlign: "justify",
  linkColor: "source-target",            // gradiente source→target
  format: (f => d => `${f(d)} TWh`)(d3.format(",.1~f")),
  width: 928,
  height: 600
});
```

---

## 4. Ejemplo Simplificado (Observable @d3/sankey/2)

Versión más directa sin componente reusable, ideal para entender el flujo:

```javascript
const width = 928;
const height = 600;
const format = d3.format(",.0f");

const svg = d3.create("svg")
    .attr("width", width)
    .attr("height", height)
    .attr("viewBox", [0, 0, width, height])
    .attr("style", "max-width: 100%; height: auto; font: 10px sans-serif;");

// Configurar generador Sankey
const sankey = d3.sankey()
    .nodeId(d => d.name)
    .nodeAlign(d3.sankeyJustify)
    .nodeWidth(15)
    .nodePadding(10)
    .extent([[1, 5], [width - 1, height - 5]]);

// Computar layout (copias para no mutar originales)
const {nodes, links} = sankey({
  nodes: data.nodes.map(d => Object.assign({}, d)),
  links: data.links.map(d => Object.assign({}, d))
});

// Escala de color
const color = d3.scaleOrdinal(d3.schemeCategory10);

// Rectángulos de nodos
svg.append("g")
    .attr("stroke", "#000")
  .selectAll()
  .data(nodes)
  .join("rect")
    .attr("x", d => d.x0)
    .attr("y", d => d.y0)
    .attr("height", d => d.y1 - d.y0)
    .attr("width", d => d.x1 - d.x0)
    .attr("fill", d => color(d.category))
  .append("title")
    .text(d => `${d.name}\n${format(d.value)} TWh`);

// Links con gradiente source-target
const link = svg.append("g")
    .attr("fill", "none")
    .attr("stroke-opacity", 0.5)
  .selectAll()
  .data(links)
  .join("g")
    .style("mix-blend-mode", "multiply");

const gradient = link.append("linearGradient")
    .attr("id", d => (d.uid = `link-${d.index}`))
    .attr("gradientUnits", "userSpaceOnUse")
    .attr("x1", d => d.source.x1)
    .attr("x2", d => d.target.x0);
gradient.append("stop")
    .attr("offset", "0%")
    .attr("stop-color", d => color(d.source.category));
gradient.append("stop")
    .attr("offset", "100%")
    .attr("stop-color", d => color(d.target.category));

link.append("path")
    .attr("d", d3.sankeyLinkHorizontal())
    .attr("stroke", d => `url(#${d.uid})`)
    .attr("stroke-width", d => Math.max(1, d.width));

link.append("title")
    .text(d => `${d.source.name} → ${d.target.name}\n${format(d.value)} TWh`);

// Labels
svg.append("g")
  .selectAll()
  .data(nodes)
  .join("text")
    .attr("x", d => d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6)
    .attr("y", d => (d.y1 + d.y0) / 2)
    .attr("dy", "0.35em")
    .attr("text-anchor", d => d.x0 < width / 2 ? "start" : "end")
    .text(d => d.name);
```

---

## 5. Ejemplo Básico (D3 Graph Gallery)

Versión legacy (d3 v4) con drag. Útil para entender el patrón original:

```javascript
var sankey = d3.sankey()
    .nodeWidth(36)
    .nodePadding(290)
    .size([width, height]);

d3.json("data_sankey.json", function(error, graph) {
  sankey.nodes(graph.nodes).links(graph.links).layout(1);

  // Links como paths
  var link = svg.append("g")
    .selectAll(".link")
    .data(graph.links)
    .enter().append("path")
      .attr("class", "link")
      .attr("d", sankey.link())
      .style("stroke-width", function(d) { return Math.max(1, d.dy); })
      .sort(function(a, b) { return b.dy - a.dy; });

  // Nodos con drag
  var node = svg.append("g")
    .selectAll(".node")
    .data(graph.nodes)
    .enter().append("g")
      .attr("class", "node")
      .attr("transform", function(d) {
        return "translate(" + d.x + "," + d.y + ")";
      })
      .call(d3.drag()
        .subject(function(d) { return d; })
        .on("start", function() {
          this.parentNode.appendChild(this);
        })
        .on("drag", dragmove));
});

// CSS para links
// .link { fill: none; stroke: #000; stroke-opacity: .2; }
// .link:hover { stroke-opacity: .5; }
```

---

## 6. Formato de Datos

### 6.1 JSON (nodos + links explícitos)
```json
{
  "nodes": [
    {"id": "Upload"},
    {"id": "OCR"},
    {"id": "Chunking"},
    {"id": "Indexing"},
    {"id": "Insights"},
    {"id": "Completed"},
    {"id": "Error"}
  ],
  "links": [
    {"source": "Upload", "target": "OCR", "value": 45},
    {"source": "OCR", "target": "Chunking", "value": 38},
    {"source": "OCR", "target": "Error", "value": 7},
    {"source": "Chunking", "target": "Indexing", "value": 35},
    {"source": "Indexing", "target": "Insights", "value": 30},
    {"source": "Insights", "target": "Completed", "value": 25},
    {"source": "Insights", "target": "Error", "value": 5}
  ]
}
```

### 6.2 CSV (solo links, nodos inferidos)
```csv
source,target,value
Upload,OCR,45
OCR,Chunking,38
OCR,Error,7
Chunking,Indexing,35
Indexing,Insights,30
Insights,Completed,25
Insights,Error,5
```

Para convertir CSV a nodos+links:
```javascript
const links = await d3.csv("data.csv", d3.autoType);
const nodes = Array.from(
  new Set(links.flatMap(l => [l.source, l.target])),
  name => ({ name, category: name.replace(/ .*/, "") })
);
const data = { nodes, links };
```

### 6.3 Datos de ejemplo (energy.csv del notebook, 68 filas)
```csv
source,target,value
Agricultural 'waste',Bio-conversion,124.729
Bio-conversion,Liquid,0.597
Bio-conversion,Losses,26.862
Bio-conversion,Solid,280.322
...
```

---

## 7. Opciones de Color para Links

Observable documenta 4 estrategias:

| Valor | Efecto | Código SVG |
|-------|--------|-----------|
| `"source-target"` | **Gradiente** de color source → color target | `linearGradient` con 2 stops |
| `"source"` | Color del nodo source | `color(d.source.category)` |
| `"target"` | Color del nodo target | `color(d.target.category)` |
| `"#aaa"` (estático) | Color fijo para todos los links | Valor directo en `stroke` |

### Gradiente source-target (implementación)
```javascript
if (linkColor === "source-target") {
  link.append("linearGradient")
      .attr("id", d => `link-gradient-${d.index}`)
      .attr("gradientUnits", "userSpaceOnUse")
      .attr("x1", d => d.source.x1)    // inicio = borde derecho source
      .attr("x2", d => d.target.x0)    // fin = borde izquierdo target
      .call(g => g.append("stop")
          .attr("offset", "0%")
          .attr("stop-color", d => color(d.source.category)))
      .call(g => g.append("stop")
          .attr("offset", "100%")
          .attr("stop-color", d => color(d.target.category)));
}
```

---

## 8. Patrones de Interactividad

### 8.1 Drag de nodos (D3 Graph Gallery)
```javascript
function dragmove(d) {
  d3.select(this)
    .attr("transform", "translate(" + d.x + "," + (
      d.y = Math.max(0, Math.min(height - d.dy, d3.event.y))
    ) + ")");
  sankey.relayout();
  link.attr("d", sankey.link());
}
```

### 8.2 Hover con opacidad (patrón CSS)
```css
.sankey-link {
  fill: none;
  stroke-opacity: 0.2;
  transition: stroke-opacity 0.2s;
}
.sankey-link:hover {
  stroke-opacity: 0.5;
}
```

### 8.3 mix-blend-mode (Observable)
```javascript
link.style("mix-blend-mode", "multiply");
```
Permite ver superposición de links con transparencia multiplicativa (fondo claro).
Para **fondos oscuros** (nuestro caso): usar `"screen"` o eliminar.

### 8.4 Labels inteligentes (izquierda/derecha según posición)
```javascript
.attr("x", d => d.x0 < width / 2 ? d.x1 + 6 : d.x0 - 6)
.attr("text-anchor", d => d.x0 < width / 2 ? "start" : "end")
```

---

## 9. Diferencias entre nuestra implementación y la referencia

### 9.1 Lo que nuestro `PipelineSankeyChartWithZoom.jsx` hace diferente

| Aspecto | Referencia Observable | Nuestra implementación |
|---------|----------------------|----------------------|
| Layout engine | `d3.sankey()` del plugin | Custom con posiciones manuales por columna |
| Links | `d3.sankeyLinkHorizontal()` (curvas Bézier) | Paths custom con curvas manuales |
| Nodos | Rectángulos simples con label | Columnas + group tags semánticos |
| Interacción | Drag + hover | Double-click collapse/expand + hover |
| Agrupación | No tiene | Grupos semánticos (Activos/No Activos) |
| Datos | `{nodes, links}` estándar | Documentos individuales transformados |
| Color links | Gradiente/source/target/estático | Color por stage del pipeline |

### 9.2 Oportunidades de mejora usando la referencia

1. **Usar `d3.sankeyLinkHorizontal()`** en vez de paths manuales — curvas más suaves y mantenibles
2. **Adoptar `linkColor: "source-target"`** — gradientes entre stages dan continuidad visual
3. **`mix-blend-mode: "screen"`** para fondo oscuro — mejor visibilidad de links superpuestos
4. **`sankey.nodeSort()`** — ordenar nodos por value para priorizar flujos grandes arriba
5. **`sankey.update(graph)`** — para recomputar links tras interacciones sin rehacer todo el layout
6. **Labels con posición inteligente** — left/right según `d.x0 < width / 2`
7. **Formato de datos estándar** `{nodes, links}` — para compatibilidad con ejemplos y debugging

### 9.3 Lo que nuestra implementación hace bien y debe conservarse

1. **Semantic zoom** — Feature avanzada no presente en la referencia
2. **Group tags** — Permite colapsar/expandir grupos de documentos
3. **Integración con `useDashboardFilters`** — Brushing & linking con otros componentes
4. **`documentDataService.js`** — Transformación centralizada (SOLID)
5. **Colores por stage del pipeline** — Semántica clara para nuestro dominio

---

## 10. Standalone HTML (exportado del notebook)

Para probar rápidamente fuera del proyecto:

```html
<!DOCTYPE html>
<meta charset="utf-8">
<title>Sankey diagram component</title>
<link rel="stylesheet" type="text/css" href="./inspector.css">
<body>
<script type="module">
import define from "./index.js";
import {Runtime, Library, Inspector} from "./runtime.js";

const runtime = new Runtime();
const main = runtime.module(define, Inspector.into(document.body));
</script>
```

**Dependencia runtime**: `@observablehq/runtime@5`

---

## 11. Checklist para Aplicar Mejoras

- [ ] Evaluar migración a `d3.sankey()` layout engine (vs. posiciones manuales)
- [ ] Implementar `d3.sankeyLinkHorizontal()` para curvas de links
- [ ] Agregar opción de gradiente `source-target` para links
- [ ] Cambiar `mix-blend-mode` a `"screen"` (fondo oscuro)
- [ ] Estandarizar formato de datos a `{nodes, links}` en `documentDataService.js`
- [ ] Agregar `sankey.nodeSort()` para priorizar flujos grandes
- [ ] Conservar semantic zoom, group tags, y filtros coordinados
- [ ] Tests: verificar que Sankey renderiza con datos reales del pipeline

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-16 | 1.0 | Creación: API reference d3-sankey, código Observable, patrones D3 Graph Gallery, análisis de gaps vs implementación actual | AI-DLC |
