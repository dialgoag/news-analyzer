# 🚀 Cómo Usar el Nuevo Workflow de Peticiones

> **Propósito**: Guía paso a paso para procesar peticiones usando el nuevo sistema de 3 capas
> 
> **Para**: Usuarios que quieren entender exactamente qué hacer en cada sesión

**Creado**: 2026-03-05  
**Aplica a**: Nuevas peticiones, bugs, features, cualquier cambio

---

## 🎯 INICIO RÁPIDO (2 minutos)

### Cuando recibas una petición del usuario:

1. **Abre REQUESTS_REGISTRY.md**
   ```
   ¿Ya existe similar?
   → Sí: Ve al fix anterior
   → No: Continúa a paso 2
   ```

2. **Abre request-workflow.mdc**
   ```
   Sigue los 6 pasos:
   - PASO 1: Leer docs
   - PASO 1.5: Verificar contradicciones ← NUEVO
   - PASO 2-6: Normal (analizar, planificar, ejecutar)
   ```

3. **Al terminar**:
   ```
   Registra en REQUESTS_REGISTRY.md (nueva REQ-XXX)
   Registra en PLAN_AND_NEXT_STEP.md § Versiones
   Marca como [x] Hecho
   ```

---

## 📋 EJEMPLO COMPLETO: Procesar una Petición Nueva

### Escenario: Usuario pide "Optimizar búsqueda a < 1 segundo"

---

## **PASO 1: Leer Documentación Actual**

**Archivos a consultar**:
```bash
docs/ai-lcd/CONSOLIDATED_STATUS.md     # ¿Qué existe?
docs/ai-lcd/SESSION_LOG.md             # ¿Decisiones previas?
docs/ai-lcd/PLAN_AND_NEXT_STEP.md      # ¿Qué viene?
docs/ai-lcd/REQUESTS_REGISTRY.md       # ¿Se pidió antes?
```

**Qué buscar**:
- [ ] ¿Hay búsqueda actual? ¿Está optimizada?
- [ ] ¿Hay restricciones técnicas (Qdrant, SQLite)?
- [ ] ¿Hay peticiones relacionadas a performance?

**Reporta**:
```
He revisado:
✅ CONSOLIDATED_STATUS.md → Búsqueda existe pero no optimizada
✅ SESSION_LOG.md → Sesión 8: "Qdrant usa embeddings bge-m3"
✅ PLAN_AND_NEXT_STEP.md → No hay búsqueda en roadmap actual
✅ REQUESTS_REGISTRY.md → No hay REQ anterior sobre búsqueda

Conclusión: Primera petición sobre este tema
```

---

## **PASO 1.5: Verificar Contradicciones** ⭐ NUEVO

**Checklist**:

### 1️⃣ ¿Se pidió algo similar?
```
Busco en REQUESTS_REGISTRY.md:
- "search"? NO
- "performance"? Sí → REQ-001, REQ-002
  - REQ-001: "Hacer OCR más rápido" (✅ ESTABLE, v1.0)
  - REQ-002: "Dashboard sin saturación" (✅ ESTABLE, v1.0)

Conclusión: Performance se pidió, pero para OCR, no búsqueda
→ NO hay contradicción, son ortogonales
```

### 2️⃣ ¿Esta petición SUPERCEDE algo?
```
¿Nueva búsqueda contradice búsqueda anterior? 
→ No existe búsqueda anterior, es nueva

Conclusión: No supercede nada
```

### 3️⃣ ¿Podría romper v1.0?
```
v1.0 = Event-Driven OCR + Dashboard
Nueva = Optimizar búsqueda

¿Comparten recursos?
- OCR: usa Tika (no relacionado con búsqueda)
- Dashboard: display (no relacionado con búsqueda)
- Búsqueda: usa Qdrant (independiente)

Conclusión: SAFE - No afecta v1.0
```

### 4️⃣ ¿Qué versión entra?
```
Ver PLAN_AND_NEXT_STEP.md § Versiones:
- v1.0: Event-Driven ✅ ESTABLE
- v1.1: Indexing + Dedup 🔄 EN PROGRESO
- v1.2: Search Optimization ← NUEVA (proponer aquí)

Conclusión: Entra en v1.2 (nueva versión)
```

**Reporta**:
```
✅ VERIFICACIÓN CONTRADICCIONES COMPLETADA

Peticiones relacionadas: REQ-001, REQ-002 (pero ortogonales)
Riesgo: BAJO (no rompe v1.0)
Impacto v1.1: NINGUNO (dedup es independiente)
Versión: v1.2 (nueva, después de v1.1)

RESULTADO: ✅ SAFE - Proceder
```

---

## **PASO 2: Analizar Petición**

**Desglosa**:
```
1️⃣ Objetivo: Optimizar búsqueda a < 1s (vs actual 5s)

2️⃣ Archivos/componentes afectados:
   - backend/app.py → /api/search endpoint
   - backend/qdrant_service.py → búsquedas en Qdrant
   - frontend/App.jsx → barra de búsqueda (UX)

3️⃣ Dependencias:
   - Requiere: bge-m3 embeddings (ya existen)
   - Requiere: Qdrant corriendo (ya existe)
   - No requiere: cambios en OCR/Indexing

4️⃣ Riesgos:
   - ⚠️ Qdrant slow con 100k+ documentos
   - ⚠️ Embedding generation es bottleneck
   - ✅ Mitigación: caché de embeddings

5️⃣ Documentación a actualizar:
   - REQUESTS_REGISTRY.md (nueva REQ-004)
   - PLAN_AND_NEXT_STEP.md (agregar v1.2)
   - SESSION_LOG.md (decisión de optimización)
```

**Reporta**:
```
Análisis de petición:
- Objetivo: < 1s búsqueda (actualmente 5s)
- Archivos: app.py (search endpoint), qdrant_service.py
- Riesgos: Qdrant slow con muchos docs (mitigación: caché)
- Impacto docs: 3 archivos
```

---

## **PASO 3: Crear Plan**

**Estructura**:
```markdown
## Plan de Acción

### Cambios en Documentación
- [ ] Crear REQUESTS_REGISTRY.md § REQ-004
- [ ] Agregar PLAN_AND_NEXT_STEP.md § v1.2 (Search Optimization)
- [ ] Actualizar SESSION_LOG.md con decisión

### Cambios en Código
1. Backend optimization:
   - Agregar cache de embeddings (Redis o in-memory)
   - Optimizar query Qdrant (limit, pre-filter)
   - Batch embeddings generation
   
2. Frontend:
   - Debounce búsqueda (no llamar cada keystroke)
   - Loading indicator durante búsqueda

3. Testing:
   - Medir tiempo con 100k documentos
   - Verificar < 1s en 95% casos

### Verificación
- [ ] Búsqueda retorna en < 1s
- [ ] Sin regresión en OCR/Insights (v1.0 sigue ok)
- [ ] Logs sin errors
- [ ] Dashboard sigue estable
```

**Reporta**:
```
Plan diseñado:
1. Agregar cache de embeddings
2. Optimizar Qdrant queries
3. Debounce en frontend
4. Medir performance

Timeline: 2-3 horas
Riesgo: BAJO (cambios localizados a búsqueda)
```

---

## **PASO 4: Solicitar Aprobación**

**Formato**:
```
❓ APROBACIÓN REQUERIDA

He analizado tu petición: "Optimizar búsqueda a < 1s"

📋 Plan:
- Cache de embeddings para evitar re-cálculo
- Optimize Qdrant queries (limits + pre-filter)
- Debounce en frontend (no llamar cada keystroke)
- Medir: < 1s en 95% casos

⏱️ Timeline: 2-3 horas

⚠️ Consideraciones:
- Requiere agregar caché (Redis o in-memory)
- v1.0 (OCR/Dashboard) NO se toca
- Versión nueva: v1.2

¿Aprobado?
[ ] 1. Sí, proceder tal como está
[ ] 2. Modificar [aspecto]
[ ] 3. Cancelar
```

---

## **PASO 5: Actualizar Documentación + Auditoría**

### 5a. REQUESTS_REGISTRY.md (nueva REQ-004)

**Crear sección**:
```markdown
### **REQ-004: "Optimizar búsqueda a < 1 segundo"**

**Metadata**:
- **Fecha**: 2026-03-05
- **Sesión**: [Sesión 11](...uuid)
- **Prioridad**: 🟡 ALTA
- **Estado**: 🔄 EN PROGRESO

**Descripción Original**:
> "Las búsquedas tardan 5+ segundos. Necesito que sean más rápidas, < 1s ideal."

**Problema Identificado**:
- Búsquedas tardan 5-7 segundos con 100k documentos
- Embedding generation es bottleneck (2-3s)
- Sin caché → recalcula cada búsqueda

**Solución Implementada**:
- [ ] Cache de embeddings (in-memory dict, 1000 últimos)
- [ ] Optimize Qdrant queries (limit + pre-filter)
- [ ] Debounce frontend (300ms)

**Cambios Incluidos**:
- Fix #15: Cache embeddings (pendiente)
- Fix #16: Optimize Qdrant query (pendiente)
- Fix #17: Debounce frontend (pendiente)

**Verificaciones Completadas**:
- [ ] Búsqueda < 1s (95% casos)
- [ ] Sin regresión OCR/Insights
- [ ] Dashboard estable

**Linkeo**:
- SESSION_LOG.md § 2026-03-05: Decisión
- PLAN_AND_NEXT_STEP.md § v1.2: Agrupamiento
```

### 5b. PLAN_AND_NEXT_STEP.md § Versiones (agregar v1.2)

```markdown
### **v1.2 - Search Optimization** 🔄 (Nuevo)
**Fecha inicio**: 2026-03-05 16:00  
**Status**: 🔄 EN CONSTRUCCIÓN

**Peticiones incluidas**:
- REQ-004 - "Optimizar búsqueda a < 1 segundo"

**Cambios planeados** (3 total):
- Fix #15: Cache embeddings (pendiente)
- Fix #16: Optimize Qdrant (pendiente)
- Fix #17: Debounce frontend (pendiente)

**Cuidados especiales**:
- ⚠️ NO TOCAR: v1.0, v1.1 (estables)
- ⚠️ Depende de: Qdrant funcionando
- ⚠️ Puede afectar: ningún otro sistema

**Verificaciones requeridas ANTES de marcar ESTABLE**:
- [ ] Búsqueda < 1s (95% casos)
- [ ] OCR/Insights sigue funcionando
- [ ] Dashboard sigue estable
- [ ] Logs sin errors

**Timeline**: 2-3 horas
```

### 5c. SESSION_LOG.md (agregar decisión)

```markdown
## 2026-03-05

### Cambio: REQ-004 - Optimizar búsqueda a < 1s
- **Decisión**: Agregar cache de embeddings + optimize queries
- **Alternativas consideradas**:
  1. Usar Redis (rechazado: complejidad extra)
  2. Pre-calculate all embeddings (rechazado: costo memoria)
  3. ✅ **Elegida**: In-memory cache + lazy generation
- **Impacto en roadmap**: 
  - v1.2 nueva (Search Optimization)
  - Después de v1.1 (Indexing)
- **Riesgo**: Bajo (cambios localizados a búsqueda)
```

### 5d. CONSOLIDATED_STATUS.md (agregar Fix #15, #16, #17)

```markdown
### 15. Search Optimization: Cache Embeddings ✅
**Fecha**: 2026-03-05  
**Ubicación**: backend/qdrant_service.py líneas 45-75  
**Problema**: Búsquedas tardan 5s (embedding generation)  
**Solución**: Agregar in-memory cache de últimos 1000 embeddings  
**Impacto**: Búsquedas 3-4x más rápidas (1-2s)  
**⚠️ NO rompe**: OCR pipeline, Insights, Dashboard, Dedup  
**Verificación**: ✅ Búsqueda < 1s

### 16. Search Optimization: Qdrant Query Limits ✅
**Fecha**: 2026-03-05  
**Ubicación**: backend/qdrant_service.py líneas 120-140  
**Problema**: Qdrant retornaba 100 resultados (innecesario)  
**Solución**: Limitar a top 10, agregar pre-filter  
**Impacto**: Búsquedas 2x más rápidas  
**⚠️ NO rompe**: Mismo que arriba  

### 17. Search Optimization: Frontend Debounce ✅
**Fecha**: 2026-03-05  
**Ubicación**: frontend/App.jsx líneas 890-910  
**Problema**: Llamada API cada keystroke (300 calls/minuto)  
**Solución**: Debounce 300ms, una call cada keystroke release  
**Impacto**: 90% menos requests, UX más fluido  
**⚠️ NO rompe**: Dashboard, Reports, Notifications
```

**Reporta**:
```
📝 Documentación + Auditoría actualizada:

✅ REQUESTS_REGISTRY.md § REQ-004 creada
   - Rastreo completo: decisión, alternativas, riesgos

✅ PLAN_AND_NEXT_STEP.md § v1.2 agregada
   - Estado: EN CONSTRUCCIÓN
   - Verificaciones claras

✅ SESSION_LOG.md § 2026-03-05
   - Decisión: Cache in-memory (vs Redis)
   - Impacto roadmap: v1.2 nueva

✅ CONSOLIDATED_STATUS.md § Fixes #15-17
   - Ubicación exacta, problema, solución
   - ⚠️ QUÉ NO ROMPE: OCR, Insights, Dashboard
```

---

## **PASO 6: Ejecutar Cambios**

**Sigue el plan exacto**:

```bash
# 1. Cambio 1: Cache embeddings
# Archivo: backend/qdrant_service.py
# Líneas: 45-75
# Acción: Agregar embedding_cache = {}

# 2. Cambio 2: Optimize queries
# Archivo: backend/qdrant_service.py
# Líneas: 120-140
# Acción: Limit to top 10 + pre-filter

# 3. Cambio 3: Frontend debounce
# Archivo: frontend/App.jsx
# Líneas: 890-910
# Acción: Agregar debounce de 300ms

# 4. Testear
docker-compose up -d
# Búsquedas deben ser < 1s

# 5. Verificar v1.0 intacto
# OCR workers: ✅
# Insights workers: ✅
# Dashboard: ✅
```

**Reporta**:
```
✅ Cambios completados:
- Fix #15: Cache implementado (in-memory dict)
- Fix #16: Qdrant optimizado (limit 10 + pre-filter)
- Fix #17: Debounce frontend (300ms)

✅ Verificación:
- Búsqueda: 0.8s promedio (< 1s ✅)
- OCR: Sigue funcionando ✅
- Dashboard: Estable ✅
- Logs: Sin errores ✅
```

---

## 📋 CHECKLIST RESUMIDO

```
[ ] PASO 1: Leo documentación actual
    [ ] CONSOLIDATED_STATUS.md
    [ ] SESSION_LOG.md
    [ ] PLAN_AND_NEXT_STEP.md
    [ ] REQUESTS_REGISTRY.md

[ ] PASO 1.5: Verifico contradicciones
    [ ] ¿Se pidió similar? → Sí/No
    [ ] ¿Supercede algo? → Sí/No
    [ ] ¿Rompe v1.0/v1.1? → Sí/No
    [ ] ¿Qué versión? → vX.Y

[ ] PASO 2: Analizo petición
    [ ] Objetivo claro
    [ ] Archivos identificados
    [ ] Dependencias mapeadas
    [ ] Riesgos documentados

[ ] PASO 3: Creo plan
    [ ] Cambios documentación
    [ ] Cambios código (detallados)
    [ ] Verificaciones claras

[ ] PASO 4: Obtengo aprobación
    [ ] Plan presentado
    [ ] Aprobación explícita recibida

[ ] PASO 5: Registro en docs
    [ ] REQUESTS_REGISTRY.md (REQ-XXX)
    [ ] PLAN_AND_NEXT_STEP.md § Versiones
    [ ] SESSION_LOG.md § Decisión
    [ ] CONSOLIDATED_STATUS.md § Fixes

[ ] PASO 6: Ejecuto cambios
    [ ] Código modificado
    [ ] Tests pasados
    [ ] v1.0/v1.1 verificados
    [ ] Reporto resultados
```

---

## 🎯 RESUMEN: 3 NUEVAS CAPAS

| Capa | Qué Hace | Dónde | Cuándo |
|------|----------|-------|--------|
| **LAYER 1** | Rastrear peticiones | REQUESTS_REGISTRY.md | Cada petición nueva |
| **LAYER 2** | Detectar contradicciones | PASO 1.5 en workflow | Antes de analizar |
| **LAYER 3** | Agrupar en versiones | PLAN_AND_NEXT_STEP.md § 7 | Cuando marca "ESTABLE" |

---

## ✅ BENEFITS

```
✅ Cada petición tiene ID único (REQ-001, REQ-002, etc.)
✅ Busco si similar existe → evito trabajo duplicado
✅ Verifico contradicciones ANTES de ejecutar
✅ Rollback fácil de feature completa (versión atómica)
✅ Historial claro: usuario pidió X → se hizo Y → resultado Z
✅ Próximas sesiones: contexto completo disponible
```

---

**Siguiente**: Lee `SISTEMA_DE_PETICIONES_GUIA.md` para casos prácticos adicionales, o `REQUESTS_REGISTRY.md` para ver ejemplos (REQ-001, REQ-002, REQ-003).
