#!/bin/bash
# Script to complete the build and verification once base image is ready

set -e

cd /Users/diego.a/Workspace/Experiments/NewsAnalyzer-RAG/rag-enterprise/rag-enterprise-structure

echo "🔨 Esperando imagen base..."

# Wait for base image (up to 30 minutes)
max_attempts=60
attempt=0
while [ $attempt -lt $max_attempts ]; do
    if docker images | grep -q "newsanalyzer-base:latest"; then
        echo "✅ Base image ready!"
        break
    fi
    attempt=$((attempt + 1))
    if [ $((attempt % 10)) -eq 0 ]; then
        echo "⏳ Intento $attempt/$max_attempts..."
    fi
    sleep 30
done

if [ $attempt -ge $max_attempts ]; then
    echo "❌ Timeout - Base image no se construyó en 30 minutos"
    exit 1
fi

echo ""
echo "=" * 80
echo "📦 Construyendo backend con imagen base..."
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
