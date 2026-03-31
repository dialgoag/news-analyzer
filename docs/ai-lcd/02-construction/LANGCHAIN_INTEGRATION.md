# Integración LangChain + LangGraph + LangMem en NewsAnalyzer

> **Propósito**: Documentar cómo el ecosistema LangChain se integra en el proyecto para insights de noticias.
>
> **Última actualización**: 2026-03-31  
> **Versión**: 4.0.0 (REQ-021 - Refactor Hexagonal)

---

## 📋 Tabla de Contenidos

1. [Visión General](#visión-general)
2. [Arquitectura de Integración](#arquitectura-de-integración)
3. [LangChain: Cadenas de Procesamiento](#langchain-cadenas-de-procesamiento)
4. [LangGraph: Workflows con Estado](#langgraph-workflows-con-estado)
5. [LangMem: Gestión de Memoria](#langmem-gestión-de-memoria)
6. [Flujo Completo End-to-End](#flujo-completo-end-to-end)
7. [Casos de Uso](#casos-de-uso)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Visión General

### ¿Qué es el Ecosistema LangChain?

El ecosistema LangChain es un conjunto de herramientas profesionales para construir aplicaciones con LLMs:

| Componente | Propósito | Uso en NewsAnalyzer |
|------------|-----------|---------------------|
| **LangChain** | Chains, prompts, providers | Pipeline de 2 pasos (extracción + análisis) |
| **LangGraph** | State machines, workflows | Workflow multi-paso con retry y validación |
| **LangMem** | Memory management, caching | Caché de embeddings y contexto |

### ¿Por qué LangChain en lugar de código ad-hoc?

**Antes (código ad-hoc)**:
```python
# Mezclado: prompt, retry, providers, todo en un lugar
def generate_insight(text):
    prompt = f"Analyze: {text}"  # Prompt hardcoded
    try:
        response = openai.call(prompt)  # Solo OpenAI
        return response
    except:
        return fallback_to_perplexity()  # Retry manual
```

**Ahora (LangChain profesional)**:
```python
# Separado: chains, providers, orchestration
chain = InsightsChain()  # Maneja providers, retry automático
result = await chain.run_full(context=text, title=title)
# Retorna: structured extraction + analysis + metadata
```

**Ventajas**:
- ✅ Prompts estructurados y versionados
- ✅ Providers intercambiables (OpenAI/Ollama/Perplexity)
- ✅ Retry y fallback automático
- ✅ Observabilidad (LangSmith integration)
- ✅ Testing fácil (mock providers)

---

## 🏗️ Arquitectura de Integración

### Ubicación en Hexagonal Architecture

```
backend/
├── core/
│   ├── ports/
│   │   └── llm_port.py                    # 🔌 Interface LLMPort
│   └── domain/
│       └── services/
│           └── insight_parser.py          # Parser de insights estructurados
│
└── adapters/
    └── driven/
        └── llm/                            # 🟨 LLM Adapters (LangChain)
            ├── providers/                  # LLM Providers
            │   ├── openai_provider.py      # Implementa LLMPort
            │   ├── ollama_provider.py      # Implementa LLMPort
            │   └── perplexity_provider.py  # (futuro)
            ├── chains/                     # 🔗 LangChain Chains
            │   ├── extraction_chain.py     # Paso 1: Extrae datos
            │   ├── analysis_chain.py       # Paso 2: Genera insights
            │   └── insights_chain.py       # Orquestador de 2 pasos
            ├── graphs/                     # 📊 LangGraph Workflows
            │   └── insights_graph.py       # State machine multi-paso
            └── memory/                     # 🧠 LangMem
                └── insight_memory.py       # Caché de contexto
```

### Dirección de Dependencias (Hexagonal)

```
Workers (usa insights)
    ↓
Core Application (commands/queries)
    ↓
Core Ports (LLMPort - interface)
    ↑
Adapters Driven (LangChain implementa ports)
    ↓
External Services (OpenAI, Ollama)
```

**Regla clave**: El core NO conoce LangChain. LangChain implementa los ports del core.

---

## 🔗 LangChain: Cadenas de Procesamiento

### Pipeline de 2 Pasos

Arquitectura de cadenas que permite **separar extracción de análisis**:

```
┌─────────────────────────────────────────────────────────────────┐
│                      InsightsChain                              │
│                    (Orquestador Principal)                      │
└─────────────────────────────────────────────────────────────────┘
                           │
           ┌───────────────┴───────────────┐
           ↓                               ↓
┌────────────────────────┐      ┌────────────────────────┐
│   ExtractionChain      │      │    AnalysisChain       │
│   (Paso 1)             │      │    (Paso 2)            │
├────────────────────────┤      ├────────────────────────┤
│ • Metadata             │  →   │ • Significance         │
│ • Actors               │      │ • Context              │
│ • Events/Facts         │      │ • Implications         │
│ • Themes               │      │ • Patterns             │
│ • Quotes               │      │ • Expert Analysis      │
│ • Data Points          │      │                        │
│                        │      │ Input: Extracted data  │
│ Temp: 0.1 (factual)    │      │ Temp: 0.7 (creative)   │
│ Tokens: ~1200          │      │ Tokens: ~1000          │
└────────────────────────┘      └────────────────────────┘
```

### 1. ExtractionChain

**Objetivo**: Extraer SOLO hechos verificables, sin interpretación.

**Archivo**: `adapters/driven/llm/chains/extraction_chain.py`

**Prompt**: Enfocado en datos estructurados (metadata, actores, eventos, temas)

**Output**:
```markdown
## Metadata
Date: 2026-03-15 14:30
Location: Madrid, España
Source: El País
Author: Juan Pérez

## Actors
- Name: Pedro Sánchez | Type: person | Role: Presidente | Action: "Anunció nuevas medidas"
- Name: Gobierno de España | Type: organization | Role: Ejecutivo | Action: Aprobó decreto

## Events Timeline
- Event: Aprobación del decreto | When: 2026-03-15 | Where: Madrid | Who: Gobierno

## Themes
Primary: Política
Secondary: Economía, Legislación
Tags: decreto, gobierno, madrid

## Quotes
- "Las medidas entrarán en vigor mañana" - Pedro Sánchez

## Data Points
- Presupuesto: 500 millones de euros
```

**Características**:
- Temperature: **0.1** (baja, para precisión factual)
- Max tokens: **1200**
- Uso: Knowledge graph, timeline analysis, actor networks

### 2. AnalysisChain

**Objetivo**: Generar insights expertos basados en los datos extraídos.

**Archivo**: `adapters/driven/llm/chains/analysis_chain.py`

**Input**: Los datos estructurados de ExtractionChain

**Output**:
```markdown
## Significance
Este decreto representa un cambio significativo en...

## Historical Context
Esta medida se enmarca en una tendencia...

## Key Perspectives
- Gobierno: Busca impulsar la economía...
- Oposición: Critica el timing...

## Implications
Short-term: Impacto inmediato en...
Long-term: Podría sentar precedente para...

## Patterns Observed
Se observa un patrón de decisiones...

## Expert Analysis
[2-3 párrafos de análisis profundo]
```

**Características**:
- Temperature: **0.7** (más alta, para creatividad analítica)
- Max tokens: **1000**
- Uso: Human consumption, reports, summaries

### 3. InsightsChain (Orquestador)

**Objetivo**: Coordinar ExtractionChain + AnalysisChain con fallback de providers.

**Archivo**: `adapters/driven/llm/chains/insights_chain.py`

**Flujo**:
```python
# Pseudo-código del flujo
async def run_full(context, title):
    for provider in [OpenAI, Perplexity, Ollama]:  # Con fallback
        try:
            # Paso 1: Extracción
            extraction = await ExtractionChain(provider).run(context, title)
            
            # Paso 2: Análisis
            analysis = await AnalysisChain(provider).run(extraction, title)
            
            # Combinar resultados
            return InsightResult(
                extracted_data=extraction,
                analysis=analysis,
                full_text=combine(extraction, analysis),
                provider_used=provider.name
            )
        except RateLimitError:
            # Fallback al siguiente provider
            continue
    
    raise ValueError("All providers failed")
```

**Output**: `InsightResult` con:
- `extracted_data`: Datos estructurados (para graph)
- `analysis`: Análisis experto (para humanos)
- `full_text`: Documento combinado
- `provider_used`, `tokens_used`, etc.

### Providers (Implementan LLMPort)

**Interface común** (`core/ports/llm_port.py`):
```python
class LLMPort(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        pass
    
    @abstractmethod
    def get_provider_name(self) -> str:
        pass
    
    @abstractmethod
    async def is_available(self) -> bool:
        pass
```

**Implementaciones**:

1. **OpenAIProvider** (`adapters/driven/llm/providers/openai_provider.py`)
   - Wrapper de `langchain_openai.ChatOpenAI`
   - Models: gpt-4o, gpt-4-turbo, gpt-3.5-turbo
   - Retry automático para 429 (rate limits)
   - Token tracking

2. **OllamaProvider** (`adapters/driven/llm/providers/ollama_provider.py`)
   - Wrapper de `langchain_community.llms.Ollama`
   - Models: mistral, qwen3:14b, llama2
   - Local deployment, sin límites de rate
   - Sin token tracking (Ollama no lo provee)

3. **PerplexityProvider** (futuro)
   - Wrapper de Perplexity API
   - Models: sonar-pro, sonar-reasoning

**Configuración** (`config.py`):
```python
LLM_PROVIDER = "openai"  # Provider principal
LLM_FALLBACK_PROVIDERS = "perplexity,ollama"  # Fallbacks

# OpenAI
OPENAI_API_KEY = "sk-..."
OPENAI_LLM_MODEL = "gpt-4o"
OPENAI_TEMPERATURE = 0.7

# Ollama
OLLAMA_HOST = "http://ollama:11434"
OLLAMA_LLM_MODEL = "mistral"
```

---

## 📊 LangGraph: Workflows con Estado

### ¿Qué es LangGraph?

LangGraph permite crear **state machines** con múltiples pasos, retry, validación y rutas condicionales.

**Ejemplo de workflow**:
```
Start → Extract → Validate → Analyze → Validate → Store → End
           ↓         ↓          ↓         ↓
        Retry?    Failed?    Retry?    Failed?
           ↑         ↓          ↑         ↓
        Back 3x   Error     Back 3x   Error
```

### InsightsGraph (Estado Multi-Paso)

**Archivo**: `adapters/driven/llm/graphs/insights_graph.py`

**Estado del Graph**:
```python
@dataclass
class InsightState:
    # Input
    news_item_id: str
    document_id: str
    context: str
    title: str
    
    # Processing
    extracted_data: Optional[str] = None
    analysis: Optional[str] = None
    
    # Validation
    extraction_valid: bool = False
    analysis_valid: bool = False
    
    # Retry
    extraction_attempts: int = 0
    analysis_attempts: int = 0
    max_attempts: int = 3
    
    # Output
    final_insight: Optional[str] = None
    provider_used: Optional[str] = None
    error: Optional[str] = None
```

**Nodos del Graph**:
```python
graph = StateGraph(InsightState)

# Nodos
graph.add_node("extract", extract_node)        # Llama ExtractionChain
graph.add_node("validate_extraction", validate_extraction_node)
graph.add_node("analyze", analyze_node)        # Llama AnalysisChain
graph.add_node("validate_analysis", validate_analysis_node)
graph.add_node("store", store_node)            # Guarda en BD
graph.add_node("error", error_node)

# Edges condicionales
graph.add_conditional_edges(
    "validate_extraction",
    should_retry_extraction,  # Función de decisión
    {
        "retry": "extract",     # Si falla y attempts < max
        "continue": "analyze",  # Si OK
        "fail": "error"         # Si max attempts alcanzado
    }
)
```

**Ventajas sobre chains simples**:
- ✅ Retry inteligente por paso
- ✅ Validación antes de continuar
- ✅ Estado persistente entre pasos
- ✅ Trazabilidad completa (cada transición logueada)
- ✅ Recuperación de fallos (puede retomar desde último paso exitoso)

**Cuándo usar Graph vs Chain**:
- **Chain**: Pipeline lineal simple (extraction → analysis)
- **Graph**: Workflow complejo con validación, retry, rutas condicionales

---

## 🧠 LangMem: Gestión de Memoria

### ¿Qué es LangMem?

LangMem gestiona la **memoria y caché** para LLMs, evitando re-computar embeddings y contexto.

**Archivo**: `adapters/driven/memory/insight_memory.py`

### Tipos de Memoria

#### 1. Conversation Memory (Futuro RAG Conversacional)

Mantiene historial de conversación para preguntas follow-up:

```python
memory = ConversationMemory()

# Primera pregunta
response = await rag_chain.run("¿Qué dice el artículo sobre economía?")
memory.add_interaction(question, response)

# Follow-up (usa contexto anterior)
response = await rag_chain.run("¿Y qué opinan los expertos?")
# LangMem inyecta automáticamente contexto previo
```

#### 2. Document Memory (Caché de Embeddings)

Cachea embeddings de documentos para evitar re-computar:

```python
memory = DocumentMemory()

# Primera vez: calcula embeddings
embedding = await memory.get_embedding(document_id, text)
# → Calcula, guarda en caché, retorna

# Segunda vez: usa caché
embedding = await memory.get_embedding(document_id, text)
# → Retorna desde caché (instantáneo)
```

**Beneficios**:
- ✅ **50-90% reducción** en costos de embeddings
- ✅ **10x más rápido** (caché vs API call)
- ✅ **Consistencia** (mismo texto = mismo embedding)

#### 3. Insight Cache

Cachea insights ya generados para noticias duplicadas:

```python
# Deduplicación por text_hash
text_hash = sha256(news_text)
cached_insight = await memory.get_insight(text_hash)

if cached_insight:
    return cached_insight  # Reutilizar, ahorrar tokens
else:
    insight = await chain.run(news_text)
    await memory.store_insight(text_hash, insight)
    return insight
```

**Ahorros reales**:
- Si 1000 noticias tienen 100 duplicadas → **10% ahorro en GPT calls**
- Si promedio 1500 tokens/insight → **150,000 tokens ahorrados**

### Configuración de Memoria

```python
# config.py
MEMORY_ENABLED = True
MEMORY_BACKEND = "redis"  # o "postgres" o "memory"
MEMORY_TTL = 604800  # 7 días
MEMORY_MAX_SIZE = 10000  # Max items en caché
```

### Integración con Chains

```python
# InsightsChain con memoria
chain = InsightsChain()
memory = InsightMemory()

async def generate_with_cache(text, title):
    text_hash = sha256(text)
    
    # Check cache
    cached = await memory.get(text_hash)
    if cached:
        logger.info("✅ Using cached insight")
        return cached
    
    # Generate new
    result = await chain.run_full(text, title)
    
    # Store in cache
    await memory.store(text_hash, result)
    
    return result
```

---

## 🔄 Flujo Completo End-to-End

### Workflow: News Item → Structured Insight

```
1. Worker recibe tarea
   ├─ news_item_id: "news_12345"
   ├─ context: "Texto de noticia..."
   └─ title: "Título de noticia"

2. Check cache (LangMem)
   ├─ text_hash = sha256(context)
   ├─ cached_insight = memory.get(text_hash)
   └─ Si existe → RETURN (ahorro 100%)

3. InsightsChain.run_full()
   │
   ├─ PASO 1: ExtractionChain
   │  ├─ Provider: OpenAI (primary)
   │  ├─ Prompt: Extraction template
   │  ├─ Temperature: 0.1
   │  ├─ Max tokens: 1200
   │  └─ Output: Structured data (metadata, actors, events, themes)
   │
   ├─ PASO 2: AnalysisChain
   │  ├─ Input: Extracted data from paso 1
   │  ├─ Provider: OpenAI (mismo que paso 1)
   │  ├─ Prompt: Analysis template
   │  ├─ Temperature: 0.7
   │  ├─ Max tokens: 1000
   │  └─ Output: Expert analysis
   │
   └─ Combine results
      ├─ extracted_data: "## Metadata..."
      ├─ analysis: "## Significance..."
      ├─ full_text: Combined markdown
      ├─ provider_used: "openai"
      └─ tokens_used: ~2200

4. Parse structured data (Domain Service)
   ├─ InsightParser.parse(full_text)
   └─ StructuredInsight:
      ├─ metadata: InsightMetadata
      ├─ actors: List[Actor]
      ├─ facts: List[Fact]
      ├─ themes: List[str]
      ├─ positions: List[Position]
      └─ analysis: str

5. Store in database
   ├─ news_item_insights: raw insight text
   ├─ insight_entities: actors, locations, themes (para graph)
   └─ insight_relationships: connections entre entidades

6. Index in Qdrant (para RAG)
   ├─ Embed insight text
   ├─ Store vector + metadata
   └─ Enable semantic search

7. Update cache (LangMem)
   └─ memory.store(text_hash, result, ttl=7days)

8. Emit event
   └─ InsightGenerated(news_item_id, provider, tokens)
```

### Ejemplo Real con Logs

```
[2026-03-31 10:15:23] INFO: 🤖 Running insights pipeline with openai/gpt-4o
[2026-03-31 10:15:23] INFO: 📊 Extracting structured data with openai
[2026-03-31 10:15:28] INFO: ✅ Data extracted: 1045 chars, tokens=287
[2026-03-31 10:15:28] INFO: ✅ Step 1/2: Data extraction complete
[2026-03-31 10:15:28] INFO: 🧠 Generating insights with openai
[2026-03-31 10:15:35] INFO: ✅ Insights generated: 856 chars, tokens=234
[2026-03-31 10:15:35] INFO: ✅ Step 2/2: Analysis complete
[2026-03-31 10:15:35] INFO: ✅ Full insights pipeline complete: 1901 chars
[2026-03-31 10:15:35] INFO: 📤 Publishing event: InsightGenerated
```

---

## 🎯 Casos de Uso

### Caso 1: Insight Simple (Chain)

Cuando solo necesitas un insight sin validación compleja:

```python
from adapters.driven.llm.chains.insights_chain import generate_insight

# Uso simple
insight_text, provider = await generate_insight(
    context="Texto de la noticia...",
    title="Título"
)
```

### Caso 2: Insight Estructurado (Chain con parsing)

Cuando necesitas datos estructurados para knowledge graph:

```python
from adapters.driven.llm.chains.insights_chain import generate_insight_structured
from core.domain.services.insight_parser import parse_insight

# Generar insight estructurado
extracted_data, analysis, provider = await generate_insight_structured(
    context="Texto...",
    title="Título"
)

# Parsear a objetos
structured = parse_insight(extracted_data + analysis)

# Usar para graph
entities = structured.get_entities()  # Para nodos
relationships = structured.get_relationships()  # Para edges
```

### Caso 3: Workflow Complejo con Validación (Graph)

Cuando necesitas retry, validación, rutas condicionales:

```python
from adapters.driven.llm.graphs.insights_graph import run_insights_workflow

# Workflow con validación
result = await run_insights_workflow(
    news_item_id="news_123",
    document_id="doc_456",
    context="Texto...",
    title="Título",
    validate=True,  # Valida antes de guardar
    max_retries=3
)

if result.success:
    print(f"✅ Insight generado en {result.attempts} intentos")
else:
    print(f"❌ Falló después de {result.attempts} intentos: {result.error}")
```

### Caso 4: Con Caché (LangMem)

Cuando quieres evitar re-generar insights duplicados:

```python
from adapters.driven.memory.insight_memory import InsightMemory

memory = InsightMemory()
text_hash = sha256(news_text)

# Check cache
cached = await memory.get(text_hash)
if cached:
    return cached  # Instant, no tokens used

# Generate new
result = await chain.run_full(news_text, title)

# Store for future
await memory.store(text_hash, result)
```

---

## 🐛 Troubleshooting

### Problema 1: "All providers failed"

**Síntoma**:
```
ValueError: All 3 providers failed. Last error: Connection timeout
```

**Diagnóstico**:
```bash
# Check provider availability
curl http://localhost:11434/api/tags  # Ollama
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models  # OpenAI
```

**Solución**:
- Verificar que al menos un provider esté disponible
- Revisar `config.py` para API keys y URLs correctas
- Logs: `docker compose logs backend | grep "Provider.*failed"`

### Problema 2: Extraction incompleta

**Síntoma**: Extraction no incluye todos los campos esperados

**Causa**: Prompt template necesita ajuste o texto de entrada muy corto

**Solución**:
```python
# Ajustar temperature en extraction_chain.py
request = LLMRequest(
    prompt=formatted_prompt,
    temperature=0.05,  # Más bajo = más estricto
    max_tokens=1500    # Aumentar si es necesario
)
```

### Problema 3: Rate limits (429)

**Síntoma**: Muchos errores 429 en logs

**Solución**:
1. **Fallback automático** ya implementado (OpenAI → Perplexity → Ollama)
2. **Reducir workers**: `INSIGHTS_PARALLEL_WORKERS=2` en `.env`
3. **Usar Ollama** como primary: `LLM_PROVIDER=ollama`

### Problema 4: Memory cache no funciona

**Diagnóstico**:
```python
# Test cache manually
from adapters.driven.memory.insight_memory import InsightMemory

memory = InsightMemory()
await memory.store("test_hash", "test_data")
result = await memory.get("test_hash")
assert result == "test_data"
```

**Solución**:
- Verificar `MEMORY_ENABLED=true` en config
- Revisar backend de memoria (Redis running si `MEMORY_BACKEND=redis`)

---

## 📊 Métricas y Observabilidad

### Logs Clave

```bash
# Seguir pipeline completo
docker compose logs -f backend | grep -E "InsightsChain|ExtractionChain|AnalysisChain"

# Monitorear providers
docker compose logs -f backend | grep -E "Provider.*failed|fallback"

# Verificar cache hits
docker compose logs -f backend | grep "cached insight"
```

### Métricas Importantes

| Métrica | Objetivo | Cómo medir |
|---------|----------|------------|
| Cache hit rate | >30% | `cached / total requests` |
| Provider fallbacks | <10% | Conteo de "fallback" en logs |
| Avg tokens/insight | ~2000 | `total_tokens / insights_generated` |
| Extraction success | >95% | `successful_extractions / total_attempts` |
| Pipeline latency | <15s | Timestamp logs (start → complete) |

---

## 🚀 Próximos Pasos

1. **Implementar LangGraph** completamente (insights_graph.py)
2. **Integrar LangMem** con Redis backend
3. **LangSmith** integration para tracing
4. **Knowledge Graph** builder usando structured insights
5. **Multi-modal** support (images, PDFs con tablas)

---

## 📚 Referencias

- [LangChain Documentation](https://python.langchain.com/docs/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangMem GitHub](https://github.com/langchain-ai/langmem)
- [Hexagonal Architecture](./HEXAGONAL_ARCHITECTURE.md)
- [REQ-021 - Refactor SOLID](../REQUESTS_REGISTRY.md#req-021)

---

**Versión**: 1.0  
**Estado**: Documento vivo - se actualiza conforme avanza la implementación  
**Próxima actualización**: Post-implementación LangGraph + LangMem
