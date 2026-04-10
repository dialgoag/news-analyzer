# 🔍 Aclaración: ObserverAgent y Almacenamiento de Resultados

> ¿Quién detecta errores? ¿Dónde se guardan los resultados de cada paso?

**Fecha**: 2026-04-10  
**Relacionado**: REQ-027, AGENT_ORCHESTRATION_ARCHITECTURE.md

---

## ❓ LAS PREGUNTAS

1. **¿El paso que detecta y administra consultas debería ser otro agente?**
2. **¿O debería ser parte del orchestrator con visión transversal?**
3. **¿La BD actual soporta toda la info extra de cada paso (tiempos, errores, resultados)?**
4. **¿Dónde se guardan los resultados de cada paso?**

---

## 🎯 RESPUESTA: ObserverAgent ES PARTE DEL ORCHESTRATOR

### Arquitectura Correcta:

```
┌─────────────────────────────────────────────────────────────────┐
│         PIPELINE ORCHESTRATOR AGENT (LangGraph)                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  RESPONSABILIDADES:                                             │
│  ✅ Ejecutar pipeline (validación → OCR → segmentation → ...)  │
│  ✅ Observar CADA paso (timing, errores, resultados)           │
│  ✅ Persistir eventos automáticamente                          │
│  ✅ Tomar decisiones basadas en resultados previos             │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              ESTADO COMPARTIDO                            │ │
│  ├───────────────────────────────────────────────────────────┤ │
│  │ • document_id: str                                        │ │
│  │ • current_stage: PipelineStage                            │ │
│  │ • pipeline_context: dict (resultados de cada paso)        │ │
│  │   ├─ ocr_result: {text, pages, duration, success}        │ │
│  │   ├─ segmentation_result: {articles, confidence, ...}    │ │
│  │   ├─ chunking_result: {chunks, count, ...}               │ │
│  │   └─ insights_result: {insights, tokens, ...}            │ │
│  │ • events: List[PipelineEvent] (timeline completo)        │ │
│  │ • errors: List[PipelineError] (errores detectados)       │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  FLUJO:                                                         │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │ Node: ocr_node                                            │ │
│  │   1. Ejecuta: ocr_tool(filepath)                          │ │
│  │   2. Guarda resultado en: state.pipeline_context.ocr      │ │
│  │   3. Auto-observa: crea PipelineEvent                     │ │
│  │      • stage: 'ocr'                                       │ │
│  │      • status: 'completed'                                │ │
│  │      • duration: 120s                                     │ │
│  │      • result_ref: document_id + '/ocr_result.json'       │ │
│  │   4. Persiste evento en PostgreSQL                        │ │
│  │   5. Persiste resultado en object store (si es grande)    │ │
│  │   6. Continúa al siguiente nodo                           │ │
│  └───────────────────────────────────────────────────────────┘ │
│                                                                 │
│  VENTAJA: Visión transversal automática                        │
│  • Orchestrator VE todos los resultados previos                │
│  • Puede decidir basándose en contexto completo                │
│  • Ejemplo: "OCR tardó mucho → skip insights para ahorrar"     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🗄️ ALMACENAMIENTO: Dos Capas

### CAPA 1: Metadata + Eventos (PostgreSQL)

```sql
-- Tabla 1: document_processing_log (eventos de cada paso)
CREATE TABLE document_processing_log (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL,
    stage VARCHAR(50) NOT NULL,  -- 'upload', 'ocr', 'segmentation', etc.
    status VARCHAR(20) NOT NULL,  -- 'started', 'completed', 'error'
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    duration_sec NUMERIC(10, 3),
    
    -- Metadata del paso
    metadata JSONB,  -- {pages: 10, engine: 'ocrmypdf', confidence: 0.85, etc.}
    
    -- Errores (si aplica)
    error_type VARCHAR(100),
    error_message TEXT,
    error_detail JSONB,  -- {traceback, context, etc.}
    
    -- Referencia al resultado completo (si es grande)
    result_ref VARCHAR(500),  -- "s3://bucket/results/{doc_id}/ocr_result.json"
    result_size_bytes BIGINT,
    
    INDEX idx_document_stage (document_id, stage),
    INDEX idx_timestamp (timestamp DESC),
    INDEX idx_status (status)
);

-- Tabla 2: document_status (estado consolidado)
CREATE TABLE document_status (
    document_id UUID PRIMARY KEY,
    
    -- Metadata del documento
    filename VARCHAR(500),
    publication_date DATE,
    newspaper_name VARCHAR(100),
    sha8_prefix VARCHAR(8),
    
    -- Pipeline status
    current_stage VARCHAR(50),
    pipeline_status VARCHAR(20),  -- 'processing', 'completed', 'error'
    
    -- Resultados consolidados (referencias)
    ocr_result_ref VARCHAR(500),
    segmentation_result_ref VARCHAR(500),
    chunking_result_ref VARCHAR(500),
    indexing_result_ref VARCHAR(500),
    insights_result_ref VARCHAR(500),
    
    -- Timestamps
    created_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    
    -- Métricas agregadas
    total_duration_sec NUMERIC(10, 3),
    stages_completed INT,
    stages_failed INT
);

-- Tabla 3: pipeline_results (resultados intermedios pequeños)
CREATE TABLE pipeline_results (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL,
    stage VARCHAR(50) NOT NULL,
    
    -- Resultado (si < 10MB, guardarlo aquí)
    result_data JSONB,  
    
    -- O referencia externa (si > 10MB)
    result_ref VARCHAR(500),
    result_size_bytes BIGINT,
    
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    INDEX idx_document_stage (document_id, stage)
);
```

### CAPA 2: Resultados Grandes (Object Store)

**Estrategia**:
- Resultados **< 1MB**: Guardar en `pipeline_results.result_data` (JSONB)
- Resultados **> 1MB**: Guardar en filesystem/S3 + referencia en `result_ref`

**Estructura de directorios**:
```
local-data/
  ├─ uploads/           # PDFs originales
  ├─ results/           # Resultados de cada paso
  │   ├─ {document_id}/
  │   │   ├─ ocr_result.json          # {text, pages, metadata}
  │   │   ├─ segmentation_result.json # {articles: [...]}
  │   │   ├─ chunking_result.json     # {chunks: [...]}
  │   │   ├─ indexing_result.json     # {vectors: [...], ids: [...]}
  │   │   └─ insights_result.json     # {insights: [...]}
```

**Ejemplo**:
```json
// local-data/results/abc123-456/ocr_result.json
{
  "text": "Contenido completo del PDF extraído...",
  "pages": 15,
  "engine": "ocrmypdf",
  "duration_sec": 120.5,
  "metadata": {
    "language": "es",
    "confidence": 0.95,
    "file_size_mb": 18.6
  }
}
```

---

## 🔄 FLUJO COMPLETO: Orchestrator con Auto-Observación

### Ejemplo: Paso de OCR

```python
# backend/adapters/driven/llm/graphs/pipeline_orchestrator_graph.py

async def ocr_node(state: OrchestratorState) -> OrchestratorState:
    """
    Nodo OCR con auto-observación integrada.
    El orchestrator tiene visión transversal.
    """
    document_id = state['document_id']
    filepath = state['filepath']
    
    # 1. REGISTRAR INICIO
    start_time = time.time()
    await _persist_event(
        document_id=document_id,
        stage='ocr',
        status='started',
        metadata={'filepath': filepath}
    )
    
    try:
        # 2. EJECUTAR TOOL
        result = await ocr_tool.ainvoke({'filepath': filepath})
        duration = time.time() - start_time
        
        # 3. GUARDAR RESULTADO EN ESTADO (visión transversal)
        state['pipeline_context']['ocr'] = {
            'text': result['text'],
            'pages': result['pages'],
            'duration': duration,
            'success': True
        }
        
        # 4. DECIDIR DÓNDE GUARDAR RESULTADO
        text_size = len(result['text'])
        
        if text_size < 1_000_000:  # < 1MB
            # Guardar en PostgreSQL (JSONB)
            await db.execute(
                """
                INSERT INTO pipeline_results (document_id, stage, result_data)
                VALUES ($1, $2, $3)
                """,
                document_id, 'ocr', result
            )
            result_ref = None
        else:  # > 1MB
            # Guardar en filesystem
            result_path = f"local-data/results/{document_id}/ocr_result.json"
            os.makedirs(os.path.dirname(result_path), exist_ok=True)
            with open(result_path, 'w') as f:
                json.dump(result, f)
            result_ref = result_path
        
        # 5. REGISTRAR EVENTO COMPLETADO
        await _persist_event(
            document_id=document_id,
            stage='ocr',
            status='completed',
            duration=duration,
            metadata={
                'pages': result['pages'],
                'text_length': text_size,
                'engine': 'ocrmypdf'
            },
            result_ref=result_ref,
            result_size_bytes=text_size
        )
        
        # 6. ACTUALIZAR document_status
        await db.execute(
            """
            UPDATE document_status 
            SET current_stage = 'ocr',
                ocr_result_ref = $2,
                updated_at = NOW()
            WHERE document_id = $1
            """,
            document_id, result_ref or f"postgresql://pipeline_results/{document_id}/ocr"
        )
        
        # 7. DECISIÓN BASADA EN CONTEXTO (visión transversal)
        if duration > 300:  # OCR tardó > 5 min
            logger.warning(f"OCR tardó {duration}s. Considerar skip de insights.")
            state['skip_insights'] = True  # Orchestrator puede decidir
        
    except Exception as e:
        duration = time.time() - start_time
        
        # REGISTRAR ERROR
        state['errors'].append({
            'stage': 'ocr',
            'error': str(e),
            'traceback': traceback.format_exc()
        })
        
        await _persist_event(
            document_id=document_id,
            stage='ocr',
            status='error',
            duration=duration,
            error_type=type(e).__name__,
            error_message=str(e),
            error_detail={'traceback': traceback.format_exc()}
        )
        
        # Orchestrator decide: ¿retry? ¿fallback? ¿skip?
        if isinstance(e, OCRTimeoutError):
            state['retry_ocr_with_tika'] = True
        else:
            raise  # Propagar error crítico
    
    return state


async def _persist_event(
    document_id: str,
    stage: str,
    status: str,
    duration: float = None,
    metadata: dict = None,
    error_type: str = None,
    error_message: str = None,
    error_detail: dict = None,
    result_ref: str = None,
    result_size_bytes: int = None
):
    """Helper para persistir eventos (parte del orchestrator)"""
    await db.execute(
        """
        INSERT INTO document_processing_log 
        (document_id, stage, status, duration_sec, metadata, 
         error_type, error_message, error_detail, result_ref, result_size_bytes)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
        """,
        document_id, stage, status, duration, 
        json.dumps(metadata) if metadata else None,
        error_type, error_message,
        json.dumps(error_detail) if error_detail else None,
        result_ref, result_size_bytes
    )
```

---

## 🎯 RESPUESTAS A TUS PREGUNTAS

### 1. ¿El paso que detecta errores debería ser otro agente?

**NO. Es parte del Orchestrator con visión transversal.**

Ventajas:
- ✅ Orchestrator ve TODO el contexto (resultados previos, errores, timing)
- ✅ Puede tomar decisiones inteligentes ("OCR tardó mucho → skip insights")
- ✅ Auto-observación en cada nodo (no necesita agente separado)
- ✅ Menos overhead (un agente vs dos)

### 2. ¿La BD actual soporta toda la info?

**SÍ, con modificaciones menores:**

**Ya existe**:
- ✅ `document_status` (estado consolidado)
- ✅ `document_stage_timing` (timing por etapa)

**Agregar**:
- 🆕 `document_processing_log` (eventos detallados con errores)
- 🆕 `pipeline_results` (resultados intermedios < 1MB)
- 🆕 Columnas en `document_status`: `*_result_ref` (referencias a resultados)

### 3. ¿Dónde se guardan los resultados?

**Estrategia híbrida**:

| Tamaño | Ubicación | Tabla | Ejemplo |
|--------|-----------|-------|---------|
| **< 1MB** | PostgreSQL | `pipeline_results.result_data` (JSONB) | Metadata de segmentation |
| **> 1MB** | Filesystem | `local-data/results/{doc_id}/*.json` | Texto OCR completo |
| **Referencia** | PostgreSQL | `document_status.*_result_ref` | Puntero al archivo |

**Consulta de resultados**:
```python
# Dashboard quiere texto OCR de un documento
async def get_ocr_result(document_id: str) -> dict:
    # 1. Buscar referencia
    ref = await db.fetchval(
        "SELECT ocr_result_ref FROM document_status WHERE document_id = $1",
        document_id
    )
    
    # 2. Cargar resultado
    if ref.startswith('postgresql://'):
        # Está en BD
        return await db.fetchval(
            "SELECT result_data FROM pipeline_results WHERE document_id = $1 AND stage = 'ocr'",
            document_id
        )
    else:
        # Está en filesystem
        with open(ref, 'r') as f:
            return json.load(f)
```

---

## 🏗️ ARQUITECTURA FINAL: Orchestrator con Auto-Observación

```
┌─────────────────────────────────────────────────────────────┐
│            PIPELINE ORCHESTRATOR AGENT                      │
│              (Visión Transversal Total)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  POR CADA NODO:                                             │
│  1. Registra evento "started" en document_processing_log    │
│  2. Ejecuta tool (ocr, segmentation, etc.)                  │
│  3. Guarda resultado:                                       │
│     • Si < 1MB → pipeline_results (JSONB)                   │
│     • Si > 1MB → filesystem + referencia                    │
│  4. Actualiza estado compartido (visión transversal)        │
│  5. Registra evento "completed" con metadata                │
│  6. Toma decisiones basadas en contexto completo            │
│                                                             │
│  SI ERROR:                                                  │
│  1. Registra evento "error" con traceback                   │
│  2. Agrega a state.errors (lista de errores)                │
│  3. Decide: ¿retry? ¿fallback? ¿skip? ¿abort?              │
│                                                             │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    POSTGRESQL                               │
├─────────────────────────────────────────────────────────────┤
│  document_processing_log (eventos + errores + referencias)  │
│  document_status (estado consolidado + refs)                │
│  pipeline_results (resultados pequeños)                     │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    FILESYSTEM                               │
├─────────────────────────────────────────────────────────────┤
│  local-data/results/{doc_id}/ocr_result.json               │
│  local-data/results/{doc_id}/segmentation_result.json      │
│  ...                                                        │
└─────────────────────────────────────────────────────────────┘
```

---

## ✅ CONCLUSIÓN

**NO necesitas un agente separado para observación.**

El **Orchestrator mismo** tiene:
- ✅ Visión transversal de todos los pasos
- ✅ Auto-observación integrada en cada nodo
- ✅ Persistencia automática de eventos, errores y resultados
- ✅ Decisiones inteligentes basadas en contexto completo

**La BD actual soporta TODO con mínimos cambios:**
- Agregar `document_processing_log` (eventos detallados)
- Agregar `pipeline_results` (resultados intermedios)
- Agregar columnas `*_result_ref` en `document_status`

**¿Te parece bien esta arquitectura o prefieres un agente separado para observación?**
