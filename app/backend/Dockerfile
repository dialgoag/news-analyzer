# GPU/CUDA Dockerfile - Para Linux con NVIDIA GPU
# Usar con: COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml
# Build: ~15-20 min (PyTorch CUDA es grande)
FROM python:3.11-slim

ENV HF_HOME=/root/.cache/huggingface
ENV TRANSFORMERS_CACHE=/root/.cache/huggingface
ENV SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface

WORKDIR /app

# Dependencies del sistema (igual que CPU)
RUN apt-get update && apt-get install -y \
    git libsm6 libxext6 libxrender-dev libgl1 libglib2.0-0 libgomp1 \
    curl unzip \
    && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://rclone.org/install.sh | bash

# PyTorch CUDA 12.1 (vs CPU en Dockerfile.cpu)
RUN pip install --no-cache-dir torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

RUN pip install --upgrade pip setuptools wheel

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
COPY backend/worker_pool.py .
COPY backend/migration_runner.py .
COPY backend/file_ingestion_service.py .
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
