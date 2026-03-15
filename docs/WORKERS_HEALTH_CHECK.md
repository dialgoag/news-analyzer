# 🏥 Workers Health Check - Auto-Restart System

## 📋 Descripción

Sistema automático de monitoreo y recuperación de workers que garantiza que el pool de trabajadores esté siempre activo y procesando tareas.

## ⚙️ Funcionamiento

### Verificación Periódica (cada 30 segundos)

El `workers_health_check()` se ejecuta automáticamente y verifica:

1. **¿Existe el worker pool?**
   - Si NO existe → Lo crea automáticamente
   
2. **¿Está corriendo el pool?**
   - Si NO está corriendo → Lo reinicia
   
3. **¿Hay threads vivos?**
   - Si active_count == 0 → Reinicia completamente el pool
   - Si active_count < pool_size → Alerta (pero no reinicia, puede ser normal)
   - Si active_count == pool_size → Todo OK ✅

### Logs de Diagnóstico

```bash
# Health check exitoso
✓ Workers health check OK: 20/20 workers alive

# Sin worker pool
⚠️  Workers health check: No active worker pool detected!
🔄 Auto-starting workers...
✅ Worker pool auto-started: 20 workers ready

# Pool corriendo pero sin threads vivos
❌ Workers health check: Pool running but NO alive threads!
🔄 Restarting worker pool...
✅ Worker pool restarted: 20 workers ready

# Algunos workers muertos (no reinicia automáticamente)
⚠️  Workers health check: Only 15/20 workers alive
```

## 🚀 Inicialización en Startup

El health check se registra automáticamente en el startup del backend:

```python
# En app.py - startup_event()
backup_scheduler.add_job(
    workers_health_check,
    trigger_type='interval',
    job_id='workers_health_check_job',
    seconds=30  # Cada 30 segundos
)
```

Mensaje en logs:
```
🏥 ===== STARTING WORKERS HEALTH CHECK ===== 🏥
✅ Workers Health Check initialized
✅ ===== WORKERS HEALTH CHECK REGISTERED ===== ✅
```

## 📊 Escenarios de Recuperación

### Escenario 1: Backend Restart
**Problema**: Después de un restart del backend, los workers no se inician automáticamente.

**Solución**: 
- El health check detecta que no hay pool
- Crea y arranca el pool automáticamente en el primer ciclo (30 segundos)
- Los usuarios NO necesitan hacer click manual en "Start Workers"

### Escenario 2: Workers Crashed
**Problema**: Todos los workers murieron por un error crítico (ej: DB connection lost).

**Solución**:
- El health check detecta `active_count == 0`
- Reinicia completamente el pool
- Recuperación automática sin intervención manual

### Escenario 3: Degradación Parcial
**Problema**: Algunos workers murieron pero otros siguen activos.

**Acción**:
- Health check emite WARNING en logs
- NO reinicia automáticamente (puede ser normal durante transiciones)
- Administradores pueden reiniciar manualmente si es necesario

## 🔧 Configuración

### Variables de Entorno

```bash
# Tamaño del pool de workers (default: 20)
WORKER_POOL_SIZE=20
```

El health check usa esta variable para determinar cuántos workers crear.

### Frecuencia del Check

Modificar en `app.py`:

```python
backup_scheduler.add_job(
    workers_health_check,
    trigger_type='interval',
    job_id='workers_health_check_job',
    seconds=30  # ← Cambiar aquí (en segundos)
)
```

**Recomendaciones**:
- Producción: `30-60` segundos (balance entre reactividad y carga)
- Development: `15-30` segundos (detección rápida de problemas)
- NO usar < 10 segundos (carga innecesaria)

## 🎯 Ventajas

### 1. **Resiliencia Automática**
- Los workers se recuperan sin intervención manual
- Reduce downtime en producción
- Elimina necesidad de scripts externos de monitoreo

### 2. **Mejor UX**
- Los usuarios NO necesitan saber que existe un botón "Start Workers"
- El sistema "simplemente funciona" después de un restart
- Menos soporte técnico requerido

### 3. **Detección Temprana**
- Identifica problemas antes de que los usuarios los noten
- Logs detallados para debugging
- Métricas de salud en tiempo real

### 4. **Lazy Initialization Mejorada**
- Compatible con el inicio lazy de workers
- No bloquea el startup del backend
- Permite que servicios críticos (Qdrant, Tika) inicialicen primero

## 📈 Monitoreo

### Verificar Health Check en Logs

```bash
# Ver logs del backend
docker compose logs -f backend | grep "health check"

# Verificar que esté registrado al inicio
docker compose logs backend | grep "WORKERS HEALTH CHECK"

# Ver ciclos de verificación
docker compose logs backend | grep "Workers health check"
```

### Métricas Clave

1. **Frecuencia de reinicio**: Si reinicia frecuentemente → problema subyacente
2. **Workers vivos**: Siempre debe ser == WORKER_POOL_SIZE
3. **Tiempo de recuperación**: Debe ser < 60 segundos después de un crash

## 🐛 Troubleshooting

### Health Check No Se Ejecuta

**Síntomas**: No aparecen logs de "Workers health check"

**Soluciones**:
1. Verificar que el backup_scheduler esté corriendo
2. Check logs de startup por errores en registro
3. Verificar que `ocr_service` y `rag_pipeline` estén listos

### Workers Se Reinician Constantemente

**Síntomas**: Logs muestran reinicio cada 30 segundos

**Causas Posibles**:
1. **Problema de DB**: SQLite locked o corrupto
2. **Problema de memoria**: Workers OOM killed
3. **Error en task_dispatcher**: Exception no manejada

**Debug**:
```bash
# Ver errores en workers
docker compose logs backend | grep -A 10 "worker_id"

# Check DB health
docker compose exec backend python -c "from database import document_status_store; print(document_status_store.health_check())"
```

### Workers Lentos Pero Vivos

**Síntomas**: Health check OK pero tareas no avanzan

**Solución**:
- El health check solo verifica que threads estén vivos
- NO verifica si están procesando
- Usar `/api/workers/status` para ver actividad real

## 🔗 Integración con Otros Componentes

### Master Pipeline Scheduler
- Ambos corren en paralelo
- Health check asegura workers
- Master scheduler asegura tareas

### API `/api/workers/start`
- Sigue funcionando para inicio manual
- Health check complementa, no reemplaza
- Útil para testing y admin manual

### Qdrant & Tika
- Health check NO verifica estos servicios
- Solo verifica workers del backend
- Servicios externos deben tener su propio monitoring

## 📝 Changelog

### v1.0 - 2026-03-05
- ✅ Implementación inicial
- ✅ Auto-start de workers si no existen
- ✅ Auto-restart si pool está muerto
- ✅ Alertas para degradación parcial
- ✅ Integración con backup_scheduler
- ✅ Logs detallados de diagnóstico

## 🚦 Estado Actual

- ✅ **ACTIVO**: Health check corriendo cada 30 segundos
- ✅ **PROBADO**: Recuperación automática funcional
- ✅ **PRODUCCIÓN**: Listo para deployment

---

**Última actualización**: 2026-03-05  
**Versión**: 1.0  
**Autor**: AI Assistant
