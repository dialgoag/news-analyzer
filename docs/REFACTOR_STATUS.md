# Estado del Refactor - Componentes Perdidos y Recuperables

**Fecha**: 2026-03-15  
**Contexto**: Refactor RAG-Enterprise submodule → app/ (código propio). Pérdida de local-data y componentes durante el proceso.

---

## 1. Estructura Actual vs. Esperada

### Estructura actual
```
app/
├── backend/                    # Código Python FastAPI (app.py, ocr_service.py, etc.)
├── frontend/
├── ocr-service/               # Servicio OCR independiente (OCRmyPDF + Tesseract)
├── docker-compose.yml         # Qdrant + Ollama + ocr-service + backend + frontend
├── .env.example
├── local-data/
└── temp/
```

### Tu versión modificada (perdida) tenía
- **PostgreSQL** (no SQLite) — migración REQ-008
- **ocr-service/** — Servicio Docker OCRmyPDF + Tesseract (puerto 9999)
- **backend/ocr_service_ocrmypdf.py** — Adaptador para el servicio OCR
- **docker-compose** con: postgres, qdrant, ocr-service, backend, frontend
- **app.py** ~5956 líneas — Master Pipeline, workers, event-driven
- **local-data/** — 231 docs, 2100 news, 2100 insights, PostgreSQL, Qdrant

---

## 2. Estructura plana

- `app/backend/` = código Python (app.py, database.py, etc.)
- `app/ocr-service/` = servicio OCR independiente
- `app/docker-compose.yml` = raíz de despliegue

El docker-compose usa `context: .` y para GPU referencia `dockerfile: backend/docker/cuda/Dockerfile`,
por eso existe la carpeta anidada.

---

## 3. Componentes perdidos — Recuperables desde documentación

### 3.1 ocr-service/ (RECREADO) ✅
- **Origen**: docs/OCR_MIGRATION_PLAN.md
- **Ubicación**: app/ocr-service/
- **Contenido**: Dockerfile, app.py (FastAPI + OCRmyPDF + PyMuPDF), requirements.txt
- **Estado**: Creado 2026-03-15

### 3.2 ocr_service_ocrmypdf.py (RECREADO) ✅
- **Origen**: docs/OCR_MIGRATION_PLAN.md, docs/ai-lcd/CONSOLIDATED_STATUS.md
- **Función**: Cliente HTTP que llama al servicio ocr-service
- **Estado**: Creado 2026-03-15

### 3.3 docker-compose con ocr-service ✅
- Tu versión tenía bind mounts a local-data
- El upstream usa volúmenes nombrados
- **Estado**: Se añade ocr-service; postgres requiere migración de database.py (SQLite→PostgreSQL)

---

## 4. Componentes NO recuperables (sin backup)

| Componente | Descripción |
|------------|-------------|
| **local-data/** | PostgreSQL, Qdrant, backups, PDFs subidos |
| **.env** | Configuración con credenciales |
| **app.py modificado** | ~5956 líneas, Master Pipeline, workers |
| **database.py PostgreSQL** | Migración completa |
| **Otras modificaciones** | pipeline_states.py, worker_pool.py, etc. |

---

## 5. Docker: CPU vs CUDA

- **Dockerfile.cpu**: Para macOS y Linux sin GPU. Sin CUDA, sin Tika. Usar `OCR_ENGINE=ocrmypdf`.
- **Dockerfile**: CUDA, Tika embebido. Para servidores con NVIDIA.
- **docker-compose.yml**: Compose principal, usa Dockerfile.cpu por defecto.
- **docker-compose.nvidia.yml**: Override para GPU NVIDIA (cambia a Dockerfile CUDA + Tika).
- ~~docker-compose.cpu.yml~~: Eliminado (redundante, el principal ya es CPU). Ver `app/docs/DOCKER.md`.

## 6. Recuperación de archivos en macOS

Ver: [docs/MACOS_RECOVERY.md](MACOS_RECOVERY.md)

---

**Nota**: En abril 2026 se restauró la optimización con imágenes base:
`backend/docker/base/cpu|cuda` generan `newsanalyzer-base:{cpu,cuda}` y
los Dockerfiles (`backend/Dockerfile.cpu`, `backend/docker/cuda/Dockerfile`) ahora derivan de ellas.
