# 🔍 Aclaración: "Agent" vs "Tool" en la Arquitectura Propuesta

> Clarificación de terminología y arquitectura técnica

**Fecha**: 2026-04-10  
**Relacionado**: REQ-027, AGENT_ORCHESTRATION_ARCHITECTURE.md

---

## ❓ LA PREGUNTA

En la documentación se mencionan:
- `ValidationAgent`, `OCRAgent`, `SegmentationAgent`, etc.
- Pero también se dice "sub-agentes como tools"
- ¿Son agentes LangChain o son funciones simples?
- ¿Cuál es la diferencia técnica?

---

## 🎯 RESPUESTA: ARQUITECTURA REAL PROPUESTA

### Concepto Clave: **"Agent" es una Interfaz Lógica, NO necesariamente LangChain**

```
┌───────────────────────────────────────────────────────────┐
│         ORCHESTRATOR AGENT (LangGraph - es agente)        │
├───────────────────────────────────────────────────────────┤
│                                                           │
│  Estado Compartido (TypedDict)                            │
│  Flujo de Control (Conditional Edges)                     │
│  Checkpoints (Recovery)                                   │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │              TOOLS (LangChain Tools)                │ │
│  ├─────────────────────────────────────────────────────┤ │
│  │                                                     │ │
│  │  validation_tool → ValidationService (NO agente)   │ │
│  │  ocr_tool        → OCRService (NO agente)          │ │
│  │  segmentation_tool → SegmentationAgent (SÍ agente) │ │
│  │  chunking_tool   → ChunkingService (NO agente)     │ │
│  │  indexing_tool   → IndexingService (NO agente)     │ │
│  │  insights_tool   → InsightsAgent (SÍ agente)       │ │
│  │  observer_tool   → ObserverService (NO agente)     │ │
│  │                                                     │ │
│  └─────────────────────────────────────────────────────┘ │
│                                                           │
└───────────────────────────────────────────────────────────┘
```

---

## 📋 REGLA DE ORO: ¿Cuándo usar un Agent vs Service?

### ✅ **USA AGENT (LangChain/LangGraph)** cuando:

1. **Necesita tomar decisiones complejas**
   - Múltiples pasos condicionales
   - Retry logic con estrategias
   - Llamadas a LLM con validación

2. **Necesita estado interno propio**
   - Memoria entre llamadas
   - Contexto que evoluciona

3. **Necesita orquestación interna**
   - Sub-flujos con branching
   - Validación → Extracción → Análisis

**Ejemplo**: `InsightsAgent` (ya existe, es LangGraph)
- Valida OCR con LLM
- Decide si enriquecer con web
- Extrae datos con OpenAI
- Analiza con retry
- Valida resultado final

### ❌ **USA SERVICE (función/clase simple)** cuando:

1. **Es una operación determinista**
   - Input → Output predecible
   - Sin decisiones complejas

2. **No necesita LLM**
   - Procesamiento de datos
   - I/O (leer, escribir, persistir)
   - Transformaciones

3. **Ya existe implementación**
   - OCRService (Tika/OCRmyPDF)
   - IndexingService (Qdrant)
   - ObserverService (PostgreSQL)

---

## 🏗️ ARQUITECTURA TÉCNICA CORRECTA

### ORCHESTRATOR AGENT (LangGraph)

```python
# backend/adapters/driven/llm/graphs/pipeline_orchestrator_graph.py

from langgraph.graph import StateGraph, END
from langchain.tools import tool

# ============================================================================
# TOOLS (envuelven Services o Agents existentes)
# ============================================================================

@tool
def validation_tool(filepath: str) -> dict:
    """
    Valida PDF y extrae metadata (fecha, periódico, sha8).
    Usa: ValidationService (clase simple, NO agente).
    """
    from backend.services.validation_service import ValidationService
    service = ValidationService()
    return service.validate_and_extract_metadata(filepath)

@tool
def ocr_tool(filepath: str, metadata: dict) -> dict:
    """
    Extrae texto del PDF.
    Usa: OCRService (clase existente, NO agente).
    """
    from backend.ocr_service import OCRService
    service = OCRService()
    text, doc_type, hash = service.extract_text(filepath)
    return {'text': text, 'doc_type': doc_type, 'hash': hash}

@tool
def segmentation_tool(text: str, metadata: dict) -> dict:
    """
    Detecta artículos en el texto.
    Usa: NewsSegmentationAgent (SÍ es agente, usa LLM Ollama).
    """
    from backend.news_segmentation_agent import NewsSegmentationAgent
    agent = NewsSegmentationAgent()  # Ya existe, es agente
    articles = agent.segment_document(text)
    return {'articles': articles}

@tool
def chunking_tool(articles: list) -> dict:
    """
    Divide artículos en chunks.
    Usa: ChunkingService (clase simple, NO agente).
    """
    from backend.services.chunking_service import ChunkingService
    service = ChunkingService()
    chunks = service.create_chunks(articles)
    return {'chunks': chunks}

@tool
def indexing_tool(chunks: list) -> dict:
    """
    Indexa chunks en Qdrant.
    Usa: IndexingService (clase simple, NO agente).
    """
    from backend.services.indexing_service import IndexingService
    service = IndexingService()
    vectors = service.index_chunks(chunks)
    return {'vectors': vectors}

@tool
def insights_tool(article: dict, context: dict) -> dict:
    """
    Genera insights estructurados.
    Usa: InsightsAgent (SÍ es agente LangGraph, ya existe).
    """
    from backend.adapters.driven.llm.graphs.insights_graph import build_insights_workflow
    workflow = build_insights_workflow()
    result = workflow.invoke({
        'news_item_id': article['id'],
        'context': article['text'],
        'title': article['title']
    })
    return result

@tool
def observer_tool(event: dict) -> dict:
    """
    Persiste evento en PostgreSQL.
    Usa: ObserverService (clase simple, NO agente).
    """
    from backend.adapters.driven.persistence.observer_service import ObserverService
    service = ObserverService()
    event_id = service.persist_event(event)
    return {'event_id': event_id, 'persisted': True}


# ============================================================================
# ORCHESTRATOR AGENT (LangGraph)
# ============================================================================

class OrchestratorState(TypedDict):
    """Estado compartido del orchestrator"""
    document_id: str
    filename: str
    metadata: dict
    pipeline_context: dict
    events: list
    current_stage: str
    error: Optional[str]

def validation_node(state: OrchestratorState) -> OrchestratorState:
    """Nodo que llama a validation_tool"""
    result = validation_tool.invoke({'filepath': state['filepath']})
    state['metadata'] = result
    state['current_stage'] = 'validation'
    
    # Persiste evento
    observer_tool.invoke({
        'stage': 'validation',
        'status': 'completed',
        'metadata': result
    })
    
    return state

def ocr_node(state: OrchestratorState) -> OrchestratorState:
    """Nodo que llama a ocr_tool"""
    result = ocr_tool.invoke({
        'filepath': state['filepath'],
        'metadata': state['metadata']
    })
    state['pipeline_context']['ocr_text'] = result['text']
    state['current_stage'] = 'ocr'
    
    observer_tool.invoke({
        'stage': 'ocr',
        'status': 'completed',
        'metadata': {'text_length': len(result['text'])}
    })
    
    return state

def segmentation_node(state: OrchestratorState) -> OrchestratorState:
    """Nodo que llama a segmentation_tool (que usa NewsSegmentationAgent)"""
    result = segmentation_tool.invoke({
        'text': state['pipeline_context']['ocr_text'],
        'metadata': state['metadata']
    })
    state['pipeline_context']['articles'] = result['articles']
    state['current_stage'] = 'segmentation'
    
    observer_tool.invoke({
        'stage': 'segmentation',
        'status': 'completed',
        'metadata': {'articles_count': len(result['articles'])}
    })
    
    return state

# ... (insights_node, indexing_node, etc.)

def build_orchestrator_workflow() -> StateGraph:
    """Construye el workflow completo"""
    workflow = StateGraph(OrchestratorState)
    
    # Nodos
    workflow.add_node("validation", validation_node)
    workflow.add_node("ocr", ocr_node)
    workflow.add_node("segmentation", segmentation_node)
    workflow.add_node("chunking", chunking_node)
    workflow.add_node("indexing", indexing_node)
    workflow.add_node("insights", insights_node)
    
    # Flujo
    workflow.set_entry_point("validation")
    workflow.add_edge("validation", "ocr")
    workflow.add_edge("ocr", "segmentation")
    workflow.add_edge("segmentation", "chunking")
    workflow.add_edge("chunking", "indexing")
    workflow.add_edge("indexing", "insights")
    workflow.add_edge("insights", END)
    
    return workflow.compile()
```

---

## 📊 RESUMEN: Qué es Agente y Qué NO

| Componente | Tipo | Tecnología | Razón |
|-----------|------|-----------|-------|
| **PipelineOrchestrator** | ✅ **AGENTE** | LangGraph | Orquesta flujo, tiene estado, checkpoints |
| validation_tool | ❌ Service | Python simple | Función determinista |
| ocr_tool | ❌ Service | Python + Tika/OCRmyPDF | Sin LLM, determinista |
| **segmentation_tool** | ✅ **AGENTE** | LangChain + Ollama | Usa LLM, decisiones complejas |
| chunking_tool | ❌ Service | Python simple | Transformación de datos |
| indexing_tool | ❌ Service | Python + Qdrant | I/O simple |
| **insights_tool** | ✅ **AGENTE** | LangGraph (existing) | Multi-step, LLM, retry logic |
| observer_tool | ❌ Service | Python + PostgreSQL | Persistencia simple |

---

## 🔄 CORRECCIÓN DE DOCUMENTACIÓN

### En vez de:
```
ValidationAgent, OCRAgent, ChunkingAgent, IndexingAgent, ObserverAgent
```

### Debe decir:
```
ValidationService, OCRService, ChunkingService, IndexingService, ObserverService
```

### Excepciones (SÍ son Agentes):
```
NewsSegmentationAgent (usa LLM Ollama)
InsightsAgent (LangGraph multi-step)
PipelineOrchestratorAgent (LangGraph main)
```

---

## 🎯 RESPUESTA FINAL A TU PREGUNTA

**¿Son todos LangChain?**
- NO. Solo los que usan LLM o necesitan orquestación compleja.

**¿Cuál es el plan?**
- **Orchestrator**: LangGraph (agente maestro)
- **Tools que usan LLM**: LangChain Agents (segmentation, insights)
- **Tools simples**: Servicios Python normales (validation, ocr, chunking, indexing)

**¿Por qué llamarlos "Agent" en los diagramas?**
- Nombre lógico para abstraer implementación
- Facilita entender el flujo sin detalles técnicos
- Pero técnicamente, solo 3 son "Agents" reales

---

## ✅ ACCIÓN REQUERIDA

Actualizar documentación para usar terminología correcta:
- `ValidationService` (no Agent)
- `OCRService` (no Agent)
- `ChunkingService` (no Agent)
- `IndexingService` (not Agent)
- `ObserverService` (no Agent)
- `NewsSegmentationAgent` ✅ (SÍ es Agent)
- `InsightsAgent` ✅ (SÍ es Agent, ya existe)
- `PipelineOrchestratorAgent` ✅ (SÍ es Agent, nuevo)

**¿Quieres que corrija los documentos ahora con la terminología correcta?**
