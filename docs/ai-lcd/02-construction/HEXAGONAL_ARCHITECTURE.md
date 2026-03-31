# Arquitectura Hexagonal + DDD - NewsAnalyzer Backend

> **Propósito**: Documentar la arquitectura hexagonal adoptada y su adaptación con Domain-Driven Design.
>
> **Última actualización**: 2026-03-31  
> **Versión**: 4.0.0 (Refactor SOLID + Hexagonal)

---

## 🎯 ¿Qué es Arquitectura Hexagonal?

La **Arquitectura Hexagonal** (también llamada **Ports & Adapters**) fue propuesta por Alistair Cockburn en 2005. Su objetivo es **aislar la lógica de negocio** de los detalles técnicos (bases de datos, APIs externas, frameworks).

### Principios fundamentales:

1. **La lógica de negocio es el centro** - No depende de nada externo
2. **Puertos** - Interfaces que definen QUÉ necesita el negocio (abstracciones)
3. **Adaptadores** - Implementaciones concretas de los puertos (PostgreSQL, FastAPI, OpenAI, etc.)
4. **Dirección de dependencias** - Todo apunta hacia adentro (hacia el core)

### Diagrama conceptual:

```
┌─────────────────────────────────────────────────────────────┐
│                    🟧 DRIVING ADAPTERS                       │
│              (Interfaces - Entrada al sistema)              │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│   │ REST API │  │   CLI    │  │ Webhooks │                │
│   └────┬─────┘  └────┬─────┘  └────┬─────┘                │
└────────┼─────────────┼─────────────┼────────────────────────┘
         │             │             │
         ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                   🟦 CORE (Domain)                          │
│              Lógica de negocio pura                         │
│   ┌─────────────────────────────────────────────┐          │
│   │  Entities • Value Objects • Domain Events   │          │
│   │  Domain Services • Business Rules           │          │
│   └─────────────────────────────────────────────┘          │
│                                                              │
│   🔌 Ports (Interfaces):                                    │
│   • DocumentRepository (port)                               │
│   • OCRService (port)                                       │
│   • LLMProvider (port)                                      │
│   • VectorStore (port)                                      │
└─────────────────────────────────────────────────────────────┘
         │             │             │
         ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                   🟨 DRIVEN ADAPTERS                         │
│            (Adaptadores - Salida del sistema)               │
│   ┌──────────┐  ┌──────────┐  ┌──────────┐                │
│   │PostgreSQL│  │  Qdrant  │  │  OpenAI  │                │
│   │ Adapter  │  │ Adapter  │  │ Adapter  │                │
│   └──────────┘  └──────────┘  └──────────┘                │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧩 ¿Por qué adaptamos DDD?

**Domain-Driven Design (DDD)** complementa la arquitectura hexagonal proporcionando **patrones tácticos** para organizar el core (dominio):

| Patrón DDD | Propósito | Ejemplo en NewsAnalyzer |
|------------|-----------|-------------------------|
| **Entity** | Objeto con identidad única | `Document`, `NewsItem`, `Worker` |
| **Value Object** | Objeto inmutable sin identidad | `DocumentId`, `TextHash`, `PipelineStatus` |
| **Aggregate** | Cluster de entidades con raíz | `Document` (raíz) + `NewsItems` (hijos) |
| **Domain Event** | Algo que ocurrió en el negocio | `DocumentUploaded`, `OCRCompleted`, `InsightGenerated` |
| **Domain Service** | Lógica que no encaja en entidades | `DocumentSegmentation`, `TextDeduplication` |
| **Repository** | Persistencia (port) | `DocumentRepository`, `InsightsRepository` |

### ¿Por qué esta combinación?

- **Hexagonal** → estructura arquitectónica (capas, dependencias)
- **DDD** → organización del dominio (entidades, eventos, servicios)
- **Event-Driven** → comunicación asíncrona entre capas

---

## 📂 Estructura de Carpetas (Hexagonal + DDD)

```
backend/
├── app.py                          # <200 líneas: FastAPI app + routers
├── config.py                       # Settings (Pydantic)
│
├── core/                           # 🟦 NÚCLEO (Domain)
│   ├── domain/                     # Lógica de negocio pura
│   │   ├── entities/               # Entidades con identidad
│   │   │   ├── document.py
│   │   │   ├── news_item.py
│   │   │   └── worker.py
│   │   ├── value_objects/          # Objetos inmutables
│   │   │   ├── document_id.py
│   │   │   ├── text_hash.py
│   │   │   └── pipeline_status.py
│   │   ├── events/                 # Domain Events
│   │   │   ├── base.py
│   │   │   ├── document_events.py
│   │   │   └── insights_events.py
│   │   └── services/               # Domain Services
│   │       ├── document_segmentation.py
│   │       ├── text_normalization.py
│   │       └── deduplication.py
│   │
│   ├── application/                # Orquestación (Use Cases)
│   │   ├── commands/               # Comandos (CQRS)
│   │   │   ├── upload_document.py
│   │   │   ├── process_ocr.py
│   │   │   └── generate_insight.py
│   │   ├── queries/                # Consultas (CQRS)
│   │   │   ├── get_dashboard_summary.py
│   │   │   └── list_documents.py
│   │   ├── services/               # Application Services
│   │   │   ├── pipeline_orchestrator.py
│   │   │   ├── worker_dispatcher.py
│   │   │   └── recovery_service.py
│   │   └── events/
│   │       └── event_bus.py        # Event bus in-memory
│   │
│   └── ports/                      # 🔌 PORTS (Interfaces)
│       ├── repositories/           # Repository ports
│       │   ├── document_repository.py
│       │   ├── insights_repository.py
│       │   └── worker_repository.py
│       ├── ocr_port.py             # OCR service port
│       ├── llm_port.py             # LLM provider port
│       ├── embeddings_port.py      # Embeddings service port
│       └── vector_store_port.py    # Vector DB port
│
├── adapters/                       # 🟨 ADAPTADORES (I/O externo)
│   ├── driving/                    # 🟧 Driving adapters (entrada)
│   │   ├── api/
│   │   │   └── v1/
│   │   │       ├── routers/
│   │   │       │   ├── documents.py
│   │   │       │   ├── insights.py
│   │   │       │   ├── dashboard.py
│   │   │       │   ├── workers.py
│   │   │       │   └── auth.py
│   │   │       ├── schemas/        # Pydantic request/response
│   │   │       └── dependencies.py
│   │   └── middleware/
│   │       ├── auth_middleware.py
│   │       └── error_handler.py
│   │
│   └── driven/                     # 🟨 Driven adapters (salida)
│       ├── persistence/            # Repositorios (implementaciones)
│       │   ├── postgres/
│       │   │   ├── base.py
│       │   │   ├── document_repository_impl.py
│       │   │   ├── insights_repository_impl.py
│       │   │   └── worker_repository_impl.py
│       │   └── migrations/
│       ├── ocr/                    # OCR adapters
│       │   ├── ocrmypdf_adapter.py
│       │   └── tika_adapter.py
│       ├── embeddings/             # Embedding adapters
│       │   ├── huggingface_adapter.py
│       │   └── perplexity_adapter.py
│       ├── vector_store/           # Vector DB adapters
│       │   └── qdrant_adapter.py
│       ├── llm/                    # 🔥 LLM adapters (LangChain)
│       │   ├── langchain_adapter.py
│       │   ├── providers/
│       │   │   ├── openai_provider.py
│       │   │   ├── perplexity_provider.py
│       │   │   └── ollama_provider.py
│       │   └── chains/
│       │       ├── insights_chain.py
│       │       └── rag_chain.py
│       ├── graphs/                 # 🔥 LangGraph workflows
│       │   └── insights_graph.py
│       ├── memory/                 # 🔥 LangMem
│       │   └── conversation_memory.py
│       └── cache/
│           └── memory_cache.py
│
├── workers/                        # 🟪 Workers (background)
│   ├── base.py
│   ├── ocr_worker.py
│   ├── chunking_worker.py
│   ├── indexing_worker.py
│   └── insights_worker.py          # 🔥 Usa LangGraph
│
├── schedulers/                     # ⏰ Schedulers
│   ├── master_pipeline_scheduler.py
│   └── backup_scheduler.py
│
└── shared/                         # 🔧 Compartido
    ├── logging.py
    ├── exceptions.py
    └── utils/
        ├── text_parsers.py
        └── file_utils.py
```

---

## 🔄 Flujo de Datos (Event-Driven)

### Ejemplo: Upload Document → OCR → Insights

```
1. Usuario sube PDF
   ├─ REST API (driving adapter)
   └─ Llama: UploadDocumentCommand (application)

2. UploadDocumentCommand
   ├─ Valida archivo
   ├─ Calcula SHA256 (domain service: Deduplication)
   ├─ Guarda en DB via DocumentRepository (port)
   │  └─ PostgreSQL adapter (driven adapter)
   └─ Emite evento: DocumentUploaded (domain event)

3. Event Bus recibe DocumentUploaded
   └─ MasterPipelineScheduler escucha evento
       └─ Encola tarea OCR

4. OCR Worker consume tarea
   ├─ Lee archivo via FileSystem
   ├─ Llama OCRPort (port)
   │  └─ OCRmyPDF Adapter (driven adapter)
   ├─ Segmenta noticias via DocumentSegmentation (domain service)
   ├─ Guarda en DB via DocumentRepository
   └─ Emite evento: OCRCompleted

5. Event Bus recibe OCRCompleted
   └─ Scheduler encola tareas de Chunking

6. Chunking Worker → Indexing Worker → Insights Worker
   └─ Insights Worker usa LangGraph (driven adapter: LLM)
       ├─ Retrieve chunks via VectorStorePort → Qdrant
       ├─ Generate insight via LLMPort → OpenAI/Ollama
       └─ Emite evento: InsightGenerated
```

### Dirección de dependencias:

```
Driving Adapters (API)
        ↓
   Application (Commands/Queries)
        ↓
   Domain (Entities/Services)
        ↓
   Ports (Interfaces)
        ↑
Driven Adapters (PostgreSQL/OpenAI/Qdrant)
```

**Regla de oro**: El dominio NO conoce a los adaptadores. Los adaptadores implementan los ports.

---

## 🎨 Patrones Aplicados

### 1. **Hexagonal Architecture**
- **Core** (domain + application) independiente de I/O
- **Ports** definen contratos
- **Adapters** implementan contratos

### 2. **Domain-Driven Design**
- **Entities** con identidad
- **Value Objects** inmutables
- **Domain Events** para comunicación
- **Aggregates** para consistencia

### 3. **CQRS (Command Query Responsibility Segregation)**
- **Commands** modifican estado (UploadDocument, GenerateInsight)
- **Queries** solo leen (GetDashboardSummary, ListDocuments)
- Separación clara de responsabilidades

### 4. **Event-Driven Architecture**
- **Event Bus** in-memory (mejora futura: Redis pub/sub)
- **Domain Events** comunican entre capas
- **Workers** consumen eventos asíncronamente

### 5. **Repository Pattern**
- **Ports** definen interfaces (DocumentRepository)
- **Adapters** implementan persistencia (PostgreSQLDocumentRepository)
- Abstracción de la base de datos

---

## 🔧 Tecnologías por Capa

| Capa | Tecnologías |
|------|-------------|
| **Core - Domain** | Python puro, Pydantic (value objects) |
| **Core - Application** | Python puro, Event bus in-memory |
| **Core - Ports** | Python protocols/ABCs |
| **Adapters - Driving** | FastAPI, Pydantic schemas |
| **Adapters - Driven (LLM)** | **LangChain**, **LangGraph**, **LangMem** |
| **Adapters - Driven (DB)** | PostgreSQL, psycopg2 |
| **Adapters - Driven (Vector)** | Qdrant |
| **Workers** | asyncio, threading |
| **Schedulers** | APScheduler |

---

## 🚀 Beneficios de esta Arquitectura

### 1. **Testeable**
```python
# Test domain service sin I/O
def test_document_segmentation():
    service = DocumentSegmentation()
    items = service.segment(text="Título 1\nContenido...")
    assert len(items) == 1
```

### 2. **Intercambiable**
```python
# Cambiar de OpenAI a Ollama sin tocar domain
llm_port = OllamaProvider()  # en lugar de OpenAIProvider()
```

### 3. **Mantenible**
- Domain tiene ~500 líneas (vs 6,700 en monolito)
- Cada adapter es independiente (~100-200 líneas)

### 4. **Escalable**
- Event bus permite agregar workers sin modificar core
- Nuevo provider LLM = nuevo adapter, no toca domain

### 5. **Observable**
- Domain events permiten tracing completo
- Logs por capa bien separados

---

## 📊 Comparación: Antes vs Después

| Métrica | Antes (Monolito) | Después (Hexagonal) |
|---------|------------------|---------------------|
| `app.py` | **6,718 líneas** | **<200 líneas** |
| `database.py` | **1,495 líneas** | Dividido en 5 repositories (~200 c/u) |
| Dependencias externas en core | ❌ Muchas (FastAPI, psycopg2, requests) | ✅ Ninguna |
| Testeable sin I/O | ❌ Imposible | ✅ Fácil |
| Cambiar LLM provider | 🟡 Modificar 10+ lugares | ✅ Cambiar 1 adapter |
| Agregar nuevo pipeline stage | 🔴 Modificar scheduler + 5 archivos | 🟢 Crear worker + emitir evento |
| Comprensión del código | 🔴 Difícil (todo mezclado) | 🟢 Clara (capa por capa) |

---

## ❓ FAQ: ¿Por qué Hexagonal + DDD para Event-Driven?

### Pregunta: ¿No debería haber una estructura específica para Event-Driven?

**Respuesta corta**: No. Event-Driven es un **patrón de comunicación**, no una arquitectura completa.

**Respuesta larga**:

Event-Driven NO reemplaza la arquitectura, la **complementa**:
- 🏗️ **Hexagonal** = Planos del edificio (estructura en capas)
- 📐 **DDD** = Habitaciones y su propósito (organización del dominio)
- 🔌 **Event-Driven** = Sistema eléctrico (comunicación entre componentes)

### ¿Dónde están los eventos en la estructura?

Los componentes Event-Driven están **distribuidos** según responsabilidad:

| Componente | Ubicación | Razón |
|------------|-----------|-------|
| **Domain Events** | `core/domain/events/` | Son conceptos del negocio (DDD) |
| **Event Bus** | `core/application/events/` | Orquestación, no es dominio puro |
| **Event Publishers** | `core/application/commands/` | Comandos emiten eventos tras operaciones |
| **Event Consumers** | `workers/` + `schedulers/` | Adaptadores que escuchan y procesan |

### ¿Por qué NO una arquitectura "Event-Driven pura"?

Arquitectura Event-Driven pura sin estructura:
```
events/
handlers/
publishers/
subscribers/
```

**Problemas**:
- ❌ ¿Dónde va la lógica de negocio? (validaciones, reglas)
- ❌ ¿Dónde van las entidades y value objects?
- ❌ ¿Dónde van los repositorios?
- ❌ Todo termina mezclado en `handlers/` → **Monolito de nuevo**

### Flujo Event-Driven en nuestra arquitectura

```
1. Usuario sube documento
   ↓
2. REST API (driving adapter) → UploadDocumentCommand
   ↓
3. Command guarda en DB via Repository (port)
   ↓
4. Command emite DocumentUploaded (domain event) → Event Bus
   ↓
5. Event Bus notifica a subscribers:
   ├─ MasterPipelineScheduler escucha → encola tarea OCR
   └─ Metrics Service escucha → registra métrica
   ↓
6. OCR Worker procesa tarea
   ↓
7. Worker emite OCRCompleted (domain event) → Event Bus
   ↓
8. Event Bus notifica → Chunking Worker inicia
```

### Domain Events = DDD + Event-Driven

Los **Domain Events** de DDD son perfectos para Event-Driven:

```python
# core/domain/events/document_events.py
@dataclass
class DocumentUploaded(DomainEvent):
    document_id: str
    filename: str
    sha256: str
    occurred_at: datetime = field(default_factory=datetime.now)

# core/application/commands/upload_document.py
class UploadDocumentCommand:
    async def execute(self, file):
        document = Document.create(file)
        await self.repo.save(document)
        
        # Emitir evento (Event-Driven)
        event = DocumentUploaded(
            document_id=document.id,
            filename=document.filename,
            sha256=document.sha256
        )
        await self.event_bus.publish(event)  # 🔥

# workers/ocr_worker.py
class OCRWorker:
    def __init__(self, event_bus: EventBus):
        # Suscribirse al evento (Event-Driven)
        event_bus.subscribe(DocumentUploaded, self.handle)  # 🔥
    
    async def handle(self, event: DocumentUploaded):
        # Procesar documento
        pass
```

### Ventajas de esta combinación

| Ventaja | Cómo lo logramos |
|---------|------------------|
| **Estructura clara** | Hexagonal define las capas |
| **Dominio bien organizado** | DDD define entidades, eventos, servicios |
| **Comunicación asíncrona** | Event-Driven integrado en las capas |
| **Testeable** | Mock del event bus, domain sin I/O |
| **Escalable** | Agregar workers = suscribir a eventos |
| **Observable** | Eventos = trazabilidad completa |

### Event Sourcing (futuro)

Si en v5.0+ queremos Event Sourcing, ENTONCES agregaríamos:

```
adapters/driven/persistence/
├── event_store/                    # 🔥 NUEVO
│   ├── postgres_event_store.py    # Guarda TODOS los eventos
│   ├── event_projection.py        # Reconstruye estado desde eventos
│   └── snapshots/                 # Optimización
```

Pero por ahora, Event Bus in-memory + Domain Events es suficiente.

---

## 🔮 Mejoras Futuras

### Corto plazo (v4.1)
- [ ] Event bus con Redis pub/sub (escalabilidad multi-instancia)
- [ ] LangSmith integration para tracing de LLM calls
- [ ] Métricas por capa (Prometheus)

### Medio plazo (v4.5)
- [ ] GraphQL API como driving adapter alternativo
- [ ] WebSocket adapter para real-time updates
- [ ] CQRS con Event Sourcing (histórico completo)

### Largo plazo (v5.0)
- [ ] Microservicios (cada aggregate = servicio)
- [ ] Kafka como event bus distribuido
- [ ] Multi-tenancy en el core

---

## 📚 Referencias

### Arquitectura Hexagonal
- [Alistair Cockburn - Hexagonal Architecture (2005)](https://alistair.cockburn.us/hexagonal-architecture/)
- [Netflix Tech Blog - Ready for changes with Hexagonal Architecture](https://netflixtechblog.com/ready-for-changes-with-hexagonal-architecture-b315ec967749)

### Domain-Driven Design
- [Eric Evans - Domain-Driven Design (Blue Book)](https://www.domainlanguage.com/ddd/)
- [Vaughn Vernon - Implementing Domain-Driven Design (Red Book)](https://vaughnvernon.com/?page_id=168)

### Event-Driven Architecture
- [Martin Fowler - Event-Driven Architecture](https://martinfowler.com/articles/201701-event-driven.html)
- [Chris Richardson - Microservices Patterns](https://microservices.io/patterns/data/event-driven-architecture.html)

### LangChain/LangGraph
- [LangChain Documentation](https://python.langchain.com/docs/get_started/introduction)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [LangMem Documentation](https://github.com/langchain-ai/langmem)

---

## 🤝 Contribución

Al agregar nueva funcionalidad:

1. **Identifica la capa correcta**:
   - ¿Es lógica de negocio? → `core/domain/`
   - ¿Es orquestación? → `core/application/`
   - ¿Es I/O externo? → `adapters/driven/`
   - ¿Es entrada al sistema? → `adapters/driving/`

2. **Define el port primero** (si no existe):
   ```python
   # core/ports/new_service_port.py
   from abc import ABC, abstractmethod
   
   class NewServicePort(ABC):
       @abstractmethod
       def do_something(self, input: str) -> str:
           pass
   ```

3. **Implementa el adapter**:
   ```python
   # adapters/driven/new_service/adapter.py
   from core.ports.new_service_port import NewServicePort
   
   class NewServiceAdapter(NewServicePort):
       def do_something(self, input: str) -> str:
           # Implementación concreta
           return f"Processed: {input}"
   ```

4. **Usa en application**:
   ```python
   # core/application/commands/use_new_service.py
   def execute(input: str, service: NewServicePort):
       return service.do_something(input)
   ```

---

**Versión**: 4.0.0  
**Estado**: Implementando (FASE 4 - LangChain/LangGraph)  
**Próxima actualización**: Post-refactor completo
