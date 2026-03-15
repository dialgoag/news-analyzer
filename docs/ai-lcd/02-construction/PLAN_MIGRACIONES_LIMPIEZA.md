# 🔧 Plan Integral: Migraciones Yoyo + Limpieza de Duplicados

## Estado Actual

**Antes de proceder**:
- ✅ Docker containers detenidos
- ✅ Datos en BD seguros (206 documentos válidos)
- ✅ Archivos en disco: 706 (3.42x duplicados)
- ✅ Sistema Yoyo-Migrations completamente implementado
- ⚠️ Bug de deduplicación identificado: document_id basado en timestamp

## Plan: 3 Fases (Simplificado)

**BUENA NOTICIA**: Migration 008 ahora incluye limpieza automática de duplicados

### FASE 1: Diagnóstico (15 min)

```bash
python diagnose_dedup_deep.py
# Verifica estado de duplicados
```

### FASE 2: Backup (5 min)

```bash
bash backup.sh
# Crea respaldo antes de limpiar
```

### FASE 3: Aplicar Migraciones (30 min)

```bash
# Las migraciones automáticamente:
# 1. ✅ Crean 8 nuevas tablas
# 2. ✅ Migran datos de DBs antiguas
# 3. ✅ LIMPIAN archivos duplicados (Migration 008)
# 4. ✅ Preservan insights valiosos

docker-compose down
docker-compose up -d --build

# Verificar
docker-compose logs backend | grep -E "MIGRATION|cleanup|✅"
```

### FASE 4: Verificación (10 min)

```bash
# Verificar migraciones aplicadas
docker-compose exec backend sqlite3 /app/data/rag_enterprise.db \
  "SELECT COUNT(*) FROM _yoyo_migration;"
# Debe mostrar: 8

# Verificar datos preservados
docker-compose exec backend sqlite3 /app/data/rag_enterprise.db \
  "SELECT COUNT(*) FROM document_insights WHERE status='done';"
# Debe mostrar: número > 0

# Verificar archivos limpios
ls local-data/uploads | wc -l
# Debe mostrar: ~206 (similar a BD)
```

---

### FASE 4: Fix de Deduplicación Futura (próximo sprint)

Después de migraciones, implementar fix permanente:

#### 4.1 Cambiar document_id a content-hash

**En `app.py` líneas 1040 y 1915**:

Cambiar:
```python
# ❌ ANTES
document_id = f"{datetime.now().timestamp()}_{filename}"

# ✅ DESPUÉS
content_hash = hashlib.sha256(file_bytes).hexdigest()
document_id = f"{content_hash}_{filename}"
```

#### 4.2 Crear migración para tabla de hashes
```python
# Migration 009: Add file_hashes table
# backend/migrations/009_file_hashes_schema.py

from yoyo import step

steps = [
    step(
        """
        CREATE TABLE IF NOT EXISTS file_hashes (
            content_hash TEXT PRIMARY KEY,
            document_id TEXT UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (document_id) REFERENCES document_status(document_id)
        )
        """,
        "DROP TABLE IF EXISTS file_hashes"
    ),
    step(
        "CREATE INDEX IF NOT EXISTS idx_file_hashes_doc ON file_hashes(document_id)",
        "DROP INDEX IF EXISTS idx_file_hashes_doc"
    ),
]
```

#### 4.3 Implementar deduplicación en upload/inbox
```python
# En run_inbox_scan() y upload_document()
def check_duplicate_content(file_bytes, filename):
    content_hash = hashlib.sha256(file_bytes).hexdigest()
    
    # Check if already processed
    existing = db.query(
        "SELECT document_id FROM file_hashes WHERE content_hash = ?",
        content_hash
    )
    
    if existing:
        logger.info(f"Archivo duplicado detectado, reutilizando {existing}")
        return existing  # ← Reutilizar en lugar de crear nuevo
    
    # Nuevo archivo
    document_id = f"{content_hash}_{filename}"
    return document_id
```

---

## Checklist por Fase

### ✅ FASE 1: Diagnóstico
- [ ] Ejecutar `python diagnose_dedup_deep.py`
- [ ] Revisar output (verifica 706 vs 206)
- [ ] Documentar estado actual

### ✅ FASE 2: Backup
- [ ] Ejecutar `bash backup.sh`
- [ ] Verificar backup en `local-data/backups/`
- [ ] Listar backups creados

### ✅ FASE 3: Migraciones (con limpieza automática)
- [ ] `docker-compose down`
- [ ] `docker-compose up -d --build`
- [ ] Esperar a que inicie (2-3 min)
- [ ] Verificar logs: `docker-compose logs backend | grep -E "MIGRATION|cleanup|✅"`
- [ ] Verificar: 8 migraciones aplicadas
- [ ] Verificar: Datos preservados (insights)
- [ ] Verificar: Archivos limpios (~206 en uploads/)

### ✅ FASE 4: Verificación Final
- [ ] Contar archivos post-limpieza: `ls local-data/uploads | wc -l`
- [ ] Comparar con BD: `docker-compose exec backend sqlite3 /app/data/rag_enterprise.db "SELECT COUNT(*) FROM document_status;"`
- [ ] Verificar no hay errores en logs
- [ ] Confirmar insights preservados
- [ ] ✅ Todo listo para development

### ✅ FASE 5: Fix Permanente (próximo sprint)
- [ ] Crear Migration 009 (file_hashes table)
- [ ] Modificar upload_document() → usar content_hash
- [ ] Modificar run_inbox_scan() → usar content_hash
- [ ] Implementar check_duplicate_content()
- [ ] Tests de deduplicación

---

## Timeline Recomendado

```
HOY (decisión + acción):
  15 min  → Fase 1: Diagnóstico
  5 min   → Fase 2: Backup
  30 min  → Fase 3: Migraciones + Limpieza AUTOMÁTICA
  10 min  → Fase 4: Verificación
  --------
  60 min  TOTAL (1 hora)

PRÓXIMA SEMANA:
  2-3 h   → Fase 5: Fix permanente (content_hash-based document_id)
```

---

## Riesgos y Mitigación

| Riesgo | Impacto | Mitigación |
|--------|--------|-----------|
| Perder datos duplicados | BAJO | Backup antes de limpiar |
| Migraciones fallan | ALTO | Backup.sh + rollback plan |
| BD inconsistente | ALTO | Migration 008 usa INSERT OR IGNORE |
| Archivos quedan huérfanos | MEDIO | Scripts de verificación |

---

## Documentación Post-Migraciones

Después de completar, actualizar:
- `docs/ai-dlc/02-construction/DATABASE_MIGRATIONS.md` (status)
- `docs/ai-dlc/02-construction/DEDUPLICATION_STRATEGY.md` (nueva)
- README de project (mencionar limpieza hecha)

---

## ¿Qué Hacer Ahora?

**Siguiente paso**:
```bash
# 1. Ejecutar diagnóstico
python diagnose_dedup_deep.py

# 2. Revisar output
# 3. Decidir: Opción A o Opción B

# 4. Informar decisión aquí
# 5. Proceder con fase elegida
```

**Output esperado de diagnóstico**:
```
Archivos físicos: 706
Documentos en BD: 206

Por carpeta:
  [timestamp]_archivo1.pdf: 5 veces
  [timestamp]_archivo2.pdf: 3 veces
  ...

Recomendación: LIMPIAR ANTES DE MIGRACIONES
```

---

**Status**: 🟡 ESPERANDO DECISIÓN Y DIAGNÓSTICO

Plan completo documentado. Listo para ejecutar cuando des la orden.
