# Backend Migrations Directory

Este directorio contiene todas las migraciones de base de datos organizadas por dominio.

## Estructura

```
migrations/
├── 001_authentication_schema.py       (Authentication & Security)
├── 002_document_status_schema.py      (Document Processing)
├── 003_event_driven_schema.py         (Event-Driven Architecture)
├── 004_document_insights_schema.py    (LLM Insights)
├── 005_news_items_schema.py           (News & Content)
├── 006_reporting_schema.py            (Analytics & Reporting)
├── 007_notifications_schema.py        (User Notifications)
└── 008_consolidate_legacy_data.py     (Data Migration)
```

## Cómo Agregar una Nueva Migración

1. **Naming**: `00X_nombre_descriptivo.py` (número secuencial)
2. **Template**:
```python
"""
Migration 00X: Descripción breve

Domain: Nombre del Dominio
Description: Descripción detallada
Depends on: 00X_previous_migration
"""

from yoyo import step

steps = [
    step(
        "SQL para CREAR",
        "SQL para REVERTIR (ROLLBACK)"
    ),
    step(
        "CREATE INDEX...",
        "DROP INDEX..."
    ),
]
```

3. **Rules**:
   - Siempre incluir forward AND rollback
   - Usar `CREATE TABLE IF NOT EXISTS` para idempotencia
   - Usar `DROP INDEX IF EXISTS` en rollback
   - Agregar índices desde el inicio
   - Una responsabilidad por migración

## Dependencias

Las migraciones se ejecutan en orden secuencial. Cada una depende de las anteriores:

```
001 (Users)
  ↓
002 (Documents)
  ↓
003 (Event-Driven)
  ↓
004 (Insights)
  ↓
005 (News Items)
  ↓
006 (Reports)
  ↓
007 (Notifications)
  ↓
008 (Legacy Data)
```

## Testing Local

Para probar una migración localmente:

```bash
# Dentro del container
cd /app

# Ver estado de migraciones
yoyo list

# Aplicar pendientes
yoyo apply

# Rollback de la última
yoyo rollback
```

## Dominios/Temas Actuales

| # | Dominio | Tabla(s) | Propósito |
|---|---------|----------|----------|
| 001 | Authentication | `users` | Control de acceso y autenticación |
| 002 | Document Processing | `document_status` | Rastreo del ciclo de vida de documentos |
| 003 | Event-Driven | `worker_tasks`, `processing_queue` | Semáforos y coordinación de workers |
| 004 | LLM Insights | `document_insights` | Insights generados por IA (VALIOSOS) |
| 005 | News Content | `news_items`, `news_item_insights` | Noticias extraídas e insights por noticia |
| 006 | Analytics | `daily_reports`, `weekly_reports` | Reportes generados |
| 007 | Notifications | `notifications`, `notification_reads` | Sistema de notificaciones in-app |
| 008 | Data Migration | N/A (proceso) | Consolidación de DBs antiguas |

## Flujo de Inicialización

```
App Start (app.py)
    ↓
database.py importado
    ↓
migration_runner.py.run_migrations() llamado
    ↓
Yoyo carga migraciones desde este dir
    ↓
Aplica secuencialmente (001, 002, ...)
    ↓
¿Todas pasaron?
    ├─ SÍ  → Inicializa stores, app continúa
    └─ NO  → sys.exit(1), app se detiene
```

## Notas Importantes

- ⚠️ **No modifiques migraciones aplicadas**: Crea una nueva en su lugar
- ✅ **Cada migración es independiente**: Nombra según lo que hace
- 🔒 **Datos valiosos**: Migration 008 preserva todos los insights generados con IA
- 📊 **Performance**: Los índices se crean al inicio para optimizar queries
- 🔄 **Rollback seguro**: Cada migración define cómo revertirse completamente

## Futura Extensión

Cuando necesites agregar más dominios:
1. Crea nueva migración en este directorio
2. Sigue el template establecido
3. Sistema aplicará automáticamente al reiniciar
4. No hay downtime - todo bloqueado en startup

Ejemplos de futuras migraciones:
- 009: User Preferences
- 010: Audit Log
- 011: Caching Strategy
- 012: Performance Optimization
