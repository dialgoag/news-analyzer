# NewsAnalyzer — comandos Docker para producción local
# Desde la raíz del repo: make help
#
# Overrides (GPU, etc.): app/.env → COMPOSE_FILE=... o export antes de make.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

APP_DIR := app
BASE_CPU_TAG ?= newsanalyzer-base:cpu
BASE_CUDA_TAG ?= newsanalyzer-base:cuda
GPU_TYPE ?= cpu
BUILD_ENV := DOCKER_BUILDKIT=0 COMPOSE_DOCKER_CLI_BUILD=0

ifeq ($(GPU_TYPE),nvidia)
BASE_TARGET := base-cuda
else
BASE_TARGET := base-cpu
endif

# Infra + dependencias sin capa de aplicación (ver app/docker-compose.yml)
ENV_SERVICES := postgres ocr-service qdrant ollama

.PHONY: help deploy deploy-quick down up run-all run-env ps logs build \
	redeploy-front redeploy-back rebuild-frontend rebuild-backend \
	base-cpu base-cuda base-all ensure-base

.DEFAULT_GOAL := help

help:
	@echo "NewsAnalyzer — Docker (stack en $(APP_DIR)/)"
	@echo ""
	@echo "  make deploy            down + rebuild SIN caché (backend+frontend) + up (todo el stack)"
	@echo "  make deploy-quick      rebuild backend+frontend (con caché) + up"
	@echo "  make redeploy-front    solo frontend: build --no-cache + recrear contenedor"
	@echo "  make redeploy-back     solo backend:  build --no-cache + recrear contenedor"
	@echo "  make run-all           levantar todos los servicios (docker compose up -d)"
	@echo "  make run-env           entorno sin app: postgres, ocr-service, qdrant, ollama"
	@echo "  make down              docker compose down"
	@echo "  make up                alias de run-all"
	@echo "  make ps                estado de contenedores"
	@echo "  make logs              logs -f (todos). SERVICE=nombre → solo ese servicio"
	@echo "  make build             solo build backend + frontend (sin up)"
	@echo "  make rebuild-frontend  build (con caché) + up solo frontend"
	@echo "  make rebuild-backend   build (con caché) + up solo backend"
	@echo "  make base-cpu          construir imagen base CPU (newsanalyzer-base:cpu)"
	@echo "  make base-cuda         construir imagen base CUDA (newsanalyzer-base:cuda)"
	@echo "  make base-all          construir ambas bases (útil para CI/artefactos compartidos)"
	@echo "  GPU_TYPE=nvidia ...    fuerza uso de base CUDA en targets con backend build"
	@echo ""
	@echo "Ej.:  make logs SERVICE=backend"
	@echo "GPU:  COMPOSE_FILE en app/.env o export COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml"

ensure-base:
	@$(MAKE) $(BASE_TARGET)

base-cpu:
	@echo "🔨 (Re)construyendo $(BASE_CPU_TAG)... (no-cache + pull latest base)"
	docker build --pull --no-cache -f $(APP_DIR)/backend/docker/base/cpu/Dockerfile -t $(BASE_CPU_TAG) .

base-cuda:
	@echo "🔨 (Re)construyendo $(BASE_CUDA_TAG)... (no-cache + pull latest base)"
	docker build --pull --no-cache -f $(APP_DIR)/backend/docker/base/cuda/Dockerfile -t $(BASE_CUDA_TAG) .

base-all: base-cpu base-cuda

deploy: ensure-base
	cd $(APP_DIR) && \
	docker compose down && \
	$(BUILD_ENV) docker compose build --no-cache backend frontend && \
	docker compose up -d

deploy-quick: ensure-base
	cd $(APP_DIR) && \
	$(BUILD_ENV) docker compose build backend frontend && \
	docker compose up -d

redeploy-front:
	cd $(APP_DIR) && \
	$(BUILD_ENV) docker compose build --no-cache frontend && \
	docker compose up -d --force-recreate frontend

redeploy-back: ensure-base
	cd $(APP_DIR) && \
	$(BUILD_ENV) docker compose build --no-cache backend && \
	docker compose up -d --force-recreate backend

run-all:
	cd $(APP_DIR) && docker compose up -d

run-env:
	cd $(APP_DIR) && docker compose up -d $(ENV_SERVICES)

up: run-all

down:
	cd $(APP_DIR) && docker compose down

ps:
	cd $(APP_DIR) && docker compose ps

logs:
	cd $(APP_DIR) && docker compose logs -f $(SERVICE)

build: ensure-base
	cd $(APP_DIR) && $(BUILD_ENV) docker compose build backend frontend

rebuild-frontend:
	cd $(APP_DIR) && \
	$(BUILD_ENV) docker compose build frontend && \
	docker compose up -d frontend

rebuild-backend: ensure-base
	cd $(APP_DIR) && \
	$(BUILD_ENV) docker compose build backend && \
	docker compose up -d backend
