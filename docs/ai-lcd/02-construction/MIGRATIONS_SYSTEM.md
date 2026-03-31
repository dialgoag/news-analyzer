# Sistema de Migraciones Yoyo-based

## Introducción

El backend utiliza **Yoyo-Migrations** para gestionar migraciones de base de datos, similar a Flyway pero para Python. Este sistema:

- ✅ Bloquea la inicialización de la aplicación hasta que todas las migraciones se completen exitosamente
- ✅ Organiza migraciones por **temas/dominios** (Authentication, Event-Driven, LLM Insights, etc.)
- ✅ Previene duplicación de tareas con semáforos en BD
- ✅ Preserva todos los datos existentes
- ✅ Permite rollback seguro de cambios

## Estructura de Migraciones

Las migraciones se encuentran en `/backend/migrations/` y están organizadas por dominio:

### 001: Autenticación
- **Archivo**: `001_authentication_schema.py`
- **Dominio**: Authentication & Security
- **Contenido**: Tabla `users` para gestión de acceso

### 002: Estado de Documentos
- **Archivo**: `002_document_status_schema.py`
- **Dominio**: Document Processing & Status Tracking
- **Contenido**: Tabla `document_status` para rastrear el ciclo de vida de documentos

### 003: Arquitectura Event-Driven
- **Archivo**: `003_event_driven_schema.py`
- **Dominio**: Event-Driven Architecture & Task Management
- **Contenido**: 
  - `worker_tasks`: Semáforo para prevenir procesamiento duplicado
  - `processing_queue`: Cola de tareas ordenada por prioridad

### 004: Insights LLM
- **Archivo**: `004_document_insights_schema.py`
- **Dominio**: LLM Insights & AI-Generated Content
- **Contenido**: Tabla `document_insights` para insights generados por IA (VALIOSOS - NO PERDER)

### 005: Noticias
- **Archivo**: `005_news_items_schema.py`
- **Dominio**: News & Content Extraction
- **Contenido**:
  - `news_items`: Ítems individuales extraídos de documentos
  - `news_item_insights`: Insights por cada ítem

### 006: Reportes
- **Archivo**: `006_reporting_schema.py`
- **Dominio**: Analytics & Reporting
- **Contenido**:
  - `daily_reports`: Reportes diarios generados
  - `weekly_reports`: Reportes semanales

### 007: Notificaciones
- **Archivo**: `007_notifications_schema.py`
- **Dominio**: User Notifications & System Events
- **Contenido**:
  - `notifications`: Bandeja de notificaciones in-app
  - `notification_reads`: Tracking de lecturas por usuario

### 008–014: Varias (normalización, insights, performance)
- **011**: Log de performance OCR
- **012**: Normaliza `document_status` a esquema único (DocStatus)
- **013**: Añade `llm_source` a `news_item_insights`
- **014**: Añade `indexed_in_qdrant_at` a `news_item_insights` (Indexing Insights etapa)

### 016: Pipeline runtime KV (pausas persistentes)
- **Archivo**: `016_pipeline_runtime_kv.py`
- **Dominio**: Operaciones / control de pipeline
- **Contenido**: Tabla `pipeline_runtime_kv` (`key`, `value` JSONB, `updated_at`) para `pause.*` e `insights.llm`. Código: `pipeline_runtime_store.py`, `insights_pipeline_control.py`.

### 015: Worker tasks — un activo por documento y tipo
- **Archivo**: `015_worker_tasks_one_active_per_doc_task.py`
- **Dominio**: Event-Driven / semáforo `worker_tasks`
- **Contenido**: Limpieza de duplicados `assigned`/`started`; índice único parcial `(document_id, task_type)` para esos estados. Código: `assign_worker` usa `pg_advisory_xact_lock` + manejo `UniqueViolation` (`database.py`).
- **Status auditoría**: `CONSOLIDATED_STATUS.md` §96

**Fuente**: `app/backend/migrations/` — listar con `ls migrations/*.py` (excluir `.disabled`)

## Cómo Funcionan las Migraciones

### En la Inicialización

```
App Start → database.py cargado → migration_runner.py ejecutado →
→ Yoyo aplica migraciones pendientes (secuencialmente) →
→ Si todas exitosas: BD lista, app inicializa stores →
→ Si alguna falla: app se detiene con error crítico
```

### Ventajas del Enfoque

1. **Bloqueante**: No hay ambigüedad - o todas las migraciones pasan o la app falla
2. **Por dominios**: Cada migración trata un aspecto (dominio) del sistema
3. **Independencia**: Migraciones posteriores pueden depender de anteriores
4. **Rollback seguro**: Cada migración define cómo revertirse
5. **Auditabilidad**: Yoyo mantiene historial de qué se aplicó y cuándo

## Agregar Nueva Migración

Cuando necesites agregar nueva funcionalidad que requiera cambios en BD:

1. **Crea archivo**: `00X_nombre_descriptivo.py` siguiendo el patrón
2. **Define tema**: Comenta qué dominio es (una línea)
3. **Escribe SQL**: Usa `step()` para forward y rollback
4. **Establece dependencias**: Referencia migraciones previas en comentario
5. **Prueba localmente**: El sistema correrá automáticamente al iniciar

Ejemplo:
```python
"""
Migration 009: Add user preferences

Domain: User Management
Description: Tables for storing user preferences and settings
Depends on: 001_authentication_schema
"""

from yoyo import step

steps = [
    step(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            user_id INTEGER PRIMARY KEY,
            theme TEXT DEFAULT 'light',
            language TEXT DEFAULT 'es',
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """,
        "DROP TABLE IF EXISTS user_preferences"
    ),
]
```

## Mitigación de Errores

Si una migración falla:

1. **Investigar log**: El backend muestra exactamente cuál migración falló
2. **Revisar SQL**: Verifica que la SQL sea válida para PostgreSQL
3. **Fijar migración**: Corriges el archivo `.py`
4. **Reiniciar**: La siguiente vez el sistema reintentará automáticamente

## Recuperación de Datos Valiosos

Si por alguna razón necesitas recuperar datos:

- `rag_enterprise.db` es la BD principal - contiene TODO
- Los datos de insights (generados con IA) están en `document_insights` y `news_item_insights`
- Siempre hay un backup en `local-data/backups/`

## Consideraciones de Performance

- **Migraciones rápidas**: Usa índices desde el inicio
- **ALTER TABLE**: PostgreSQL soporta ADD COLUMN IF NOT EXISTS; usar para compatibilidad
- **Batch inserts**: Para migración 008, los INSERTs son IGNORE para no fallar con duplicados

## Referencias

- **Ejecutor**: `app/backend/migration_runner.py` — invocado desde `database.py` al cargar
- **Directorio**: `MIGRATIONS_DIR` (default `/app/migrations` en Docker)
- **Status**: `CONSOLIDATED_STATUS.md` §96 (015), §95 (file naming), histórico §88 (014)
