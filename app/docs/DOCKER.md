# Guía Docker - NewsAnalyzer-RAG

> Flujo unificado de Docker Compose para CPU (Mac/Linux) y GPU (NVIDIA/AMD)

**Última actualización**: 2026-03-15

---

## 1. Resumen

| Plataforma | Comando | Dockerfile | OCR |
|------------|---------|------------|-----|
| **Mac / Linux sin GPU** | `docker compose up -d` | `Dockerfile.cpu` | ocrmypdf (ocr-service) |
| **Linux + NVIDIA** | `COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml docker compose up -d` | `Dockerfile` (CUDA) | tika |
| **Linux + AMD ROCm** | `COMPOSE_FILE=docker-compose.yml:docker-compose.amd.yml docker compose up -d` | `Dockerfile.cpu` | ocrmypdf |

El compose principal (`docker-compose.yml`) usa **CPU por defecto**. Los overrides de GPU son opcionales.

---

## 2. Archivos

| Archivo | Propósito |
|---------|-----------|
| `docker-compose.yml` | Compose principal. Backend con `Dockerfile.cpu`, OCR via ocr-service |
| `docker-compose.nvidia.yml` | Override: backend con CUDA, Tika embebido, GPU asignada |
| `docker-compose.amd.yml` | Override: Ollama con imagen ROCm, dispositivos `/dev/kfd`, `/dev/dri` |
| `backend/Dockerfile.cpu` | Imagen CPU: PyTorch CPU, sin Java/Tika, ~5-8 min build |
| `backend/Dockerfile` | Imagen CUDA: PyTorch CUDA 12.8, Tika, ~15-20 min build |
| `build.sh` | Script de build: detecta GPU o usa `GPU_TYPE` del `.env` |

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
