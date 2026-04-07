# Mejoras para Coordenadas Paralelas del Pipeline

## 📊 Propósito de la Visualización

### ¿Qué es?
Una visualización de **coordenadas paralelas** que muestra el flujo completo de procesamiento de documentos a través del pipeline, con capacidad de **bifurcación** en el eje de noticias.

### ¿Para qué sirve?
1. **Identificar cuellos de botella**: Ver en qué etapa se acumulan documentos
2. **Detectar patrones de error**: Visualizar qué temas/documentos fallan más
3. **Analizar granularidad**: Entender la relación documento → news_items → insights
4. **Rastrear flujo completo**: Desde upload hasta indexing de insights

### ¿Cómo funciona?
- **Ejes 1-4** (Upload, OCR, Chunking, Indexing): Cada línea = 1 documento
- **Eje 5** (News Items): **BIFURCACIÓN** - 1 documento → N news_items
- **Ejes 6-7** (Insights, Index Insights): Cada línea = 1 news_item

## 🎨 Mejoras Visuales Propuestas

### 1. Descripción Mejorada
**Antes**:
> "Cada línea representa un documento; en el eje de noticias se bifurca según las noticias detectadas. Usa el zoom vertical y desplázate para inspeccionar detalles."

**Después**:
> **Flujo Pipeline: Documento → Noticias → Insights**
> 
> Visualiza el recorrido completo de cada documento. Las líneas se **bifurcan** en el eje "News Items" (1 doc → N noticias). Filtra por tema, agrupa por fecha, y detecta cuellos de botella.

### 2. Leyenda Expandida

**Actual** (solo estados):
- Paso completado (verde)
- En progreso (naranja)
- Pendiente (azul)
- Error (rojo)

**Propuesta** (estados + conceptos):
```
Estados:
✓ Completado  🔄 En progreso  ⏳ Pendiente  ❌ Error

Conceptos:
📄 Ejes 1-4: Nivel documento (1 línea = 1 PDF)
📰 Eje 5: Bifurcación (1 doc → N news_items)
💡 Ejes 6-7: Nivel news_item (1 línea = 1 noticia + insights)

Controles:
🔍 Click: Filtrar documento
🎨 Click en banda de tema: Filtrar por tema
📊 Agrupaciones: Por documento, día, semana, mes
```

### 3. Título y Contexto

**Antes**:
```
🛰️ Coordenadas Paralelas del Pipeline
```

**Después**:
```
📊 Flujo Pipeline: Documento → Noticias → Insights
Coordenadas paralelas con bifurcación por news_item
```

### 4. Tooltips Mejorados

**Antes**:
```
Documento: example.pdf
Doc ID: abc123
Tema: Política
News: Título noticia (#3)
Insights: done
Indexing: indexed
```

**Después**:
```
📄 Documento: example.pdf (abc123)
📌 Tema: Política
📰 News Item #3: "Título noticia"
   ├─ Insights: done ✓
   └─ Indexing: indexed ✓

Pipeline: Upload ✓ → OCR ✓ → Chunking ✓ → Indexing 🔄
```

### 5. Sección de Ayuda Contextual

Agregar un panel colapsable con:
```
💡 ¿Cómo interpretar esta visualización?

1. Flujo de Izquierda a Derecha
   - Las líneas representan el progreso de los documentos
   - Color indica estado (verde=ok, naranja=procesando, rojo=error)

2. Bifurcación en "News Items"
   - 1 documento se divide en N news_items detectados
   - Cada noticia genera su propia línea hacia Insights

3. Agrupaciones y Filtros
   - Agrupa por fecha para ver tendencias temporales
   - Filtra por tema para analizar categorías específicas
   - Click en líneas para ver detalles

4. Cuellos de Botella
   - Muchas líneas en un eje = posible cuello de botella
   - Revisa el panel "Análisis Pipeline" para más detalles
```

## 🛠️ Implementación Propuesta

### Paso 1: Actualizar Descripción
```jsx
<p className="parallel-description">
  <strong>Flujo Pipeline: Documento → Noticias → Insights</strong>
  <br />
  Visualiza el recorrido completo de cada documento. Las líneas se <strong>bifurcan</strong> en el eje "News Items" (1 doc → N noticias). 
  Filtra por tema, agrupa por fecha, y detecta cuellos de botella.
</p>
```

### Paso 2: Agregar Leyenda Expandida
```jsx
<details className="parallel-help">
  <summary>💡 ¿Cómo interpretar esta visualización?</summary>
  <div className="parallel-help-content">
    {/* Contenido de ayuda */}
  </div>
</details>
```

### Paso 3: Mejorar Tooltips
```jsx
function buildTooltip(line) {
  const stages = Object.entries(line.stageStates)
    .map(([stage, state]) => `${stage} ${getStateIcon(state)}`)
    .join(' → ');
  
  return `
    <div class="parallel-tooltip__title">📄 ${line.docName || line.docId}</div>
    <div class="parallel-tooltip__meta">
      <strong>📌 Tema:</strong> ${line.topicLabel || '—'}
    </div>
    <div class="parallel-tooltip__meta">
      <strong>📰 News Item #${line.newsMeta.item_index ?? '—'}:</strong> 
      ${line.newsMeta.title || '—'}
    </div>
    <div class="parallel-tooltip__status">
      <strong>Pipeline:</strong> ${stages}
    </div>
    <div class="parallel-tooltip__meta">
      ├─ Insights: ${line.axisValues.insights} ${getStateIcon(line.axisValues.insights)}
      <br>
      └─ Indexing: ${line.axisValues.indexInsights} ${getStateIcon(line.axisValues.indexInsights)}
    </div>
  `;
}
```

### Paso 4: Mejorar CSS con Design Tokens

Completar estilos faltantes:
- `.parallel-description`: Estilo para descripción expandida
- `.parallel-help`: Panel de ayuda contextual
- `.parallel-tooltip__status`: Tooltips mejorados
- Actualizar colores hardcodeados en D3

## 📝 Justificación Conceptual

### Por qué esta visualización es útil:

1. **Vista holística**: Ver todo el pipeline en un solo lugar
2. **Granularidad múltiple**: Entender documento vs news_item
3. **Detección de patrones**: Temas que fallan más, cuellos de botella temporales
4. **Análisis temporal**: Agrupaciones por día/semana/mes revelan tendencias
5. **Interactividad**: Filtros y hover permiten exploración profunda

### Métricas clave que revela:

- **Eficiencia del pipeline**: ¿Dónde se acumulan tareas?
- **Tasa de bifurcación**: ¿Cuántos news_items por documento?
- **Completitud**: ¿Qué % llega hasta Index Insights?
- **Patrones de error**: ¿Qué temas fallan más?
- **Tendencias temporales**: ¿Hay días con más errores?

## 🎯 Próximos Pasos

1. ✅ Actualizar descripción y título
2. ✅ Agregar panel de ayuda contextual
3. ✅ Mejorar tooltips con iconos y estructura
4. ✅ Completar CSS con design tokens
5. ✅ Actualizar colores D3 para usar variables CSS
6. ✅ Build y deploy

---

**Fecha**: 2026-04-07  
**Estado**: PROPUESTO → EN IMPLEMENTACIÓN
