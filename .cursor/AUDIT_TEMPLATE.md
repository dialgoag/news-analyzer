# 📋 Plantilla de Auditoría - Cómo Registrar Cambios

## Propósito

Esta es una **plantilla de referencia** para mostrar exactamente CÓMO registrar cambios en el historial para que:
- ✅ Nadie olvide qué se hizo
- ✅ Se eviten regresiones
- ✅ Todo el mundo sepa qué no debe tocarse

---

## 📝 Plantilla Completa para un Cambio

Usar esta estructura CADA VEZ que hagas cambios:

### Paso 1: Registrar en CONSOLIDATED_STATUS.md

```markdown
### [NÚMERO]. [Título del cambio] ✅
**Fecha**: 2026-03-05  
**Ubicación**: archivo/nombre.py líneas X-Y  
**Problema**: [Descripción breve del problema actual]  
**Solución**: [Qué se cambió exactamente]  
**Impacto**: [Qué mejora/cambia]  
**⚠️ NO rompe**: 
  - Funcionalidad A ✅
  - Funcionalidad B ✅
  - Funcionalidad C ✅
**Verificación**:
  - [ ] Punto de control 1
  - [ ] Punto de control 2
  - [ ] Punto de control 3
```

### Paso 2: Registrar en SESSION_LOG.md

```markdown
## 2026-03-05

### Cambio: [Título del cambio]
**Tipo**: [Bug fix / Feature / Refactor / Optimization]  
**Prioridad**: [Alta / Media / Baja]  

**Decisión**: [Por qué se decidió hacer esto ahora]  
**Alternativas consideradas**: 
  - Opción A: [Por qué no]
  - Opción B: [Por qué no]

**Impacto en roadmap**: 
  - Acelera: [Qué feature futura]
  - Retrasa: [Nada / o qué se retrasa]

**Riesgos conocidos**: 
  - Risk 1: [Cómo se mitiga]
  - Risk 2: [Cómo se mitiga]

**Próximos pasos afectados**: 
  - Feature X: [Cómo se beneficia]
  - Feature Y: [Neutral]
```

### Paso 3: Actualizar PLAN_AND_NEXT_STEP.md

```markdown
## ✅ Completado (Historial)
- [x] Cambio A (2026-03-05) - ESTABLE, test passed
- [x] Cambio B (2026-03-04) - ESTABLE, crítico para OCR

## 🚫 Congelado (No tocar)
- ❌ Funcionalidad X - Razón: crítica
  - Depende de: [X, Y]
  - Ver: CONSOLIDATED_STATUS.md § Fix #N
  - Ver: SESSION_LOG.md § 2026-03-04
```

---

## 🎯 Ejemplo Completo: Cambio Real

### Escenario: Se arreglaron 3 SQL errors el 2026-03-04

#### CONSOLIDATED_STATUS.md
```markdown
## 🔧 FIXES APLICADOS HOY (2026-03-04)

### 1. SQL Error: `no such column: task_id` ✅
**Fecha**: 2026-03-04  
**Ubicación**: backend/app.py líneas 2962, 3021  
**Problema**: get_workers_status endpoint usaba `SELECT task_id FROM worker_tasks` pero columna no existe  
**Solución**: Cambié a `SELECT document_id FROM worker_tasks` (nombre correcto)  
**Impacto**: Workers status endpoint funciona sin errores, devuelve status correcto  
**⚠️ NO rompe**: 
  - OCR workers ✅
  - Insights workers ✅
  - Dashboard metrics ✅
  - Event-driven queue ✅
**Verificación**:
  - [x] Endpoint responde sin errors
  - [x] GET /api/workers/status devuelve status válido
  - [x] Dashboard muestra workers correctamente

### 2. SQL Error: `no such column: id` ✅
**Fecha**: 2026-03-04  
**Ubicación**: backend/app.py línea 1561  
**Problema**: Insights fallback hacía `SELECT id FROM news_item_insights` pero id no existe  
**Solución**: Cambié a `SELECT news_item_id FROM news_item_insights`  
**Impacto**: Fallback para news_item_insights funciona correctamente, insights se cargan sin error  
**⚠️ NO rompe**: 
  - OCR pipeline ✅
  - Dashboard ✅
  - Deduplication ✅
**Verificación**:
  - [x] Insights cargan correctamente
  - [x] Fallback no genera errors

### 3. Async Workers Never Awaited ✅
**Fecha**: 2026-03-04  
**Ubicación**: backend/app.py líneas ~1765, ~1600  
**Problema**: Scheduler (sync context) intentaba usar `asyncio.create_task()` que solo funciona en async context  
**Solución**: Cambié a `asyncio.run_coroutine_threadsafe()` que funciona en cualquier thread  
**Impacto**: Workers async se ejecutan correctamente en background, no hay "coroutine never awaited" warnings  
**⚠️ NO rompe**: 
  - OCR pipeline ✅
  - Insights pipeline ✅
  - Event-driven queue ✅
  - Dashboard refresh ✅
**Verificación**:
  - [x] Logs no tienen "coroutine never awaited"
  - [x] Workers ejecutándose en background
  - [x] Sin errores en scheduler jobs
```

#### SESSION_LOG.md
```markdown
## 2026-03-04

### Cambio: SQL Errors - task_id, id, async context
**Tipo**: Bug fix (critical path)  
**Prioridad**: Alta  

**Decisión**: Se detectaron 3 SQL errors bloqueando funcionalidades. Se arreglaron inmediatamente porque impactaban status viewers y insights.  

**Alternativas consideradas**: 
  - Ignorar: No, son blockers
  - Defer: No, bloquean workers status

**Impacto en roadmap**: 
  - Acelera: Deduplication verification (workers status era blocker)
  - Retrasa: Nada

**Riesgos conocidos**: 
  - Risk: Hay más queries con nombres de columnas antiguos
  - Mitigación: Grep'd codebase, no encontré más

**Próximos pasos afectados**: 
  - Verification script: Ahora puede ejecutarse
  - Deduplication audit: Ahora puede contar workers
```

#### PLAN_AND_NEXT_STEP.md
```markdown
## ✅ Completado (2026-03-04)
- [x] SQL Error: task_id (2026-03-04) - ESTABLE ✅
- [x] SQL Error: id (2026-03-04) - ESTABLE ✅
- [x] Async context issue (2026-03-04) - ESTABLE ✅

## 🚫 Congelado (No tocar sin razón crítica)
- ❌ Database schema (worker_tasks, news_item_insights)
  - Razón: Recién arregladas queries, delicadas
  - Ver: CONSOLIDATED_STATUS.md § Fixes Aplicados HOY
  - Ver: SESSION_LOG.md § 2026-03-04
```

---

## ✅ Checklist para Registrar Cambios

Cuando termines un cambio:

### En CONSOLIDATED_STATUS.md
- [ ] ¿Incluí número secuencial?
- [ ] ¿Incluí fecha?
- [ ] ¿Incluí ubicación exacta (archivo + líneas)?
- [ ] ¿Incluí problema, solución, impacto?
- [ ] ¿Marqué qué NO se rompe?
- [ ] ¿Incluí verificación?
- [ ] ¿El registro es CONCISO (3-5 líneas por sección)?

### En SESSION_LOG.md
- [ ] ¿Incluí tipo de cambio?
- [ ] ¿Incluí decisión (por qué)?
- [ ] ¿Incluí alternativas consideradas?
- [ ] ¿Incluí impacto en roadmap?
- [ ] ¿Incluí riesgos y mitigaciones?

### En PLAN_AND_NEXT_STEP.md
- [ ] ¿Marqué cambio como [x] Completado?
- [ ] ¿Agregué fecha?
- [ ] ¿Incluí estado (ESTABLE / EN PROGRESO)?
- [ ] ¿Incluí sección 🚫 Congelado si es crítico?

---

## 🔴 Anti-Patrones (Qué NO hacer)

### ❌ Registrar sin ubicación
```
Problema: Se arregló un bug
```
**Por qué es malo**: Nadie sabe dónde está el cambio

### ✅ Correcto
```
Ubicación: backend/app.py línea 2962
Problema: Columna task_id no existe
```

---

### ❌ Registrar sin "qué no se rompe"
```
Cambio: Se refactorizó indexing
```
**Por qué es malo**: No sabes qué verificar, qué podría romperse

### ✅ Correcto
```
⚠️ NO rompe: OCR pipeline, Dashboard, Deduplication
Verificación: [x] OCR workers ejecutándose
```

---

### ❌ Decisión sin contexto
```
SESSION_LOG: "Se cambió el código"
```
**Por qué es malo**: Nadie entiende POR QUÉ

### ✅ Correcto
```
Decisión: Se refactorizó porque OCR workers estaban bloqueados por sync IO
Alternativas: Mantener sync (no escala), usar threads (hecho hoy)
```

---

## 📌 Resumen

**El historial es el contrato del proyecto:**
- ✅ Qué está seguro cambiar
- ✅ Qué está congelado
- ✅ Qué se hizo, cuándo, por qué
- ✅ Qué nunca debe romperse

**Registralo BIEN desde el inicio. Te ahorrará horas de debugging.**

---

**Última actualización**: 2026-03-05  
**Próxima revisión**: Cuando haya próximos cambios
