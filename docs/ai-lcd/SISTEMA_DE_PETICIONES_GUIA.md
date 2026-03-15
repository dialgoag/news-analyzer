# 🗺️ Guía: Sistema de Rastreo de Peticiones

> **Propósito**: Entender cómo usar los 3 nuevos documentos para rastrear peticiones sin perder contexto

**Creado**: 2026-03-05  
**Para**: Usuarios que quieren entender estructura de peticiones → cambios → consolidación

---

## 📚 Los 3 Documentos Clave

| Documento | Propósito | Cuándo Leerlo |
|-----------|-----------|---------------|
| **REQUESTS_REGISTRY.md** | Rastrear peticiones originales (REQ-001, REQ-002, etc.) | Antes de nueva petición (buscar si similar existe) |
| **request-workflow.mdc** | Cómo procesar una petición (6 pasos + Paso 1.5 contradicciones) | Cuando recibes nueva petición |
| **PLAN_AND_NEXT_STEP.md § 7** | Agrupar peticiones en versiones consolidadas (v1.0, v1.1, etc.) | Cuando marca grupo como "ESTABLE" |

---

## 🔄 Flujo Típico de una Petición

### Escenario: Usuario pide "Optimizar performance de búsqueda"

#### **PASO 1**: Leer REQUESTS_REGISTRY.md
```
Usuario: "Optimizar performance de búsqueda"
→ Busco en tabla si hay algo similar
→ ¿Existe REQ-002 "Dashboard sin saturación Tika"? 
   → Sí, pero es sobre OCR, no búsqueda
   → No es similar
→ Conclusion: Es petición NUEVA
```

#### **PASO 1.5**: Verificar Contradicciones (request-workflow.mdc)
```
Nuevo: "Optimizar performance de búsqueda"
→ ¿Se pidió algo similar? NO
→ ¿Contradice v1.0 Event-Driven? NO
→ ¿Podría romper OCR? NO
→ Conclusion: SAFE - Sin contradicciones
```

#### **PASO 2-6**: Procesar (como siempre)
- Analizar
- Planificar
- Aprobación usuario
- Registrar + Documentar
- Ejecutar

#### **PASO 5 Especial**: Registrar en REQUESTS_REGISTRY.md
```markdown
### **REQ-004: "Optimizar performance de búsqueda"**

**Metadata**:
- Fecha: 2026-03-05
- Sesión: [Sesión 11](...uuid)
- Prioridad: 🟡 ALTA
- Estado: 🔄 EN PROGRESO

**Descripción Original**:
> "Las búsquedas tardan 5+ segundos. Necesito que sean más rápidas, < 1s ideal."

[... resto de secciones ...]
```

#### **PASO 5 Extra**: Actualizar PLAN_AND_NEXT_STEP.md § Versiones
```markdown
### **v1.2 - Search Optimization** 🔄 (nuevo)
**Peticiones incluidas**:
- REQ-004 - "Optimizar performance de búsqueda"

**Status**: 🟡 EN CONSTRUCCIÓN
[... resto de detalles ...]
```

---

## 🎯 Casos Prácticos

### Caso 1: "¿Se pidió esto antes?"

**Usuario pregunta**: "¿Podemos paralelizar insights?"

**Proceso**:
1. Abro REQUESTS_REGISTRY.md
2. Busco "paralleliz" / "insight"
3. Encuentro REQ-001 con link a SESSION_LOG § Sesión 10
4. Leo que SÍ se pidió y ya está hecho (Fix #6)
5. Respondo: "Ya existe (REQ-001, v1.0 ESTABLE)"

---

### Caso 2: "¿Esto contradice algo anterior?"

**Usuario pide**: "Cambiar de asyncio a threading para OCR"

**Proceso** (PASO 1.5):
1. Busco en REQUESTS_REGISTRY.md: REQ-001 dice "event-driven async OCR"
2. Nuevo request contradice: "threading" vs "asyncio"
3. Verifico SESSION_LOG § Sesión 10: "Decidimos asyncio porque..."
4. En plan explico: "REQ-001 SUPERCEDE esto, razón: ..."
5. Considero aprobación usuario

---

### Caso 3: "¿Qué cambios fueron por qué petición?"

**Usuario pregunta**: "¿Por qué hiciste Fix #8 (health check cache)?"

**Proceso**:
1. Busco en REQUESTS_REGISTRY.md todas las REQ con "health" / "cache"
2. Encuentro REQ-002: "Dashboard sin saturación Tika"
3. Fix #8 está en REQ-002 § Cambios Incluidos
4. Puedo trazar: Usuario pidió (REQ-002) → Incluye fix (Fix #8)

---

### Caso 4: "¿Qué es ESTABLE y qué NO?"

**Usuario pregunta**: "¿Qué puedo hacer para dashboard?"

**Proceso**:
1. Leo PLAN_AND_NEXT_STEP.md § 7 (Versiones Consolidadas)
2. v1.0: ✅ ESTABLE (Event-Driven + Dashboard) - NO TOCAR
3. v1.1: 🔄 EN CONSTRUCCIÓN (Indexing + Dedup) - En progress
4. Respondo: "v1.0 está congelada, v1.1 es siguiente"

---

### Caso 5: "¿Cómo rollback una feature completa?"

**Usuario dice**: "Revierte OCR event-driven y vuelve a ThreadPoolExecutor"

**Proceso**:
1. Busco PLAN_AND_NEXT_STEP.md § v1.0 (Event-Driven Base)
2. Leo: "Cambios agrupados: Fix #5, #6, #8, #9, #10, #11"
3. En CONSOLIDATED_STATUS.md busco esos 6 fixes
4. Veo commit hashes asociados
5. Puedo hacer: `git revert <6 commits>`

---

## 🛠️ Checklists Prácticos

### Checklist: Nueva Petición

```
[ ] Leer REQUESTS_REGISTRY.md (¿Se pidió antes?)
[ ] Ejecutar PASO 1.5: Verificar contradicciones
    [ ] ¿Se pidió similar? ¿Rechazada o SUPERCEDIDA?
    [ ] ¿Rompe algo de v1.0/v1.1?
    [ ] ¿Qué versión entra?
[ ] Procesar petición (PASOS 2-6)
[ ] Registrar en REQUESTS_REGISTRY.md (nueva REQ-XXX)
[ ] Actualizar PLAN_AND_NEXT_STEP.md (nueva versión o agregar a existente)
[ ] Marcar completo
```

### Checklist: Marcar Feature como ESTABLE

```
[ ] Todos los cambios ejecutados
[ ] Verificaciones completadas (checklist en plan)
[ ] Logs sin errores
[ ] Testeado manualmente
[ ] Abro PLAN_AND_NEXT_STEP.md § Versiones
[ ] Marco versión como "✅ ESTABLE"
[ ] Completo: "Cambios agrupados", "Verificaciones", "Rollback"
[ ] Congelo en "❌ 🚫 CONGELADO: [Razón]"
[ ] Siguiente versión entra en "🔄 EN CONSTRUCCIÓN"
```

### Checklist: Auditoría de Contradicciones

```
[ ] Para cada REQ nueva, verificar:
    [ ] ¿Contradice REQ anterior? (buscar en REQUESTS_REGISTRY)
    [ ] ¿Supercede algo? (marcar anterior como SUPERCEDIDA)
    [ ] ¿Afecta otra versión? (incluir verificación en plan)
    [ ] ¿Entra en nueva versión o versión existente?
[ ] Documentar en SESSION_LOG.md si hay decisiones complejas
```

---

## 📊 Estructura Mental

```
USUARIO PIDE (en sesión N)
     ↓
REQUESTS_REGISTRY.md (registro persistente)
     ├─ REQ-001 (sesión 3)
     ├─ REQ-002 (sesión 10)
     ├─ REQ-003 (sesión 11)
     └─ REQ-004 (sesión N) ← NUEVA
     
PASO 1.5: ¿Contradice?
     ├─ Buscar si similar
     ├─ Buscar si SUPERCEDE
     ├─ Verificar impacto
     └─ Decidir versión (v1.0, v1.1, v1.2, etc.)

EJECUTAR (PASOS 2-6)
     ↓
REGISTRAR
     ├─ CONSOLIDATED_STATUS.md (Fix #14)
     ├─ SESSION_LOG.md (Decisión)
     └─ REQUESTS_REGISTRY.md (REQ-004 detallada)

AGRUPAR EN VERSIÓN
     ↓
PLAN_AND_NEXT_STEP.md § Versiones
     ├─ v1.0: ✅ ESTABLE (congelada)
     ├─ v1.1: 🔄 EN CONSTRUCCIÓN (in progress)
     └─ v1.2: 🟡 PLANEADA (next)
```

---

## 🎓 Ejemplo Completo: REQ-002

**Petición original** (Sesión 10):
> "El dashboard marca 'unhealthy' frecuentemente"

**En REQUESTS_REGISTRY.md**:
- ID: REQ-002
- Estado: ✅ ESTABLE
- Cambios: Fix #8, #10, #11
- Versión: v1.0

**En CONSOLIDATED_STATUS.md**:
- Fix #8: Optimizar health check
- Fix #10: Async workers dispatch
- Fix #11: Dashboard sticky header

**En SESSION_LOG.md § Sesión 10**:
- "Decidimos cache 3s porque health check no es crítico"
- "Decidimos sticky header porque UX"

**En PLAN_AND_NEXT_STEP.md § v1.0**:
- "v1.0 - Event-Driven Base + Dashboard Confiable"
- "Cambios agrupados: Fix #8, #10, #11"
- "Status: ESTABLE (Congelada, no modificar)"

**Usar esta info para**:
- ✅ Saber que dashboard es confiable (ESTABLE)
- ✅ Saber por qué el health check es rápido (decisión documentada)
- ✅ Poder rollback de v1.0 si algo falla (6 commits específicos)
- ✅ Evitar cambiar dashboard sin consideración de v1.0

---

## ❓ Preguntas Frecuentes

### P: "¿Cada petición necesita nueva versión?"
**R**: No. Versión = grupo de peticiones **relacionadas** que forman feature. 
- REQ-001 + REQ-002 = v1.0 (ambas sobre evento-driven + confiabilidad)
- REQ-003 = parte de v1.1 (diferente scope: dedup + indexing)

### P: "¿Cuándo marcar ESTABLE?"
**R**: Cuando:
- Todos los cambios están hechos ✅
- Verificaciones pasadas ✅
- Testeado en vivo ✅
- Documentación actualizada ✅

### P: "¿Qué pasa si usuario quiere cambiar v1.0?"
**R**: CUIDADO - está congelada. Opciones:
1. Crear v1.0.1 (patch, mínimos cambios)
2. Esperar a v2.0 (major refactor)
3. Explicar impacto de cambiar algo "congelado"

### P: "¿Cómo sé si una petición es importante?"
**R**: Ver:
- Prioridad en REQUESTS_REGISTRY (🔴 CRÍTICA vs 🟢 NORMAL)
- Estado en PLAN_AND_NEXT_STEP (✅ ESTABLE = muy importante)
- Linkeo: si aparece en múltiples REQUESTS = importante

---

## 📞 Cuándo Contactar

Si hay **contradicción clara** entre peticiones:
- No proceder sin aclaración del usuario
- Documentar en PASO 1.5
- Ejemplos:
  - "Usa threading" vs "Usa asyncio"
  - "Elimina esta tabla" vs "Usa esa tabla"
  - "Revierte cambio X" vs "Depende cambio X"

---

**Próximo paso**: Ver `REQUESTS_REGISTRY.md` para peticiones actuales, o `request-workflow.mdc` para procesar nueva petición.
