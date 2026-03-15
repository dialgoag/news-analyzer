# Environment Configuration - NewsAnalyzer-RAG

> Variables de entorno y su configuración

**Última actualización**: 2026-03-02
**Fase AI-DLC**: 03-operations
**Audiencia**: DevOps, Admin

---

## Variables de Entorno

### Infraestructura

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GPU_TYPE` | `nvidia` | Tipo de GPU: `nvidia`, `amd`, `cpu` |
| `COMPOSE_FILE` | `docker-compose.yml:docker-compose.nvidia.yml` | Archivos compose a usar |
| `VITE_API_URL` | `http://localhost:8000` | URL del backend (vista desde el navegador del usuario) |
| `BACKEND_PORT` | `8000` | Puerto del backend |
| `FRONTEND_PORT` | `3000` | Puerto del frontend |

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
| `CHUNK_SIZE` | `1000` | Tamaño de cada trozo de texto al indexar (caracteres). |
| `CHUNK_OVERLAP` | `100` | Solapamiento entre trozos (caracteres). |

Cuando `INGEST_AUTO_TUNE_ON_START=true`, el backend escribe el valor recomendado en el archivo `.env`. Por defecto usa el `.env` del directorio de trabajo. En Docker, para persistir en un archivo montado, define `ENV_FILE_PATH` con la ruta absoluta (p. ej. `/app/data/.env`).

## Configuraciones de Ejemplo

### Desarrollo Local (Mac)

```env
GPU_TYPE=cpu
COMPOSE_FILE=docker-compose.yml
VITE_API_URL=http://localhost:8000
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...tu-key...
OPENAI_MODEL=gpt-4o
```

### Producción (Servidor Linux con dominio)

```env
GPU_TYPE=cpu
COMPOSE_FILE=docker-compose.yml
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
