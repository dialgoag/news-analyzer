# Guía de Migración: Código Actual → Hexagonal + LangChain

> **Propósito**: Mapeo detallado de cómo migrar el código monolítico actual a la nueva arquitectura.
>
> **Última actualización**: 2026-03-31  
> **REQ-021**: Refactor Backend SOLID + Hexagonal

---

## 📋 Mapeo: Dónde va cada pieza

### app.py (6,718 líneas) → Múltiples archivos

| Código actual (app.py) | Nueva ubicación | Justificación |
|------------------------|-----------------|---------------|
| **Líneas 71-93**: `parse_news_date_from_filename()` | `shared/utils/text_parsers.py` | Utilidad pura, sin I/O |
| **Líneas 87-92**: `_normalize_text_for_hash()` | `core/domain/services/text_normalization.py` | Domain service (regla de negocio) |
| **Líneas 95-185**: `segment_news_items_from_text()` | `core/domain/services/document_segmentation.py` | Domain service (core business logic) |
| **Líneas 498-890**: `master_pipeline_scheduler()` | `schedulers/master_pipeline_scheduler.py` | Scheduler separado |
| **Líneas 1496-1593**: `_ocr_worker_task()` | `workers/ocr_worker.py` | Worker separado |
| **Líneas 2430-2680**: `_insights_worker_task()` | `workers/insights_worker.py` | **Worker que USA LangGraph** |
| **Líneas 2887-2957**: `_handle_insights_task()` | **ELIMINAR** - Reemplazado por InsightsChain | LangChain reemplaza lógica |
| **Líneas 3266-3500**: Dashboard endpoints | `adapters/driving/api/v1/routers/dashboard.py` | REST endpoints separados |
| **Líneas 3800-4100**: Documents endpoints | `adapters/driving/api/v1/routers/documents.py` | REST endpoints separados |
| **Líneas 4723-4910**: `get_dashboard_summary()` queries | `core/application/queries/get_dashboard_summary.py` | Query handler (CQRS) |

---

## 🔄 Migración del Código de Insights

### ANTES: Monolítico en app.py

```python
# app.py línea ~2887
async def _handle_insights_task(task_data: dict, worker_id: str):
    news_item_id = task_data.get('news_item_id')
    document_id = task_data.get('document_id')
    filename = task_data.get('filename', '')
    title = task_data.get('title', '')
    
    # Check dedup (hardcoded logic)
    news_item = news_item_store.get_by_id(news_item_id)
    text_hash = hashlib.sha256(news_item['text'].encode()).hexdigest()
    existing = news_item_insights_store.get_done_by_text_hash(text_hash)
    if existing:
        # Reuse
        news_item_insights_store.copy_from_hash(news_item_id, text_hash)
        return
    
    # Retrieve chunks from Qdrant (hardcoded)
    chunks = qdrant_connector.search_by_document_id(document_id, limit=50)
    if not chunks:
        raise ValueError("No chunks found")
    
    # Generate insight (hardcoded prompt, solo OpenAI)
    prompt = f"""Analyze this news:
    Title: {title}
    Text: {' '.join([c['text'] for c in chunks])}
    """
    
    try:
        response = rag_pipeline.generate_insights_with_fallback(prompt, "insights")
        insight_text = response
    except RateLimitError:
        # Re-encolar manualmente
        news_item_insights_store.set_status(news_item_id, "pending")
        return
    
    # Save (sin estructura)
    news_item_insights_store.update(
        news_item_id=news_item_id,
        summary=insight_text,
        analysis=None,  # No hay análisis separado
        llm_source="openai"  # Hardcoded
    )
```

**Problemas**:
- ❌ Mezclado: dedup, retrieval, generation, storage
- ❌ Sin estructura en output
- ❌ Prompt hardcoded
- ❌ Solo OpenAI
- ❌ Retry manual
- ❌ No testeable

### DESPUÉS: Hexagonal + LangChain

```python
# workers/insights_worker.py
from core.application.commands.generate_insight import GenerateInsightCommand
from core.application.events.event_bus import get_event_bus
from adapters.driven.memory.insight_memory import InsightMemory

async def process_insight_task(task_data: dict):
    """
    Process insight generation task.
    
    This is just orchestration - all logic is in commands/chains.
    """
    # 1. Create command (Application layer)
    command = GenerateInsightCommand(
        llm_chain=insights_chain,        # Injected dependency
        memory=insight_memory,            # Injected dependency
        repository=insights_repository,   # Injected dependency
        event_bus=get_event_bus()        # Injected dependency
    )
    
    # 2. Execute command (all logic inside)
    result = await command.execute(
        news_item_id=task_data['news_item_id'],
        document_id=task_data['document_id'],
        context=task_data['context'],
        title=task_data['title']
    )
    
    # 3. Done - command handles everything
    return result
```

```python
# core/application/commands/generate_insight.py
class GenerateInsightCommand:
    """
    Command: Generate insight for a news item.
    
    Responsibilities:
    - Check cache (dedup)
    - Retrieve chunks
    - Generate insight (via chain)
    - Parse structured data
    - Store in database
    - Update cache
    - Emit event
    """
    
    def __init__(
        self,
        llm_chain: InsightsChain,              # Port
        memory: InsightMemory,                  # Port
        repository: InsightsRepository,         # Port
        vector_store: VectorStorePort,          # Port
        event_bus: EventBus
    ):
        # Dependency Injection (Hexagonal)
        self.llm_chain = llm_chain
        self.memory = memory
        self.repository = repository
        self.vector_store = vector_store
        self.event_bus = event_bus
    
    async def execute(
        self,
        news_item_id: str,
        document_id: str,
        context: str,
        title: str
    ) -> InsightResult:
        """Execute command."""
        
        # 1. Check cache (LangMem)
        text_hash = self._compute_hash(context)
        cached = await self.memory.get(text_hash)
        if cached:
            logger.info("✅ Cache hit, reusing insight")
            await self.repository.save_cached(news_item_id, cached)
            return cached
        
        # 2. Retrieve chunks (via port)
        chunks = await self.vector_store.search_by_document(
            document_id=document_id,
            limit=50
        )
        
        if not chunks:
            raise ValueError("No chunks found for document")
        
        # 3. Generate insight (LangChain)
        # Combines chunks into context
        full_context = "\n\n".join([chunk.text for chunk in chunks])
        
        result = await self.llm_chain.run_full(
            context=full_context,
            title=title
        )
        
        # 4. Parse structured data (Domain Service)
        from core.domain.services.insight_parser import parse_insight
        structured = parse_insight(result.full_text)
        
        # 5. Save (via repository port)
        await self.repository.save(
            news_item_id=news_item_id,
            insight_result=result,
            structured_data=structured
        )
        
        # 6. Update cache (LangMem)
        await self.memory.store(text_hash, result)
        
        # 7. Emit event (Event-Driven)
        event = InsightGenerated(
            news_item_id=news_item_id,
            document_id=document_id,
            insight_text=result.full_text,
            llm_provider=result.provider_used,
            llm_model=result.model_used,
            processing_time_seconds=0.0,  # TODO: track
            tokens_used=result.extraction_tokens + result.analysis_tokens
        )
        await self.event_bus.publish(event)
        
        return result
    
    def _compute_hash(self, text: str) -> str:
        """Compute text hash for dedup."""
        from core.domain.services.text_normalization import normalize_text
        normalized = normalize_text(text)
        return hashlib.sha256(normalized.encode()).hexdigest()
```

**Ventajas**:
- ✅ **~100 líneas** por archivo (vs 500 en monolito)
- ✅ **Testeable**: Mock cada dependency
- ✅ **Single Responsibility**: Cada clase hace UNA cosa
- ✅ **Dependency Injection**: Fácil cambiar implementaciones
- ✅ **Observabilidad**: Eventos + logs estructurados

---

## 🧪 Testing: Antes vs Después

### ANTES: Imposible testear sin I/O

```python
# No se puede testear _handle_insights_task sin:
# - PostgreSQL running
# - Qdrant running
# - OpenAI API key
# - Network access

# Test imposible:
def test_insights_generation():
    result = await _handle_insights_task(task_data, "worker_1")
    # ❌ Requires full stack running
```

### DESPUÉS: Testing con mocks

```python
# Test command con mocks (sin I/O)
def test_generate_insight_command():
    # Arrange: Mock dependencies
    mock_chain = MockInsightsChain()
    mock_memory = MockInsightMemory()
    mock_repo = MockInsightsRepository()
    mock_vector = MockVectorStore()
    mock_bus = MockEventBus()
    
    command = GenerateInsightCommand(
        llm_chain=mock_chain,
        memory=mock_memory,
        repository=mock_repo,
        vector_store=mock_vector,
        event_bus=mock_bus
    )
    
    # Act
    result = await command.execute(
        news_item_id="test_123",
        document_id="doc_456",
        context="Test news text",
        title="Test title"
    )
    
    # Assert
    assert result.provider_used == "mock"
    assert mock_repo.save_called
    assert mock_bus.events_published == 1
    # ✅ No I/O required!
```

```python
# Test chain con mock provider
def test_insights_chain():
    # Mock provider
    mock_provider = MockLLMProvider(
        responses={
            "extraction": "## Metadata\nDate: 2026-03-31\n...",
            "analysis": "## Significance\nThis is important because..."
        }
    )
    
    chain = InsightsChain(providers=[mock_provider])
    
    result = await chain.run_full(
        context="News text",
        title="Title"
    )
    
    assert "Metadata" in result.extracted_data
    assert "Significance" in result.analysis
    assert result.provider_used == "mock"
    # ✅ Testeable sin OpenAI!
```

---

## 🎯 Checklist de Migración

### Pre-requisitos
- [x] Documentación arquitectura hexagonal
- [x] Documentación LangChain integration
- [x] Estructura de carpetas creada
- [x] Dependencies agregadas a requirements.txt
- [x] Commit + push del estado actual

### FASE 1: Estructura Base
- [x] Crear carpetas hexagonales
- [x] `config.py` centralizado
- [x] Domain events base
- [x] Event bus in-memory
- [ ] Mover utils a `shared/utils/`

### FASE 2: LangChain Chains
- [x] LLMPort interface
- [x] OpenAIProvider
- [x] OllamaProvider
- [x] ExtractionChain
- [x] AnalysisChain
- [x] InsightsChain (orchestrator)
- [ ] PerplexityProvider

### FASE 3: LangGraph Workflow
- [ ] InsightState dataclass
- [ ] InsightsGraph nodes
- [ ] Validation logic
- [ ] Conditional edges
- [ ] Integration with chains

### FASE 4: LangMem Cache
- [ ] InsightMemory class
- [ ] Cache backend (PostgreSQL)
- [ ] TTL management
- [ ] Integration with commands

### FASE 5: Application Layer
- [ ] GenerateInsightCommand
- [ ] Queries para dashboard
- [ ] Event handlers
- [ ] Recovery service

### FASE 6: Adaptar app.py
- [ ] Importar nuevo código
- [ ] Reemplazar `_handle_insights_task`
- [ ] Actualizar workers para usar commands
- [ ] Verificar funcionalidad

### FASE 7: Testing
- [ ] Unit tests para chains
- [ ] Integration tests para workflow
- [ ] End-to-end test
- [ ] Performance benchmarks

---

## 🚀 Ejecución: Orden de Implementación

### Iteración 1: Chains básicas (AHORA)
1. ✅ ExtractionChain
2. ✅ AnalysisChain
3. ✅ InsightsChain
4. ⏳ Integrar en worker (sin romper código actual)

### Iteración 2: LangGraph
1. State machine
2. Validation nodes
3. Retry logic
4. Integration tests

### Iteración 3: LangMem
1. Cache layer
2. Memory management
3. Performance tests

### Iteración 4: Refactor resto
1. Dashboard queries
2. Document commands
3. Auth refactor

---

## ⚠️ Consideraciones Importantes

### 1. Backward Compatibility

Durante migración, AMBOS sistemas coexisten:

```python
# app.py (temporal)
USE_LANGCHAIN = os.getenv("USE_LANGCHAIN", "false") == "true"

if USE_LANGCHAIN:
    # Nuevo código
    from workers.insights_worker import process_insight_task
    result = await process_insight_task(task_data)
else:
    # Código legacy
    result = await _handle_insights_task(task_data, worker_id)
```

### 2. No romper Pipeline

El master scheduler SIGUE funcionando durante migración:

```python
# schedulers/master_pipeline_scheduler.py
# Mantiene PASOS 0-6 exactamente iguales
# Solo cambia cómo se ejecutan los workers
```

### 3. Database Schema NO cambia (aún)

```sql
-- news_item_insights table se mantiene igual
-- Solo cambiamos cómo se GENERA el contenido
-- Future: agregar tablas para structured data
```

### 4. Rollback Plan

Si algo falla, revertir es fácil:

```bash
git revert HEAD  # Revertir último commit
docker compose build backend
docker compose up -d backend
# Sistema vuelve al código legacy
```

---

## 📊 Ejemplo Completo: Migrar _insights_worker_task

### PASO A: Código actual (app.py)

```python
# app.py línea 2430 (ANTES)
async def _insights_worker_task(news_item_id: str, document_id: str, filename: str, title: str, worker_id: str):
    try:
        # Update worker status
        worker_task_data = db.get_worker_task(worker_id, document_id, TaskType.INSIGHTS)
        db.update_worker_task(worker_id, document_id, TaskType.INSIGHTS, WorkerStatus.STARTED)
        
        # Check dedup by text_hash
        news_item = news_item_store.get_by_id(news_item_id)
        text_normalized = _normalize_text_for_hash(news_item['text'])
        text_hash = hashlib.sha256(text_normalized.encode()).hexdigest()
        
        existing = news_item_insights_store.get_done_by_text_hash(text_hash)
        if existing:
            news_item_insights_store.copy_from_hash(news_item_id, text_hash)
            db.update_worker_task(worker_id, document_id, TaskType.INSIGHTS, WorkerStatus.COMPLETED)
            return
        
        # Retrieve chunks
        all_chunks = qdrant_connector.scroll_by_filter(
            document_id=document_id,
            content_type='chunk',
            limit=50
        )
        
        if not all_chunks:
            raise ValueError("No chunks found")
        
        # Build context
        context = "\n\n".join([chunk['text'] for chunk in all_chunks[:50]])
        
        # Generate insight (hardcoded)
        insight_text = rag_pipeline.generate_insights_with_fallback(context, "insights")
        
        # Save
        news_item_insights_store.update(
            news_item_id=news_item_id,
            summary=insight_text[:500],
            analysis=insight_text,
            llm_source="openai"  # Hardcoded
        )
        
        # Index in Qdrant
        if rag_pipeline:
            await _index_insight_in_qdrant(news_item_id, document_id, filename, insight_text, title)
        
        # Complete
        db.update_worker_task(worker_id, document_id, TaskType.INSIGHTS, WorkerStatus.COMPLETED)
        
    except Exception as e:
        logger.error(f"Insights task failed: {e}", exc_info=True)
        db.update_worker_task(worker_id, document_id, TaskType.INSIGHTS, WorkerStatus.ERROR, str(e))
        raise
```

### PASO B: Código migrado (Hexagonal + LangChain)

```python
# workers/insights_worker.py (DESPUÉS)
from core.application.commands.generate_insight import GenerateInsightCommand
from core.application.events.event_bus import get_event_bus
from core.domain.events.insights_events import InsightGenerated
from adapters.driven.llm.chains.insights_chain import InsightsChain
from adapters.driven.memory.insight_memory import InsightMemory
from shared.exceptions import RateLimitError

# Dependency injection setup (app startup)
insights_chain = InsightsChain()  # Auto-configures providers
insight_memory = InsightMemory()
insights_repository = InsightsRepositoryImpl()
vector_store = QdrantAdapter()
event_bus = get_event_bus()

async def process_insight_task(task_data: dict, worker_id: str):
    """
    Process insight generation task using Hexagonal + LangChain.
    
    Clean worker code - all logic delegated to command.
    """
    try:
        # Update worker status (via repository)
        await worker_repository.update_status(
            worker_id=worker_id,
            document_id=task_data['document_id'],
            task_type=TaskType.INSIGHTS,
            status=WorkerStatus.STARTED
        )
        
        # Create and execute command
        command = GenerateInsightCommand(
            llm_chain=insights_chain,
            memory=insight_memory,
            repository=insights_repository,
            vector_store=vector_store,
            event_bus=event_bus
        )
        
        result = await command.execute(
            news_item_id=task_data['news_item_id'],
            document_id=task_data['document_id'],
            context=task_data['context'],
            title=task_data['title']
        )
        
        # Complete worker
        await worker_repository.update_status(
            worker_id=worker_id,
            document_id=task_data['document_id'],
            task_type=TaskType.INSIGHTS,
            status=WorkerStatus.COMPLETED
        )
        
        logger.info(
            f"✅ Insight generated: provider={result.provider_used}, "
            f"tokens={result.extraction_tokens + result.analysis_tokens}"
        )
        
        return result
        
    except RateLimitError as e:
        # Rate limit - re-enqueue (don't mark as error)
        logger.warning(f"⚠️ Rate limit, re-enqueueing: {e}")
        await insights_repository.set_status(
            news_item_id=task_data['news_item_id'],
            status="pending"
        )
        await worker_repository.delete_worker_task(worker_id)
        
    except Exception as e:
        logger.error(f"❌ Insight generation failed: {e}", exc_info=True)
        await worker_repository.update_status(
            worker_id=worker_id,
            document_id=task_data['document_id'],
            task_type=TaskType.INSIGHTS,
            status=WorkerStatus.ERROR,
            error_message=str(e)[:200]
        )
        raise
```

**Diferencias clave**:
- ✅ **50 líneas** vs 250 líneas (80% reducción)
- ✅ **Dependency injection** (testeable)
- ✅ **Single Responsibility** (worker solo orquesta)
- ✅ **Lógica en command** (reutilizable)
- ✅ **Chains manejan LLM** (providers, fallback, retry)
- ✅ **Events emitidos** (observabilidad)

---

## 🎯 Próximos Archivos a Crear

1. **core/application/commands/generate_insight.py** (comando principal)
2. **adapters/driven/llm/graphs/insights_graph.py** (LangGraph workflow)
3. **adapters/driven/memory/insight_memory.py** (LangMem cache)
4. **core/ports/repositories/insights_repository.py** (port)
5. **adapters/driven/persistence/postgres/insights_repository_impl.py** (implementación)

---

**Estado**: En progreso  
**Próximo paso**: Implementar LangGraph workflow con validación
