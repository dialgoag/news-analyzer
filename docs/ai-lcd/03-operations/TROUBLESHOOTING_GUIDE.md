# Troubleshooting Guide - NewsAnalyzer-RAG

> Problemas comunes y soluciones

**Última actualización**: 2026-03-27
**Fase AI-DLC**: 03-operations
**Audiencia**: Admin, Desarrolladores

---

## Problemas Comunes

### Backend no arranca / "unhealthy"

**Causa**: El backend descarga el modelo de embeddings (~2.3GB) la primera vez.

**Solución**: Esperar 5-10 minutos. Verificar:
```bash
docker compose logs -f backend
# Esperar "Application startup complete"
```

### Error "OPENAI_API_KEY required"

**Causa**: `LLM_PROVIDER=openai` pero no se configuró la API key.

**Solución**: Agregar en `.env`:
```env
OPENAI_API_KEY=sk-...tu-key...
```

### CORS errors en el frontend

**Causa**: `ALLOWED_ORIGINS` no coincide con la URL del browser.

**Solución**: En `.env`, configurar exactamente la URL que el usuario ve:
```env
ALLOWED_ORIGINS=https://tudominio.com
```

### "No relevant documents found"

**Causa**: Umbral de relevancia muy alto o documentos no indexados.

**Solución**:
1. Verificar que hay documentos subidos
2. Bajar el threshold en `.env`:
```env
RELEVANCE_THRESHOLD=0.3
```
3. Reiniciar: `docker compose down && docker compose up -d`

### Password de admin perdido

**Solución**:
```bash
# Opción A: Ver logs
docker compose logs backend | grep "Password:"

# Opción B: Reset
echo "ADMIN_DEFAULT_PASSWORD=nuevo-password" >> .env
docker compose exec backend rm /app/data/rag_users.db
docker compose restart backend
```

### Ollama timeout (si usas LLM local)

**Causa**: Ollama tarda en descargar el modelo la primera vez.

**Solución**: Esperar. Ver progreso:
```bash
docker compose logs -f ollama
```

### Tika: "Connection aborted" o "Connection refused" con varios workers de inbox

**Causa**: Varios workers de ingesta llaman a Tika a la vez; el servidor Tika (por defecto en modo fork) puede saturarse o cerrar conexiones.

**Qué hace el backend** (sin tocar workers):
- **Tika con `-noFork`**: un solo proceso JVM, más estable bajo carga concurrente.
- **Connection pooling** (`requests.Session` con `HTTPAdapter`): reutiliza conexiones en lugar de abrir muchas.
- **Reintentos con backoff**: ante `ConnectionError` se reintenta hasta 3 veces antes de reiniciar Tika.
- **Lock al reiniciar Tika**: solo un worker reinicia el proceso; los demás esperan.

Si sigue fallando, reduce concurrencia en `.env`: `INGEST_PARALLEL_WORKERS=1` o `2`.

### Login: 422 en `/api/auth/login`

**Causa**: El modelo `LoginRequest` exige `username` con longitud mínima 3 y `password` mínima 6 (`auth_models.py`).

**Solución**: Usar credenciales que cumplan esos mínimos; el formulario del frontend valida con `minLength`. Si el error persiste, revisar el cuerpo JSON (debe ser `{ "username", "password" }`).

### Login: `ERR_EMPTY_RESPONSE` o “Cannot reach the API”

**Causa**: Backend caído, puerto distinto, o `VITE_API_URL` del frontend no apunta al API real (p. ej. Docker vs localhost).

**Solución**: `curl http://localhost:8000/health`; alinear `VITE_API_URL` en build del frontend con la URL accesible desde el navegador.

### Dashboard: mismo nombre de archivo en varias filas OCR / Workers

**Causa posible 1 (corregida en Fix #96)**: Dos `worker_tasks` activos para el mismo `document_id` y `task_type` (misma fuente de filename en JOIN). Aplicar migración **015** y código `assign_worker` actualizado.

**Causa posible 2**: Varios **documentos distintos** con el **mismo** `filename` en `document_status` (contenido distinto; IDs distintos) — comportamiento esperado; distinguir por `document_id` o fecha en nombre.

**Referencia**: `CONSOLIDATED_STATUS.md` §96; `ORDERLY_SHUTDOWN_AND_REBUILD.md`.

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-27 | 1.1 | Login, workers duplicados, enlaces ops | AI-LCD |
| 2026-03-02 | 1.0 | Creación inicial | AI-DLC |
