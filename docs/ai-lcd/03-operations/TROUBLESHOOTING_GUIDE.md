# Troubleshooting Guide - NewsAnalyzer-RAG

> Problemas comunes y soluciones

**Última actualización**: 2026-03-02
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

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación inicial | AI-DLC |
