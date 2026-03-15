# Code Organization - NewsAnalyzer-RAG

> Estructura del código y convenciones

**Última actualización**: 2026-03-02
**Fase AI-DLC**: 02-construction
**Audiencia**: Desarrolladores

---

## 1. Estructura del Repositorio

```
NewsAnalyzer-RAG/
├── docs/
│   └── ai-dlc/                          # Documentación AI-DLC (este directorio)
│       ├── README.md
│       ├── SESSION_LOG.md               # ← LEER PRIMERO en cada sesión
│       ├── 01-inception/
│       ├── 02-construction/
│       └── 03-operations/
├── rag-enterprise/                      # RAG Enterprise (I3K-IT) clonado
│   ├── rag-enterprise-structure/        # Código principal
│   │   ├── backend/                     # FastAPI backend
│   │   │   ├── app.py                   # App principal + endpoints
│   │   │   ├── rag_pipeline.py          # Pipeline RAG + LLM clients
│   │   │   ├── ocr_service.py           # OCR: PyMuPDF + Tika + Tesseract
│   │   │   ├── embeddings_service.py    # HuggingFace embeddings
│   │   │   ├── qdrant_connector.py      # Qdrant vector DB
│   │   │   ├── database.py             # SQLite + roles
│   │   │   ├── auth.py                 # JWT tokens
│   │   │   ├── middleware.py           # Permission checks
│   │   │   ├── backup_service.py       # Backups (rclone)
│   │   │   ├── backup_scheduler.py     # Cron
│   │   │   ├── backup_models.py        # Pydantic models
│   │   │   ├── auth_models.py          # Auth Pydantic models
│   │   │   ├── Dockerfile              # Backend container
│   │   │   └── requirements.txt        # Python deps
│   │   ├── database/                    # DB migrations
│   │   ├── docker-compose.yml           # Orquestación principal
│   │   ├── docker-compose.nvidia.yml    # Override GPU NVIDIA
│   │   ├── docker-compose.amd.yml       # Override GPU AMD
│   │   ├── .env.example                 # Template de configuración
│   │   ├── setup.sh                     # Script de instalación (Ubuntu)
│   │   └── cleanup.sh                   # Script de limpieza
│   ├── frontend/                        # React + Vite frontend
│   │   ├── src/
│   │   ├── Dockerfile.frontend
│   │   └── package.json
│   ├── docs/                            # Docs originales de RAG Enterprise
│   └── README.md                        # README original
└── README.md                            # README del proyecto (por crear)
```

## 2. Archivos Clave por Funcionalidad

### Autenticación y Permisos

| Archivo | Responsabilidad |
|---------|----------------|
| `database.py` | Schema SQLite, UserRole enum, CRUD usuarios |
| `auth.py` | Creación de JWT tokens (HS256) |
| `auth_models.py` | Pydantic models: LoginRequest, UserCreate, etc. |
| `middleware.py` | Decoradores de permisos: require_admin, require_upload_permission |

### Pipeline RAG

| Archivo | Responsabilidad |
|---------|----------------|
| `rag_pipeline.py` | RAGPipeline class, OllamaChatDirect, chunking, query |
| `embeddings_service.py` | HuggingFace embeddings (BAAI/bge-m3) |
| `qdrant_connector.py` | Insert/search vectors en Qdrant |
| `ocr_service.py` | PDF → texto (PyMuPDF, Tika, Tesseract) |

### API Endpoints

Todo en `app.py` (archivo monolítico de ~1247 líneas).

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación inicial | AI-DLC |
