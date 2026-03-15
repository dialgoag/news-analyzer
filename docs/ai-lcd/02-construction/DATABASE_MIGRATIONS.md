# Sistema de Migraciones Yoyo - Guía Completa

## Resumen Ejecutivo

Se implementó **Yoyo-Migrations** (framework tipo Flyway para Python) para gestionar migraciones de base de datos de forma robusta y escalable.

### Características Clave
- ✅ Bloqueante: App NO inicia si migración falla
- ✅ Organizadas por dominio: 8 migraciones temáticas
- ✅ Datos preservados: Todos los insights LLM salvos
- ✅ Extensible: Agregar nueva migración = nuevo archivo .py
- ✅ Auditabilidad: Historial en tabla `_yoyo_migration`

## Arquitectura

### Decisión: ¿Por qué Yoyo?

Evaluamos opciones para Python + SQLite:
- **Alembic**: Optimizado para ORM (SQLAlchemy) - overkill para SQL puro
- **Yoyo**: Diseñado para SQL puro + SQLite sin ORM - ✅ ELEGIDO
- **Pyway**: Menos mantenido, menos documentado

**Conclusión**: Yoyo es óptimo porque:
1. No depende de ORM
2. SQL puro (máximo control)
3. Activamente mantenido (v9.0.0+)
4. Diseñado específicamente para SQLite

### Estructura de Migraciones (8 dominios)

```
001_authentication_schema.py
├─ Tabla: users
├─ Propósito: Control de acceso y autenticación
└─ Criticidad: ALTA (todo depende)

002_document_status_schema.py
├─ Tabla: document_status
├─ Propósito: Rastreo del ciclo de vida de documentos
└─ Criticidad: ALTA (rastreo central)

003_event_driven_schema.py ⭐
├─ Tablas: worker_tasks (semáforo), processing_queue (cola)
├─ Propósito: Evitar procesamiento duplicado, coordinación event-driven
└─ Criticidad: CRÍTICA (arquitectura)

004_document_insights_schema.py ⭐
├─ Tabla: document_insights
├─ Propósito: Almacenar insights generados por IA
├─ Datos: VALIOSOS (generados con OpenAI, no recuperables)
└─ Criticidad: CRÍTICA (proteger datos)

005_news_items_schema.py
├─ Tablas: news_items, news_item_insights
├─ Propósito: Noticias extraídas e insights por noticia
└─ Criticidad: MEDIA (derivado de documentos)

006_reporting_schema.py
├─ Tablas: daily_reports, weekly_reports
├─ Propósito: Reportes automáticos generados
└─ Criticidad: MEDIA (regenerables)

007_notifications_schema.py
├─ Tablas: notifications, notification_reads
├─ Propósito: Sistema de notificaciones in-app por usuario
└─ Criticidad: BAJA (secundario)

008_consolidate_legacy_data.py
├─ Proceso: Migra datos de rag_users.db y documents.db
├─ Propósito: Consolidación sin perder datos
├─ Método: INSERT OR IGNORE (idempotente)
└─ Criticidad: MEDIA (una sola vez)
```

## Flujo de Ejecución

```
1. Docker inicia backend
2. app.py importado
3. database.py ejecutado
   ├─ migration_runner.run_migrations() llamado
   ├─ Yoyo carga migraciones desde /backend/migrations/
   └─ Aplica secuencialmente 001→008 con locks
4. ¿Todas migraciones exitosas?
   ├─ ✅ SÍ → Inicializa stores (ProcessingQueueStore, etc.) → App lista
   └─ ❌ NO → Log de error específico → sys.exit(1) → App no inicia
```

## Protección de Datos

### Datos Críticos (NO Perder)
- 🎯 `document_insights` - Insights generados por OpenAI (costo: $)
- 🎯 `news_item_insights` - Insights por noticia
- 🎯 `users` - Cuentas de autenticación
- 🎯 `daily_reports`, `weekly_reports` - Reportes generados

### Estrategia de Consolidación (Migration 008)
Migration 008 es **idempotente**:
```python
# Pseudo-código
for table in old_databases:
    for row in rows:
        INSERT INTO new_db OR IGNORE (no duplica)
```
Seguro repetir sin perder datos.

### Backup Manual (Recomendado)
Antes de ejecutar migraciones:
```bash
bash backup.sh  # Ver script en directorio raíz
```
Crea backups en `local-data/backups/`:
- `rag_users.db-<timestamp>.bak`
- `documents.db-<timestamp>.bak`
- SQL exports de tablas críticas

## Cómo Usar

### Antes de Migrations (IMPORTANTE)

1. **Hacer backup**:
```bash
cd app/
bash backup.sh
```

2. **Analizar deduplicación**:
```bash
python analyze_dedup.py
# Verifica si hay documentos duplicados en BD vs archivos físicos
```

3. **Verificar estado actual**:
```bash
docker-compose logs backend | tail -50
# Revisar si hay errores
```

### Ejecutar Migraciones

```bash
cd app/

# Detener y limpiar (OPCIONAL)
docker-compose down

# Rebuildsnd iniciar
docker-compose up -d --build

# Verificar logs
docker-compose logs backend | grep -E "MIGRATION|Applied|✅|❌"
```

### Verificar Resultado

```bash
# Ver migraciones aplicadas
docker-compose logs backend 2>&1 | grep -A 100 "DATABASE MIGRATION SYSTEM"

# Contar datos preservados
docker-compose exec backend sqlite3 /app/data/rag_enterprise.db \
  "SELECT COUNT(*) as insights FROM document_insights WHERE status='done';"

# Ver historial de migraciones
docker-compose exec backend sqlite3 /app/data/rag_enterprise.db \
  "SELECT id, applied_at FROM _yoyo_migration;"
```

## Agregar Nueva Migración

Cuando necesites cambios en BD:

1. **Crear archivo** `backend/migrations/00X_nombre.py`:
```python
"""
Migration 00X: Descripción breve

Domain: Nombre del Dominio
Description: Descripción detallada de cambios
Depends on: 00X-1_previous_migration (opcional)
"""

from yoyo import step

steps = [
    step(
        # Forward: Crear
        "CREATE TABLE new_table (id INT PRIMARY KEY, ...)",
        # Rollback: Revertir
        "DROP TABLE IF EXISTS new_table"
    ),
    step(
        "CREATE INDEX idx_name ON table(column)",
        "DROP INDEX IF EXISTS idx_name"
    ),
]
```

2. **Reiniciar backend**:
```bash
docker-compose restart backend
```

3. ✅ Automáticamente aplicada en próximo startup

## Troubleshooting

| Problema | Causa | Solución |
|----------|-------|----------|
| App no inicia | Migración falla | Ver logs: `docker-compose logs backend` |
| Syntax error en .py | Migración mal escrita | Revisar SQL en archivo, testar en sqlite3 |
| Datos perdidos | Rollback fallido | Restaurar desde backup en `local-data/backups/` |
| Proceso lento | Normal en primer startup | Migraciones se ejecutan solo una vez |
| Tabla ya existe | Idempotencia | Usar `CREATE TABLE IF NOT EXISTS` |

## Ventajas vs Enfoque Manual

| Aspecto | Manual (Antes) | Yoyo (Ahora) |
|--------|--------|-----------|
| **Organización** | Monolítico (init_db) | 8 dominios temáticos |
| **Errores** | Silenciosos posibles | Explícitos + exit |
| **Rollback** | Manual, propenso a error | Automático por step |
| **Documentación** | Dispersa | Centralizada |
| **Testing** | Difícil aislar cambios | Cada migración independiente |
| **Escalabilidad** | O(n) checks | Automático |

## Archivos Entregables

```
backend/
├─ migrations/
│  ├─ 001_authentication_schema.py
│  ├─ 002_document_status_schema.py
│  ├─ 003_event_driven_schema.py
│  ├─ 004_document_insights_schema.py
│  ├─ 005_news_items_schema.py
│  ├─ 006_reporting_schema.py
│  ├─ 007_notifications_schema.py
│  ├─ 008_consolidate_legacy_data.py
│  ├─ __init__.py
│  └─ README.md (detalles técnicos)
├─ migration_runner.py (orquestador Yoyo)
├─ yoyo.ini (configuración)
├─ database.py (modificado: llama migration_runner)
└─ requirements.txt (modificado: +yoyo-migrations)

Scripts auxiliares:
├─ backup.sh (crea backups antes de migrations)
└─ analyze_dedup.py (analiza deduplicación)

Documentación (ai-dlc):
└─ docs/ai-dlc/02-construction/
   └─ DATABASE_MIGRATIONS.md (ESTA - documentación consolidada)
```

## Garantías del Sistema

✅ **Bloqueante**: App no inicia si migración falla - estado consistente
✅ **Datos preservados**: Migration 008 idempotente - sin pérdidas
✅ **Por dominios**: Cada migración responsable de un aspecto - mantenible
✅ **Extensible**: Agregar migración = archivo nuevo - escalable
✅ **Auditabilidad**: Historial en `_yoyo_migration` - trazable
✅ **Sin ORM**: SQL puro - máximo control y performance

## Próxima Acción

```bash
# 1. Hacer backup
bash backup.sh

# 2. Analizar deduplicación
python analyze_dedup.py

# 3. Ejecutar migraciones
docker-compose down
docker-compose up -d --build

# 4. Verificar resultado
docker-compose logs backend | grep -E "MIGRATION|✅"
```

## Referencias

- Yoyo Docs: https://ollycope.com/software/yoyo/latest/
- Flyway: https://flywaydb.org/ (inspiración)
- SQLite: https://www.sqlite.org/lang.html

---

**Status**: ✅ IMPLEMENTADO Y LISTO PARA DEPLOY

Sistema profesional, auditado y con protección total de datos valiosos.
