# Base image for CUDA-enabled backend builds
# Includes system deps, Java (for Tika), rclone, and PyTorch CUDA wheels
FROM python:3.11-slim

ENV HF_HOME=/root/.cache/huggingface \
    TRANSFORMERS_CACHE=/root/.cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/root/.cache/huggingface

WORKDIR /opt/newsanalyzer

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
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# rclone for backups + model syncs
RUN curl -fsSL https://rclone.org/install.sh | bash

RUN pip install --upgrade pip setuptools wheel

# PyTorch CUDA stack is the heaviest layer; keep it here
ARG TORCH_INDEX_URL=https://download.pytorch.org/whl/cu121
ARG TORCH_VERSION=2.6.0
ARG TORCHVISION_VERSION=0.21.0
ARG TORCHAUDIO_VERSION=2.6.0
RUN pip install --no-cache-dir --index-url ${TORCH_INDEX_URL} \
    torch==${TORCH_VERSION} \
    torchvision==${TORCHVISION_VERSION} \
    torchaudio==${TORCHAUDIO_VERSION}

LABEL org.opencontainers.image.source="news-analyzer" \
      org.opencontainers.image.description="CUDA base for fast backend rebuilds" \
      org.opencontainers.image.version="2026.03"
