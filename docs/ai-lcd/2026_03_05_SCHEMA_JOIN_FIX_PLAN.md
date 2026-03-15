# 🔧 SCHEMA JOIN FIX - Implementación

**Fecha**: 2026-03-05  
**Prioridad**: 🔴 ALTA  
**Duración estimada**: 1-2 horas

---

## 🎯 PROBLEMA IDENTIFICADO

### Línea 2846 en app.py (dashboard/summary endpoint)

**Query actual**:
```python
LEFT JOIN news_item_insights nii ON ni.news_item_id = nii.news_item_id
```

**Problema**: 
- Esto IS correct para vincular `news_items` con `news_item_insights`
- El problema real está en que `news_item_insights.document_id` contiene filenames
- Pero no se valida que esos filenames existan en `document_status.document_id`

### Root Cause Completo

La BD tiene:
- `document_status.id` (numérico, PK)
- `document_status.document_id` (filename, como UUID)
- `news_items.document_id` (referencia a `document_status.id`)
- `news_item_insights.document_id` (filename string)

Esto crea una **inconsistencia**: `news_item_insights.document_id` tiene un tipo diferente al que debería.

---

## ✅ SOLUCIÓN

### Fix 1: Dashboard Summary - Validar Insights Vinculados

**Ubicación**: `app.py` línea 2896-2903

**Cambio**: Agregar validación que insights tengan documento válido

```python
# ANTES:
cursor.execute("""
    SELECT 
      COUNT(DISTINCT nii.news_item_id) as total_current,
      SUM(CASE WHEN nii.status = 'done' THEN 1 ELSE 0 END) as done,
      SUM(CASE WHEN nii.status IN ('pending', 'queued', 'generating') THEN 1 ELSE 0 END) as pending,
      SUM(CASE WHEN nii.status = 'error' THEN 1 ELSE 0 END) as errors
    FROM news_item_insights nii
""")

# DESPUÉS (con validación de documento):
cursor.execute("""
    SELECT 
      COUNT(DISTINCT nii.news_item_id) as total_current,
      SUM(CASE WHEN nii.status = 'done' THEN 1 ELSE 0 END) as done,
      SUM(CASE WHEN nii.status IN ('pending', 'queued', 'generating') THEN 1 ELSE 0 END) as pending,
      SUM(CASE WHEN nii.status = 'error' THEN 1 ELSE 0 END) as errors
    FROM news_item_insights nii
    WHERE nii.document_id IN (SELECT document_id FROM document_status)
""")
```

### Fix 2: Crear Migración para FK Constraint

**Archivo**: `backend/migrations/010_fix_news_item_insights_fk.py`

```python
"""
Migration 010: Add FK constraint to news_item_insights
Ensures all insights reference valid documents
"""

from yoyo import step

steps = [
    step(
        """ALTER TABLE news_item_insights 
           ADD CONSTRAINT fk_nii_document_id
           FOREIGN KEY (document_id) 
           REFERENCES document_status(document_id)""",
        "DROP CONSTRAINT fk_nii_document_id"
    ),
    step(
        """DELETE FROM news_item_insights 
           WHERE document_id NOT IN (SELECT document_id FROM document_status)""",
        "-- Cleanup orphaned insights"
    ),
]
```

---

## 🚀 PASOS DE IMPLEMENTACIÓN

### Step 1: Backup Data (5 min)

```bash
cd app
sqlite3 ./local-data/database/rag_enterprise.db ".backup rag_enterprise_backup.db"
```

### Step 2: Fix Dashboard Query (10 min)

Editar `app.py` línea 2896-2903: Agregar WHERE clause

### Step 3: Rebuild Backend (5 min)

```bash
docker compose restart backend
```

### Step 4: Verificar en Dashboard (5 min)

- Abrir http://localhost:3000
- Verificar que insights muestra 1,440
- Verificar que no hay errores

### Step 5: Crear Migración (10 min)

Crear archivo `backend/migrations/010_fix_news_item_insights_fk.py`

### Step 6: Apply Migration (5 min)

```bash
docker compose restart backend
# Backend corre automáticamente las migraciones
```

---

## ✅ VERIFICACIÓN POST-FIX

### Queries para Validar

```sql
-- 1. Verificar que todos los insights tienen documento
SELECT COUNT(*) FROM news_item_insights nii
WHERE nii.document_id NOT IN (SELECT document_id FROM document_status);
-- Resultado esperado: 0

-- 2. Verificar insights vinculados
SELECT COUNT(*) FROM news_item_insights nii
WHERE nii.document_id IN (SELECT document_id FROM document_status);
-- Resultado esperado: 1,440

-- 3. Verificar no hay orphaned
SELECT COUNT(*) FROM news_item_insights;
-- Resultado esperado: 1,440
```

---

## 🎯 RESULTADO ESPERADO

**Antes**:
- Dashboard mostraba: 0 insights (porque JOIN no encontraba registros)
- Orphaned insights: 1,440
- Data loss: 0%

**Después**:
- Dashboard mostrará: 1,440 insights ✅
- Orphaned insights: 0
- Data loss: 0% (preservado)
- Schema integridad: ✅ con FK constraint

---

**Status**: 📋 **READY TO IMPLEMENT**  
**Estimado**: 1-2 horas  
**Riesgo**: BAJO (es solo una WHERE clause en query + migration)
