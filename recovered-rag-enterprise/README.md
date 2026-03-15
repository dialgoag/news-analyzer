# Código extraído de imágenes Docker (15 mar 2026)

Contenido exportado desde:
- **rag-enterprise-structure-backend:latest**
- **rag-enterprise-structure-ocr-service:latest**
- **rag-enterprise-structure-frontend:latest**

## Dónde está el código que importa

| Imagen | Código dentro del export |
|--------|--------------------------|
| **Backend** | `backend/app/` — app.py (~5956 líneas), database.py, pipeline_states.py, worker_pool.py, rag_pipeline.py, ocr_service.py, auth, migrations, etc. |
| **OCR service** | `ocr-service/app/` — app.py, requirements.txt |
| **Frontend** | `frontend/app/dist/` — build de producción (HTML/JS/CSS). No incluye el código fuente React (src/); la imagen solo contenía el artefacto compilado. |

Cada carpeta (`backend/`, `ocr-service/`, `frontend/`) es el filesystem raíz del contenedor; el resto son binarios del sistema (usr, etc, var…).

## Cómo usar el backend recuperado

Para reemplazar el código actual del backend con el recuperado:

```bash
# Ejemplo: copiar solo el código Python del backend
cp -r recovered-rag-enterprise/backend/app/* RAG-Enterprise/rag-enterprise-structure/backend/
# o a app/backend/ según dónde esté tu proyecto activo
```

Ajusta las rutas según tu estructura (RAG-Enterprise submodule vs app/backend).
