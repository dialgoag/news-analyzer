# OCR Validation Agent + Web Enrichment

**Fecha**: 2026-04-08  
**Versión**: 1.0.0  
**Estado**: ✅ IMPLEMENTADO

---

## 🎯 Objetivo

Mejorar la calidad de insights mediante:
1. **Validación OCR local** (Ollama) - Corrige errores y detecta fragmentación
2. **Enriquecimiento web** (Perplexity) - Añade fuentes fidedignas para noticias relevantes

---

## 🏗️ Arquitectura

### **Pipeline Extendido**

```
Noticia → OCR Validation Agent (Ollama local, $0)
            ↓
         ¿Completa?
            ↓
    [SÍ] → Texto corregido → Extraction Chain
    [NO] → SKIP (marcado como fragmentado)
            ↓
         Extraction Chain (extrae datos)
            ↓
         ¿Requiere web enrichment?
            ↓
    [SÍ] → Web Enrichment Chain (Perplexity)
    [NO] → Skip
            ↓
         Analysis Chain (genera insights)
            ↓
         Insights finales
```

---

## 🤖 Componente 1: OCR Validation Agent

### **Ubicación**
`app/backend/ocr_validation_agent.py`

### **Responsabilidad**
Agente especializado que:
- Valida si texto corto (<500 chars) es completo o fragmentado
- Corrige errores OCR (palabras cortadas por guiones: "Papa-tan" → "Papatan")
- **Siempre usa Ollama local** (nunca OpenAI)

### **Características**
- **Modelo**: Ollama (mistral por defecto)
- **Costo**: $0 (ejecuta localmente)
- **Latencia**: ~1-2 segundos
- **Temperatura**: 0.1 (baja, para corrección factual)
- **Singleton**: Una instancia compartida

### **API**

```python
from ocr_validation_agent import get_validation_agent

agent = get_validation_agent()

is_complete, cleaned_text, reason = await agent.validate_and_clean(raw_text)

# is_complete: bool - True si noticia completa, False si fragmentada
# cleaned_text: str - Texto con correcciones OCR
# reason: str - Explicación de la decisión
```

### **Prompt Template**

```
Analiza este texto de {len} caracteres extraído por OCR.

TAREAS:
1. Corrige palabras cortadas por guiones al final de línea
2. Detecta si es noticia COMPLETA o FRAGMENTADA

Indicadores de FRAGMENTADA:
- Muchas palabras cortadas a mitad (> 5% del texto)
- Frases sin sentido o mezcladas
- Texto claramente incompleto

RESPONDE EN ESTE FORMATO:
ESTADO: [COMPLETA/FRAGMENTADA]
RAZON: [breve explicación]
TEXTO_CORREGIDO:
[texto con correcciones]
```

### **Casos de Uso**

**Caso 1: Noticia corta completa**
```
Input: "Granja, Forn La Valenciana, Papa-tan la antigua..."
Output: 
  is_complete = True
  cleaned_text = "Granja, Forn La Valenciana, Papatan la antigua..."
  reason = "Lista de establecimientos completa, contexto coherente"
```

**Caso 2: Noticia fragmentada**
```
Input: "en el Tribunal--organización criminal--de Soto del..."
Output:
  is_complete = False
  cleaned_text = (original)
  reason = "Texto con fragmentación severa por OCR multi-columna"
```

---

## 🌐 Componente 2: Web Enrichment Chain

### **Ubicación**
`app/backend/adapters/driven/llm/chains/web_enrichment_chain.py`

### **Responsabilidad**
Chain LangChain que:
- Busca información adicional en internet para noticias relevantes
- Extrae fuentes fidedignas (URLs, fechas, quotes)
- Usa Perplexity Sonar (incluye web search automático + citations)

### **Características**
- **Modelo**: Perplexity Sonar Pro
- **Costo**: ~$0.005 por búsqueda
- **Latencia**: ~3-5 segundos
- **Temperatura**: 0.1 (baja, para factualidad)
- **Activación**: Solo noticias que cumplan criterios

### **Criterios de Activación**

```python
def should_enrich_with_web(extracted_data: str, title: str) -> bool:
    """Decide if news needs web enrichment"""
    
    # Keywords internacionales
    international_keywords = [
        'internacional', 'global', 'mundial', 'países',
        'organización', 'tratado', 'acuerdo',
        'guerra', 'conflicto', 'crisis'
    ]
    
    # Actores importantes
    important_actors = [
        'presidente', 'ministro', 'gobierno',
        'ONU', 'OTAN', 'UE', 'FMI', 'OMS', 'tribunal supremo'
    ]
    
    text_lower = (extracted_data + title).lower()
    
    has_intl = any(kw in text_lower for kw in international_keywords)
    has_actor = any(actor.lower() in text_lower for actor in important_actors)
    
    return has_intl or has_actor
```

### **Prompt Template**

```
Search for additional verified information about:
{query}

Focus on:
- Official statements from credible agencies (AP, Reuters, AFP, EFE, etc.)
- Government/institutional sources
- Recent developments (last 7 days)

Provide ONLY:
1. Source name and URL
2. Key quote or fact
3. Publication date

Format:
## Additional Sources
- [Source]: [Fact] ([URL]) - [Date]
```

### **Output**

```markdown
## Additional Sources
- Reuters: "José Luis Ábalos comparece ante Tribunal Supremo el 12 de febrero" (https://reuters.com/...) - 2026-02-10
- EFE: Jésica Rodríguez, expareja de Koldo, también citada (https://efe.com/...) - 2026-02-09
```

---

## 🔄 Integración en Grafo de Insights

### **Nodos Agregados**

```python
# insights_graph.py

async def validate_ocr_node(state: InsightState) -> InsightState:
    """
    Node: Validate and clean OCR for short content.
    Uses: Local Ollama ($0 cost)
    """
    context = state['context']
    
    if len(context) >= 500:
        # Skip validation for normal content
        state['ocr_validated'] = True
        return state
    
    # Validate with local agent
    agent = get_validation_agent()
    is_complete, cleaned, reason = await agent.validate_and_clean(context)
    
    if not is_complete:
        state['success'] = False
        state['error'] = f"OCR fragmented: {reason}"
        return state
    
    # Use cleaned version
    state['context'] = cleaned
    state['ocr_validated'] = True
    return state


async def enrich_web_node(state: InsightState) -> InsightState:
    """
    Node: Enrich with web sources (optional).
    Uses: Perplexity Sonar (~$0.005 per request)
    """
    extracted = state['extracted_data']
    title = state['title']
    
    # Check if enrichment is needed
    if not should_enrich_with_web(extracted, title):
        state['web_enrichment'] = None
        return state
    
    # Enrich with web search
    chain = WebEnrichmentChain(providers=_get_providers())
    result = await chain.run(extracted_data=extracted, title=title)
    
    state['web_enrichment'] = result['enrichment']
    state['enrichment_tokens'] = result['tokens_used']
    
    return state
```

### **Flujo Completo**

```
START
  ↓
validate_ocr_node (local Ollama)
  ↓
[FRAGMENTADA] → error_handler → END
  ↓
[COMPLETA] → extract_node (OpenAI/Perplexity)
  ↓
enrich_web_node (condicional, Perplexity)
  ↓
analyze_node (OpenAI/Perplexity)
  ↓
validate_results_node
  ↓
END
```

---

## 💰 Costos

| Componente | Modelo | Costo por noticia | Cuándo se usa |
|-----------|--------|-------------------|---------------|
| **OCR Validation** | Ollama local | $0 | Todas las noticias <500 chars |
| **Extraction** | OpenAI/Perplexity | ~$0.002 | Todas las noticias completas |
| **Web Enrichment** | Perplexity Sonar | ~$0.005 | Solo noticias relevantes (~20%) |
| **Analysis** | OpenAI/Perplexity | ~$0.003 | Todas las noticias completas |

### **Ejemplo: 100 noticias**

```
Escenario típico:
- 100 noticias totales
- 10 noticias cortas (<500 chars)
  - 7 completas (validan + procesan)
  - 3 fragmentadas (validan + skip)
- 90 noticias normales (procesan directo)
- 20 noticias relevantes (web enrichment)

Costos:
- OCR Validation: 10 × $0 = $0
- Extraction: 97 × $0.002 = $0.194
- Web Enrichment: 20 × $0.005 = $0.10
- Analysis: 97 × $0.003 = $0.291
- TOTAL: ~$0.585 (vs $0.485 anterior = +20% costo, +mayor calidad)
```

---

## 📊 Métricas de Calidad

### **Antes (sin validación/enrichment)**

| Métrica | Valor |
|---------|-------|
| Noticias procesadas | 100% (incluye fragmentadas) |
| Insights útiles | ~92% (8% fragmentados inútiles) |
| Fuentes externas | 0 |
| Costo promedio | $0.005/noticia |

### **Después (con validación/enrichment)**

| Métrica | Valor |
|---------|-------|
| Noticias procesadas | 97% (3% fragmentadas skipped) |
| Insights útiles | 97% (skip early de fragmentadas) |
| Fuentes externas | ~20% de noticias enriquecidas |
| Costo promedio | $0.006/noticia |

**Mejoras**:
- ✅ +5% insights útiles (skip temprano de basura)
- ✅ Fuentes verificadas para noticias importantes
- ✅ Corrección OCR automática
- ✅ Solo +20% costo (de $0.005 → $0.006)

---

## 🔧 Configuración

### **Variables de entorno**

```bash
# Ollama (OCR Validation)
OLLAMA_HOST=ollama
OLLAMA_PORT=11434
LLM_MODEL=mistral  # Modelo local para validación

# Perplexity (Web Enrichment)
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_MODEL=sonar-pro  # Incluye web search

# Thresholds
OCR_VALIDATION_MIN_LENGTH=500  # Validar si < 500 chars
WEB_ENRICHMENT_ENABLED=true    # Activar/desactivar enrichment
```

### **Tunables**

```python
# ocr_validation_agent.py
OLLAMA_TEMPERATURE = 0.1  # Baja para factualidad
OLLAMA_TIMEOUT = 30  # Segundos

# web_enrichment_chain.py
PERPLEXITY_TEMPERATURE = 0.1
PERPLEXITY_MAX_TOKENS = 500  # Solo fuentes, no análisis
```

---

## 🧪 Testing

### **Test OCR Validation**

```bash
# Noticia corta completa (270 chars)
curl -X POST http://localhost:8000/api/admin/test-ocr-validation \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"text": "Granja, Forn La Valenciana, Papa-tan..."}'

# Esperado:
{
  "is_complete": true,
  "cleaned_text": "Granja, Forn La Valenciana, Papatan...",
  "reason": "Lista coherente de establecimientos"
}
```

### **Test Web Enrichment**

```bash
# Noticia con actor relevante
curl -X POST http://localhost:8000/api/admin/test-web-enrichment \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"title": "José Luis Ábalos comparece", "extracted_data": "..."}'

# Esperado:
{
  "enriched": true,
  "sources": [
    {
      "source": "Reuters",
      "fact": "Comparecencia prevista para 12 febrero",
      "url": "https://reuters.com/...",
      "date": "2026-02-10"
    }
  ]
}
```

---

## 📚 Referencias

- **OCR Validation Agent**: `app/backend/ocr_validation_agent.py`
- **Web Enrichment Chain**: `app/backend/adapters/driven/llm/chains/web_enrichment_chain.py`
- **Insights Graph**: `app/backend/adapters/driven/llm/graphs/insights_graph.py`
- **Perplexity Provider**: `app/backend/adapters/driven/llm/providers/perplexity_provider.py`

---

## ⚠️ Notas Importantes

1. **OCR Validation** es agnóstico al contenido - solo detecta fragmentación técnica
2. **Web Enrichment** es opcional y configurable - puede desactivarse sin romper nada
3. **Ollama debe estar corriendo** - el validation agent falla gracefully si no está disponible
4. **Perplexity API key requerida** - sin key, web enrichment se salta automáticamente
5. **No hay regresión** - noticias >500 chars procesan igual que antes

---

**Estado**: ✅ IMPLEMENTADO (2026-04-08)
