# Guía Docker - NewsAnalyzer-RAG

> Flujo unificado de Docker Compose para CPU (Mac/Linux) y GPU (NVIDIA/AMD)

**Última actualización**: 2026-03-20

---

## 0. Convención: “producción” local y qué es desplegar

En este proyecto, **“producción”** suele significar el **stack Docker corriendo en tu máquina** (backend, frontend, bases de datos, etc. en `localhost`), no un servidor remoto—salvo que en otro doc se indique un entorno concreto.

**Mandar cambios a esa producción local** = volver a **construir las imágenes** de los servicios que tocaste (sobre todo `frontend` y/o `backend`) y **sustituir los contenedores actuales**: pararlos y eliminarlos, luego levantar otros con las imágenes nuevas. En la práctica:

1. `docker compose down` — baja y **elimina** los contenedores del compose (no borra volúmenes por defecto).
2. `docker compose build …` — reconstruye solo lo necesario (o `--no-cache` si quieres build limpio).
3. `docker compose up -d` — crea y arranca contenedores nuevos.

Los **datos persistentes** (Postgres, Qdrant, uploads, etc.) viven en **volúmenes**; `docker compose down` **no** los destruye. Para borrar también datos habría que usar flags explícitos (`-v`) o `docker volume rm`—solo si sabes lo que haces.

Ejemplo típico tras cambios de UI o API:

```bash
cd app
docker compose down
docker compose build --no-cache frontend backend
docker compose up -d
```

**Atajo (raíz del repo)**: `Makefile` — `make help` lista todo. Resumen:

| Objetivo | Comando |
|----------|---------|
| Despliegue completo (backend+frontend, sin caché) | `make deploy` |
| Solo frontend (sin caché, recrea contenedor) | `make redeploy-front` |
| Solo backend (sin caché, recrea contenedor) | `make redeploy-back` |
| Levantar **todo** el stack | `make run-all` (o `make up`) |
| Entorno **sin** backend ni frontend (Postgres, OCR, Qdrant, Ollama) | `make run-env` |

Build con caché (más rápido): `make rebuild-frontend` / `make rebuild-backend`, o `cd app && docker compose build … && docker compose up -d …`.

---

## 1. Resumen

| Plataforma | Comando | Dockerfile | OCR |
|------------|---------|------------|-----|
| **Mac / Linux sin GPU** | `docker compose up -d` | `backend/Dockerfile.cpu` | ocrmypdf (ocr-service) |
| **Linux + NVIDIA** | `COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml docker compose up -d` | `backend/docker/cuda/Dockerfile` | tika |
| **Linux + AMD ROCm** | `COMPOSE_FILE=docker-compose.yml:docker-compose.amd.yml docker compose up -d` | `backend/Dockerfile.cpu` | ocrmypdf |

El compose principal (`docker-compose.yml`) usa **CPU por defecto**. Los overrides de GPU son opcionales.

---

## 2. Archivos

| Archivo | Propósito |
|---------|-----------|
| `docker-compose.yml` | Compose principal. Backend con `backend/Dockerfile.cpu`, OCR via ocr-service |
| `docker-compose.nvidia.yml` | Override: backend con CUDA, Tika embebido, GPU asignada |
| `docker-compose.amd.yml` | Override: Ollama con imagen ROCm, dispositivos `/dev/kfd`, `/dev/dri` |
| `backend/Dockerfile.cpu` | Imagen CPU (deriva de `newsanalyzer-base:cpu`) |
| `backend/docker/cuda/Dockerfile` | Imagen CUDA (deriva de `newsanalyzer-base:cuda`) |
| `backend/docker/base/cpu/Dockerfile` | Imagen base CPU (apt + rclone + PyTorch CPU) |
| `backend/docker/base/cuda/Dockerfile` | Imagen base CUDA (apt + Java + PyTorch CUDA) |
| `build.sh` | Script de build: detecta GPU o usa `GPU_TYPE` y construye la base si falta |

---

### 2.1 Imágenes base y flujo de build

- **Objetivo**: mover las capas lentas (apt, Java, PyTorch) a una imagen reutilizable (`newsanalyzer-base:{cpu|cuda}`) y dejar que el Dockerfile copie solo código + `pip install -r requirements.txt`.
- **Construcción**:
  - CPU (default): `docker build -f backend/docker/base/cpu/Dockerfile -t newsanalyzer-base:cpu .`
  - CUDA: `docker build -f backend/docker/base/cuda/Dockerfile -t newsanalyzer-base:cuda .`
- `app/build.sh` y `../complete_build.sh` verifican automáticamente si la base existe y la construyen (primer build ≈20‑30 min, rebuilds ≈2‑3 min).
- Puedes sobreescribir los tags con `BASE_CPU_TAG` / `BASE_CUDA_TAG` al invocar los scripts si necesitas versionarlos.
- Los Dockerfiles finales usan `FROM newsanalyzer-base:{cpu|cuda}`; al construir con el builder clásico de Docker (ver abajo) se reutiliza la imagen local sin intentar pull del registry. Si necesitas apuntar a un registry distinto, pasa `--build-arg BASE_IMAGE=<registry>/<imagen>:tag`.
- Como Docker Compose usa BuildKit por defecto (que siempre intenta bajar todas las bases), los targets `make build/deploy/...` exportan `DOCKER_BUILDKIT=0` y `COMPOSE_DOCKER_CLI_BUILD=0` para forzar el builder clásico y reutilizar las imágenes locales. Si prefieres BuildKit necesitas publicar las bases en un registry accesible y ajustar `BASE_IMAGE`.

---

## 3. Uso

### 3.1 Mac o Linux sin GPU (por defecto)

```bash
cd app
cp .env.example .env
# Editar .env si hace falta
docker compose up -d
```

### 3.2 Linux con NVIDIA

```bash
cd app
export COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml
docker compose up -d
```

O en `.env`:
```env
COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml
```

### 3.3 Linux con AMD ROCm

```bash
cd app
export COMPOSE_FILE=docker-compose.yml:docker-compose.amd.yml
docker compose up -d
```

### 3.4 Build rápido (desarrollo)

```bash
cd app
./build.sh
# Luego: docker compose up -d
```

`build.sh` usa `GPU_TYPE` del `.env` o detecta `nvidia-smi` en Linux.
Si la imagen base correspondiente no existe, la construye antes de lanzar el `docker compose build backend`.

### 3.5 Rebuild tras cambios en código (backend/frontend)

Equivale a **desplegar en producción local**: ver **§0** (bajar contenedores, rebuild, subir de nuevo).

```bash
cd app
docker compose down
docker compose build --no-cache backend frontend
docker compose up -d
```

Usar tras fixes de dashboard, API, etc. Ver `docs/ai-lcd/CONSOLIDATED_STATUS.md` para el historial de cambios.

---

## 4. Servicios

| Servicio | Puerto | Descripción |
|----------|--------|-------------|
| frontend | 3000 | React + Vite |
| backend | 8000, 9998 | FastAPI, RAG, OCR |
| ocr-service | 9999 | OCRmyPDF (Tesseract) |
| qdrant | 6333 | Vector DB |
| ollama | 11434 | LLM local |

---

## 5. Variables de entorno relevantes

| Variable | Default | Descripción |
|----------|---------|-------------|
| `GPU_TYPE` | `cpu` | Para `build.sh`: `cpu`, `nvidia`, `amd` |
| `COMPOSE_FILE` | (ninguno) | Override: `docker-compose.yml:docker-compose.nvidia.yml` |
| `OCR_ENGINE` | `ocrmypdf` (CPU) / `tika` (NVIDIA) | Motor OCR |
| `VITE_API_URL` | `http://localhost:8000` | URL del backend para el frontend |
| `BACKEND_PORT` | `8000` | Puerto del backend |
| `FRONTEND_PORT` | `3000` | Puerto del frontend |
| `EMBEDDING_DEVICE` | auto (cuda si disponible) | Forzar `cuda` o `cpu` para embeddings |

Ver `.env.example` y `docs/ai-lcd/03-operations/ENVIRONMENT_CONFIGURATION.md` para el resto.

---

## 6. Diferencias Dockerfile.cpu vs Dockerfile

| Aspecto | Dockerfile.cpu | Dockerfile (CUDA) |
|---------|----------------|-------------------|
| Base | python:3.11-slim | nvidia/cuda:12.9.0-runtime-ubuntu22.04 |
| PyTorch | CPU | CUDA 12.8 |
| Tika | No | Sí (embebido) |
| OCR recomendado | ocrmypdf (ocr-service) | tika o ocrmypdf |
| Tiempo build | ~5-8 min | ~15-20 min |
| Uso | Mac, Linux sin GPU | Linux con NVIDIA |

---

## 7. Troubleshooting

### Backend no arranca
- Esperar 3-5 min en primer arranque (descarga embedding model)
- Ver logs: `docker compose logs -f backend`

### GPU no detectada (NVIDIA)
```bash
nvidia-smi
docker run --rm --gpus all nvidia/cuda:12.9.0-runtime-ubuntu22.04 nvidia-smi
```

### OCR falla en Mac
- Usar `OCR_ENGINE=ocrmypdf` (default en CPU)
- Verificar que `ocr-service` esté healthy: `docker compose ps`

### Cambiar de CPU a GPU
```bash
docker compose down
export COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml
docker compose build backend
docker compose up -d
```

---

## 8. Referencias

- [DEPLOYMENT_GUIDE.md](../../docs/ai-lcd/03-operations/DEPLOYMENT_GUIDE.md) - Despliegue paso a paso
- [ENVIRONMENT_CONFIGURATION.md](../../docs/ai-lcd/03-operations/ENVIRONMENT_CONFIGURATION.md) - Variables de entorno
- [TROUBLESHOOTING_GUIDE.md](../../docs/ai-lcd/03-operations/TROUBLESHOOTING_GUIDE.md) - Problemas comunes
