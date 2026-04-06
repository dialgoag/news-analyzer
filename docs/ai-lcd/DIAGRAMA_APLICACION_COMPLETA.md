# Arquitectura detallada NewsAnalyzer-RAG (Mermaid)

> Diagramas **lo más completos posible** respecto al código en `app/backend`, `app/frontend` e infra `app/docker-compose.yml`.  
> **Leyenda**: **D** = determinístico (reglas, heurísticas, SQL, vectores fijos). **LLM** = llamada a modelo generativo (OpenAI / Ollama / Perplexity). **LG** = flujo **LangGraph** (grafo de estados con reintentos). No hay “agentes” autónomos con herramientas en bucle; el único flujo multi-paso orquestado es **insights** vía LangGraph + cadenas.

**Referencias de código**: `app/backend/app.py`, `app/backend/rag_pipeline.py`, `app/backend/database.py`, `app/backend/migrations/*.py`, `core/`, `adapters/`, `pipeline_states.py`.

---

## 1. Hexagonal: capas y carpetas

```mermaid
flowchart TB
    subgraph Driving["🔷 Driving adapters — entrada"]
        direction TB
        R_AUTH["routers/auth.py"]
        R_DOC["routers/documents.py"]
        R_DASH["routers/dashboard.py"]
        R_WORK["routers/workers.py"]
        R_REP["routers/reports.py"]
        R_NOT["routers/notifications.py"]
        R_Q["routers/query.py"]
        R_ADM["routers/admin.py"]
        R_NEWS["routers/news_items.py"]
        MW["middleware.py — JWT, roles"]
        SCH["schemas/*.py — Pydantic"]
        LEG["app.py — endpoints legacy + lifespan + schedulers"]
    end

    subgraph Core["🔶 Core (dominio + casos de uso)"]
        direction TB
        ENT["entities: Document, NewsItem, Worker, StageTimingRecord"]
        VO["value_objects: DocumentId, TextHash, PipelineStatus…"]
        DSVC["domain/services: insight_parser.py"]
        ASVC["application/services: InsightsWorkerService"]
        EVT["domain/events + EventBus (in-memory)"]
        P_REP["ports/repositories: DocumentRepository, NewsItemRepository, WorkerRepository, StageTimingRepository"]
        P_LLM["ports/llm_port.py: LLMPort, LLMChainPort, LLMRequest/Response"]
    end

    subgraph Driven["🔹 Driven adapters — salida"]
        direction TB
        PG_DOC["PostgresDocumentRepository"]
        PG_NEWS["PostgresNewsItemRepository"]
        PG_W["PostgresWorkerRepository"]
        PG_ST["PostgresStageTimingRepository"]
        G_INS["graphs/insights_graph.py — LangGraph"]
        C_EXT["chains: ExtractionChain, AnalysisChain, InsightsChain"]
        PRV["providers: OpenAIProvider, OllamaProvider"]
        MEM["memory/insight_memory.py — LangMem → insight_cache"]
        LEGDB["database.py — *Store legacy"]
    end

    subgraph Infra["Infra compartida (no hex puro)"]
        RAG["rag_pipeline.RAGPipeline"]
        OCR["ocr_service → HTTP ocr-service"]
        QD["qdrant_connector.QdrantConnector"]
        EMB["embeddings_service / PerplexityEmbeddingsService"]
        FILE["file_ingestion_service"]
        BS["backup_scheduler.BackupScheduler"]
    end

    Driving --> MW
    MW --> Core
    Core --> P_REP
    P_REP --> PG_DOC & PG_NEWS & PG_W & PG_ST
    ASVC --> MEM
    ASVC --> G_INS
    G_INS --> C_EXT
    C_EXT --> PRV
    LEG --> RAG & OCR & QD & EMB & FILE & LEGDB & Core
```

---

## 2. Puertos (interfaces) ↔ implementaciones

```mermaid
flowchart LR
    subgraph Ports["core/ports"]
        DR[DocumentRepository]
        NR[NewsItemRepository]
        WR[WorkerRepository]
        STR[StageTimingRepository]
        LLM[LLMPort / LLMChainPort]
    end

    subgraph ImplPG["adapters/driven/persistence/postgres"]
        DRi[document_repository_impl]
        NRi[news_item_repository_impl]
        WRi[worker_repository_impl]
        STRi[stage_timing_repository_impl]
    end

    subgraph ImplLLM["adapters/driven/llm"]
        OPr[OpenAIProvider]
        OlPr[OllamaProvider]
        EC[ExtractionChain]
        AC[AnalysisChain]
        IC[InsightsChain]
    end

    DR --> DRi
    NR --> NRi
    WR --> WRi
    STR --> STRi
    LLM -.-> OPr & OlPr & EC & AC & IC
```

---

## 3. Entidades de dominio (resumen)

```mermaid
classDiagram
    class Document {
        +DocumentId id
        +filename
        +sha256
        +PipelineStatus status
        +DocumentType document_type
    }
    class NewsItem {
        +news_item_id
        +document_id
        +text_hash
    }
    class Worker {
        +worker_id
        +task_type
        +status
    }
    class StageTimingRecord {
        +document_id
        +news_item_id
        +stage
        +created_at
        +updated_at
    }
    Document "1" --> "*" NewsItem
```

---

## 4. PostgreSQL: tablas (migraciones)

| Tabla | Migración / rol |
|-------|-------------------|
| `users` | 001 — auth |
| `document_status` | 002 — estado pipeline, OCR text, reprocess |
| `worker_tasks`, `processing_queue` | 003 — cola event-driven + semáforo |
| `document_insights` | 004 — insights legacy a nivel documento |
| `news_items`, `news_item_insights` | 005 — noticias + insights por ítem |
| `daily_reports`, `weekly_reports` | 006 |
| `notifications`, `notification_reads` | 007 |
| `ocr_performance_log` | 011 |
| `pipeline_runtime_kv` | 016 — pausas / config runtime JSONB |
| `insight_cache` | 017 — LangMem (dedup por `text_hash`) |
| `document_stage_timing` (+ triggers varios) | 018 — auditoría por stage |

```mermaid
erDiagram
    users ||--o{ notification_reads : reads
    notifications ||--o{ notification_reads : has

    document_status ||--o{ news_items : contains
    document_status ||--o{ document_stage_timing : timing
    news_items ||--|| news_item_insights : has

    processing_queue }o--|| document_status : document_id
    worker_tasks }o--|| document_status : document_id

    insight_cache {
        varchar text_hash PK
        text full_text
        varchar provider_used
    }

    pipeline_runtime_kv {
        varchar key PK
        jsonb value
    }
```

---

## 5. Qdrant y volúmenes (fuera de Postgres)

```mermaid
flowchart LR
    BE[Backend]
    QC[QdrantConnector]
    QD[(Qdrant :6333)]
    COLL["Colección(es) de chunks\nmetadata: document_id, news_item_id…"]
    HF["~/.cache/huggingface\nembeddings BAAI/bge-m3 u otro"]
    BE --> QC --> QD --> COLL
    BE --> HF
```

---

## 6. Contenedores Docker (red `rag-network`)

```mermaid
flowchart TB
    U[Usuario] --> FE[frontend Vite/React :3000]
    FE -->|JWT + REST| BE[backend FastAPI :8000]
    BE --> PG[(postgres:17)]
    BE --> QD[(qdrant)]
    BE --> OL[ollama]
    BE -->|HTTP OCR| OCRS[ocr-service :9999]
    BE -. uploads/inbox/backups .-> VOL[volúmenes local-data]
```

---

## 7. Pipeline de documento: etapas y naturaleza (D vs LLM)

Orden lógico de **estados** (`pipeline_states.py`): `upload_*` → `ocr_*` → `chunking_*` → `indexing_*` → `insights_*` → `completed`.

```mermaid
flowchart TB
    subgraph UP["Upload D"]
        U1[SHA256 / dedup archivo]
        U2[document_status insert]
        U3[file en uploads o inbox]
    end

    subgraph OCR["OCR D + servicio externo"]
        O1[master_pipeline_scheduler asigna worker_tasks]
        O2[_ocr_worker_task async]
        O3[HTTP a ocr-service / Tesseract / ocrmypdf]
        O4[ocr_performance_log opcional]
        O5[document_status.ocr_text]
    end

    subgraph CH["Chunking D"]
        C1[segment_news_items_from_text — heurística títulos / páginas]
        C2[rag_pipeline.chunk_text — RecursiveCharacterTextSplitter]
        C3[news_item_store.upsert_items]
        C4[text_hash por cuerpo de noticia]
    end

    subgraph IX["Indexing D"]
        I1[embeddings batch — HuggingFace / Perplexity embed]
        I2[Qdrant upsert puntos]
        I3[document_status num_chunks / flags]
    end

    subgraph INS["Insights LLM + LG + cache D"]
        L0[Fetch chunks contexto desde Qdrant]
        L1[InsightsWorkerService]
        L2{Dedup text_hash?}
        L3[LangMem insight_cache hit?]
        L4[run_insights_workflow LangGraph]
        L5[ExtractionChain LLM]
        L6[validate_extraction_node D]
        L7[AnalysisChain LLM]
        L8[validate_analysis_node D]
        L9[finalize_node D]
        L10[Persist news_item_insights]
    end

    UP --> OCR --> CH --> IX --> INS
    L2 -->|sí| L10
    L2 --> L3
    L3 -->|hit| L10
    L3 -->|miss| L4
    L4 --> L5 --> L6 --> L7 --> L8 --> L9 --> L10
```

**`TaskType`** (`processing_queue` / `worker_tasks`): `ocr`, `chunking`, `indexing`, `insights`, `indexing_insights`.  
**`QueueStatus`**: `pending`, `processing`, `completed`.  
**`WorkerStatus`**: `assigned`, `started`, `completed`, `error`.

---

## 8. Orquestación: `master_pipeline_scheduler` + colas

```mermaid
flowchart LR
    BS[BackupScheduler APScheduler]
    MS[master_pipeline_scheduler ~10s]
    INBOX[inbox scan 5 min]
    BK[daily/weekly report jobs]

    PQ[(processing_queue)]
    WT[(worker_tasks)]
    DS[(document_status)]

    W1[_ocr_worker_task]
    W2[_chunking path en app.py]
    W3[_indexing worker]
    W4[_insights_worker_task]

    BS --> INBOX & MS & BK
    MS --> DS
    MS --> PQ
    MS --> WT
    MS --> W1 & W2 & W3 & W4
```

---

## 9. LangGraph: grafo de insights (nodos y ramas)

Flujo real (`adapters/driven/llm/graphs/insights_graph.py`).

```mermaid
flowchart TD
    START([START]) --> extract[extract_node — LLM ExtractionChain]
    extract --> ve[validate_extraction_node — D heurística markdown]
    ve -->|retry| extract
    ve -->|continue| analyze[analyze_node — LLM AnalysisChain]
    ve -->|fail| err[error_node]
    analyze --> va[validate_analysis_node — D]
    va -->|retry| analyze
    va -->|continue| fin[finalize_node — concatena texto D]
    va -->|fail| err
    fin --> ENDN([END])
    err --> ENDN
```

---

## 10. Consulta RAG (chat): embedding D + búsqueda D + respuesta LLM

```mermaid
sequenceDiagram
    participant FE as Frontend React
    participant API as routers/query.py
    participant RP as RAGPipeline
    participant EMB as EmbeddingsService
    participant Q as QdrantConnector
    participant LLM as OpenAI/Ollama/Perplexity chain

    FE->>API: POST /api query + JWT
    API->>RP: query con historial usuario
    RP->>EMB: embed pregunta
    RP->>Q: search vectores + threshold
    RP->>LLM: prompt contexto + pregunta
    LLM-->>RP: respuesta
    RP-->>API: answer + sources
    API-->>FE: JSON
```

---

## 11. Frontend (capa presentación)

SPA **React** (`app/frontend/src`), build **Vite**, consume API vía `VITE_API_URL`. Componentes de dashboard (ej. `PipelineDashboard.jsx`, `WorkerLoadCard.jsx`, gráficos Sankey) hablan con `/api/dashboard`, `/api/workers`, etc.

```mermaid
flowchart LR
    subgraph FE["frontend/src"]
        PD[PipelineDashboard.jsx]
        WC[WorkerLoadCard.jsx]
        PPC[ParallelPipelineCoordinates.jsx]
    end
    PD & WC & PPC -->|fetch| API[Backend /api/*]
```

---

## 12. Coexistencia legacy vs hexagonal

**Stores legacy** (`database.py`, conviven con repositorios):

| Clase | Responsabilidad principal |
|-------|---------------------------|
| `DocumentStatusStore` | Fila `document_status`, estado pipeline |
| `ProcessingQueueStore` | `processing_queue` |
| `DailyReportStore` / `WeeklyReportStore` | Reportes |
| `NotificationStore` | `notifications` + lecturas |
| `DocumentInsightsStore` | `document_insights` |
| `NewsItemStore` | `news_items` |
| `NewsItemInsightsStore` | `news_item_insights` |

```mermaid
flowchart TB
    subgraph New["Patrón nuevo"]
        REPOS[Ports + Postgres*Repository]
    end
    subgraph Old["Legacy en transición"]
        STORES[Stores en database.py]
    end
    APP[app.py]
    APP --> REPOS
    APP --> STORES
    ROUTERS["routers v2"] --> REPOS
    ROUTERS --> APP module globals
```

---

## Notas de precisión

1. **Determinista** no implica “rápido”: OCR e embeddings pueden ser costosos, pero **no son generación libre con LLM**.
2. **Insights**: los nodos `validate_*` son **reglas sobre texto** (presencia de secciones `## Metadata`, longitud mínima, etc.), no otro LLM.
3. **`document_insights`** (tabla a nivel documento) coexiste con **`news_item_insights`** (por noticia); el flujo principal de producción para el dashboard de noticias es por **news item** + LangGraph.
4. **`EventBus`** está en core pero la orquestación pesada sigue en **`app.py`** + schedulers; conviene ver esto como evolución incremental REQ-021.

---

## Cómo visualizar

| Herramienta | Uso |
|-------------|-----|
| Preview Markdown en IDE | Ver diagramas embebidos |
| https://mermaid.live | Pegar **un bloque** `mermaid` si el render falla por tamaño |
| GitHub / GitLab | Vista previa del `.md` |

Si algún diagrama supera el límite del renderizador, **copia solo ese bloque** a Mermaid Live o divídelo en dos `subgraph` más pequeños manteniendo los mismos nombres de archivo y clases.
