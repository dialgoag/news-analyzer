#!/bin/bash
# Script to complete the build and verification once base image is ready

set -e

cd "$(dirname "$0")/app"

BASE_CPU_TAG=${BASE_CPU_TAG:-newsanalyzer-base:cpu}
BASE_CUDA_TAG=${BASE_CUDA_TAG:-newsanalyzer-base:cuda}

build_base() {
    local dockerfile=$1
    local tag=$2

    if docker image inspect "$tag" >/dev/null 2>&1; then
        echo "✅ Imagen base $tag ya existe"
    else
        echo "🔨 Construyendo imagen base $tag ..."
        docker build -f "$dockerfile" -t "$tag" .
    fi
}

if [[ "${GPU_TYPE}" == "nvidia" ]]; then
    BASE_TAG=$BASE_CUDA_TAG
    BASE_FILE=backend/docker/base/cuda/Dockerfile
else
    BASE_TAG=$BASE_CPU_TAG
    BASE_FILE=backend/docker/base/cpu/Dockerfile
fi

build_base "$BASE_FILE" "$BASE_TAG"

echo ""
echo "=" * 80
echo "📦 Construyendo backend con imagen base ${BASE_TAG}..."
echo "=" * 80

docker-compose build backend

echo ""
echo "=" * 80
echo "🚀 Iniciando servicios..."
echo "=" * 80

docker-compose up -d backend

echo "⏳ Esperando a que backend esté healthy..."
sleep 15

# Verify backend is running
if docker-compose ps backend | grep -q "healthy"; then
    echo "✅ Backend is healthy"
else
    echo "⚠️  Backend starting up..."
    sleep 10
fi

echo ""
echo "=" * 80
echo "🔍 Ejecutando verificación de deduplicación..."
echo "=" * 80

docker-compose exec backend python3 /app/verify_deduplication.py

echo ""
echo "✅ COMPLETADO"
