# Shutdown ordenado y rebuild (Backend / Frontend)

> **Fuente única** para parar workers con coherencia en BD y reconstruir imágenes Docker.  
> **Fase**: 03-operations | **Última actualización**: 2026-03-28

---

## Cuándo usar

- Antes de **`docker compose build`** del backend (código del pipeline / workers / migraciones).
- Cuando quieras **evitar tareas colgadas** en `processing_queue` o `worker_tasks` tras un reinicio brusco.
- Opcional pero recomendado antes de recrear el contenedor `backend`.

---

## 1. Shutdown ordenado (API)

**Endpoint**: `POST /api/workers/shutdown`  
**Base URL**: misma que el backend (ej. `http://localhost:8000`).

**Autenticación**: obligatoria. Header `Authorization: Bearer <access_token>` de un usuario con rol **`admin`** (`require_admin`). Falta de cabecera Bearer → **403**; token inválido/expirado → **401**; usuario sin rol admin → **403**.

Obtener token: `POST /api/auth/login` con usuario `admin` (respuesta incluye `access_token`).

**Efectos** (ver implementación en `app/backend/app.py`):

1. Detiene `generic_worker_pool` si está activo.
2. Pasa filas `processing_queue` con `status = 'processing'` a **`pending`** (reprocesables).
3. Marca `worker_tasks` en `assigned` / `started` como **`error`** con mensaje *Shutdown ordenado…* (los filtros de análisis suelen excluirlos como errores “reales”; ver dashboard).
4. **Persiste en PostgreSQL** (`pipeline_runtime_kv`) **pausa en todos los pasos** del pipeline (OCR, chunking, indexing, insights LLM, indexado de insights). Tras reiniciar el backend, **no** se reanuda el trabajo hasta **«Reanudar todo»** en el dashboard (admin) o `PUT /api/admin/insights-pipeline` con `resume_all: true`. `POST /api/workers/start` solo levanta el pool; **no** quita las pausas.

**Ejemplo** (sustituir `$TOKEN` por el JWT del admin):

```bash
curl -sS -X POST http://localhost:8000/api/workers/shutdown \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN"
```

**Arranque manual del pool** (`POST /api/workers/start`): mismas reglas — solo **ADMIN** y Bearer token.

**Tiempo de respuesta**: puede tardar decenas de segundos si el servidor está muy cargado; no cancelar el cliente a los pocos segundos.

---

## 2. Rebuild Backend

Desde el directorio **`app/`** (donde está `docker-compose.yml`)):

```bash
cd app
docker compose build backend
docker compose up -d backend
```

Las migraciones Yoyo (p. ej. **015** — worker único; **016** — `pipeline_runtime_kv` para pausas) se aplican al arrancar el backend.

---

## 3. Rebuild Frontend

```bash
cd app
docker compose build frontend
docker compose up -d frontend
```

Tras el build, los assets llevan hash nuevo; conviene **refresco fuerte** en el navegador (evitar caché vieja).

---

## 4. Compose: dependencia `ocr-service` unhealthy

`backend` declara `depends_on: ocr-service: condition: service_healthy`. Si el OCR está en jobs largos, el healthcheck puede marcar **unhealthy** aunque el servicio funcione.

**Síntoma**: `docker compose up -d backend` falla con “dependency failed … ocr-service is unhealthy”.

**Opciones**:

- Esperar a que `ocr-service` vuelva a healthy y repetir `docker compose up -d backend`.
- Si el contenedor `rag-backend` ya fue recreado pero no arrancó: `docker start rag-backend` (workaround puntual).

---

## 5. Referencias cruzadas

| Tema | Documento |
|------|-----------|
| Fix duplicados OCR / migración 015 | `CONSOLIDATED_STATUS.md` §96 |
| Login 422 / red vacía | `CONSOLIDATED_STATUS.md` §97, §Troubleshooting abajo |
| Lista de migraciones | `02-construction/MIGRATIONS_SYSTEM.md` |
| Variables de entorno | `ENVIRONMENT_CONFIGURATION.md` |

---

## Troubleshooting rápido (login)

- **422** en `POST /api/auth/login`: el API exige `username` ≥ 3 caracteres y `password` ≥ 6 (`auth_models.py`). El frontend valida con `minLength` en el formulario.
- **`ERR_EMPTY_RESPONSE` / no hay `err.response`**: backend caído, URL incorrecta o `VITE_API_URL` distinta del API real.

---

| Fecha | Cambio |
|-------|--------|
| 2026-03-27 | Creación: shutdown API, rebuild, workaround OCR unhealthy |
| 2026-03-27 | Shutdown + start requieren JWT rol `admin` (Fix #98) |
