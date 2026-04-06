# Base image for CPU-only backend builds
# Contains system deps, rclone, pip upgrades, and pinned PyTorch CPU wheels
FROM python:3.11-slim

ENV HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface

WORKDIR /opt/newsanalyzer

# Core system dependencies reused across all CPU builds
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    curl \
    unzip \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# rclone (downloads/backups) rarely changes, so keep it in base layer
RUN curl -fsSL https://rclone.org/install.sh | bash

# Keep pip toolchain up to date
RUN pip install --upgrade pip setuptools wheel

# Heavyweight PyTorch CPU wheels (stable pin to avoid frequent rebuilds)
ARG PYTORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu
ARG TORCH_VERSION=2.6.0
ARG TORCHVISION_VERSION=0.21.0
ARG TORCHAUDIO_VERSION=2.6.0
RUN pip install --no-cache-dir --index-url ${PYTORCH_CPU_INDEX_URL} \
    torch==${TORCH_VERSION} \
    torchvision==${TORCHVISION_VERSION} \
    torchaudio==${TORCHAUDIO_VERSION}

LABEL org.opencontainers.image.source="news-analyzer" \
      org.opencontainers.image.description="CPU base for fast backend rebuilds" \
      org.opencontainers.image.version="2026.03"
