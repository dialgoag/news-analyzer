# NewsAnalyzer — comandos Docker para producción local
# Desde la raíz del repo: make help
#
# Overrides (GPU, etc.): app/.env → COMPOSE_FILE=... o export antes de make.

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

APP_DIR := app

# Infra + dependencias sin capa de aplicación (ver app/docker-compose.yml)
ENV_SERVICES := postgres ocr-service qdrant ollama

.PHONY: help deploy deploy-quick down up run-all run-env ps logs build \
	redeploy-front redeploy-back rebuild-frontend rebuild-backend

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
	@echo ""
	@echo "Ej.:  make logs SERVICE=backend"
	@echo "GPU:  COMPOSE_FILE en app/.env o export COMPOSE_FILE=docker-compose.yml:docker-compose.nvidia.yml"

deploy:
	cd $(APP_DIR) && \
	docker compose down && \
	docker compose build --no-cache backend frontend && \
	docker compose up -d

deploy-quick:
	cd $(APP_DIR) && \
	docker compose build backend frontend && \
	docker compose up -d

redeploy-front:
	cd $(APP_DIR) && \
	docker compose build --no-cache frontend && \
	docker compose up -d --force-recreate frontend

redeploy-back:
	cd $(APP_DIR) && \
	docker compose build --no-cache backend && \
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

build:
	cd $(APP_DIR) && docker compose build backend frontend

rebuild-frontend:
	cd $(APP_DIR) && \
	docker compose build frontend && \
	docker compose up -d frontend

rebuild-backend:
	cd $(APP_DIR) && \
	docker compose build backend && \
	docker compose up -d backend
