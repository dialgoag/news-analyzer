# Estado Actual — NewsAnalyzer-RAG (2026-04-07)

> Radiografía breve del sistema a la fecha indicada. Usar este archivo como punto de partida antes de revisar código o planear nuevas tareas.

## Resumen ejecutivo
- **Versión viva**: Backend hexagonal Fase 5E completada (Fix #111) + migración de timestamps (Fix #112) + hardening de contenedor CPU (Fix #119).
- **En producción local**: Docker Compose (`app/docker-compose.yml`) con backend FastAPI, frontend React/Vite, PostgreSQL 17, Qdrant, Ollama opcional.
- **Prioridad activa**: REQ-021 (refactor backend) enfocado ahora en Fase 6 — traslado de routers y limpieza de stores legacy.
- **Salud**: última suite de humo ejecutada el 2026-04-07 (`smoke_1.log` + `docs/ai-lcd/artifacts/dashboard_2026-04-07_after.json`).

## Arquitectura viva
- **Backend**: `app/backend` con dominio en `core/` (entidades, repositorios) + adaptadores Postgres/Qdrant en `adapters/`. `app/backend/app.py` conserva colas/cron legacy mientras se termina la migración a routers v2 (`adapters/driving/api/v1/routers/`).
- **Frontend**: `app/frontend` (React + Vite) consume `/api/*` ya servidos por routers modulares (`documents`, `workers`, `dashboard`, `admin`).
- **Persistencia**: PostgreSQL 17 (documentos, news, timings) + Qdrant para vectores (chunks e insights). OCR usa OCRmyPDF + Tesseract (spa+eng); embeddings BAAI/bge-m3.
- **Infra**: Dockerfiles separados CPU/GPU (`app/backend/Dockerfile.cpu`, `app/backend/docker/base/cuda/Dockerfile`). CPU corre como usuario no-root usando `APP_UID/GID`.

## Operación y despliegue
1. `cp app/.env.example app/.env` y completar secretos (JWT, OpenAI, etc.).
2. `make build-backend-cpu` o `docker compose build backend` (ver `Makefile`).
3. `docker compose up -d` en `app/`.
4. Revisar `docker compose logs backend` hasta ver "Application startup complete".
5. Credenciales iniciales: `docker compose logs backend | grep "Password"`.

Referencias complementarias:
- `docs/ai-lcd/03-operations/DEPLOYMENT_GUIDE.md`
- `docs/ai-lcd/03-operations/INGEST_GUIDE.md`
- `docs/ai-lcd/03-operations/TROUBLESHOOTING_GUIDE.md`

## Evidencia y monitoreo
- **Smoke API**: `smoke_1.log` (token admin + `scripts/run_api_smoke.sh`). Resultado almacenado en `docs/ai-lcd/artifacts/dashboard_2026-04-07_after.json`.
- **Workers**: métricas expuestas vía `GET /api/workers/status` tras migrar a `WorkerRepository`.
- **Trazabilidad**: `document_stage_timing` concentra los hitos `upload/ocr/chunking/indexing/insights` por documento/news. Scripts en `app/backend/scripts/*` (ej. `check_upload_symlink_db_consistency.py`).

## Backlog inmediato
| ID | Objetivo | Estado | Próximo paso |
|----|----------|--------|--------------|
| **PEND-018** | Unificar estados `news_item_insights` al canon `insights_*`. | Planeado | Migración con parada corta + actualización de repositorios/routers.
| **PEND-013** | Pool Postgres robusto (sin `PoolError`). | Mitigación aplicada | Validar estabilidad en carga y cerrar incidente. |
| **PEND-014** | `pipeline_runtime_kv` compatible tuple/dict. | Mitigación aplicada | Monitorear arranques y limpiar banderas temporales. |
| **PEND-015** | Validación temprana de archivos no-PDF antes de OCR. | Pendiente | Añadir verificación de mimetype + clasificación de error permanente. |
| **REQ-014** | Mejoras UX dashboard. | Pendiente | Definir alcance UI tras estabilizar API. |
| **Backlog #7** | Persistir `extracted_data/analysis` de insights para reportes. | No iniciado | Diseñar esquema JSONB + refactor de reportes (ver notas en `DECISION_LOG.md`). |

> Mantener esta tabla corta (≤7 entradas). Archivar tareas completadas en los PRs y, si amerita, en `docs/DECISION_LOG.md`.

## Riesgos conocidos
- Mezcla temporal de rutas legacy en `app/backend/app.py`; retirar después de concluir Fase 6 para evitar drift.
- Retries manuales pueden despertar documentos legacy; usar guardrails (`force_legacy=true`) descritos en `INGEST_GUIDE.md`.
- OCR puede recibir archivos inválidos; mientras se implementa PEND-015, revisar carpeta `app/local-data/uploads/PEND-016/` antes de reintentar.

## Cómo usar este documento
1. Actualiza la fecha y el bloque "Resumen ejecutivo" cada vez que cambie el estado real de la app.
2. Mantén la tabla de backlog sincronizada con issues/PEND/REQ vigentes.
3. Registra decisiones y justificaciones detalladas en `docs/DECISION_LOG.md` y mantén allí los enlaces a evidencia.
