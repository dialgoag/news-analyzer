# 📋 Guía de Diagnóstico de Segmentación de Noticias

## 🔍 Problema Identificado

Algunos archivos PDF (ej: `28-12-26-El Mundo.pdf`) muestran **pocas noticias detectadas** (2 noticias) cuando deberían tener muchas más.

## ⚙️ Cómo Funciona la Segmentación

El sistema usa **heurísticas automáticas** para identificar noticias individuales en un PDF:

### Algoritmo de Detección (`segment_news_items_from_text`)

```python
# 1. Busca líneas que parezcan TÍTULOS:
- Longitud: entre 12-140 caracteres
- Contenido: debe tener letras
- Capitalización: 
  * Ratio de mayúsculas >= 75%, O
  * Ratio de palabras en Title Case >= 70%

# 2. Validación contextual:
- El título debe estar precedido por línea vacía
- Debe tener un body siguiente con >= 30 caracteres

# 3. Extracción del body:
- Desde el título hasta el siguiente título detectado
- Mínimo 200 caracteres (se descartan bodies muy cortos)

# 4. Fallback si no detecta títulos:
- Si el PDF tiene múltiples páginas (\f): 1 noticia por página
- Si no: 1 noticia = documento completo
```

## 🛠️ Endpoint de Diagnóstico

### URL
```
GET /api/documents/{document_id}/segmentation-diagnostic
```

### Respuesta
```json
{
  "document_id": "...",
  "filename": "28-12-26-El Mundo.pdf",
  "ocr_stats": {
    "total_chars": 45000,
    "total_lines": 850,
    "non_empty_lines": 720,
    "avg_line_length": 52.94
  },
  "ocr_excerpt": "Primeras 2000 caracteres del OCR...",
  "segmentation_result": {
    "detected_items": 2,
    "items_preview": [
      {
        "title": "TÍTULO DETECTADO",
        "body_length": 3500,
        "body_excerpt": "Primeros 200 caracteres..."
      }
    ]
  },
  "stored_items": {
    "count": 2,
    "items": [...]
  },
  "title_candidates": [
    {
      "line_number": 25,
      "text": "ECONOMÍA NACIONAL CRECE UN 3%",
      "upper_ratio": 0.95
    }
  ]
}
```

## 🔬 Cómo Diagnosticar un Documento

### Paso 1: Obtener el `document_id`

Desde el dashboard o lista de documentos:
```javascript
// En el frontend, el document_id está en cada fila de la tabla
doc.document_id
```

### Paso 2: Llamar al endpoint

```bash
# Usando curl (necesitas el token de autenticación)
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/api/documents/DOCUMENT_ID/segmentation-diagnostic
```

O desde el navegador (estando logueado):
```
http://localhost:8000/api/documents/DOCUMENT_ID/segmentation-diagnostic
```

### Paso 3: Analizar los resultados

#### ✅ Indicadores de buena segmentación:
- `detected_items` >= 10 (para PDFs de periódicos)
- `title_candidates` muestra muchos títulos con `upper_ratio` > 0.7
- Los `items_preview` tienen títulos descriptivos y bodies largos

#### ⚠️ Indicadores de problema:
- `detected_items` < 5 en un PDF grande (> 100 páginas)
- Pocos `title_candidates` (< 5)
- `ocr_excerpt` muestra texto corrupto o mal formateado
- Bodies muy cortos (< 500 caracteres)

## 🐛 Causas Comunes de Fallos

### 1. **OCR de Baja Calidad**
- El texto extraído está corrupto o mal formateado
- Los títulos no se preservan como líneas separadas
- Demasiados errores tipográficos

**Solución**: Mejorar la calidad del PDF original o usar OCR más robusto

### 2. **Formato No Estándar**
- El periódico no usa títulos en mayúsculas
- Layout de múltiples columnas confunde la extracción
- Títulos muy largos (> 140 caracteres)

**Solución**: Ajustar heurísticas en `segment_news_items_from_text`

### 3. **PDF de Página Única**
- El PDF es una imagen escaneada de toda la página
- No hay separadores claros entre noticias

**Solución**: Usar segmentación basada en layout visual o LLM

## 🔧 Mejoras Potenciales

### Opción 1: Segmentación con LLM
```python
def segment_with_llm(text: str) -> List[Dict]:
    """Usa GPT-4 para identificar títulos y segmentar"""
    prompt = f"""
    Analiza el siguiente texto de un periódico e identifica:
    1. Títulos de noticias individuales
    2. Inicio y fin de cada noticia
    
    Formato JSON: [{{"title": "...", "start_marker": "...", "end_marker": "..."}}]
    
    TEXTO:
    {text[:10000]}
    """
    # Llamar a GPT-4 y parsear JSON
```

### Opción 2: Análisis de Layout con OCR Avanzado
- Usar `pytesseract` con `--psm 3` (modo automático)
- Extraer bounding boxes de texto
- Identificar columnas y bloques visualmente

### Opción 3: Heurísticas Mejoradas
```python
# Agregar más patrones de título:
- Detectar números de sección: "1.", "2.", etc.
- Detectar keywords: "REPORTAJE", "ANÁLISIS", "OPINIÓN"
- Usar NER para detectar nombres propios (lugares, personas)
- Analizar espaciado vertical (doble salto de línea)
```

## 📊 Estadísticas Esperadas (Periódicos Típicos)

| Periódico | Páginas | Noticias Esperadas | Chars/Noticia |
|-----------|---------|-------------------|---------------|
| El Mundo  | 50-80   | 30-60             | 800-2000      |
| El País   | 60-100  | 40-80             | 1000-2500     |
| La Vanguardia | 70-120 | 50-100         | 700-1800      |
| Expansión | 30-50   | 20-40             | 1500-3000     |

## 📝 Ejemplo de Uso desde el Frontend

```javascript
async function diagnoseDocument(documentId) {
  const response = await axios.get(
    `${API_URL}/api/documents/${documentId}/segmentation-diagnostic`,
    { headers: { Authorization: `Bearer ${token}` }}
  );
  
  const diagnostic = response.data;
  
  console.log(`Detected ${diagnostic.segmentation_result.detected_items} news items`);
  console.log(`Title candidates: ${diagnostic.title_candidates.length}`);
  
  if (diagnostic.segmentation_result.detected_items < 10) {
    alert("⚠️ Possible segmentation issue - check OCR quality");
  }
}
```

## 🎯 Recomendaciones

1. **Para cada batch de PDFs nuevos**: Ejecutar diagnóstico en 2-3 archivos muestra
2. **Si hay problemas consistentes**: Ajustar heurísticas o considerar LLM
3. **Monitorear métricas**:
   - Promedio de noticias por documento por fuente
   - Ratio de noticias con body < 500 chars
   - Documentos con 0-2 noticias detectadas

## 🔗 Referencias

- Código: `backend/app.py` → `segment_news_items_from_text()`
- Endpoint: `GET /api/documents/{document_id}/segmentation-diagnostic`
- Tabla DB: `news_items` (almacena noticias detectadas)
- Tabla DB: `news_item_insights` (almacena insights generados)

---

**Última actualización**: 2026-03-05  
**Versión**: 1.0
