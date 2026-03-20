# 📊 Resumen Visual del Sistema de Peticiones

> **Propósito**: Ver de un vistazo qué archivos son nuevos, qué cambió, y dónde buscar
>
> **Creado**: 2026-03-05

---

## 🆕 LOS 4 DOCUMENTOS NUEVOS

### 1. **REQUESTS_REGISTRY.md** 📋
**Propósito**: Rastrear TODAS las peticiones del usuario  
**Ubicación**: `docs/ai-lcd/REQUESTS_REGISTRY.md`  
**Contenido**:
- Tabla de peticiones (REQ-001, REQ-002, REQ-003, etc.)
- Detalles de cada petición: descripción, problema, solución, cambios, verificaciones
- Análisis de contradicciones entre peticiones

**Cuándo leer**:
- ✅ Cuando recibas petición nueva (¿se pidió antes?)
- ✅ Cuando busques contexto de cambio anterior (¿por qué se hizo?)
- ✅ Cuando verifiques contradicciones (¿rompe algo?)

**Ejemplo de entrada**:
```
REQ-001: "Hacer OCR más rápido (event-driven)"
- Fecha: 2026-03-01
- Status: ✅ ESTABLE (v1.0)
- Cambios: Fix #5, #6, #9
- Problema: Scheduler OCR saturaba Tika (4 workers simultáneos)
- Solución: Event-driven con semáforo BD (máx 2)
```

---

### 2. **request-workflow.mdc (MEJORADO)** 🔄
**Propósito**: Cómo procesar una petición (6 pasos + Paso 1.5)  
**Ubicación**: `.cursor/rules/request-workflow.mdc`  
**Cambio**: **Nuevo PASO 1.5** - Verificar Contradicciones

**Pasos**:
```
PASO 1:   Leer documentación actual
PASO 1.5: ⭐ VERIFICAR CONTRADICCIONES (NUEVO)
          ├─ ¿Se pidió similar antes?
          ├─ ¿Esta petición supercede algo?
          ├─ ¿Podría romper otro cambio?
          └─ ¿Qué versión entra?
PASO 2:   Analizar petición
PASO 3:   Crear plan
PASO 4:   Solicitar aprobación
PASO 5:   Registrar + documentar
PASO 6:   Ejecutar cambios
```

**Cuándo usar**:
- ✅ Cada vez que recibas petición nueva
- ✅ Especialmente PASO 1.5 (evita contradicciones)

---

### 3. **PLAN_AND_NEXT_STEP.md (MEJORADO)** 🗺️
**Propósito**: Agrupar peticiones en versiones consolidadas  
**Ubicación**: `docs/ai-lcd/PLAN_AND_NEXT_STEP.md`  
**Cambio**: **Nueva sección § 7** - VERSIONES CONSOLIDADAS

**Estructura**:
```
## 📦 VERSIONES CONSOLIDADAS

### v1.0 - Event-Driven Base + Dashboard ✅ ESTABLE
  Peticiones: REQ-001, REQ-002
  Cambios: Fix #5, #6, #8, #9, #10, #11
  Status: 🟢 CONGELADA (no modificar)
  
### v1.1 - Indexing + Dedup 🔄 EN CONSTRUCCIÓN
  Peticiones: REQ-003
  Cambios: Fix #12, #13
  Status: 🟡 EN PROGRESO (50%)
  
### v1.2 - Search Optimization (futura)
  Peticiones: REQ-004
  Cambios: Fix #15, #16, #17
  Status: 🟡 PLANEADA
```

**Cuándo usar**:
- ✅ Para saber qué está "ESTABLE" (congelado)
- ✅ Para saber qué está "EN CONSTRUCCIÓN" (cuidado)
- ✅ Para ver qué versión entra nueva petición
- ✅ Para rollback de feature completa (versión atómica)

---

### 4. **COMO_USAR_WORKFLOW.md** 🚀 (TÚ ESTÁS AQUÍ)
**Propósito**: Guía paso a paso con ejemplo completo  
**Ubicación**: `docs/ai-lcd/COMO_USAR_WORKFLOW.md`  
**Contenido**:
- Inicio rápido (2 minutos)
- Ejemplo completo: "Optimizar búsqueda"
- Paso a paso con reportes
- Checklists prácticos

**Cuándo leer**:
- ✅ Primera vez procesando petición
- ✅ Cuando necesites entender qué va dónde
- ✅ Cuando necesites un template para reportar

---

## 🔗 FLUJO VISUAL COMPLETO

```
USUARIO PIDE (sesión N)
     ↓
¿Se pidió algo similar?
     ↓
REQUESTS_REGISTRY.md ← Busco aquí
     ├─ Sí, existe: Ve a REQ anterior
     └─ No, es nueva: Continúa ↓

PASO 1.5 en request-workflow.mdc ← Hago aquí
     ├─ ¿Se pidió similar? (buscado en REQUESTS_REGISTRY)
     ├─ ¿Supercede algo?
     ├─ ¿Rompe v1.0/v1.1? (busco en PLAN_AND_NEXT_STEP § 7)
     └─ ¿Qué versión? ↓

EJECUTAR PASOS 2-6 ← Sigo request-workflow.mdc
     ↓
REGISTRAR
     ├─ REQUESTS_REGISTRY.md (nueva REQ-XXX)
     ├─ PLAN_AND_NEXT_STEP.md (agregar a vX.Y)
     ├─ SESSION_LOG.md (decisión)
     └─ CONSOLIDATED_STATUS.md (Fixes)

MARCAR ESTABLE
     ↓
PLAN_AND_NEXT_STEP.md § Versiones ← Consolido aquí
     ├─ Cambio status vX.Y → ✅ ESTABLE
     ├─ Cambio status vX+1.Y → 🔄 EN CONSTRUCCIÓN
     └─ Siguiente versión lista
```

---

## 📖 MAPA DE REFERENCIAS

```
¿Quiero saber...?              Dónde buscar?
─────────────────────────────────────────────────
"¿Qué está pendiente?"          PENDING_BACKLOG.md (técnico) + REQUESTS_REGISTRY (REQ-014)
"¿Se pidió esto antes?"         REQUESTS_REGISTRY.md
"¿Por qué se hizo Fix #8?"      REQUESTS_REGISTRY.md § REQ-002
"¿Qué está estable?"            PLAN_AND_NEXT_STEP.md § 7
"¿Qué está en construcción?"    PLAN_AND_NEXT_STEP.md § 7
"¿Cómo procesar petición?"      request-workflow.mdc (6 pasos + 1.5)
"¿Cómo reportar cada paso?"     COMO_USAR_WORKFLOW.md (ejemplos)
"¿Qué requiere aprobación?"     request-workflow.mdc § PASO 4
"¿Cómo rollback feature?"       PLAN_AND_NEXT_STEP.md § v1.X
"¿Decisión detrás cambio?"      SESSION_LOG.md
"¿Estado actual técnico?"       CONSOLIDATED_STATUS.md
"¿Ejemplos prácticos?"          SISTEMA_DE_PETICIONES_GUIA.md
```

---

## 🎯 COMPARATIVA: ANTES vs DESPUÉS

| Aspecto | ANTES | DESPUÉS | Beneficio |
|---------|-------|---------|-----------|
| Rastreo de peticiones | ❌ No existe | ✅ REQUESTS_REGISTRY.md | Saber quién pidió qué |
| Buscar si se pidió antes | 🤷 Manual | ✅ PASO 1.5 automático | Evitar duplicados |
| Detectar contradicciones | ⚠️ Informal | ✅ Checklist explícito | Evitar conflictos |
| Agrupar cambios | ⚠️ Informal | ✅ Versiones consolidadas | Rollback atomic |
| Linkeo petición → cambios | ❌ No existe | ✅ REQ-XXX § Fix #N | Trazabilidad completa |
| Documentación | ✅ Existe | ✅ Existe (mejorada) | Más clara |
| Flujo de trabajo | ✅ 6 pasos | ✅ 6 pasos + 1.5 | Más seguro |

---

## 📚 CÓMO LEER LOS 4 DOCUMENTOS

### En orden de importancia:
1. **COMO_USAR_WORKFLOW.md** (COMIENZA AQUÍ)
   - Lee ejemplo completo
   - Entiende flujo
   - Copia template

2. **request-workflow.mdc**
   - Lee PASO 1.5 detenidamente
   - Los demás pasos no cambiaron

3. **REQUESTS_REGISTRY.md**
   - Ve ejemplos: REQ-001, REQ-002, REQ-003
   - Entiende estructura
   - Úsalo como template para REQ-004, etc.

4. **PLAN_AND_NEXT_STEP.md § 7**
   - Lee Versiones Consolidadas
   - Entiende v1.0 (estable), v1.1 (construcción), etc.
   - Úsalo para marcar dónde entra nueva petición

---

## ✅ CHECKLIST: PRIMER USO

```
[ ] Leí COMO_USAR_WORKFLOW.md (este archivo)
[ ] Entendí flujo visual (3 capas: Peticiones → Contradicciones → Versiones)
[ ] Abrí REQUESTS_REGISTRY.md (vi ejemplos REQ-001/002/003)
[ ] Abrí request-workflow.mdc (leí PASO 1.5)
[ ] Abrí PLAN_AND_NEXT_STEP.md § 7 (vi Versiones Consolidadas)
[ ] Entiendo: REQ-XXX → Fixes #N → vX.Y (versión)

Próximo: Procesar primera petición con nuevo workflow
```

---

## 🚀 CASO DE USO: PRIMERA PETICIÓN NEW

**Usuario pide**: "Agregar autenticación de 2FA"

**Tú haces**:
1. Abres REQUESTS_REGISTRY.md
   ```
   ¿Existe 2FA? → NO
   ¿Existe autenticación? → SÍ (REQ-X)
   ¿Contradice? → NO (ortogonal)
   ```

2. Haces PASO 1.5
   ```
   ¿Similar? No (2FA es nueva)
   ¿Supercede? No
   ¿Rompe v1.0? No
   Versión: v1.3 (nueva)
   ```

3. Registras en REQUESTS_REGISTRY.md
   ```
   REQ-005: "Agregar autenticación 2FA"
   ```

4. Registras en PLAN_AND_NEXT_STEP.md
   ```
   v1.3: 2FA Authentication 🔄 EN CONSTRUCCIÓN
   ```

5. Ejecutas PASOS 2-6 (normal)

6. Actualizas CONSOLIDATED_STATUS.md
   ```
   Fix #18: 2FA implementation
   Fix #19: Backend validation
   ```

✅ **Completo**: REQ-005 registrada, v1.3 creada, todo documentado

---

## 💡 TIPS PRÁCTICOS

### Tip 1: Template para copiar
```
Archivo: REQUESTS_REGISTRY.md
Busca: ### **REQ-001: ...
Copia hasta "REQ-002:" → TEMPLATE
Cambia números → Nueva REQ
```

### Tip 2: Rápida búsqueda de contradicciones
```bash
# En REQUESTS_REGISTRY.md busca:
# - Palabra clave de la petición
# - Si existe → leer detalles
# - Si no existe → es nueva
```

### Tip 3: Ver estado actual
```
Abre PLAN_AND_NEXT_STEP.md § 7
Ve qué versión está "ESTABLE"
→ Esas NO se tocan
Ve qué versión está "EN CONSTRUCCIÓN"
→ Esa es próxima prioridad
```

### Tip 4: Reportar cada PASO
```
PASO 1: "He revisado [archivos] y confirmo que..."
PASO 1.5: "✅ VERIFICACIÓN: No hay contradicciones porque..."
PASO 2: "Análisis: [objetivo, archivos, riesgos]..."
PASO 3: "Plan: [cambios, timeline, verificaciones]..."
PASO 4: "❓ APROBACIÓN: ¿Aceptas? Si/No"
PASO 5: "📝 Documentación: Registrado en REQUESTS_REGISTRY.md § REQ-XXX"
PASO 6: "✅ Cambios: Ejecutado, todo OK"
```

---

## ❌ ERRORES COMUNES A EVITAR

```
❌ Error 1: Saltarse PASO 1.5
   → Procesar sin verificar contradicciones
   → Resultado: Conflictos silenciosos
   ✅ Solución: SIEMPRE hacer PASO 1.5

❌ Error 2: No registrar en REQUESTS_REGISTRY.md
   → Ejecutar pero no documentar petición
   → Resultado: Pérdida de contexto
   ✅ Solución: REQ-XXX SIEMPRE

❌ Error 3: No actualizar PLAN_AND_NEXT_STEP.md
   → No saber qué versión entra petición
   → Resultado: Versiones confusas
   ✅ Solución: Agregar vX.Y siempre

❌ Error 4: No marcar ESTABLE cuando se termina
   → Permanecer en EN CONSTRUCCIÓN indefinidamente
   → Resultado: No saber qué está congelado
   ✅ Solución: Marcar ✅ cuando listo + verificaciones ok

❌ Error 5: Tocar versión marcada CONGELADA
   → Romper feature anterior
   → Resultado: Regresiones
   ✅ Solución: Ver PLAN_AND_NEXT_STEP.md 🚫 NO TOCAR
```

---

## 📞 CUÁNDO PARAR Y PREGUNTAR

Si en PASO 1.5 encuentras:
```
❌ Contradicción clara (threading vs asyncio, delete vs keep)
❌ Impacto en v1.0 ESTABLE
❌ Cambio propuesto contradice decisión anterior

→ DETENER
→ Explicar contradicción al usuario
→ Pedir aclaración
→ Reanudar cuando usuario responda
```

---

**Ahora**: Listos para procesar peticiones con el nuevo sistema. 🚀

¿Tienes una petición para procesar? ¡Vamos!
