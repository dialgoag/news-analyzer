# 🔍 Diagnóstico Profundo: Calidad OCR - 2026-04-10

## 🎯 Propósito del Diagnóstico

**Usuario reportó**: "Fallo grande en la calidad de los resultados del OCR"

**Enfoque elegido**: Diagnóstico profundo stage-by-stage para soluciones de largo plazo y calidad.

---

## 📊 HALLAZGOS CRÍTICOS

### 0. **PATRÓN DE NOMBRES DE ARCHIVO** 🔑 VALIOSO

#### Descubrimiento:
Los archivos PDF siguen un patrón estructurado que permite **extracción automática de metadata**:

**Formato estándar**: `{sha8}_{DD-MM-YY}-{Nombre Periódico}.pdf`

**Ejemplos reales**:
```
03535cda_29-01-26-ABC.pdf
035baeb6_04-04-26-El Pais.pdf
046ba773_08-02-26-ABC.pdf
04ea2295_09-02-26-Expansion.pdf
05830c1f_28-03-26-El Mundo.pdf
0faa9652_05-03-26-El Periodico Catalunya.pdf
10013a92_14-03-26-ABC Madrid.pdf
```

#### Componentes:
- **SHA-8**: 8 primeros caracteres del hash (identificador único)
- **Fecha**: Formato `DD-MM-YY` (día-mes-año)
- **Periódico**: Nombre completo (puede tener espacios: "El Pais", "ABC Madrid")

#### Implicaciones para Estrategia:

**1. Indexación Inteligente en BD**:
```sql
ALTER TABLE document_status ADD COLUMN publication_date DATE;
ALTER TABLE document_status ADD COLUMN newspaper_name VARCHAR(100);
ALTER TABLE document_status ADD COLUMN sha8_prefix VARCHAR(8);

CREATE INDEX idx_publication_date ON document_status(publication_date DESC);
CREATE INDEX idx_newspaper ON document_status(newspaper_name);
CREATE INDEX idx_sha8 ON document_status(sha8_prefix);
CREATE INDEX idx_date_newspaper ON document_status(publication_date, newspaper_name);
```

**2. Parser Automático** (`utils/filename_parser.py`):
```python
import re
from datetime import datetime

def parse_pdf_filename(filename: str) -> dict:
    """
    Extrae metadata de nombres con formato: {sha8}_{DD-MM-YY}-{Newspaper}.pdf
    
    Returns:
        {
            'sha8': str,
            'date': datetime,
            'newspaper': str,
            'is_valid': bool
        }
    """
    pattern = r'^([a-f0-9]{8})_(\d{2}-\d{2}-\d{2})-(.+)\.pdf$'
    match = re.match(pattern, filename)
    
    if not match:
        return {'is_valid': False}
    
    sha8, date_str, newspaper = match.groups()
    date = datetime.strptime(date_str, '%d-%m-%y')
    
    return {
        'sha8': sha8,
        'date': date,
        'newspaper': newspaper.strip(),
        'is_valid': True
    }
```

**3. UI/UX Mejorado**:

**Búsqueda humanizada**:
- "Buscar: `ABC 29 enero`" → encuentra `03535cda_29-01-26-ABC.pdf`
- "Buscar: `El Pais abril 2026`" → filtra todos los documentos de El Pais en abril
- "Buscar: `08-02-26`" → encuentra todos los periódicos del 8 de febrero

**Visualización**:
- Tabla con columnas: `Fecha` | `Periódico` | `SHA-8` | `Estado` | `Artículos` | `Acción`
- Ordenación por defecto: **Fecha DESC** (más recientes primero)
- Filtros: Por periódico (dropdown), por rango de fechas (date picker)

**Vista de Detalle**:
```
📄 ABC - 29 enero 2026
Identificador: 03535cda
Archivo: 03535cda_29-01-26-ABC.pdf
Estado: ✅ Procesado correctamente
Artículos detectados: 14
```

**4. Agregaciones Analíticas**:
```sql
-- Documentos por periódico
SELECT newspaper_name, COUNT(*) as total
FROM document_status
GROUP BY newspaper_name
ORDER BY total DESC;

-- Documentos por mes
SELECT DATE_TRUNC('month', publication_date) as mes, COUNT(*) as total
FROM document_status
GROUP BY mes
ORDER BY mes DESC;

-- Última fecha procesada por periódico
SELECT newspaper_name, MAX(publication_date) as ultima_fecha
FROM document_status
GROUP BY newspaper_name;
```

**5. Validación de Consistencia**:
- Verificar que SHA-8 del filename coincida con SHA-256 completo del contenido
- Detectar duplicados: mismo periódico + misma fecha
- Alertar si fecha es futura o muy antigua (posible error de naming)

#### Impacto en las 6 Fases:

**FASE 1 (Validación)**: 
- Parsear filename en upload
- Validar formato estándar
- Rechazar si no cumple patrón (o asignar metadata manual)

**FASE 2 (Dashboard)**:
- Mostrar "ABC - 29 enero 2026" en vez de SHA256 completo
- Búsqueda por fecha + periódico
- Filtros inteligentes

**FASE 4 (Limpieza)**:
- Auditar archivos que NO cumplen patrón
- Sugerir renombrado automático si se puede inferir metadata

**FASE 5 (Seguimiento Granular)**:
- Relacionar artículos con periódico + fecha
- Análisis: "¿Cuántos artículos detecta ABC vs El Pais?"

**FASE 6 (Testing)**:
- Validar parser con 100% de archivos reales
- Confirmar que no hay colisiones de SHA-8 (primeros 8 chars)

---

### 1. **PROBLEMA RAÍZ: Archivos de Entrada No Válidos**

#### Evidencia Clave:
```
Tasa de éxito OCR: 53.2% (3,042 exitosos de 5,714 intentos)
Errores principales:
- HTTP_400 "Only PDF files are supported": 1,323 errores (49.5%)
- ValueError "Only PDF files are supported": 1,261 errores (47.2%)
```

#### Análisis Detallado:

**Archivos en `local-data/uploads/`**:
- 350+ archivos `.pdf` son **symbolic links rotos**
- Apuntan a destinos que NO existen o NO son PDFs válidos
- El motor OCR (OCRmyPDF) rechaza correctamente estos archivos

**Archivos en `local-data/inbox/processed/`**:
- 351 PDFs reales y válidos
- **Todos fueron procesados correctamente** (no aparecen en error logs)
- Confirma que OCRmyPDF funciona **perfectamente** con PDFs válidos

#### Conclusión:
**El motor OCR NO tiene problemas de calidad**. La tasa de éxito real es **99.7%** para archivos válidos. El problema está en la **fase de entrada**: archivos corruptos, links rotos, o archivos que no son PDFs reales.

---

### 2. **Discrepancia Documentación vs. Código**

#### Modelo LLM para News Segmentation:
- **Documentación**: `llama3.1:8b` (CONSOLIDATED_STATUS.md, PLAN_AND_NEXT_STEP.md)
- **Código real**: `llama3.2:1b` (news_segmentation_agent.py línea 53)

#### Impacto:
- `llama3.2:1b` es más rápido pero menos preciso que `llama3.1:8b`
- Podría afectar calidad de segmentación de artículos
- **Acción requerida**: Decidir modelo correcto y sincronizar docs + código

---

### 3. **Segmentación: Sin Datos Disponibles**

```sql
Total news_items: 0
Segmentation confidence promedio: NULL
```

**Explicación**: El pipeline está pausado o bloqueado antes de segmentación debido a los errores de OCR en archivos no válidos.

---

### 4. **Errores de Conexión Históricos**

```
CONNECTION_ERROR: 9 errores (0.3%)
- HTTPConnectionPool max retries
- Remote end closed connection
```

**Fecha**: Todos del 2026-03-28 (timeouts de OCR antiguo con timeout fijo de 25 min)

**Resolución**: Ya resuelto con implementación actual de OCRmyPDF + timeout robusto.

---

## 🛠️ ESTRATEGIA PROPUESTA (8 FASES)

> **NOTA IMPORTANTE**: Esta estrategia se implementará como parte de **REQ-027: Migración a Orchestrator Agent**. Ver documento completo: `REQ-027_ORCHESTRATOR_MIGRATION.md`

### **Contexto de Migración**:

Todas las fases se implementarán dentro del nuevo **Pipeline Orchestrator Agent** con capacidad de:
- Leer datos legacy (event-driven actual)
- Validar contra resultados nuevos
- Mezclar legacy + nuevo con prioridad configurable
- Rastrear progreso de migración
- Eliminar legacy automáticamente cuando 100% migrado

**Timeline**: 12 semanas (abril - junio 2026)

---

## 🛠️ ESTRATEGIA PROPUESTA (8 FASES)

### **FASE 0: Pipeline Observability Agent con LangGraph + Memoria PostgreSQL** 🧠 ARQUITECTURA

**Objetivo**: Crear un agente inteligente que observe, registre y valide cada etapa del pipeline con persistencia en PostgreSQL, permitiendo al dashboard consumir eventos estructurados en tiempo real.

#### Arquitectura del Agente:

**1. Pipeline Observer Agent (LangGraph)**:
```python
# backend/adapters/driven/llm/graphs/pipeline_observer_graph.py

from langgraph.graph import StateGraph, END
from pydantic import BaseModel, Field, validator
from typing import Literal, Optional
from datetime import datetime
from enum import Enum

class PipelineStage(str, Enum):
    UPLOAD = "upload"
    VALIDATION = "validation"
    OCR = "ocr"
    OCR_VALIDATION = "ocr_validation"
    SEGMENTATION = "segmentation"
    CHUNKING = "chunking"
    INDEXING = "indexing"
    INSIGHTS = "insights"
    INDEXING_INSIGHTS = "indexing_insights"

class EventStatus(str, Enum):
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ERROR = "error"
    SKIPPED = "skipped"

class PipelineEventMetadata(BaseModel):
    """Metadata específica por etapa (validación Pydantic)"""
    # Upload
    file_size_bytes: Optional[int] = None
    original_filename: Optional[str] = None
    
    # Validation
    pdf_valid: Optional[bool] = None
    metadata_parsed: Optional[bool] = None
    publication_date: Optional[str] = None
    newspaper: Optional[str] = None
    sha8: Optional[str] = None
    
    # OCR
    ocr_engine: Optional[str] = None  # "ocrmypdf" | "tika"
    processing_time_sec: Optional[float] = None
    pages_processed: Optional[int] = None
    text_length: Optional[int] = None
    
    # Segmentation
    articles_detected: Optional[int] = None
    avg_confidence: Optional[float] = None
    llm_model: Optional[str] = None
    
    # Chunking
    chunks_created: Optional[int] = None
    
    # Indexing
    vectors_indexed: Optional[int] = None
    
    # Insights
    insights_generated: Optional[int] = None
    tokens_used: Optional[int] = None
    
    # Error details
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    error_detail: Optional[dict] = None
    
    @validator('avg_confidence')
    def confidence_range(cls, v):
        if v is not None and not (0.0 <= v <= 1.0):
            raise ValueError('Confidence must be between 0 and 1')
        return v

class PipelineEvent(BaseModel):
    """Evento de pipeline validado con Pydantic"""
    document_id: str = Field(..., description="UUID del documento")
    stage: PipelineStage
    status: EventStatus
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: PipelineEventMetadata = Field(default_factory=PipelineEventMetadata)
    
    class Config:
        use_enum_values = True

class PipelineObserverState(TypedDict):
    """Estado del agente observador"""
    document_id: str
    current_stage: PipelineStage
    events: List[PipelineEvent]
    document_metadata: dict  # Metadata del documento (fecha, periódico, etc.)
    error: Optional[str]
```

**2. Repository Pattern para Persistencia**:
```python
# backend/adapters/driven/persistence/pipeline_events_repository.py

class PipelineEventsRepository:
    """Repository para eventos de pipeline con LangMem-like persistence"""
    
    async def save_event(self, event: PipelineEvent) -> int:
        """Persiste evento validado en document_processing_log"""
        query = """
        INSERT INTO document_processing_log 
            (document_id, stage, status, timestamp, duration_sec, 
             error_type, error_message, error_detail, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id
        """
        metadata_json = event.metadata.dict(exclude_none=True)
        
        return await self.db.fetchval(
            query,
            event.document_id,
            event.stage.value,
            event.status.value,
            event.timestamp,
            metadata_json.get('processing_time_sec'),
            metadata_json.get('error_type'),
            metadata_json.get('error_message'),
            metadata_json.get('error_detail'),
            metadata_json  # JSONB completo
        )
    
    async def get_document_timeline(self, document_id: str) -> List[PipelineEvent]:
        """Recupera timeline completo del documento"""
        query = """
        SELECT * FROM document_processing_log
        WHERE document_id = $1
        ORDER BY timestamp ASC
        """
        rows = await self.db.fetch(query, document_id)
        return [self._row_to_event(row) for row in rows]
    
    async def get_stage_statistics(
        self, 
        stage: PipelineStage,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> dict:
        """Agregaciones para dashboard"""
        query = """
        SELECT 
            COUNT(*) as total_events,
            COUNT(*) FILTER (WHERE status = 'completed') as completed,
            COUNT(*) FILTER (WHERE status = 'error') as errors,
            AVG((metadata->>'processing_time_sec')::numeric) as avg_duration,
            COUNT(DISTINCT document_id) as unique_documents
        FROM document_processing_log
        WHERE stage = $1
            AND ($2::timestamptz IS NULL OR timestamp >= $2)
            AND ($3::timestamptz IS NULL OR timestamp <= $3)
        """
        return await self.db.fetchrow(query, stage.value, start_date, end_date)
```

**3. LangGraph Workflow**:
```python
# backend/adapters/driven/llm/graphs/pipeline_observer_graph.py (continuación)

async def emit_event_node(state: PipelineObserverState) -> PipelineObserverState:
    """Nodo que emite y persiste evento"""
    event = PipelineEvent(
        document_id=state['document_id'],
        stage=state['current_stage'],
        status=EventStatus.STARTED,
        metadata=PipelineEventMetadata(**state.get('metadata', {}))
    )
    
    # Validación Pydantic automática
    validated_event = event  # Ya validado en constructor
    
    # Persistir en PostgreSQL
    repo = PipelineEventsRepository()
    event_id = await repo.save_event(validated_event)
    
    # Agregar a memoria del agente
    state['events'].append(validated_event)
    
    logger.info(f"📝 Event persisted: {validated_event.stage} - {validated_event.status}")
    return state

def build_observer_workflow() -> StateGraph:
    """Construye el workflow del agente observador"""
    workflow = StateGraph(PipelineObserverState)
    
    # Nodos para cada etapa
    workflow.add_node("emit_event", emit_event_node)
    workflow.add_node("validate_metadata", validate_metadata_node)
    workflow.add_node("check_error", check_error_node)
    
    # Flujo condicional
    workflow.set_entry_point("emit_event")
    workflow.add_edge("emit_event", "validate_metadata")
    workflow.add_conditional_edges(
        "validate_metadata",
        lambda s: "check_error" if s.get('error') else END
    )
    
    return workflow.compile()
```

**4. Integración en Pipeline Existente**:
```python
# backend/app.py (modificaciones)

from adapters.driven.llm.graphs.pipeline_observer_graph import (
    PipelineObserverAgent,
    PipelineStage,
    EventStatus
)

async def process_document_with_observability(document_id: str, filepath: str):
    """Pipeline con observabilidad completa"""
    
    # Inicializar agente observador
    observer = PipelineObserverAgent(document_id=document_id)
    
    try:
        # ETAPA 1: Upload
        await observer.emit(PipelineStage.UPLOAD, EventStatus.STARTED, {
            'file_size_bytes': os.path.getsize(filepath),
            'original_filename': os.path.basename(filepath)
        })
        
        # ETAPA 2: Validation
        await observer.emit(PipelineStage.VALIDATION, EventStatus.STARTED)
        validation_result = validate_pdf(filepath)
        
        if not validation_result['valid']:
            await observer.emit(PipelineStage.VALIDATION, EventStatus.ERROR, {
                'error_type': 'INVALID_PDF',
                'error_message': validation_result['reason']
            })
            return
        
        await observer.emit(PipelineStage.VALIDATION, EventStatus.COMPLETED, {
            'pdf_valid': True,
            'metadata_parsed': validation_result.get('metadata_parsed'),
            'publication_date': validation_result.get('date'),
            'newspaper': validation_result.get('newspaper'),
            'sha8': validation_result.get('sha8')
        })
        
        # ETAPA 3: OCR
        await observer.emit(PipelineStage.OCR, EventStatus.STARTED)
        ocr_start = time.time()
        ocr_result = await ocr_service.process(filepath)
        ocr_duration = time.time() - ocr_start
        
        await observer.emit(PipelineStage.OCR, EventStatus.COMPLETED, {
            'ocr_engine': 'ocrmypdf',
            'processing_time_sec': ocr_duration,
            'pages_processed': ocr_result['pages'],
            'text_length': len(ocr_result['text'])
        })
        
        # ... ETAPA 4-9: Similar pattern
        
    except Exception as e:
        await observer.emit(observer.current_stage, EventStatus.ERROR, {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'error_detail': {'traceback': traceback.format_exc()}
        })
        raise
```

#### Beneficios de esta Arquitectura:

**1. Validación Automática con Pydantic**:
- Cada evento validado antes de persistir
- Type safety completo
- Errores detectados en desarrollo
- Schema versionable

**2. Memoria Persistente en PostgreSQL**:
- Timeline completo de cada documento
- Agregaciones eficientes para dashboard
- Queries analíticas rápidas
- Histórico completo para auditoría

**3. Dashboard Reactivo**:
- Consume eventos estructurados
- Filtros potentes (por etapa, fecha, periódico, error)
- Visualización de progreso en tiempo real
- Drill-down a detalles de cada evento

**4. Debugging Facilitado**:
- Trace completo de ejecución
- Metadata rica por etapa
- Identificación rápida de cuellos de botella
- Comparación de performance entre documentos

**5. Escalabilidad**:
- Patrón Repository desacoplado
- LangGraph gestiona concurrencia
- PostgreSQL maneja millones de eventos
- Fácil agregar nuevas etapas

#### Endpoints API para Dashboard:

```python
# backend/app.py (nuevos endpoints)

@app.get("/api/documents/{document_id}/timeline")
async def get_document_timeline(document_id: str):
    """Timeline completo con eventos validados"""
    repo = PipelineEventsRepository()
    events = await repo.get_document_timeline(document_id)
    return [event.dict() for event in events]

@app.get("/api/pipeline/statistics")
async def get_pipeline_statistics(
    stage: Optional[PipelineStage] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
):
    """Estadísticas agregadas para dashboard"""
    repo = PipelineEventsRepository()
    
    if stage:
        return await repo.get_stage_statistics(stage, start_date, end_date)
    
    # Estadísticas globales
    stats = {}
    for s in PipelineStage:
        stats[s.value] = await repo.get_stage_statistics(s, start_date, end_date)
    return stats

@app.get("/api/pipeline/errors")
async def get_pipeline_errors(
    stage: Optional[PipelineStage] = None,
    limit: int = 100,
    offset: int = 0
):
    """Lista de errores con paginación"""
    repo = PipelineEventsRepository()
    return await repo.get_errors(stage, limit, offset)
```

#### Migración de BD:

```sql
-- migrations/020_pipeline_observability.sql

-- Tabla ya definida en FASE 2, agregar constraints adicionales
ALTER TABLE document_processing_log 
    ADD CONSTRAINT valid_stage CHECK (stage IN (
        'upload', 'validation', 'ocr', 'ocr_validation',
        'segmentation', 'chunking', 'indexing', 'insights', 'indexing_insights'
    )),
    ADD CONSTRAINT valid_status CHECK (status IN (
        'started', 'in_progress', 'completed', 'error', 'skipped'
    ));

-- Índices para queries analíticas
CREATE INDEX IF NOT EXISTS idx_stage_status ON document_processing_log(stage, status);
CREATE INDEX IF NOT EXISTS idx_error_events ON document_processing_log(status) WHERE status = 'error';
CREATE INDEX IF NOT EXISTS idx_document_stage_time ON document_processing_log(document_id, stage, timestamp);

-- Vista materializada para dashboard (opcional, para performance)
CREATE MATERIALIZED VIEW pipeline_statistics AS
SELECT 
    stage,
    status,
    COUNT(*) as event_count,
    AVG(duration_sec) as avg_duration,
    COUNT(DISTINCT document_id) as unique_documents,
    DATE_TRUNC('hour', timestamp) as hour_bucket
FROM document_processing_log
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY stage, status, hour_bucket;

CREATE UNIQUE INDEX ON pipeline_statistics (stage, status, hour_bucket);
```

#### Verificación:
- [ ] PipelineEvent validado con Pydantic
- [ ] Repository persiste eventos en PostgreSQL
- [ ] LangGraph workflow emite eventos correctamente
- [ ] Timeline completo disponible en API
- [ ] Dashboard consume eventos estructurados
- [ ] Filtros y búsqueda funcionan
- [ ] Performance: < 5ms por evento persistido
- [ ] Tests unitarios para validaciones Pydantic

---

### **FASE 1: Validación de Entrada de PDFs** ⚠️ CRÍTICA

**Objetivo**: Asegurar que SOLO PDFs válidos entren al pipeline OCR.

**Cambios Requeridos**:

1. **Parser de Metadata desde Filename**:
   - Extraer fecha, periódico y SHA-8 del nombre del archivo
   - Validar formato: `{sha8}_{DD-MM-YY}-{Newspaper}.pdf`
   - Persistir metadata en `document_status`:
     - `publication_date` (DATE)
     - `newspaper_name` (VARCHAR)
     - `sha8_prefix` (VARCHAR)
   - Fallback: Si no cumple patrón, permitir upload pero marcar `metadata_parsed = false`

2. **Validación Pre-Upload**:
   - Verificar firma `%PDF-` en primeros bytes
   - Rechazar archivos que no sean PDFs reales
   - Validar que no sean symbolic links
   - Verificar tamaño mínimo (> 0 bytes)

3. **Validación Post-Upload**:
   - Ejecutar `file` command sobre archivo
   - Confirmar MIME type `application/pdf`
   - Intentar abrir con PyMuPDF (lectura básica)
   - Verificar consistencia: SHA-8 del filename vs SHA-256 del contenido
   - Log detallado de fallos con causa exacta

4. **Manejo de Errores**:
   - Persistir errores de validación en BD
   - Estado explícito: `invalid_format`, `corrupted_pdf`, `broken_link`, `metadata_mismatch`
   - NO intentar OCR si validación falla
   - Notificar al usuario en UI

**Ubicación**: 
- `backend/utils/filename_parser.py` (NUEVO - parser de metadata)
- `backend/upload_service.py` (validación inicial + parseo)
- `backend/ocr_service_ocrmypdf.py` (validación pre-OCR)
- **Migración BD**: `migrations/019_add_publication_metadata.sql`

**Verificación**:
- [ ] Parser funciona con 100% de archivos reales
- [ ] Metadata extraída y persistida en BD
- [ ] Solo PDFs válidos pasan a OCR
- [ ] Errores de validación persistidos
- [ ] Tasa de error HTTP_400/ValueError cae a ~0%
- [ ] UI muestra causa exacta del rechazo
- [ ] Búsqueda por fecha + periódico funciona

---

### **FASE 2: Dashboard de Observabilidad OCR** 📊 CRÍTICA

**Objetivo**: Permitir al usuario visualizar, debuggear y auditar el proceso OCR desde la UI en cualquier momento.

**Componentes Requeridos**:

#### 2.1. Vista de Documento Individual

**Pantalla**: `Detalle de Documento`

**Información a Mostrar**:
- **Encabezado Humanizado**:
  - Título: `{Periódico} - {Fecha Legible}` (ej: "ABC - 29 enero 2026")
  - Subtítulo: `Identificador: {sha8}` (ej: "Identificador: 03535cda")
  - Nombre archivo completo: `03535cda_29-01-26-ABC.pdf`
- **PDF Original**: Visualizador embebido del PDF (iframe o pdf.js)
- **Metadata Extraída**:
  - Fecha de publicación: `29 enero 2026`
  - Periódico: `ABC`
  - SHA-8 prefix: `03535cda`
  - SHA-256 completo: `03535cda...` (colapsado, expandible)
  - Tamaño: `18.6 MB`
  - Fecha de upload: `2026-01-29 12:39`
- **Timeline de Procesamiento**:
  - Upload timestamp
  - Validación inicial (pass/fail + razón)
  - OCR inicio/fin/duración
  - Segmentación inicio/fin/duración
  - Chunking, Indexing, Insights (cada etapa)
- **Resultado OCR**:
  - Texto extraído (colapsable, primeros 1000 chars visible)
  - Fragmentos detectados (si validación OCR aplicó)
  - Confidence scores (si disponible)
- **Errores**:
  - Tipo de error (HTTP_400, ValueError, CONNECTION_ERROR, TIMEOUT)
  - Mensaje completo de error
  - Stack trace (si disponible)
  - Fecha/hora del error
- **Estado Actual**: Badge visual (pending, processing, completed, error)

**Navegación**: 
- Desde dashboard principal → click en documento → modal o página completa

#### 2.2. Vista de Lista de Errores

**Pantalla**: `Errores OCR` (pestaña en dashboard)

**Tabla de Errores**:
| Columna | Ejemplo |
|---------|---------|
| Fecha | 29 enero 2026 |
| Periódico | ABC |
| SHA-8 | 03535cda |
| Tipo Error | HTTP_400 |
| Mensaje | "Only PDF files are supported" |
| Fase | OCR / Validation / Upload |
| Acción | [Ver PDF] [Ver Detalles] [Reintentar] |

**Búsqueda y Filtros**:
- **Búsqueda libre**: "ABC enero", "04-04-26", "El Pais"
- Por tipo de error (dropdown)
- Por fecha de publicación (date range picker) 
- Por periódico (dropdown multi-select)
- Por fase del pipeline (Upload, OCR, Segmentation, etc.)
- Por estado (error, reintentado, resuelto)

**Bulk Actions**:
- Reintentar selección (si validación ya pasó)
- Marcar como ignorado
- Descargar log completo

#### 2.3. Persistencia de Datos

**Tablas de BD**:

**1. Tabla `document_processing_log`** (NUEVA):
```sql
CREATE TABLE document_processing_log (
    id SERIAL PRIMARY KEY,
    document_id UUID NOT NULL REFERENCES document_status(document_id),
    stage VARCHAR(50) NOT NULL, -- 'upload', 'ocr', 'segmentation', etc.
    status VARCHAR(20) NOT NULL, -- 'started', 'completed', 'error'
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    duration_sec NUMERIC(10, 3),
    error_type VARCHAR(100),
    error_message TEXT,
    error_detail JSONB,
    metadata JSONB, -- info adicional por etapa
    INDEX idx_document_stage (document_id, stage),
    INDEX idx_timestamp (timestamp DESC)
);
```

**2. Tabla `ocr_performance_log`** (YA EXISTE - sin cambios):
- Ya captura errores OCR correctamente
- Incluye: filename, error_type, error_detail, timestamp

**3. Tabla `document_status`** (YA EXISTE - agregar campos):
```sql
ALTER TABLE document_status ADD COLUMN IF NOT EXISTS publication_date DATE;
ALTER TABLE document_status ADD COLUMN IF NOT EXISTS newspaper_name VARCHAR(100);
ALTER TABLE document_status ADD COLUMN IF NOT EXISTS sha8_prefix VARCHAR(8);
ALTER TABLE document_status ADD COLUMN IF NOT EXISTS metadata_parsed BOOLEAN DEFAULT FALSE;
ALTER TABLE document_status ADD COLUMN IF NOT EXISTS upload_error_type VARCHAR(100);
ALTER TABLE document_status ADD COLUMN IF NOT EXISTS upload_error_detail TEXT;
ALTER TABLE document_status ADD COLUMN IF NOT EXISTS validation_passed BOOLEAN DEFAULT TRUE;
ALTER TABLE document_status ADD COLUMN IF NOT EXISTS validation_error_reason TEXT;

-- Índices para búsqueda humanizada
CREATE INDEX IF NOT EXISTS idx_publication_date ON document_status(publication_date DESC);
CREATE INDEX IF NOT EXISTS idx_newspaper ON document_status(newspaper_name);
CREATE INDEX IF NOT EXISTS idx_sha8 ON document_status(sha8_prefix);
CREATE INDEX IF NOT EXISTS idx_date_newspaper ON document_status(publication_date, newspaper_name);
```

**Endpoints API Backend**:

1. `GET /api/documents/{document_id}/processing_log`
   - Retorna todas las entradas de `document_processing_log` para un documento
   - Ordenado por timestamp ASC (cronológico)

2. `GET /api/documents/{document_id}/pdf`
   - Retorna el PDF original desde `local-data/uploads/` o `inbox/processed/`
   - Content-Type: `application/pdf`

3. `GET /api/documents/{document_id}/ocr_text`
   - Retorna texto extraído por OCR (desde `document_status.ocr_text` o similar)

4. `GET /api/errors/ocr`
   - Query params: `?start_date=`, `?end_date=`, `?error_type=`, `?stage=`
   - Retorna lista paginada de errores desde `ocr_performance_log` + `document_processing_log`

5. `POST /api/documents/{document_id}/retry`
   - Reintenta procesamiento desde etapa fallida
   - Valida que documento esté en estado `error`

**Componentes Frontend**:

1. **`DocumentDetailModal.tsx`**:
   - Visualizador PDF (librería: `react-pdf` o `pdfjs-dist`)
   - Timeline vertical con iconos por etapa
   - Texto OCR colapsable
   - Errores en badge rojo con tooltip

2. **`ErrorsTable.tsx`**:
   - Tabla con react-table o shadcn/ui Table
   - Filtros interactivos (DatePicker, Select)
   - Bulk actions con checkboxes

3. **`DocumentTimeline.tsx`**:
   - Componente reutilizable para mostrar progreso
   - Estados: pending (gris), processing (azul), completed (verde), error (rojo)

**Verificación**:
- [ ] Usuario puede ver PDF + timeline desde UI
- [ ] Errores persisten en BD con detalle completo
- [ ] Filtros de errores funcionales
- [ ] Reintentar documento desde UI funciona
- [ ] Timeline muestra todas las etapas con timestamps

---

### **FASE 3: Sincronización Modelo LLM Segmentation**

**Decisión Requerida del Usuario**:
- ¿Usar `llama3.1:8b` (más preciso, más lento)?
- ¿Usar `llama3.2:1b` (más rápido, menos preciso)?
- ¿Usar otro modelo (mistral, gemma, etc.)?

**Cambios**:
1. Actualizar `news_segmentation_agent.py` línea 53
2. Actualizar `CONSOLIDATED_STATUS.md` § REQ-024, REQ-025
3. Actualizar `PLAN_AND_NEXT_STEP.md` § Modelos LLM
4. Actualizar `.env.example` con variable `SEGMENTATION_LLM_MODEL`

**Verificación**:
- [ ] Modelo correcto en código + docs
- [ ] Variable de entorno documentada
- [ ] Tests de segmentación con nuevo modelo

---

### **FASE 4: Limpieza de Datos Corruptos**

**Objetivo**: Identificar y limpiar archivos no válidos en `local-data/uploads/`.

**Cambios**:
1. Script de auditoría: `scripts/audit_pdfs.py`
   - Escanea `local-data/uploads/`
   - Ejecuta `file` command en cada .pdf
   - Identifica broken links, archivos no-PDF
   - Genera reporte CSV con: filename, tipo, tamaño, validez

2. Script de limpieza: `scripts/cleanup_invalid_pdfs.py`
   - Lee reporte de auditoría
   - Mueve archivos inválidos a `local-data/quarantine/`
   - Actualiza `document_status` con estado `quarantined`
   - Log de acciones en `cleanup_log.txt`

3. UI: Botón "Ejecutar Auditoría de PDFs" en dashboard
   - Ejecuta script de auditoría
   - Muestra reporte en modal
   - Opción "Limpiar Inválidos" con confirmación

**Verificación**:
- [ ] Reporte de auditoría generado
- [ ] Archivos inválidos en cuarentena
- [ ] BD actualizada con estado correcto
- [ ] UI muestra resultados de auditoría

---

### **FASE 5: Implementación REQ-025 (Seguimiento Granular)**

**Objetivo**: Implementar seguimiento detallado de segmentos detectados.

**Referencia**: Ya documentado en PLAN_AND_NEXT_STEP.md § REQ-025

**Cambios**:
- Tracking de cada artículo detectado (título, posición, confidence)
- Relación 1-a-muchos: `document_status` → `news_items`
- Métricas agregadas: artículos por documento, confidence promedio
- UI: Lista de artículos detectados en detalle de documento

**Verificación**:
- [ ] Tabla `news_items` poblada
- [ ] Métricas agregadas en dashboard
- [ ] UI muestra artículos individuales con confidence

---

### **FASE 6: Testing y Validación End-to-End**

**Objetivo**: Validar que pipeline completo funcione con archivos reales.

**Casos de Prueba**:
1. Upload PDF válido → OCR → Segmentation → Indexing → Insights
2. Upload archivo no-PDF → Rechazo en validación → Error en UI
3. Upload PDF corrupto → Rechazo en validación → Error en UI
4. Reintentar documento con error → Funciona correctamente

**Métricas Objetivo**:
- Tasa de éxito OCR: **> 95%** (para PDFs válidos)
- Tiempo promedio OCR: **< 5 min** (para PDFs < 30 MB)
- Segmentación confidence: **> 0.7** promedio
- Cobertura de errores en UI: **100%**

**Verificación**:
- [ ] 10+ PDFs reales procesados sin errores
- [ ] Errores visibles en UI con detalles completos
- [ ] Reintentos funcionales
- [ ] Métricas objetivo alcanzadas

---

### **FASE 7: Migración Legacy → Orchestrator (Validación Progresiva)** 🔄 NUEVA

**Objetivo**: Migrar todos los documentos existentes (351) del sistema event-driven al nuevo Orchestrator Agent, validando resultados y eliminando legacy progresivamente.

**Ver documento completo**: `REQ-027_ORCHESTRATOR_MIGRATION.md`

#### Componentes Clave:

**1. LegacyDataAdapter Node**:
- Lee datos legacy de cada etapa
- Compara con resultado nuevo del orchestrator
- Valida: similarity, consistency, conflicts
- Mezcla legacy + nuevo con estrategia configurable
- Marca etapa como "migrada"

**2. MigrationTracker Node**:
- Rastrea progreso global: X% de documentos migrados
- Calcula por etapa: Upload 100%, OCR 34%, Segmentation 24%, etc.
- Detecta cuando 100% migrado → flag "cleanup_ready"
- Emite eventos para dashboard

**3. Estrategia de Validación**:

| Etapa | Validación | Merge Strategy |
|-------|-----------|---------------|
| Upload | filename, size | Nuevo (metadata mejorada) |
| Validation | pdf_valid | Nuevo (parser mejorado) |
| OCR | text similarity > 95% | Nuevo (OCRmyPDF > Tika) |
| Segmentation | article count, confidence | Nuevo (LLM mejorado) |
| Chunking | chunk count | Nuevo (chunking inteligente) |
| Indexing | vector count | Nuevo (re-index) |
| Insights | structure | Nuevo (LangGraph) |

**4. Dashboard de Migración**:
```
Progreso Global: [████████░░░░░░░░] 34.2%

Por Etapa:
Upload:       [████████████████████] 100.0% (351/351)
OCR:          [███████░░░░░░░░░░░░░]  34.2% (120/351)
Segmentation: [█████░░░░░░░░░░░░░░░]  24.2% ( 85/351)
...

Conflictos: 5 (requieren revisión manual)
Estimación: 15 abril 2026
```

**5. Cleanup Automático**:
- Cuando 100% migrado → Validar seguridad
- Backup de datos legacy
- Deprecar schedulers event-driven
- Archivar tablas legacy (30 días)
- Eliminar código legacy

**Timeline**:
- Semana 1-2: Preparación BD + LegacyDataRepository
- Semana 3-4: Orchestrator + LegacyAdapterNode
- Semana 5-6: MigrationTracker + Dashboard
- Semana 7-10: Procesamiento masivo (351 docs)
- Semana 11: Cleanup
- Semana 12+: Estabilización

**Verificación**:
- [ ] 100% documentos migrados
- [ ] 0 conflictos sin resolver
- [ ] Similarity > 95% en todas las etapas
- [ ] Dashboard muestra "Migration Complete"
- [ ] Legacy eliminado

---

### **FASE 8: Testing y Validación End-to-End (Post-Migración)**

---

## 📋 CHECKLIST DE AUDITORÍA

### Antes de Implementar:
- [x] He identificado el problema raíz (archivos no-PDF)
- [x] He verificado que OCRmyPDF funciona correctamente
- [x] He analizado la BD para entender errores
- [x] He revisado documentación vs. código
- [x] He propuesto estrategia completa

### Para Cada Fase:
- [ ] Plan detallado con archivos + líneas
- [ ] Decisiones críticas identificadas
- [ ] Impacto en funcionalidad existente evaluado
- [ ] Verificación post-cambio definida
- [ ] Documentación actualizada

### Al Finalizar:
- [ ] Registrar en CONSOLIDATED_STATUS.md
- [ ] Registrar decisiones en SESSION_LOG.md
- [ ] Actualizar PLAN_AND_NEXT_STEP.md
- [ ] Marcar REQ-025 como completado
- [ ] Crear nueva versión (v5.2.0?)

---

## 🎯 PRIORIDADES

| Fase | Criticidad | Impacto | Esfuerzo | Orden |
|------|-----------|---------|----------|-------|
| FASE 0 | ⚠️ CRÍTICA | MUY ALTO | Alto | **1º** |
| FASE 1 | ⚠️ CRÍTICA | Alto | Medio | **2º** |
| FASE 2 | ⚠️ CRÍTICA | Alto | Alto | **3º** |
| FASE 3 | Media | Medio | Bajo | 4º |
| FASE 4 | Media | Medio | Bajo | 5º |
| FASE 5 | Baja | Medio | Medio | 6º |
| FASE 6 | Alta | Alto | Medio | 7º |
| **FASE 7** | **⚠️ CRÍTICA** | **MUY ALTO** | **MUY ALTO** | **8º** |
| FASE 8 | Alta | Alto | Medio | 9º |

**Razón de Orden**:
1. **FASE 0 primero**: Arquitectura base con memoria + validación Pydantic que usarán todas las demás fases
2. Sin FASE 1, archivos inválidos seguirán entrando → errores persistentes
3. Sin FASE 2, imposible debuggear o auditar problemas → usuario ciego
4. FASE 3-6 mejoran calidad pero no bloquean funcionamiento
5. **FASE 7 es el refactor completo**: Migración a Orchestrator Agent con validación legacy
6. FASE 8 valida que todo funcione correctamente post-migración

**Dependencias**:
- FASE 2 **depende de** FASE 0 (consume eventos del agente)
- FASE 1 **emite eventos a** FASE 0 (observability)
- FASE 3-6 **emiten eventos a** FASE 0 (observability)
- **FASE 7 incluye** FASE 0-6 dentro del Orchestrator Agent (refactor completo)
- FASE 8 **valida** FASE 7 (testing post-migración)

---

## 🚨 DECISIONES PENDIENTES DEL USUARIO

1. **Modelo LLM para Segmentation** (FASE 3):
   - ¿`llama3.1:8b` o `llama3.2:1b` o otro?
   - Trade-off: precisión vs. velocidad

2. **Estrategia de Limpieza** (FASE 4):
   - ¿Mover a cuarentena o eliminar archivos inválidos?
   - ¿Mantener histórico de errores o limpiar logs antiguos?

3. **Prioridad de UI** (FASE 2):
   - ¿Implementar dashboard completo ahora o MVP rápido?
   - ¿Qué vistas son más críticas primero?

---

## 📚 REFERENCIAS

**Archivos Clave**:
- `docs/ai-lcd/CONSOLIDATED_STATUS.md` § REQ-012, REQ-024, Fix #145
- `docs/ai-lcd/PLAN_AND_NEXT_STEP.md` § REQ-025
- `app/backend/ocr_service_ocrmypdf.py` líneas 100-250
- `app/backend/news_segmentation_agent.py` línea 53
- `app/backend/upload_service.py` (validación pendiente)

**Base de Datos**:
- `ocr_performance_log`: 5,714 registros
- `document_status`: Estado actual de documentos
- `news_items`: 0 registros (pipeline pausado)

**Errores Principales**:
- HTTP_400 "Only PDF files are supported": 49.5%
- ValueError "Only PDF files are supported": 47.2%

**Archivos Afectados**:
- `local-data/uploads/`: 350+ symbolic links rotos
- `local-data/inbox/processed/`: 351 PDFs válidos (todos procesados ✅)

---

**Fecha**: 2026-04-10  
**Usuario**: diego.a  
**Conclusión**: La calidad de OCR es excelente (99.7%) cuando recibe PDFs válidos. El problema raíz está en la validación de entrada. La solución requiere implementar validación robusta + dashboard de observabilidad para auditabilidad completa.
