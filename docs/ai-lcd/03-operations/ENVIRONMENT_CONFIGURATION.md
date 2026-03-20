# Environment Configuration - NewsAnalyzer-RAG

> **Fuente única** de variables de entorno. Evitar duplicar en otros docs.

**Última actualización**: 2026-03-20
**Fase AI-DLC**: 03-operations
**Audiencia**: DevOps, Admin

**Valores por defecto**: Definidos en `app/docker-compose.yml`. Override con `.env` o variables de entorno.

**Producción local (convención)**: En este repo, “producción” suele ser el **Docker Compose en tu máquina**. Actualizar el servicio en ejecución implica **rebuild de imagen(es)** y **reemplazar contenedores** (`docker compose down` → `build` → `up`). Detalle y comandos: [`app/docs/DOCKER.md`](../../../app/docs/DOCKER.md) §0.

---

## Variables de Entorno

### Workers del Pipeline

| Variable | Default | Descripción |
|----------|---------|-------------|
| `PIPELINE_WORKERS_COUNT` | `4` | Tamaño total del pool de workers |
| `OCR_PARALLEL_WORKERS` | `4` | Máx. workers OCR simultáneos |
| `CHUNKING_PARALLEL_WORKERS` | `4` | Máx. workers de chunking |
| `INDEXING_PARALLEL_WORKERS` | `4` | Máx. workers de indexing (chunks) |
| `INSIGHTS_PARALLEL_WORKERS` | `4` | Máx. workers de insights (LLM) |
| `INDEXING_INSIGHTS_PARALLEL_WORKERS` | `4` | Máx. workers indexando insights en Qdrant |

### Infraestructura

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GPU_TYPE` | `cpu` | Para scripts (build.sh): `cpu`, `nvidia`, `amd` |
| `COMPOSE_FILE` | (ninguno) | Override GPU: `docker-compose.yml:docker-compose.nvidia.yml` o `docker-compose.yml:docker-compose.amd.yml` |
| `VITE_API_URL` | `http://localhost:8000` | URL del backend (vista desde el navegador del usuario) |
| `BACKEND_PORT` | `8000` | Puerto del backend |
| `FRONTEND_PORT` | `3000` | Puerto del frontend |

**Nota**: Por defecto `docker compose up -d` usa CPU (Mac, Linux sin GPU). Ver [app/docs/DOCKER.md](../../app/docs/DOCKER.md).

### LLM Provider (MODIFICACIÓN NewsAnalyzer-RAG)

| Variable | Default | Descripción |
|----------|---------|-------------|
| `LLM_PROVIDER` | `ollama` | Provider del LLM: `openai` o `ollama` |
| `OPENAI_API_KEY` | (vacío) | API key de OpenAI (requerido si provider=openai) |
| `OPENAI_MODEL` | `gpt-4o` | Modelo de OpenAI a usar |
| `LLM_MODEL` | `mistral` | Modelo Ollama (solo si provider=ollama) |
| `OLLAMA_HOST` | `ollama` | Host de Ollama |
| `OLLAMA_PORT` | `11434` | Puerto de Ollama |

### Embeddings y RAG

| Variable | Default | Descripción |
|----------|---------|-------------|
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | Modelo de embeddings (HuggingFace) |
| `RELEVANCE_THRESHOLD` | `0.35` | Umbral de similitud para retrieval |

### Seguridad

| Variable | Default | Descripción |
|----------|---------|-------------|
| `JWT_SECRET_KEY` | (random) | Secreto para firmar JWT tokens. **GENERAR PROPIO EN PRODUCCIÓN** |
| `ALLOWED_ORIGINS` | `*` | CORS origins permitidos. **RESTRINGIR EN PRODUCCIÓN** |
| `ADMIN_DEFAULT_PASSWORD` | (random) | Password del admin inicial (se muestra en logs si no se configura) |
| `QDRANT_API_KEY` | (vacío) | API key para Qdrant (opcional) |

### Limits e Ingesta

Todas estas variables se leen desde `.env` (o `env_file` en Docker) al arrancar el backend.

| Variable | Default | Descripción |
|----------|---------|-------------|
| `MAX_UPLOAD_SIZE_MB` | `100` | Tamaño máximo de archivo (MB) |
| `INBOX_DIR` | (vacío) | Si está definida (p. ej. `/app/inbox`), el backend escanea esta carpeta cada 5 min y procesa archivos nuevos. Ver `INGEST_GUIDE.md`. |
| `INGEST_PARALLEL_WORKERS` | `2` | Número de documentos que se procesan en paralelo en cada ciclo de inbox (1 = secuencial). Puede ser un número o **`auto`** (heurística por CPU/RAM en cada arranque). |
| `INGEST_AUTO_TUNE_ON_START` | `false` | Si `true`/`1`/`yes`: al arrancar el backend se ejecuta la heurística de capacidad, se usa el valor recomendado en esta ejecución y se escribe en `.env` (si el archivo existe, p. ej. en el host). Así el sistema se autoajusta sin ejecutar el script a mano. |
| `INGEST_DEFER_REPORT_GENERATION` | `false` | Si `true`/`1`/`yes`, no se genera reporte diario tras cada documento indexado; solo el job de las 23:00. Útil en ingesta masiva. |
| `INGEST_REPORT_THROTTLE_MINUTES` | `0` | Con DEFER=false: regenerar el reporte diario de una fecha como máximo cada N minutos. Ej.: 10 → durante ingesta masiva del mismo día se llama al LLM una vez cada 10 min en lugar de una por archivo. |
| `INSIGHTS_QUEUE_ENABLED` | `true` | Si true: al indexar un documento se encola para generar "insights" (reporte por archivo) en una cola con throttling. Ver OPENAI_RATE_LIMITS_AND_USAGE.md. |
| `INSIGHTS_THROTTLE_SECONDS` | `60` | Segundos de espera ante 429 antes de reintentar la generación de insights. |
| `INSIGHTS_MAX_RETRIES` | `5` | Número máximo de reintentos por documento en la cola de insights. |
| `CHUNK_SIZE` | `2000` | Tamaño de cada trozo de texto al indexar (caracteres). |
| `CHUNK_OVERLAP` | `300` | Solapamiento entre trozos (caracteres). |
| `INDEXING_BATCH_SIZE` | `100` | Chunks por batch al indexar en Qdrant (menor = menos riesgo de timeout). |
| `QDRANT_TIMEOUT_SEC` | `1200` | Timeout (segundos) para operaciones Qdrant (indexing de docs grandes). |
| `MIGRATIONS_DIR` | `/app/migrations` | Directorio de migraciones Yoyo (ejecutadas al iniciar el backend). |

Cuando `INGEST_AUTO_TUNE_ON_START=true`, el backend escribe el valor recomendado en el archivo `.env`. Por defecto usa el `.env` del directorio de trabajo. En Docker, para persistir en un archivo montado, define `ENV_FILE_PATH` con la ruta absoluta (p. ej. `/app/data/.env`).

## Configuraciones de Ejemplo

### Desarrollo Local (Mac)

```env
GPU_TYPE=cpu
# COMPOSE_FILE no necesario (CPU por defecto)
VITE_API_URL=http://localhost:8000
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...tu-key...
OPENAI_MODEL=gpt-4o
```

### Producción (Servidor Linux con dominio)

```env
GPU_TYPE=cpu
# COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml  # si hay GPU
VITE_API_URL=https://api.tudominio.com
JWT_SECRET_KEY=<openssl rand -hex 32>
ALLOWED_ORIGINS=https://tudominio.com
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...tu-key...
OPENAI_MODEL=gpt-4o
ADMIN_DEFAULT_PASSWORD=password-seguro-admin
```

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación inicial | AI-DLC |
| 2026-03-15 | 1.1 | GPU_TYPE/COMPOSE_FILE actualizados (CPU default) | AI-DLC |
| 2026-03-16 | 1.2 | Workers del pipeline (default 4); INDEXING_INSIGHTS_PARALLEL_WORKERS; CHUNK_SIZE/OVERLAP 2000/300; INDEXING_BATCH_SIZE, QDRANT_TIMEOUT_SEC, MIGRATIONS_DIR | AI-DLC |
