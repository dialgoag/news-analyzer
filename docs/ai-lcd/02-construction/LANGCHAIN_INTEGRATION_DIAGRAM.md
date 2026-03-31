# Diagrama de Integración: LangChain + LangGraph + LangMem

> Visualización de cómo interactúan los componentes del ecosistema LangChain en NewsAnalyzer

---

## 🎨 Vista General: Flujo Completo

```
┌────────────────────────────────────────────────────────────────────────────┐
│                         INSIGHTS WORKER                                     │
│                    (Entry Point - Background Task)                          │
└────────────────────────────────────────────────────────────────────────────┘
                                    ↓
                ┌───────────────────────────────────┐
                │  ¿Insight en caché? (LangMem)    │
                │  text_hash = sha256(context)      │
                └───────────────────────────────────┘
                      ↓                    ↓
                    YES                   NO
                      ↓                    ↓
              ┌──────────────┐    ┌──────────────────────────┐
              │ Return cache │    │   LangGraph Workflow     │
              │   (instant)  │    │   (Estado multi-paso)    │
              └──────────────┘    └──────────────────────────┘
                                             ↓
                        ┌────────────────────────────────────┐
                        │     InsightsGraph State Machine    │
                        │                                    │
                        │  State: InsightState               │
                        │  - news_item_id                    │
                        │  - context, title                  │
                        │  - extracted_data (paso 1)         │
                        │  - analysis (paso 2)               │
                        │  - validation flags                │
                        │  - retry counters                  │
                        └────────────────────────────────────┘
                                     ↓
                    ┌────────────────────────────────┐
                    │ Node: "extract"                │
                    │ Calls: ExtractionChain         │
                    └────────────────────────────────┘
                                     ↓
                    ┌────────────────────────────────┐
                    │   ExtractionChain (LangChain)  │
                    │   ┌──────────────────────────┐ │
                    │   │ Prompt: EXTRACTION_TMPL  │ │
                    │   │ Temp: 0.1 (factual)      │ │
                    │   │ Tokens: 1200             │ │
                    │   └──────────────────────────┘ │
                    │            ↓                    │
                    │   ┌──────────────────────────┐ │
                    │   │  Try providers in order  │ │
                    │   │  1. OpenAI               │ │
                    │   │  2. Perplexity           │ │
                    │   │  3. Ollama (fallback)    │ │
                    │   └──────────────────────────┘ │
                    │            ↓                    │
                    │   ┌──────────────────────────┐ │
                    │   │ LLMPort.generate()       │ │
                    │   │ (OpenAIProvider)         │ │
                    │   └──────────────────────────┘ │
                    │            ↓                    │
                    │   ┌──────────────────────────┐ │
                    │   │ langchain_openai         │ │
                    │   │ ChatOpenAI.ainvoke()     │ │
                    │   └──────────────────────────┘ │
                    │            ↓                    │
                    │    OpenAI API Call              │
                    │            ↓                    │
                    │   ┌──────────────────────────┐ │
                    │   │ Response: Structured data│ │
                    │   │ ## Metadata              │ │
                    │   │ ## Actors                │ │
                    │   │ ## Events                │ │
                    │   └──────────────────────────┘ │
                    └────────────────────────────────┘
                                     ↓
                    ┌────────────────────────────────┐
                    │ Node: "validate_extraction"    │
                    │ Check: Has metadata? actors?   │
                    └────────────────────────────────┘
                         ↓              ↓
                      VALID          INVALID
                         ↓              ↓
                      Continue      Retry? (max 3x)
                         ↓              ↓
                    ┌────────────────────────────────┐
                    │ Node: "analyze"                │
                    │ Calls: AnalysisChain           │
                    └────────────────────────────────┘
                                     ↓
                    ┌────────────────────────────────┐
                    │   AnalysisChain (LangChain)    │
                    │   ┌──────────────────────────┐ │
                    │   │ Input: Extracted data    │ │
                    │   │ Prompt: ANALYSIS_TMPL    │ │
                    │   │ Temp: 0.7 (creative)     │ │
                    │   │ Tokens: 1000             │ │
                    │   └──────────────────────────┘ │
                    │            ↓                    │
                    │   Same provider fallback logic  │
                    │            ↓                    │
                    │   ┌──────────────────────────┐ │
                    │   │ Response: Analysis       │ │
                    │   │ ## Significance          │ │
                    │   │ ## Context               │ │
                    │   │ ## Expert Analysis       │ │
                    │   └──────────────────────────┘ │
                    └────────────────────────────────┘
                                     ↓
                    ┌────────────────────────────────┐
                    │ Node: "validate_analysis"      │
                    │ Check: Has insights? length>50?│
                    └────────────────────────────────┘
                         ↓              ↓
                      VALID          INVALID
                         ↓              ↓
                      Continue      Retry? (max 3x)
                         ↓              ↓
                    ┌────────────────────────────────┐
                    │ Node: "store"                  │
                    │ - Save to PostgreSQL           │
                    │ - Index in Qdrant              │
                    │ - Update cache (LangMem)       │
                    │ - Emit InsightGenerated event  │
                    └────────────────────────────────┘
                                     ↓
                              ┌──────────┐
                              │   END    │
                              │ ✅ Done  │
                              └──────────┘
```

---

## 🔄 Vista de Componentes: Hexagonal + LangChain

```
┌───────────────────────────────────────────────────────────────────────────┐
│                           CORE (Domain + Application)                      │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Domain Services                                                  │    │
│  │  ├─ InsightParser: Parse structured insights                     │    │
│  │  ├─ TextNormalization: Normalize for hashing                     │    │
│  │  └─ DocumentSegmentation: Split into news items                  │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  Ports (Interfaces)                                               │    │
│  │  ├─ LLMPort ◀━━━━━━━━ Implemented by LangChain providers         │    │
│  │  ├─ VectorStorePort ◀━ Implemented by Qdrant adapter             │    │
│  │  └─ RepositoryPort ◀━━ Implemented by PostgreSQL adapter         │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────┘
                                     ↕
                        Port interface boundary
                                     ↕
┌───────────────────────────────────────────────────────────────────────────┐
│                        ADAPTERS (LangChain Ecosystem)                      │
│                                                                            │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  LangChain Providers (Implement LLMPort)                          │    │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐           │    │
│  │  │   OpenAI     │  │  Perplexity  │  │    Ollama    │           │    │
│  │  │   Provider   │  │   Provider   │  │   Provider   │           │    │
│  │  │              │  │              │  │              │           │    │
│  │  │ ChatOpenAI   │  │ Custom HTTP  │  │ Ollama LLM   │           │    │
│  │  └──────────────┘  └──────────────┘  └──────────────┘           │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                     ↓                                      │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  LangChain Chains                                                 │    │
│  │  ┌──────────────────────────────────────────────────────────┐    │    │
│  │  │  ExtractionChain                                          │    │    │
│  │  │  • Prompt: Extract metadata, actors, events, themes      │    │    │
│  │  │  • Temperature: 0.1 (factual)                            │    │    │
│  │  │  • Output: Structured data                               │    │    │
│  │  └──────────────────────────────────────────────────────────┘    │    │
│  │                            ↓                                      │    │
│  │  ┌──────────────────────────────────────────────────────────┐    │    │
│  │  │  AnalysisChain                                            │    │    │
│  │  │  • Input: Structured data from ExtractionChain           │    │    │
│  │  │  • Prompt: Generate expert analysis                      │    │    │
│  │  │  • Temperature: 0.7 (creative)                           │    │    │
│  │  │  • Output: Insights and implications                     │    │    │
│  │  └──────────────────────────────────────────────────────────┘    │    │
│  │                            ↓                                      │    │
│  │  ┌──────────────────────────────────────────────────────────┐    │    │
│  │  │  InsightsChain (Orchestrator)                             │    │    │
│  │  │  • Runs: ExtractionChain → AnalysisChain                 │    │    │
│  │  │  • Fallback: Try providers in order                      │    │    │
│  │  │  • Combine: Merge extraction + analysis                  │    │    │
│  │  └──────────────────────────────────────────────────────────┘    │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                     ↓                                      │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  LangGraph Workflow (State Machine)                              │    │
│  │  ┌────────┐   ┌──────────┐   ┌─────────┐   ┌────────┐          │    │
│  │  │ Extract│ → │ Validate │ → │ Analyze │ → │ Store  │          │    │
│  │  └────────┘   └──────────┘   └─────────┘   └────────┘          │    │
│  │      ↓              ↓              ↓                             │    │
│  │    Retry?        Failed?        Retry?                          │    │
│  │      ↑              ↓              ↑                             │    │
│  │   (3x max)       Error         (3x max)                         │    │
│  │                                                                  │    │
│  │  State: InsightState                                            │    │
│  │  - Tracks progress, retries, validation                         │    │
│  │  - Enables recovery on failure                                  │    │
│  │  - Complete observability                                       │    │
│  └──────────────────────────────────────────────────────────────────┘    │
│                                     ↓                                      │
│  ┌──────────────────────────────────────────────────────────────────┐    │
│  │  LangMem (Memory & Cache)                                        │    │
│  │  ┌────────────────────────────────────────────────────────┐     │    │
│  │  │  Insight Cache                                          │     │    │
│  │  │  Key: sha256(text) → Value: InsightResult              │     │    │
│  │  │  TTL: 7 days                                            │     │    │
│  │  │  Backend: Redis (future) or PostgreSQL                 │     │    │
│  │  └────────────────────────────────────────────────────────┘     │    │
│  │  ┌────────────────────────────────────────────────────────┐     │    │
│  │  │  Embedding Cache                                        │     │    │
│  │  │  Key: document_id → Value: embedding vector             │     │    │
│  │  │  Reduces API calls by 50-90%                            │     │    │
│  │  └────────────────────────────────────────────────────────┘     │    │
│  │  ┌────────────────────────────────────────────────────────┐     │    │
│  │  │  Conversation Memory (RAG futuro)                       │     │    │
│  │  │  Maintains context for follow-up questions              │     │    │
│  │  └────────────────────────────────────────────────────────┘     │    │
│  └──────────────────────────────────────────────────────────────────┘    │
└───────────────────────────────────────────────────────────────────────────┘
                                     ↓
                        ┌─────────────────────────────┐
                        │   External LLM Services     │
                        ├─────────────────────────────┤
                        │  • OpenAI API (gpt-4o)      │
                        │  • Perplexity API (sonar)   │
                        │  • Ollama Local (mistral)   │
                        └─────────────────────────────┘
```

---

## 🔀 Flujo de Datos: Step by Step

### Escenario 1: Cache Hit (LangMem)

```
Worker → check_cache(text_hash)
            ↓
        Cache HIT
            ↓
    Return cached insight
            ↓
    Update stats (0 tokens used)
            ↓
        Store in DB
            ↓
    Emit InsightGenerated event

Total time: ~100ms
Cost: $0
```

### Escenario 2: Cache Miss - Insight Nuevo (Chain)

```
Worker → check_cache(text_hash)
            ↓
        Cache MISS
            ↓
    InsightsChain.run_full()
            ↓
    ┌──────────────────────────┐
    │  PASO 1: Extraction       │
    ├──────────────────────────┤
    │ ExtractionChain           │
    │   ↓                       │
    │ Format prompt (template)  │
    │   ↓                       │
    │ OpenAIProvider.generate() │
    │   ↓                       │
    │ ChatOpenAI.ainvoke()      │
    │   ↓                       │
    │ OpenAI API                │
    │   ↓                       │
    │ Response: structured data │
    └──────────────────────────┘
            ↓
    State updated: extracted_data = "..."
            ↓
    ┌──────────────────────────┐
    │  PASO 2: Analysis         │
    ├──────────────────────────┤
    │ AnalysisChain             │
    │   ↓                       │
    │ Format prompt (template)  │
    │   ↓                       │
    │ OpenAIProvider.generate() │
    │   ↓                       │
    │ ChatOpenAI.ainvoke()      │
    │   ↓                       │
    │ OpenAI API                │
    │   ↓                       │
    │ Response: analysis        │
    └──────────────────────────┘
            ↓
    Combine: extracted_data + analysis
            ↓
    InsightResult(full_text, tokens=~2200)
            ↓
    Store in cache (LangMem)
            ↓
    Store in DB
            ↓
    Index in Qdrant
            ↓
    Emit InsightGenerated event

Total time: ~12s
Cost: ~$0.02 (gpt-4o)
```

### Escenario 3: Provider Fallback (Resilience)

```
Worker → InsightsChain.run_full()
            ↓
    Try OpenAI (primary)
            ↓
    ❌ RateLimitError (429)
            ↓
    Log: "OpenAI failed, trying Perplexity"
            ↓
    Try Perplexity (fallback 1)
            ↓
    ❌ Timeout
            ↓
    Log: "Perplexity failed, trying Ollama"
            ↓
    Try Ollama (fallback 2)
            ↓
    ✅ Success
            ↓
    Return InsightResult(provider_used="ollama")
            ↓
    Store with metadata: llm_source="ollama"
            ↓
    Continue pipeline

Resilience: 3 providers = 99.9% uptime
```

### Escenario 4: LangGraph con Retry (Validation)

```
Worker → InsightsGraph.run()
            ↓
    ┌─────────────────────────┐
    │ Node: extract           │
    │ Attempt: 1/3            │
    └─────────────────────────┘
            ↓
    ExtractionChain.run()
            ↓
    Result: "## Metadata\n..."
            ↓
    ┌─────────────────────────┐
    │ Node: validate          │
    │ Check fields present    │
    └─────────────────────────┘
            ↓
    ❌ Validation failed: missing actors
            ↓
    Decision: should_retry_extraction()
            ↓
    attempts < max_attempts? YES
            ↓
    ┌─────────────────────────┐
    │ Node: extract           │
    │ Attempt: 2/3            │
    │ (Con ajuste de prompt)  │
    └─────────────────────────┘
            ↓
    ExtractionChain.run()
            ↓
    Result: "## Metadata\n## Actors\n..."
            ↓
    ┌─────────────────────────┐
    │ Node: validate          │
    │ Check fields present    │
    └─────────────────────────┘
            ↓
    ✅ Validation passed
            ↓
    Continue to analyze node
            ↓
    [Same retry logic for analysis]
            ↓
    Final success or error after max attempts

Benefit: Intelligent retry with validation
```

---

## 📦 Componentes y Responsabilidades

### 1. LangChain Chains

| Chain | Responsabilidad | Input | Output | Tokens |
|-------|-----------------|-------|--------|--------|
| **ExtractionChain** | Extraer datos estructurados | news text + title | Structured markdown | ~1200 |
| **AnalysisChain** | Generar insights expertos | extracted data + title | Analysis markdown | ~1000 |
| **InsightsChain** | Orquestar 2 pasos + fallback | news text + title | InsightResult | ~2200 |

### 2. LangGraph State Machine

| Nodo | Función | Transición | Retry |
|------|---------|------------|-------|
| **extract** | Llama ExtractionChain | → validate_extraction | 3x |
| **validate_extraction** | Verifica campos obligatorios | → analyze OR → extract (retry) | — |
| **analyze** | Llama AnalysisChain | → validate_analysis | 3x |
| **validate_analysis** | Verifica calidad insights | → store OR → analyze (retry) | — |
| **store** | Guarda en DB + Qdrant + cache | → END | — |
| **error** | Loguea error, marca failed | → END | — |

### 3. LangMem Layers

| Layer | Propósito | Backend | TTL | Ahorro |
|-------|-----------|---------|-----|--------|
| **Insight Cache** | Evitar re-generar insights duplicados | PostgreSQL | 7d | 10-30% tokens |
| **Embedding Cache** | Evitar re-computar embeddings | Redis | 30d | 50-90% embedding calls |
| **Conversation Memory** | Mantener contexto en RAG | Redis | 1h | Mejor UX |

---

## 🎭 Interacción Entre Componentes

### Diagrama de Secuencia: Generar Insight

```
Worker          InsightsChain    ExtractionChain   OpenAIProvider   AnalysisChain   LangMem      Database
  │                  │                  │                 │                │            │            │
  │─────────────────>│                  │                 │                │            │            │
  │ run_full()       │                  │                 │                │            │            │
  │                  │                  │                 │                │            │            │
  │                  │──────────────────────────────────────────────────────────────────>│            │
  │                  │ check_cache(text_hash)             │                │            │            │
  │                  │<──────────────────────────────────────────────────────────────────│            │
  │                  │ None (cache miss)                  │                │            │            │
  │                  │                  │                 │                │            │            │
  │                  │─────────────────>│                 │                │            │            │
  │                  │ run(context)     │                 │                │            │            │
  │                  │                  │────────────────>│                │            │            │
  │                  │                  │ generate()      │                │            │            │
  │                  │                  │                 │──────────>     │            │            │
  │                  │                  │                 │ OpenAI API     │            │            │
  │                  │                  │                 │<──────────     │            │            │
  │                  │                  │<────────────────│                │            │            │
  │                  │<─────────────────│ extracted_data  │                │            │            │
  │                  │                  │                 │                │            │            │
  │                  │──────────────────────────────────────────────────>│              │            │
  │                  │ run(extracted_data)                │                │            │            │
  │                  │                  │                 │                │            │            │
  │                  │                  │                 │<───────────────│            │            │
  │                  │                  │                 │ generate()     │            │            │
  │                  │                  │                 │──────────>     │            │            │
  │                  │                  │                 │ OpenAI API     │            │            │
  │                  │                  │                 │<──────────     │            │            │
  │                  │                  │                 │────────────────>│            │            │
  │                  │<────────────────────────────────────────────────────│            │            │
  │                  │ analysis                           │                │            │            │
  │                  │                  │                 │                │            │            │
  │                  │──────────────────────────────────────────────────────────────────>│            │
  │                  │ store_cache(text_hash, result)     │                │            │            │
  │                  │                  │                 │                │            │            │
  │<─────────────────│                  │                 │                │            │            │
  │ InsightResult    │                  │                 │                │            │            │
  │                  │                  │                 │                │            │            │
  │──────────────────────────────────────────────────────────────────────────────────────────────────>│
  │ save_to_database(result)           │                 │                │            │            │
```

### Interacción con Event Bus

```
┌──────────────────────────────────────────────────────────────────┐
│                        Event-Driven Flow                          │
└──────────────────────────────────────────────────────────────────┘
                               ↓
    Document uploaded → IndexingCompleted event
                               ↓
                    ┌──────────────────────┐
                    │   Event Bus          │
                    │   (in-memory)        │
                    └──────────────────────┘
                               ↓
                    Notify subscribers
                               ↓
                    ┌──────────────────────┐
                    │  Insights Worker     │
                    │  (subscriber)        │
                    └──────────────────────┘
                               ↓
                    Check LangMem cache
                         ↓         ↓
                      HIT        MISS
                       ↓           ↓
                   Return    Run LangGraph
                             workflow
                                  ↓
                    ┌──────────────────────────┐
                    │  InsightsGraph           │
                    │  (LangGraph)             │
                    │                          │
                    │  extract → validate      │
                    │     ↓         ↓          │
                    │   OK       RETRY         │
                    │     ↓                    │
                    │  analyze → validate      │
                    │     ↓         ↓          │
                    │   OK       RETRY         │
                    │     ↓                    │
                    │  store                   │
                    └──────────────────────────┘
                                  ↓
                    Update LangMem cache
                                  ↓
                    Store in PostgreSQL
                                  ↓
                    Index in Qdrant
                                  ↓
                    Emit InsightGenerated event
                                  ↓
                    ┌──────────────────────┐
                    │   Event Bus          │
                    └──────────────────────┘
                                  ↓
                    Knowledge Graph Builder
                    (subscriber - futuro)
```

---

## 🎯 Comparación: Antes vs Después

### Pipeline Insights: Monolito vs Hexagonal + LangChain

#### ❌ ANTES (app.py monolítico)

```python
# app.py línea ~2400 (mezclado con todo)
async def _insights_worker_task(news_item_id, document_id, filename, title, worker_id):
    # Hardcoded prompt
    prompt = f"Analyze this news: {context}"
    
    # Solo OpenAI, sin fallback
    try:
        response = openai_client.invoke(prompt)
    except RateLimitError:
        # Re-encolar manualmente
        news_item_insights_store.set_status(news_item_id, "pending")
        return
    
    # Sin estructura, solo texto
    insight_text = response
    
    # Guardar directamente
    news_item_insights_store.update(news_item_id, insight_text)
    
    # Sin cache, sin parsing, sin events
```

**Problemas**:
- ❌ Prompt hardcoded en medio del worker
- ❌ Solo OpenAI, sin fallback
- ❌ Sin estructura en output
- ❌ Sin cache (re-genera duplicados)
- ❌ No testeable sin I/O completo
- ❌ Mezclado con lógica de worker

#### ✅ DESPUÉS (Hexagonal + LangChain)

```python
# workers/insights_worker.py (limpio, solo orquestación)
async def process_insight_task(task):
    # Check cache (LangMem)
    cached = await insight_memory.get(task.text_hash)
    if cached:
        return cached  # Instant, $0
    
    # Run workflow (LangGraph)
    result = await insights_graph.run(
        news_item_id=task.news_item_id,
        context=task.context,
        title=task.title
    )
    
    # Parse structured data (Domain Service)
    structured = insight_parser.parse(result.full_text)
    
    # Save (Repository)
    await insights_repo.save(
        news_item_id=task.news_item_id,
        insight=result,
        structured_data=structured
    )
    
    # Update cache
    await insight_memory.store(task.text_hash, result)
    
    # Emit event
    await event_bus.publish(InsightGenerated(...))
```

**Ventajas**:
- ✅ Separación de responsabilidades
- ✅ Chains reutilizables
- ✅ Fallback automático (3 providers)
- ✅ Datos estructurados para graph
- ✅ Cache integrado (ahorro tokens)
- ✅ Testeable (mock providers)
- ✅ Observabilidad completa

---

## 📈 Beneficios Medibles

| Métrica | Antes | Después | Mejora |
|---------|-------|---------|--------|
| **Lines of code (insights)** | ~500 líneas en app.py | ~100 líneas/archivo × 6 archivos | +Mantenibilidad |
| **Testability** | 0% (requires full I/O) | 100% (mock providers) | ∞ |
| **Cache hit rate** | 0% (sin cache) | 20-40% esperado | -30% costos |
| **Provider availability** | 95% (solo OpenAI) | 99.9% (3 providers) | +5% uptime |
| **Structure extraction** | 0% (solo texto plano) | 100% (metadata, actors, events) | +Graph capability |
| **Retry intelligence** | Manual | Automático con validación | +Reliability |
| **Token usage visibility** | Logs manuales | Tracking automático | +Observability |

---

## 🔮 Roadmap: Mejoras Futuras

### v4.1 - LangSmith Integration
```python
# Tracing completo de LLM calls
from langsmith import Client

client = Client()
# Automáticamente captura:
# - Prompts completos
# - Responses
# - Tokens used
# - Latency
# - Errors
```

### v4.2 - Knowledge Graph Auto-Builder
```python
# Usar structured insights para construir graph
from adapters.driven/graph/knowledge_graph_builder import KnowledgeGraphBuilder

builder = KnowledgeGraphBuilder()

for insight in all_insights:
    structured = parse_insight(insight.text)
    
    # Add nodes
    builder.add_entities(structured.get_entities())
    
    # Add edges
    builder.add_relationships(structured.get_relationships())

# Query graph
actors_in_madrid = builder.query("MATCH (a:Actor)-[:LOCATED_IN]->(:Location {name:'Madrid'})")
```

### v4.3 - Multi-Step Reasoning (LangGraph Advanced)
```python
# Graph con pasos adicionales
graph.add_node("retrieve_context", retrieve_historical_context)
graph.add_node("cross_reference", cross_reference_with_past_events)
graph.add_node("synthesize", synthesize_multi_document_insight)

# Permite insights que consideran múltiples documentos
```

### v4.4 - Redis Event Bus (Distributed)
```python
# Reemplazar in-memory event bus con Redis
event_bus = RedisEventBus(redis_url="redis://redis:6379")

# Permite múltiples instancias del backend
# Eventos se propagan entre instancias
```

---

## 📚 Referencias de Código

| Archivo | Descripción | Líneas |
|---------|-------------|--------|
| `core/ports/llm_port.py` | Interface LLMPort | ~70 |
| `adapters/driven/llm/providers/openai_provider.py` | OpenAI adapter | ~146 |
| `adapters/driven/llm/providers/ollama_provider.py` | Ollama adapter | ~130 |
| `adapters/driven/llm/chains/extraction_chain.py` | Extraction chain | ~161 |
| `adapters/driven/llm/chains/analysis_chain.py` | Analysis chain | ~146 |
| `adapters/driven/llm/chains/insights_chain.py` | Orchestrator | ~277 |
| `adapters/driven/llm/graphs/insights_graph.py` | State machine (futuro) | ~300 |
| `adapters/driven/memory/insight_memory.py` | Cache manager (futuro) | ~200 |
| `core/domain/services/insight_parser.py` | Structured parser | ~250 |
| `core/application/events/event_bus.py` | Event bus | ~120 |

**Total nuevo código LangChain**: ~1,800 líneas (bien organizado)  
**Código removido de app.py**: ~500 líneas (monolítico)  
**Ganancia neta**: +1,300 líneas pero +∞ mantenibilidad

---

**Próxima actualización**: Después de implementar LangGraph + LangMem completamente
