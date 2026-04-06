# GPU/CUDA Dockerfile - Para Linux con NVIDIA GPU
# Usa imagen base newsanalyzer-base:cuda con dependencias pesadas preinstaladas
ARG BASE_IMAGE=newsanalyzer-base:cuda
FROM ${BASE_IMAGE}

WORKDIR /app

# Dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Backend code
COPY backend/app.py .
COPY backend/rag_pipeline.py .
COPY backend/ocr_service.py .
COPY backend/ocr_service_ocrmypdf.py .
COPY backend/embeddings_service.py .
COPY backend/qdrant_connector.py .
COPY backend/auth.py .
COPY backend/auth_models.py .
COPY backend/database.py .
COPY backend/middleware.py .
COPY backend/backup_service.py .
COPY backend/backup_models.py .
COPY backend/backup_scheduler.py .
COPY backend/pipeline_states.py .
# worker_pool.py REMOVED in Fase 5C - GenericWorkerPool eliminated
COPY backend/migration_runner.py .
COPY backend/file_ingestion_service.py .
COPY backend/pipeline_runtime_store.py .
COPY backend/insights_pipeline_control.py .

# Hexagonal Architecture directories (REQ-021)
COPY backend/core/ core/
COPY backend/adapters/ adapters/

COPY backend/migrations/ ./migrations/
COPY backend/entrypoint.sh .
RUN chmod +x /app/entrypoint.sh

RUN mkdir -p /app/uploads /app/data /app/backups /app/inbox

EXPOSE 8000

# GPU: CUDA visible (override en compose nvidia)
ENV CUDA_VISIBLE_DEVICES=0
ENV OLLAMA_HOST=ollama
ENV OLLAMA_PORT=11434

HEALTHCHECK --interval=30s --timeout=120s --start-period=120s --retries=5 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]
