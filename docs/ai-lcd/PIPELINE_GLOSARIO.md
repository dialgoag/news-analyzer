# Glosario del Pipeline - Chunks, Embeddings, Insights

> **Referencia**: Etapas y conceptos. Variables de entorno → `03-operations/ENVIRONMENT_CONFIGURATION.md`

## Flujo del pipeline

```
PDF → OCR → Chunking → Indexing → Insights → Indexing Insights
```

## 1. OCR (Optical Character Recognition)

- **Qué**: Extrae texto del PDF.
- **Quién**: `ocr_service` (ocrmypdf o Tika).
- **Salida**: Texto plano.

## 2. Chunking

- **Qué**: Divide el texto en segmentos (chunks) por noticia.
- **Quién**: LangChain `RecursiveCharacterTextSplitter` + lógica de segmentación.
- **Salida**: `chunk_records` (lista de dicts con `text`, `news_item_id`, etc.).
- **NO usa LLM** (OpenAI/Ollama). Es solo división de texto.

## 3. Indexing (Embeddings + Qdrant)

- **Qué**: Convierte chunks en vectores (embeddings) y los guarda en Qdrant.
- **Embeddings**: Vectores numéricos que representan el significado del texto.
- **Quién**: `EmbeddingsService` (HuggingFace Sentence-Transformers, ej. BAAI/bge-m3).
- **NO usa OpenAI ni Ollama**. Solo modelos locales (Sentence-Transformers).
- **Salida**: Chunks indexados en Qdrant para búsqueda semántica.

## 4. Insights

- **Qué**: Resumen/analisis por noticia en Markdown (temas, postura, etc.).
- **Quién**: **LLM** configurado en `LLM_PROVIDER` (openai, perplexity u ollama).
- **Entrada**: Chunks de Qdrant concatenados como contexto.
- **Salida**: Texto Markdown guardado en `news_item_insights.content`.

## 5. Indexing Insights

- **Qué**: Vectoriza el contenido de cada insight y lo inserta en Qdrant para RAG.
- **Quién**: `EmbeddingsService` + `QdrantConnector` (mismo flujo que chunks).
- **Entrada**: `news_item_insights.content` (status=done).
- **Salida**: Vectores en Qdrant con `content_type=insight`; columna `indexed_in_qdrant_at` en DB.
- **Config**: `INDEXING_INSIGHTS_PARALLEL_WORKERS` (default 4). Ver `ENVIRONMENT_CONFIGURATION.md`.

## Calidad de embeddings (HuggingFace)

- **Prefijo de instrucción**: BGE usa "Represent this sentence for retrieving relevant passages: "; E5 usa "query:" / "passage:". Mejora la búsqueda.
- **Chunk size**: 2000 por defecto (configurable con `CHUNK_SIZE`).
- **Overlap**: 300 por defecto (`CHUNK_OVERLAP`).
- **Modelo alternativo**: `EMBEDDING_MODEL=intfloat/e5-large-v2` para probar E5 (1024d, multilingüe).

## Resumen

| Concepto | Generado por | Usa API externa |
|----------|--------------|-----------------|
| **Chunks** | LangChain (splitter) | No |
| **Embeddings** | HuggingFace (BGE, MiniLM, etc.) | No (modelo local) |
| **Indexing** | Embeddings + Qdrant | No |
| **Insights** | LLM (OpenAI/Perplexity/Ollama) | Sí (OpenAI/Perplexity) o No (Ollama local) |
| **Indexing Insights** | Embeddings + Qdrant | No |

Los **429** solo pueden ocurrir en **Insights**, porque es el único paso que llama a APIs externas (OpenAI, Perplexity).

---

## ¿Insights vectorizados en Qdrant?

**Sí, implementado (2026-03-16).** Los insights se guardan en Postgres (`news_item_insights.content`) y se vectorizan en una etapa separada (**Indexing Insights**) para RAG. Mejora preguntas de alto nivel ("¿qué postura tienen los artículos sobre X?"). Ver `CONSOLIDATED_STATUS.md §88` y `INDEXING_INSIGHTS_GAP_ANALYSIS.md`.
