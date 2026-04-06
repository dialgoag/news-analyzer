# Guía de Ingesta - NewsAnalyzer-RAG

> Carga masiva y carpeta inbox para no subir documentos uno a uno en la UI

**Última actualización**: 2026-04-06
**Fase AI-DLC**: 03-operations
**Audiencia**: Admin, DevOps
**Relación**: UC-06 (carga masiva), UC-07 (carpeta inbox)

---

## 1. Resumen

Hay dos formas de ingestar muchos documentos sin usar la interfaz web:

| Método | Uso típico | Requiere |
|--------|------------|----------|
| **Script de carga masiva** | Lote inicial (p. ej. 150 PDFs) o lotes puntuales | Ejecutar script con ruta de carpeta |
| **Carpeta inbox** | Archivos nuevos diarios (p. ej. 8/día); el sistema los detecta y procesa solo | Copiar archivos a una carpeta; backend vigilando |

---

## 2. Script de carga masiva

### 2.1 Descripción

Un script (p. ej. `scripts/bulk_upload.py`) que:
- Hace login contra la API con usuario/contraseña (admin o super_user)
- Recorre una carpeta local y sube cada archivo con extensión admitida vía `POST /api/documents/upload`
- Los documentos se procesan en segundo plano en el backend (igual que si se subieran por la UI)

### 2.2 Uso

```bash
# Desde el host (backend debe estar levantado)
cd app

# Opción A: variables de entorno
export RAG_API_URL=http://localhost:8000
export RAG_USERNAME=admin
export RAG_PASSWORD=tu_password
python scripts/bulk_upload.py /ruta/a/mis/pdf

# Opción B: argumentos
python scripts/bulk_upload.py /ruta/a/mis/pdf --api-url http://localhost:8000 --username admin --password tu_password
```

### 2.3 Formatos admitidos

Los mismos que la UI: `.pdf`, `.txt`, `.doc`, `.docx`, `.ppt`, `.pptx`, `.xls`, `.xlsx`, `.odt`, `.rtf`, `.html`, `.xml`, `.json`, `.csv`, `.md`, imágenes (`.jpg`, `.png`, etc.).

### 2.4 Notas

- El script no espera a que termine el procesamiento de cada archivo; el backend encola y procesa en background.
- Para muchos archivos, revisar `docker compose logs backend` para ver progreso y posibles errores.

---

## 3. Carpeta inbox (vigilada)

### 3.1 Descripción

- Una carpeta (p. ej. `local-data/inbox`) se monta en el contenedor del backend.
- Si en `.env` se define `INBOX_DIR=/app/inbox`, el backend ejecuta un job periódico (cada 5 min) que:
  - **Al arranque**: lanza el primer escaneo **60 segundos después** de iniciar (para que Tika y el pipeline estén estables y no se saturen con muchos workers a la vez).
  - **Cada 5 min**: lista archivos en esa carpeta (solo en la raíz de la inbox)
  - Por cada archivo con extensión admitida: lo procesa (OCR → chunk → index) y lo mueve a `inbox/processed/` para no volver a procesarlo
- Los archivos procesados quedan también en `uploads` con su `document_id` para poder descargarlos desde la UI.

### 3.2 Configuración

**Variables de entorno** (en `.env`):

```bash
# Carpeta vigilada: si está definida, el backend escanea cada 5 min
# Dejar vacío para desactivar
INBOX_DIR=/app/inbox
```

**Docker Compose** (p. ej. `docker-compose.local.yml`): montar la carpeta y pasar la variable:

```yaml
backend:
  environment:
    INBOX_DIR: ${INBOX_DIR:-}
  volumes:
    - ./local-data/inbox:/app/inbox
```

### 3.3 Uso

1. Crear la carpeta local: `mkdir -p app/local-data/inbox`
2. Copiar o mover archivos nuevos a `local-data/inbox`
3. En unos minutos el backend los detectará, los procesará y los moverá a `local-data/inbox/processed/`

### 3.4 Notas

- Solo se procesan archivos en la **raíz** de la inbox (no subcarpetas).
- Tras procesar, el archivo se mueve a `processed/`; no se borra por si se quiere conservar.
- El mismo límite de tamaño (`MAX_UPLOAD_SIZE_MB`) aplica.

### 3.5 Sanity check de symlinks vs BD (diagnóstico rápido)

Cuando veas errores `File not found` en OCR, valida consistencia entre:
- symlink `uploads/{document_id}.pdf`
- archivo real en `inbox/processed/`
- `document_status.filename` y `processing_queue.filename`

Script disponible:
- `app/backend/scripts/check_upload_symlink_db_consistency.py`

Uso recomendado (read-only):
```bash
# Desde backend (tras rebuild de imagen) o desde host con entorno Python + psycopg2
python scripts/check_upload_symlink_db_consistency.py --use-container-paths
```

Fixes opcionales (solo casos inequívocos):
```bash
python scripts/check_upload_symlink_db_consistency.py \
  --use-container-paths \
  --apply-symlink-fix \
  --apply-db-filename-fix
```

Si ejecutas desde host (no dentro del contenedor), añade:
- `--local-data-root /ruta/al/proyecto/app/local-data`
- `--dsn "host=127.0.0.1 port=5432 dbname=<db> user=<user> password=<password>"`

---

## 4. Reset para re-ingesta limpia

Si quieres borrar la base de datos (y opcionalmente Qdrant) para re-empezar con documentos que tengan `news_date` y reportes coherentes:

**Importante:** al resetear datos, conviene **devolver los archivos de `inbox/processed/` a `inbox/`** para que el próximo escaneo los vuelva a procesar. El script de reset puede hacerlo con `--requeue-inbox`.

### 4.1 Procedimiento completo (prioridad AI-DLC): reset + mover a inbox + recrear front y back

Seguir estos pasos **en orden** cuando quieras dejar datos limpios, archivos listos para reingestar y código actualizado en los contenedores:

| Paso | Acción | Comando / Acción |
|------|--------|-------------------|
| 1 | Bajar el stack | `cd app` y `COMPOSE_FILE=docker-compose.local.yml docker compose down` |
| 2 | Limpiar datos (uploads, BD, Qdrant) | `rm -rf local-data/uploads/* local-data/database/* local-data/qdrant/*` |
| 3 | Mover archivos de processed a inbox | `for f in local-data/inbox/processed/*; do [ -f "$f" ] && mv "$f" local-data/inbox/; done` |
| 4 | Recrear imágenes backend y frontend | `COMPOSE_FILE=docker-compose.local.yml docker compose build --no-cache backend frontend` |
| 5 | Levantar el stack | `COMPOSE_FILE=docker-compose.local.yml docker compose up -d` |
| 6 | Comprobar | Frontend http://localhost:3000, login con `ADMIN_DEFAULT_PASSWORD`; en ~1 min el primer escaneo de inbox procesará archivos de `inbox/`. |

**Nota:** Si usas el script `reset_for_reingest.sh` en lugar del paso 2 manual, haz **primero** `docker compose down`, luego el script (con `--qdrant --requeue-inbox` para mover processed→inbox), y después los pasos 4–5.

### 4.2 Reset solo con script (sin recrear imágenes)

1. **Detener el backend** para que no tenga la BD abierta:
   ```bash
   cd app
   COMPOSE_FILE=docker-compose.local.yml docker compose stop backend
   ```

2. **Ejecutar el script de reset**:
   ```bash
   ./scripts/reset_for_reingest.sh              # solo BD SQLite (document_status, reportes, notificaciones, usuarios)
   ./scripts/reset_for_reingest.sh --qdrant     # BD + borrar colección de Qdrant (vectores)
   ./scripts/reset_for_reingest.sh --qdrant --requeue-inbox   # además devuelve los archivos de inbox/processed/ a inbox/ para que se reindexen en el próximo escaneo (~5 min)
   ```
   Desde el host, si Qdrant va por Docker, usa `QDRANT_HOST=localhost` para el curl:  
   `QDRANT_HOST=localhost ./scripts/reset_for_reingest.sh --qdrant --requeue-inbox`

3. **Levantar de nuevo**:
   ```bash
   COMPOSE_FILE=docker-compose.local.yml docker compose up -d backend
   ```
   El admin se crea de nuevo con `ADMIN_DEFAULT_PASSWORD` de `.env`.

4. **Re-ingestar**: subir por la UI, usar `bulk_upload.py` o copiar archivos a `local-data/inbox`.

---

## 5. Ingesta más rápida

Todo lo de esta sección forma parte de la **tarea prioritaria AI-DLC** (barra de estado en el Dashboard, cola de insights por noticia con LLM, optimización del uso de la API key OpenAI). Ver `OPENAI_RATE_LIMITS_AND_USAGE.md` §0.

| Opción | Variable | Efecto |
|--------|----------|--------|
| **Varios documentos en paralelo (inbox)** | `INGEST_PARALLEL_WORKERS=2` o `auto` | El job de inbox procesa hasta N archivos a la vez. Con **`auto`** el backend usa heurística (CPU/RAM) en cada arranque. |
| **Autoajuste al arrancar** | `INGEST_AUTO_TUNE_ON_START=true` | Al iniciar el backend se ejecuta la heurística, se usa el valor recomendado y se escribe en `.env` (si existe). No hace falta ejecutar el script a mano. |
| **No generar reporte tras cada doc** | `INGEST_DEFER_REPORT_GENERATION=true` | Durante la ingesta no se llama al LLM por cada documento indexado; los reportes se generan con el job de las 23:00. Muy útil en ingesta masiva. |
| **Throttle de reporte diario** | `INGEST_REPORT_THROTTLE_MINUTES=10` | Con DEFER=false: regenerar el reporte de una fecha como máximo cada 10 min. Reduce llamadas al LLM cuando indexas muchos archivos del mismo día. |

Añadir en `.env` cuando quieras priorizar velocidad o autoajuste:
```bash
# Valor fijo o automático por heurística en cada arranque
INGEST_PARALLEL_WORKERS=2
# INGEST_PARALLEL_WORKERS=auto

# Que el backend calcule y guarde el óptimo al arrancar (y lo use en esta ejecución)
# INGEST_AUTO_TUNE_ON_START=true

INGEST_DEFER_REPORT_GENERATION=true
```

### 5.1 Cuántos workers paralelos soporta mi sistema

El script `suggest_parallel_workers.py` combina **heurística** (CPU y RAM) y, opcionalmente, un **benchmark real** con el mismo modelo de embeddings que usa el backend:

```bash
cd app

# Solo heurística (rápido; no carga el modelo)
python scripts/suggest_parallel_workers.py

# Benchmark real: carga el modelo, simula documentos, mide tiempo con 1, 2, 3, 4 workers
python scripts/suggest_parallel_workers.py --benchmark

# Escribir el valor recomendado en .env
python scripts/suggest_parallel_workers.py --benchmark --set-env
```

- **Sin `--benchmark`**: usa número de CPUs y RAM (si está disponible) y sugiere un valor conservador.
- **Con `--benchmark`**: requiere el mismo entorno que el backend (p. ej. ejecutar dentro del contenedor o en un venv con las mismas dependencias). Descarga el modelo si no está en caché y mide throughput (docs/min) con 1, 2, 3 y 4 workers; recomienda el que más rinda.
- **`--set-env`**: actualiza o añade `INGEST_PARALLEL_WORKERS=<recomendado>` en tu `.env`.

Para ejecutar el benchmark en el mismo entorno que el backend (mismo modelo y GPU/CPU), puedes usar el contenedor montando el directorio de scripts o ejecutando desde el host con un venv que tenga `sentence-transformers` y el mismo `EMBEDDING_MODEL` que el backend. Ejemplo desde el host (con dependencias instaladas):

```bash
python scripts/suggest_parallel_workers.py --benchmark --set-env
```

---

## 6. Referencia rápida

| Acción | Comando / Acción |
|--------|-------------------|
| Carga masiva (150 PDFs en `/docs/pdfs`) | `python scripts/bulk_upload.py /docs/pdfs` (con env o args de login) |
| Activar inbox | `INBOX_DIR=/app/inbox` en `.env`, volumen `./local-data/inbox:/app/inbox` en compose. Escaneo al arranque + cada 5 min. |
| Ver logs de procesamiento | `docker compose logs -f backend` |
| Comprobar documentos indexados | UI → Documents o `GET /api/documents` con token |
| Reset para re-ingesta limpia | `./scripts/reset_for_reingest.sh` (opcional `--qdrant`, `--requeue-inbox` para reindexar lo que estaba en inbox) |
| **Reset completo + inbox + rebuild** (prioridad AI-DLC) | Ver §4.1: down → limpiar datos → mover processed→inbox → `build --no-cache backend frontend` → up |
| Acelerar inbox | `INGEST_PARALLEL_WORKERS=2`, `INGEST_DEFER_REPORT_GENERATION=true` |
| Cola insights + optimización OpenAI | `INSIGHTS_QUEUE_ENABLED=true`, `INSIGHTS_THROTTLE_SECONDS`, `INSIGHTS_MAX_RETRIES`. Ver OPENAI_RATE_LIMITS_AND_USAGE.md §0 (tarea prioritaria AI-DLC). |
| Sugerir workers para tu máquina | `python scripts/suggest_parallel_workers.py` (opcional `--benchmark --set-env`) |

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación: BR-09, BR-10, UC-06, UC-07, guía de ingesta | AI-DLC |
| 2026-03-02 | 1.1 | §4 Reset para re-ingesta (§4), §5 Ingesta más rápida (paralelo + diferir reporte) | AI-DLC |
| 2026-03-02 | 1.2 | §5 y §6: enlace a tarea prioritaria AI-DLC (barra de estado, indexado, ingesta LLM, optimización OpenAI) en OPENAI_RATE_LIMITS_AND_USAGE.md §0 | AI-DLC |
| 2026-03-02 | 1.3 | §4.1 Procedimiento completo (prioridad AI-DLC): reset + mover a inbox + recrear front/back; §6 referencia rápida | AI-DLC |
