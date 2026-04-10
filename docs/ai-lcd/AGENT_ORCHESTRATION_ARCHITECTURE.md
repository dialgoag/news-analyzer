# 🤖 Arquitectura de Orquestación con Agentes

> Comparación: Pipeline actual vs. Orchestrator Agent con sub-agentes como tools

**Fecha**: 2026-04-10  
**Estado**: Propuesta de Diseño

---

## 📊 ARQUITECTURA ACTUAL (Event-Driven)

```
┌─────────────────────────────────────────────────────────────┐
│                     SCHEDULERS (sincronos)                   │
├─────────────────────────────────────────────────────────────┤
│  Upload Scheduler (10s) → Check slots → Spawn worker        │
│  OCR Scheduler (15s)    → Check slots → Spawn worker        │
│  Segmentation (5s)      → Check slots → Spawn worker        │
│  Chunking (5s)          → Check slots → Spawn worker        │
│  Indexing (5s)          → Check slots → Spawn worker        │
│  Insights (2s)          → Check slots → Spawn worker        │
│  Indexing Insights (5s) → Check slots → Spawn worker        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    POSTGRES (coordinación)                   │
├─────────────────────────────────────────────────────────────┤
│  • processing_queue (tasks: pending/processing/done)        │
│  • worker_tasks (semáforo: assigned/started/completed)      │
│  • document_status (pipeline state por documento)           │
│  • document_stage_timing (timing por etapa)                 │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                  WORKERS ASYNC (independientes)              │
├─────────────────────────────────────────────────────────────┤
│  _upload_worker_task()                                       │
│  _ocr_worker_task()          → OCRService → Tika/OCRmyPDF   │
│  _segmentation_worker_task() → NewsSegmentationAgent (LLM)  │
│  _chunking_worker_task()                                     │
│  _indexing_worker_task()     → Qdrant                        │
│  _insights_worker_task()     → InsightsGraph (LangGraph)    │
│  _indexing_insights_worker()                                 │
└─────────────────────────────────────────────────────────────┘
```

### Características Actuales:

✅ **Fortalezas**:
- Event-driven resiliente (si worker crash, se recupera)
- Semáforos en BD (control de concurrencia)
- Cada worker independiente
- Escalable (ajustar `MAX_WORKERS` por etapa)

❌ **Debilidades**:
- Sin visibilidad unificada del pipeline
- Cada scheduler independiente (7 schedulers corriendo)
- Difícil debuggear flujo completo de un documento
- No hay memoria/contexto compartido entre etapas
- Logging disperso

---

## 🎯 ARQUITECTURA PROPUESTA (Orchestrator Agent)

```
┌───────────────────────────────────────────────────────────────────┐
│              PIPELINE ORCHESTRATOR AGENT (LangGraph)              │
├───────────────────────────────────────────────────────────────────┤
│                                                                   │
│  Estado Compartido (TypedDict):                                   │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ • document_id: str                                          │ │
│  │ • filename: str                                             │ │
│  │ • metadata: {date, newspaper, sha8}                         │ │
│  │ • pipeline_context: {ocr_text, chunks, vectors, insights}  │ │
│  │ • events: List[PipelineEvent]  (memoria persistente)       │ │
│  │ • current_stage: PipelineStage                              │ │
│  │ • error: Optional[str]                                      │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Tools (Sub-agentes):                                             │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ 1. validation_tool    → ValidationAgent                     │ │
│  │ 2. ocr_tool           → OCRAgent                            │ │
│  │ 3. segmentation_tool  → SegmentationAgent (LLM)             │ │
│  │ 4. chunking_tool      → ChunkingAgent                       │ │
│  │ 5. indexing_tool      → IndexingAgent                       │ │
│  │ 6. insights_tool      → InsightsAgent (LangGraph existing)  │ │
│  │ 7. observer_tool      → ObserverAgent (persistence)         │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Flujo de Control:                                                │
│  ┌─────────────────────────────────────────────────────────────┐ │
│  │ START → validation_tool                                     │ │
│  │           ↓ (metadata)                                      │ │
│  │         ocr_tool                                            │ │
│  │           ↓ (text)                                          │ │
│  │         segmentation_tool                                   │ │
│  │           ↓ (articles)                                      │ │
│  │         chunking_tool                                       │ │
│  │           ↓ (chunks)                                        │ │
│  │         indexing_tool                                       │ │
│  │           ↓ (vectors)                                       │ │
│  │         insights_tool                                       │ │
│  │           ↓ (insights)                                      │ │
│  │         observer_tool (persiste eventos en cada paso)       │ │
│  │           ↓                                                 │ │
│  │         END                                                 │ │
│  └─────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  Decisiones (Conditional Edges):                                  │
│  • Si validation_tool falla → END (error)                         │
│  • Si ocr_tool falla → retry o fallback (Tika)                    │
│  • Si segmentation_tool timeout → continuar con chunks básicos    │
│  • Si insights_tool falla → skip (documento sigue indexado)       │
└───────────────────────────────────────────────────────────────────┘
                               ↓
┌───────────────────────────────────────────────────────────────────┐
│                  POSTGRES (persistencia + memoria)                │
├───────────────────────────────────────────────────────────────────┤
│  • document_processing_log (eventos del orchestrator)             │
│  • document_status (estado final)                                 │
│  • orchestrator_state (checkpoint de LangGraph para recovery)     │
└───────────────────────────────────────────────────────────────────┘
```

### Comunicación Agéntica:

```
ORCHESTRATOR AGENT
     │
     ├─► [Tool Call] validation_tool(filepath)
     │        │
     │        └─► ValidationAgent
     │               • Valida PDF
     │               • Extrae metadata (fecha, periódico, sha8)
     │               • Retorna: {valid: bool, metadata: dict}
     │
     ├─► [Tool Call] ocr_tool(filepath, metadata)
     │        │
     │        └─► OCRAgent
     │               • Decide engine (OCRmyPDF vs Tika)
     │               • Extrae texto
     │               • Retorna: {text: str, pages: int, duration: float}
     │
     ├─► [Tool Call] segmentation_tool(text, metadata)
     │        │
     │        └─► SegmentationAgent (LLM)
     │               • Usa Ollama llama3.2:1b
     │               • Detecta artículos
     │               • Retorna: {articles: List[Article], confidence: float}
     │
     ├─► [Tool Call] insights_tool(article, context)
     │        │
     │        └─► InsightsAgent (LangGraph existing)
     │               • Validación OCR (Ollama)
     │               • Web enrichment (Perplexity)
     │               • Extracción (OpenAI/Ollama)
     │               • Análisis (OpenAI)
     │               • Retorna: {insight: str, tokens: int}
     │
     └─► [Tool Call] observer_tool(event)
              │
              └─► ObserverAgent
                     • Valida con Pydantic
                     • Persiste en PostgreSQL
                     • Retorna: {event_id: int, persisted: bool}
```

---

## 🔄 FLUJO DETALLADO: Un Documento en el Sistema

### ACTUAL (Event-Driven):

```
Usuario sube PDF
     ↓
Upload Scheduler detecta archivo → Spawn _upload_worker_task
     ↓ (marca en worker_tasks: upload/started)
Upload worker valida → Marca document_status: upload_done
     ↓ (crea task en processing_queue: task_type=ocr)
     
OCR Scheduler detecta task → Spawn _ocr_worker_task
     ↓ (marca en worker_tasks: ocr/started)
OCR worker procesa → OCRService → Tika/OCRmyPDF
     ↓ (guarda text en document_status)
OCR worker marca document_status: ocr_done
     ↓ (crea task en processing_queue: task_type=segmentation)
     
Segmentation Scheduler detecta → Spawn _segmentation_worker_task
     ↓ (marca en worker_tasks: segmentation/started)
Segmentation worker → NewsSegmentationAgent (LLM)
     ↓ (guarda articles en news_items)
Segmentation worker marca document_status: segmentation_done
     ↓ (crea task en processing_queue: task_type=chunking)
     
... (continúa similar para chunking, indexing, insights)

[PROBLEMA]: Cada worker es independiente, no comparte contexto,
            difícil ver el flujo completo de un documento.
```

### PROPUESTA (Orchestrator Agent):

```
Usuario sube PDF
     ↓
ORCHESTRATOR AGENT inicia para ese documento
     ↓
Estado inicial: {document_id, filename, pipeline_context: {}}
     ↓
     
Node: validation_node
     ├─► Tool: validation_tool(filepath)
     │      └─► ValidationAgent
     │             • Valida PDF ✅
     │             • Extrae metadata: {date: "29-01-26", newspaper: "ABC", sha8: "03535cda"}
     ├─► Tool: observer_tool({stage: "validation", status: "completed", metadata: {...}})
     └─► Estado actualizado: metadata agregada, event registrado
     
Node: ocr_node
     ├─► Tool: ocr_tool(filepath, metadata)
     │      └─► OCRAgent
     │             • Usa OCRmyPDF
     │             • Extrae texto (100,000 chars)
     ├─► Tool: observer_tool({stage: "ocr", status: "completed", metadata: {duration: 120s, ...}})
     └─► Estado actualizado: pipeline_context.ocr_text = "...", event registrado
     
Node: segmentation_node
     ├─► Tool: segmentation_tool(state.pipeline_context.ocr_text, state.metadata)
     │      └─► SegmentationAgent (LLM)
     │             • Detecta 14 artículos
     │             • Confidence promedio: 0.85
     ├─► Tool: observer_tool({stage: "segmentation", status: "completed", metadata: {articles: 14, ...}})
     └─► Estado actualizado: pipeline_context.articles = [...], event registrado
     
Node: insights_node (for each article)
     ├─► Tool: insights_tool(article, state.pipeline_context)
     │      └─► InsightsAgent (LangGraph existing)
     │             • Genera insight estructurado
     ├─► Tool: observer_tool({stage: "insights", status: "completed", metadata: {tokens: 500, ...}})
     └─► Estado actualizado: pipeline_context.insights = [...], event registrado
     
Node: end_node
     └─► Estado final: {success: true, events: [10 eventos], pipeline_context: {...}}

[VENTAJA]: Un solo agente ve TODO el flujo, comparte contexto,
           puede tomar decisiones inteligentes basadas en estado previo.
```

---

## 🧠 VENTAJAS DEL ORCHESTRATOR AGENT

### 1. **Contexto Compartido**
```
Estado del Agente (memoria):
{
  document_id: "abc123",
  metadata: {date: "29-01-26", newspaper: "ABC"},
  pipeline_context: {
    ocr_text: "...",           ← OCR agent lo guardó
    articles: [14 articles],   ← Segmentation agent lo guardó
    chunks: [50 chunks],       ← Chunking agent lo guardó
    vectors: [50 vectors],     ← Indexing agent lo guardó
    insights: [14 insights]    ← Insights agent lo guardó
  }
}

Cada sub-agente puede leer el contexto previo:
- InsightsAgent ve el texto OCR original (para validación)
- ChunkingAgent ve los artículos segmentados (para chunking inteligente)
- ObserverAgent ve TODO para persistir eventos ricos
```

### 2. **Decisiones Inteligentes**
```
Conditional Edges (LangGraph):

def should_retry_ocr(state):
    if state.get('ocr_error') and state['ocr_attempts'] < 3:
        return "retry_with_fallback"  # Intenta con Tika
    return "proceed_to_segmentation"

def should_skip_insights(state):
    if state['metadata']['newspaper'] == "Newsletter interno":
        return "skip_insights"  # No vale la pena insights para newsletters
    return "run_insights"

def should_enrich_with_web(state):
    article = state['current_article']
    if article['confidence'] > 0.8 and "economía" in article['title'].lower():
        return "enrich_with_perplexity"  # Solo enriquecer artículos relevantes
    return "skip_enrichment"
```

### 3. **Recovery Robusto**
```
Si Orchestrator Agent crashea:
1. LangGraph guarda checkpoint en PostgreSQL (orchestrator_state)
2. Al reiniciar, recupera estado exacto:
   • Qué node ejecutó
   • Qué tools llamó
   • Qué contexto tenía
3. Continúa desde último checkpoint
4. No repite trabajo ya hecho

Ejemplo:
- OCR completado ✅ (texto en estado)
- Segmentation crasheó ❌
- Al reiniciar: Skip OCR (ya está en contexto), ejecuta Segmentation
```

### 4. **Observabilidad Unificada**
```
ObserverAgent (como tool):
- Llamado por Orchestrator en CADA transición
- Persiste eventos con contexto completo
- Dashboard consume timeline unificado

Timeline en DB:
[
  {stage: "validation", status: "completed", timestamp: "10:00:00"},
  {stage: "ocr", status: "started", timestamp: "10:00:05"},
  {stage: "ocr", status: "completed", timestamp: "10:02:05", metadata: {duration: 120s}},
  {stage: "segmentation", status: "started", timestamp: "10:02:06"},
  ...
]

Usuario ve: "Este documento está en Segmentation, OCR tardó 2 min"
```

### 5. **Escalabilidad Horizontal**
```
Scheduler (uno solo, simple):
while True:
    if available_orchestrator_slots() > 0:
        document = get_next_pending_document()
        spawn_orchestrator_agent(document)
    sleep(5s)

Cada Orchestrator Agent:
- Procesa 1 documento end-to-end
- Usa sub-agentes como tools (local)
- Persiste checkpoints (recovery)
- Libera slot al terminar

Escalar: MAX_ORCHESTRATOR_AGENTS = 10 (en vez de 7 schedulers)
```

---

## 📐 COMPARACIÓN: COMUNICACIÓN

### ACTUAL (Event-Driven):

```
VENTAJAS:
✅ Resiliente a crashes (workers independientes)
✅ Escalable por etapa (ajustar workers por tipo)
✅ Simple de entender (cada scheduler autónomo)

DESVENTAJAS:
❌ Sin contexto compartido entre etapas
❌ 7 schedulers corriendo en paralelo
❌ Difícil debuggear flujo completo
❌ Logging disperso (cada worker loggea independiente)
❌ No hay memoria del pipeline
❌ Decisiones reactivas (no proactivas)
```

### PROPUESTA (Orchestrator Agent):

```
VENTAJAS:
✅ Contexto compartido (memoria del documento)
✅ Decisiones inteligentes (basadas en estado previo)
✅ Recovery robusto (checkpoints de LangGraph)
✅ Observabilidad unificada (un agente ve todo)
✅ Un solo scheduler (simple)
✅ Timeline completo por documento
✅ Sub-agentes como tools (reutilizables)
✅ Análisis de resultados en cada paso (Observer tiene contexto completo)

DESVENTAJAS:
❌ Más complejo de implementar (LangGraph)
❌ Requiere refactor de workers existentes
❌ Checkpoints en BD (overhead de estado)
```

---

## 🎯 RECOMENDACIÓN FINAL

### Opción A: **Hybrid Approach** (Recomendado)

```
ORCHESTRATOR AGENT (para documentos nuevos)
     +
EVENT-DRIVEN WORKERS (para tareas independientes)

Ejemplo:
- Documento nuevo → Orchestrator Agent (flujo completo)
- Reintentar OCR fallido → Event-driven worker (tarea específica)
- Bulk reindexing → Event-driven workers (paralelismo masivo)
```

### Opción B: **Full Orchestrator** (Futuro)

```
Un solo Orchestrator Agent por documento
Tools = Sub-agentes especializados
Comunicación 100% agéntica
BD solo para persistencia + checkpoints
```

---

## 📋 PRÓXIMOS PASOS

1. **Validar Propuesta con Usuario**:
   - ¿Orchestrator Agent solo o Hybrid?
   - ¿Prioridad: observabilidad o refactor completo?

2. **Implementar FASE 0** (si Orchestrator):
   - PipelineOrchestratorAgent (LangGraph)
   - Sub-agentes como tools
   - ObserverAgent para persistencia

3. **Implementar FASE 0** (si Hybrid):
   - ObserverAgent standalone
   - Integrar en workers existentes
   - Dashboard consume eventos

4. **Testing**:
   - 10 documentos con Orchestrator
   - Comparar performance vs. Event-driven
   - Validar recovery en crash

---

**Decisión del Usuario**: ¿Qué enfoque prefieres?
- **A**: Hybrid (Orchestrator + Event-driven coexistiendo)
- **B**: Full Orchestrator (refactor completo a agentes)
- **C**: Solo mejorar observabilidad (mantener Event-driven actual)
