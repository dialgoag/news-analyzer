#!/bin/bash
# Build rápido para desarrollo
# Por defecto: CPU (Mac, Linux sin GPU) - 5-8 min
# Con GPU: COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml ./build.sh
set -e
cd "$(dirname "$0")"

# GPU: usar override si GPU_TYPE=nvidia o si hay nvidia-smi
BASE_CPU_TAG=${BASE_CPU_TAG:-newsanalyzer-base:cpu}
BASE_CUDA_TAG=${BASE_CUDA_TAG:-newsanalyzer-base:cuda}

ensure_base_image() {
    local dockerfile=$1
    local tag=$2

    if docker image inspect "$tag" >/dev/null 2>&1; then
        echo "✅ Base $tag ya disponible"
    else
        echo "⏳ Construyendo base $tag (primer build puede tardar 20-30 min)..."
        docker build -f "$dockerfile" -t "$tag" .
    fi
}

if [[ "${GPU_TYPE}" == "nvidia" ]] || ([[ "$OSTYPE" != "darwin"* ]] && command -v nvidia-smi &>/dev/null); then
    echo "🔧 Build con CUDA (NVIDIA)"
    ensure_base_image backend/docker/base/cuda/Dockerfile "$BASE_CUDA_TAG"
    export COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml
else
    echo "🔧 Build CPU (macOS o sin GPU)"
    ensure_base_image backend/docker/base/cpu/Dockerfile "$BASE_CPU_TAG"
fi

docker compose build backend
echo "✅ Backend construido. Ejecutar: docker compose up -d"
