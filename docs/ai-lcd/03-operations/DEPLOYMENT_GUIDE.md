# Deployment Guide - NewsAnalyzer-RAG

> Guía paso a paso para desplegar el sistema

**Última actualización**: 2026-03-27
**Fase AI-DLC**: 03-operations
**Audiencia**: DevOps, Admin

---

## 0. Docker Compose unificado

**Por defecto**:
```bash
docker compose up -d   # CPU (Mac, Linux sin GPU)
```

**Con GPU NVIDIA**:
```bash
COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml docker compose up -d
```

Ver [app/docs/DOCKER.md](../../app/docs/DOCKER.md) para guía completa.

---

## 1. Requisitos

| Recurso | Mínimo | Recomendado |
|---------|--------|-------------|
| **OS** | Ubuntu 20.04+ | Ubuntu 22.04 |
| **CPU** | 4 cores | 8 cores |
| **RAM** | 16 GB | 32 GB |
| **Disco** | 50 GB | 100 GB |
| **GPU** | No requerida (CPU mode) | NVIDIA 8-16GB VRAM |
| **Docker** | 24.0+ | Última |
| **Docker Compose** | v2.26+ | Última |

**Nota**: En Mac con Docker Desktop funciona para desarrollo/testing (imágenes x86 en emulación).

## 2. Despliegue Rápido (Desarrollo Local)

```bash
# 1. Clonar el proyecto
cd /path/to/workspace
git clone <repo-url> NewsAnalyzer-RAG
cd app

# 2. Crear .env desde template
cp .env.example .env

# 3. Editar .env con tu configuración
# Ver ENVIRONMENT_CONFIGURATION.md para detalle de cada variable

# 4. Levantar servicios (CPU por defecto; ver §0 para GPU)
docker compose up -d

# 5. Ver logs (esperar "Application startup complete")
docker compose logs -f backend

# 6. Obtener password de admin
docker compose logs backend | grep "Password:"

# 7. Acceder
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
```

## 2.5 Shutdown ordenado y rebuild (backend / frontend)

Antes de **reconstruir** el backend (cambios de pipeline o migraciones), conviene un shutdown que revierta colas y libere `worker_tasks` activos:

- **Guía única**: [ORDERLY_SHUTDOWN_AND_REBUILD.md](./ORDERLY_SHUTDOWN_AND_REBUILD.md) (`POST /api/workers/shutdown`, `docker compose build`, workaround si `ocr-service` está *unhealthy*).

## 3. Despliegue Producción (Servidor con Dominio)

### 3.1 Configurar .env para producción

```bash
# En .env:
GPU_TYPE=cpu
# COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml  # si hay GPU
VITE_API_URL=https://api.tudominio.com
BACKEND_PORT=8000
FRONTEND_PORT=3000

# Seguridad (OBLIGATORIO en producción)
JWT_SECRET_KEY=$(openssl rand -hex 32)
ALLOWED_ORIGINS=https://tudominio.com

# OpenAI
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...tu-api-key...
OPENAI_MODEL=gpt-4o
```

### 3.2 Reverse Proxy (Nginx o Caddy)

Necesitas un reverse proxy que:
- Sirva HTTPS (Let's Encrypt)
- Rutee `tudominio.com` → frontend (:3000)
- Rutee `api.tudominio.com` → backend (:8000)

### 3.3 Crear usuarios

```bash
# 1. Obtener token de admin
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "PASSWORD_DEL_LOG"}'

# 2. Crear usuario familiar (read-only)
curl -X POST http://localhost:8000/api/admin/users \
  -H "Authorization: Bearer TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "mama",
    "email": "mama@email.com",
    "password": "password-seguro",
    "role": "user"
  }'
```

## 4. Comandos de Gestión

```bash
# Iniciar
docker compose up -d

# Parar
docker compose down

# Ver logs
docker compose logs -f backend

# Reiniciar backend (tras cambiar .env)
docker compose down && docker compose up -d

# Limpiar todo (BORRA DATOS)
docker compose down -v
```

## 5. Verificación Post-Despliegue

```bash
# Health check
curl http://localhost:8000/health

# System config
curl http://localhost:8000/api/system/info

# Test login
curl -X POST http://localhost:8000/api/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "..."}'
```

---

## Protocolo de Despliegue Seguro (Rebuild)

Protocolo obligatorio para cualquier rebuild/redeploy del backend.
Evita tareas huérfanas, estados inconsistentes y pérdida de progreso.

### Pipeline State Machine

```
document_status.status sigue la convención {stage}_{state}:

  upload_pending → upload_processing → upload_done
    → ocr_pending → ocr_processing → ocr_done
    → chunking_pending → chunking_processing → chunking_done
    → indexing_pending → indexing_processing → indexing_done
    → (insights per news_item: pending → generating → done)
    → completed

Terminal: error, paused

Transiciones (ejemplo: stage=indexing, prev=chunking):
  {prev}_done          → master scheduler crea task {stage}
  task pending          → master scheduler asigna worker
  worker inicia         → {stage}_processing
  worker termina        → {stage}_done
  crash/restart         → rollback {stage}_processing → {prev}_done
```

### Paso 1: Parar backend

```bash
cd app
docker compose stop backend
```

### Paso 2: Limpiar BD (PostgreSQL sigue vivo)

Ejecutar cada comando por separado contra `rag-postgres`:

```bash
# 1) Borrar worker_tasks huérfanos (no hay threads vivos)
docker exec rag-postgres psql -U raguser -d rag_enterprise \
  -c "DELETE FROM worker_tasks WHERE status IN ('started', 'assigned')"

# 2) processing_queue: processing → pending
docker exec rag-postgres psql -U raguser -d rag_enterprise \
  -c "UPDATE processing_queue SET status = 'pending' WHERE status = 'processing'"

# 3) Rollback document_status: {stage}_processing → {prev_stage}_done
docker exec rag-postgres psql -U raguser -d rag_enterprise \
  -c "UPDATE document_status SET status = 'upload_done',   error_message = NULL WHERE status = 'ocr_processing'" \
  -c "UPDATE document_status SET status = 'ocr_done',      error_message = NULL WHERE status = 'chunking_processing'" \
  -c "UPDATE document_status SET status = 'chunking_done', error_message = NULL WHERE status = 'indexing_processing'" \
  -c "UPDATE document_status SET status = 'indexing_done',  error_message = NULL WHERE status = 'insights_processing'"

# 4) Insights huérfanos: generating → pending
docker exec rag-postgres psql -U raguser -d rag_enterprise \
  -c "UPDATE news_item_insights SET status = 'pending', error_message = NULL WHERE status = 'generating'"

# 5) (Opcional) Insights con error → pending para reprocesar
docker exec rag-postgres psql -U raguser -d rag_enterprise \
  -c "UPDATE news_item_insights SET status = 'pending', error_message = NULL WHERE status = 'error'"

# 6) (Opcional) Limpiar worker_tasks históricos en error
docker exec rag-postgres psql -U raguser -d rag_enterprise \
  -c "DELETE FROM worker_tasks WHERE status = 'error'"
```

### Paso 3: Verificar estado limpio

```bash
docker exec rag-postgres psql -U raguser -d rag_enterprise \
  -c "SELECT status, COUNT(*) FROM document_status GROUP BY status ORDER BY COUNT(*) DESC" \
  -c "SELECT status, COUNT(*) FROM news_item_insights GROUP BY status ORDER BY COUNT(*) DESC" \
  -c "SELECT task_type, status, COUNT(*) FROM processing_queue WHERE status != 'completed' GROUP BY task_type, status" \
  -c "SELECT status, COUNT(*) FROM worker_tasks WHERE status NOT IN ('completed') GROUP BY status"
```

Esperado: cero `*_processing` en document_status, cero `generating` en insights,
cero `processing` en processing_queue, cero `started/assigned` en worker_tasks.

### Paso 4: Rebuild y restart

```bash
docker compose up -d --build backend
```

### Paso 5: Verificar startup recovery

```bash
# Esperar ~30s a que arranque, luego:
docker logs rag-backend --tail 30 | grep -i "startup\|recovery\|cleanup"
```

El log debe mostrar `Startup recovery: no orphaned tasks found` (porque ya limpiamos).

### Notas

- El backend incluye `detect_crashed_workers()` que hace esta misma limpieza
  automáticamente al arrancar. El protocolo manual es una red de seguridad.
- El PASO 0 del master scheduler también detecta workers >5min y hace rollback
  durante la ejecución normal (runtime crash recovery).
- Los 12 docs en `error` con `OCR returned empty text` son legítimos y no se
  reprocesan (no tienen texto útil).

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación inicial | AI-DLC |
| 2026-03-15 | 1.1 | Protocolo de despliegue seguro (rebuild) | AI-DLC |
| 2026-03-15 | 1.2 | Docker Compose unificado (CPU default, GPU override) | AI-DLC |
