# Architecture Detailed - NewsAnalyzer-RAG

> Arquitectura completa del sistema

**Última actualización**: 2026-03-02
**Fase AI-DLC**: 02-construction
**Audiencia**: Desarrolladores

---

## 1. Diagrama de Arquitectura

```
┌─────────────────────────────────────────────────────────────────┐
│                    Docker Compose Network                        │
│                                                                  │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │  Frontend     │    │  Backend     │    │  Qdrant      │       │
│  │  React+Vite   │───→│  FastAPI     │───→│  Vector DB   │       │
│  │  :3000        │    │  :8000       │    │  :6333       │       │
│  └──────────────┘    └──────┬───────┘    └──────────────┘       │
│                             │                                    │
│                      ┌──────┴───────┐                            │
│                      │              │                             │
│                ┌─────▼─────┐  ┌─────▼──────┐                     │
│                │  Ollama    │  │  OpenAI    │                     │
│                │  (local)   │  │  API       │                     │
│                │  :11434    │  │  (externo) │                     │
│                └───────────┘  └────────────┘                     │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
         │
         │  HTTPS (Cloudflare Tunnel / Nginx reverse proxy)
         ▼
   ┌─────────────┐
   │  Internet    │
   │  Usuarios    │
   └─────────────┘
```

## 2. Servicios Docker

| Servicio | Imagen | Puerto | Función |
|----------|--------|--------|---------|
| **frontend** | Build local (React) | 3000 | UI web |
| **backend** | Build local (FastAPI) | 8000 | API REST, RAG pipeline, auth |
| **qdrant** | qdrant/qdrant:v1.15.2 | 6333 | Base de datos vectorial |
| **ollama** | ollama/ollama:latest | 11434 | LLM local (opcional con OpenAI) |

## 3. Pipeline RAG

```
PDF upload → OCR Service → Text Extraction → Chunking → Embeddings → Qdrant
                                                                        │
User query → Embed query → Qdrant search → Top-K chunks → LLM prompt → Response
```

### 3.1 Procesamiento de Documentos (Upload)

1. **Upload**: Frontend envía PDF al backend via multipart/form-data
2. **Detección**: `OCRService.analyze_pdf()` determina si es texto o escaneado
3. **Extracción**:
   - PDF con texto: PyMuPDF (`fitz`) extrae texto directamente
   - PDF escaneado: Apache Tika (OCR Java) o Tesseract (fallback)
4. **Chunking**: `RecursiveCharacterTextSplitter` (2000 chars, 400 overlap)
5. **Embeddings**: `BAAI/bge-m3` via HuggingFace genera vectores
6. **Indexación**: Vectores + metadata se guardan en Qdrant

### 3.2 Consulta (Query)

1. **Query**: Usuario escribe pregunta
2. **Embedding**: La pregunta se convierte a vector
3. **Retrieval**: Qdrant busca los top-K chunks más similares (threshold ≥ 0.35)
4. **Context building**: Chunks relevantes se formatean como contexto
5. **LLM**: Prompt (contexto + pregunta + historial) se envía al LLM
6. **Response**: LLM genera respuesta con citas a las fuentes

### 3.3 LLM Provider (Modificación clave)

El sistema original solo soporta Ollama. La modificación agrega soporte para OpenAI:

| Provider | Configuración | Cuándo usar |
|----------|--------------|-------------|
| `openai` | `OPENAI_API_KEY` + `OPENAI_MODEL` | Producción (respuestas de alta calidad) |
| `ollama` | `OLLAMA_HOST` + `LLM_MODEL` | Desarrollo local / sin internet / privacidad |

Variable de selección: `LLM_PROVIDER=openai` o `LLM_PROVIDER=ollama`

## 4. Modelo de Autenticación y Permisos

```
JWT Token (HS256, 8h expiry)
    │
    ├── role: "admin"       → Todo: CRUD usuarios, CRUD documentos, config, backup
    ├── role: "super_user"  → Subir/borrar documentos + consultar
    └── role: "user"        → Solo consultar (read-only)
```

### Endpoints por permiso

| Endpoint | admin | super_user | user |
|----------|-------|-----------|------|
| `POST /api/upload` | OK | OK | 403 |
| `DELETE /api/documents/{id}` | OK | OK | 403 |
| `POST /api/query` | OK | OK | OK |
| `GET /api/documents` | OK | OK | OK |
| `POST /api/admin/users` | OK | 403 | 403 |
| `GET /api/admin/users` | OK | 403 | 403 |

## 5. Base de Datos

**SQLite** (`/app/data/rag_users.db`) para gestión de usuarios:

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,  -- bcrypt
    role TEXT NOT NULL,           -- admin/super_user/user
    created_at TEXT NOT NULL,
    last_login TEXT,
    is_active INTEGER DEFAULT 1
);
```

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación inicial | AI-DLC |
