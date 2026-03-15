# NewsAnalyzer-RAG

> Plataforma web para análisis profundo de noticias en PDF con IA

Basado en [RAG Enterprise](https://github.com/I3K-IT/RAG-Enterprise) con soporte para OpenAI API.

---

## Qué hace

- Sube PDFs de noticias y analiza su contenido completo (texto, tablas, OCR)
- Chat con IA para preguntar sobre las noticias
- Sistema de usuarios con permisos (admin / super_user / usuario read-only)
- Interfaz web accesible desde cualquier navegador

## Stack

| Componente | Tecnología |
|-----------|-----------|
| Backend | FastAPI (Python) |
| Frontend | React + Vite |
| Database | PostgreSQL 17 |
| LLM | OpenAI GPT-4o (API) o Ollama (local) |
| Embeddings | BAAI/bge-m3 (local) |
| Vector DB | Qdrant |
| OCR | OCRmyPDF + Tesseract (spa+eng) |
| Auth | JWT + RBAC |

## Quick Start

```bash
cd RAG-Enterprise/rag-enterprise-structure

# 1. Configurar
cp .env.example .env
# Editar .env: configurar LLM_PROVIDER, OPENAI_API_KEY, etc.

# 2. Levantar
docker compose up -d

# 3. Ver logs (esperar "Application startup complete")
docker compose logs -f backend

# 4. Obtener password admin
docker compose logs backend | grep "Password:"

# 5. Abrir http://localhost:3000
```

## Roles de Usuario

| Rol | Puede hacer |
|-----|------------|
| `admin` | Todo: gestionar usuarios, subir/borrar documentos, configurar |
| `super_user` | Subir y borrar documentos + consultar |
| `user` | Solo consultar (read-only) |

## Documentación

Ver `docs/ai-lcd/` para documentación completa:

- **[CONSOLIDATED_STATUS](docs/ai-lcd/CONSOLIDATED_STATUS.md)** -- Estado actual del proyecto
- **[SESSION_LOG](docs/ai-lcd/SESSION_LOG.md)** -- Decisiones entre sesiones
- **[Business Requirements](docs/ai-lcd/01-inception/BUSINESS_REQUIREMENTS.md)**
- **[Architecture](docs/ai-lcd/02-construction/ARCHITECTURE_DETAILED.md)**
- **[OpenAI Integration](docs/ai-lcd/02-construction/OPENAI_INTEGRATION.md)**
- **[Deployment Guide](docs/ai-lcd/03-operations/DEPLOYMENT_GUIDE.md)**
- **[Environment Config](docs/ai-lcd/03-operations/ENVIRONMENT_CONFIGURATION.md)**
- **[Troubleshooting](docs/ai-lcd/03-operations/TROUBLESHOOTING_GUIDE.md)**
