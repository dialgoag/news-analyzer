#!/bin/bash
# Build rápido para desarrollo
# Por defecto: CPU (Mac, Linux sin GPU) - 5-8 min
# Con GPU: COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml ./build.sh
set -e
cd "$(dirname "$0")"

# GPU: usar override si GPU_TYPE=nvidia o si hay nvidia-smi
if [[ "${GPU_TYPE}" == "nvidia" ]] || ([[ "$OSTYPE" != "darwin"* ]] && command -v nvidia-smi &>/dev/null); then
    echo "🔧 Build con CUDA (NVIDIA)"
    export COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml
else
    echo "🔧 Build CPU (macOS o sin GPU)"
fi

docker compose build backend
echo "✅ Backend construido. Ejecutar: docker compose up -d"
