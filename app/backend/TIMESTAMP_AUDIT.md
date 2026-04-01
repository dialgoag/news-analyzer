# Auditoría de Timestamps: created_at / updated_at

## Estado Actual por Tabla

| Tabla | created_at | updated_at | Timestamps Alternativos | Crítico |
|----|----|----|----|---|
| **users** | ✅ YES | ❌ NO | last_login | Medio |
| **document_status** | ❌ NO | ❌ NO | ingested_at, indexed_at | **ALTO** |
| **worker_tasks** | ❌ NO | ❌ NO | assigned_at, started_at, completed_at | Medio |
| **processing_queue** | ✅ YES | ❌ NO | processed_at | Bajo |
| **news_items** | ✅ YES | ✅ YES | - | OK |
| **news_item_insights** | ✅ YES | ✅ YES | - | OK |
| **document_insights** | ✅ YES | ✅ YES | - | OK |
| **daily_reports** | ✅ YES | ✅ YES | report_date | OK |
| **weekly_reports** | ✅ YES | ✅ YES | week_start | OK |
| **notifications** | ✅ YES | ❌ N/A | - | OK (no updates) |
| **notification_reads** | ❌ N/A | ❌ N/A | read_at | OK (inmutable) |
| **ocr_performance_log** | ❌ N/A | ❌ N/A | timestamp | OK (append-only) |
| **pipeline_runtime_kv** | ❌ NO | ✅ YES | - | Bajo |
| **insight_cache** | ❌ NO | ❌ NO | cached_at, last_accessed_at | Bajo |

## Prioridad de Cambios

### 🔴 CRÍTICO (Rompe código actual)

1. **document_status** - ❌ NO tiene `created_at` / `updated_at`
   - **Problema**: `DocumentRepository` asume que existen → SQL errors
   - **Impacto**: Workers de indexing, OCR, chunking fallan
   - **Solución**: Agregar ambos timestamps

### 🟡 MEDIO (Buenas prácticas)

2. **worker_tasks** - ❌ NO tiene timestamps estándar
   - **Tiene**: `assigned_at`, `started_at`, `completed_at` (lifecycle)
   - **Consideración**: ¿Agregar `created_at` para auditoría? Lifecycle timestamps son suficientes
   - **Decisión**: **NO agregar** - lifecycle timestamps son más útiles

3. **users** - ✅ Tiene `created_at`, ❌ NO tiene `updated_at`
   - **Consideración**: ¿Se actualizan usuarios? (cambio de password, role, etc.)
   - **Decisión**: **SÍ agregar `updated_at`** para auditoría de cambios

### 🟢 BAJO (Opcional)

4. **processing_queue** - ✅ Tiene `created_at`, ❌ NO tiene `updated_at`
   - **Tiene**: `processed_at` (suficiente para su propósito)
   - **Decisión**: **NO agregar** - queue es transitoria

5. **pipeline_runtime_kv** - ❌ NO tiene `created_at`, ✅ Tiene `updated_at`
   - **Propósito**: Key-value store, solo importa última actualización
   - **Decisión**: **Agregar `created_at`** para saber cuándo se creó cada config

6. **insight_cache** - Usa `cached_at` / `last_accessed_at` (equivalentes)
   - **Decisión**: **NO cambiar** - nombres más específicos para su dominio

## Estándar Global Propuesto

### Regla de Oro

**Toda tabla transaccional con estado mutable DEBE tener `created_at` + `updated_at`**

### Excepciones Permitidas

- **Tablas append-only** (logs, events): Solo `timestamp` o `created_at`
- **Tablas inmutables** (junction tables): Solo `created_at` si aplica
- **Tablas con lifecycle específico** (worker_tasks): Usar timestamps de dominio
- **Tablas con semántica específica** (insight_cache): Nombres de dominio OK

### Implementación Estándar

```sql
-- Columnas
created_at TIMESTAMP NOT NULL DEFAULT NOW()
updated_at TIMESTAMP NOT NULL DEFAULT NOW()

-- Trigger para updated_at automático
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_<table>_updated_at 
BEFORE UPDATE ON <table> 
FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Índices (opcional, según uso)
CREATE INDEX idx_<table>_created ON <table>(created_at DESC);
CREATE INDEX idx_<table>_updated ON <table>(updated_at DESC);
```

## Plan de Acción

### Migration 018: Agregar timestamps estándar

```python
"""
Migration 018: Standardize timestamps (created_at/updated_at)

Adds created_at/updated_at to tables missing them per best practices.
"""

steps = [
    # 1. document_status (CRÍTICO)
    step("""
        ALTER TABLE document_status 
        ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    """),
    
    # 2. users (para auditoría)
    step("""
        ALTER TABLE users 
        ADD COLUMN updated_at TIMESTAMP NOT NULL DEFAULT NOW()
    """),
    
    # 3. pipeline_runtime_kv (para auditoría de configs)
    step("""
        ALTER TABLE pipeline_runtime_kv 
        ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT NOW()
    """),
    
    # 4. Crear función de trigger (reutilizable)
    step("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
           NEW.updated_at = NOW();
           RETURN NEW;
        END;
        $$ language 'plpgsql'
    """),
    
    # 5. Triggers para updated_at automático
    step("""
        CREATE TRIGGER update_document_status_updated_at 
        BEFORE UPDATE ON document_status 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """),
    
    step("""
        CREATE TRIGGER update_users_updated_at 
        BEFORE UPDATE ON users 
        FOR EACH ROW EXECUTE FUNCTION update_updated_at_column()
    """),
    
    # 6. Índices para queries por timestamp
    step("CREATE INDEX idx_document_status_created ON document_status(created_at DESC)"),
    step("CREATE INDEX idx_document_status_updated ON document_status(updated_at DESC)"),
]
```

## Impacto en Código

### Archivos que se benefician

1. **PostgresDocumentRepository** ✅
   - Ya usa `created_at` / `updated_at` en código
   - Solo falta que existan en DB

2. **PostgresNewsItemRepository** ✅
   - news_items y news_item_insights YA tienen timestamps
   - No requiere cambios

3. **Legacy stores** (document_status_store, etc.)
   - Pueden seguir usando solo `ingested_at` hasta eliminarse
   - Compatibilidad backward

### Archivos que NO cambian

- `worker_tasks`: Lifecycle timestamps son suficientes
- `processing_queue`: Es transitoria, created_at suficiente
- `insight_cache`: Dominio-específico, OK como está

## Resumen

**Cambios necesarios:**
- ✅ Agregar `created_at` + `updated_at` a **document_status** (CRÍTICO)
- ✅ Agregar `updated_at` a **users** (auditoría)
- ✅ Agregar `created_at` a **pipeline_runtime_kv** (auditoría)
- ✅ Triggers automáticos para `updated_at`
- ✅ Índices para performance

**Resultado:**
- Sistema consistente con estándar de industria
- Auditoría completa de cambios
- Código ya preparado (repositories) funciona sin cambios adicionales
- Troubleshooting facilitado
