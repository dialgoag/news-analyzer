# 🚀 COMPILAR Y TESTEAR

## Compilación (Con Base Image Rápido)

```bash
cd app/

# 1. Build backend (usa Dockerfile.cpu que hereda de base)
docker-compose -f docker-compose.local.yml build backend

# 2. Lanzar con docker-compose.local.yml
docker-compose -f docker-compose.local.yml up -d

# 3. Verificar status
docker-compose -f docker-compose.local.yml ps
```

## Verificación

```bash
# Health check
curl http://localhost:8000/health

# Dashboard
http://localhost:3000
```

## Testing (Opcional)

1. Agregar 50 PDFs a `upload/inbox/`
2. Monitorear logs: `docker-compose -f docker-compose.local.yml logs backend -f`
3. Verificar: OCR workers máx 4 simultáneos, sin timeout Tika

## Success Criteria

✅ docker-compose ps → todos "Up"
✅ /health → OK
✅ Dashboard carga sin errores
✅ Logs: sin errores SQL
✅ Inbox files → processing_queue → OCR workers (uno a uno)

---

Ver `CONSOLIDATED_STATUS.md` para status completo
