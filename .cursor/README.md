# 📑 Índice de Sistema Cursor - NewsAnalyzer-RAG

**Fecha**: 2026-03-05  
**Estado**: ✅ Completo y operacional

---

## 📁 Estructura Creada

```
.cursor/
├── rules/
│   ├── env-protection.mdc               👈 Protege valores sensibles
│   ├── request-workflow.mdc             👈 Workflow de 6 pasos obligatorio
│   └── audit-and-history.mdc            👈 Sistema de auditoría + historial
│
├── AGENTS.md                            👈 Instrucciones para agentes
├── SYSTEM_SUMMARY.md                    👈 Resumen ejecutivo (START HERE)
├── TESTING_RULES.md                     👈 Cómo verificar que funciona
├── AUDIT_TEMPLATE.md                    👈 Plantilla de auditoría
└── README.md (este archivo)             👈 Índice
```

---

## 🚀 Cómo Empezar

### 1. Lee SYSTEM_SUMMARY.md (5 min)
Entenderás el sistema completo: qué hace, por qué, cómo funciona.

### 2. Lee AUDIT_TEMPLATE.md (5 min)
Ver ejemplos reales de cómo registrar cambios correctamente.

### 3. Prueba el sistema
Haz una petición y verifica que siga los 6 pasos.

---

## 📖 Referencia Rápida

| Archivo | Propósito | Cuándo leer |
|---------|-----------|-----------|
| **SYSTEM_SUMMARY.md** | Resumen del sistema completo | Primero, para entender todo |
| **TESTING_RULES.md** | Cómo verificar que las reglas funcionan | Para validar que está cargado |
| **AUDIT_TEMPLATE.md** | Ejemplos de auditoría correcta | Para ver cómo registrar cambios |
| **AGENTS.md** | Instrucciones para agentes IA | Los agentes deberían leerlo |
| **rules/env-protection.mdc** | Protección del .env | Referencia técnica |
| **rules/request-workflow.mdc** | Workflow de 6 pasos | Referencia técnica |
| **rules/audit-and-history.mdc** | Sistema de auditoría | Referencia técnica |

---

## 🎯 El Sistema en 30 Segundos

```
┌─────────────────────────────────────────────────────────┐
│ CUALQUIER PETICIÓN                                      │
│ "Agreg una nueva feature", "Arregla bug X", etc.       │
└────────────────┬────────────────────────────────────────┘
                 │
    ┌────────────▼────────────┐
    │ 1. LEER DOCS            │ Lee docs/ai-lcd/
    │ 2. ANALIZAR             │ Qué, dónde, riesgos
    │ 3. PLANIFICAR           │ Pasos concretos
    │ 4. ⚠️ APROBACIÓN         │ ESPERA OK del usuario
    │ 5. AUDITORÍA            │ Registra en CONSOLIDATED_STATUS.md
    │                         │ + SESSION_LOG.md
    │                         │ + PLAN_AND_NEXT_STEP.md
    │                         │ + "QUÉ NO ROMPE"
    │ 6. EJECUTAR             │ Cambios + verificación
    └────────────┬────────────┘
                 │
    ┌────────────▼────────────────────────────────┐
    │ ✅ CAMBIO COMPLETADO, DOCUMENTADO Y AUDITED │
    └─────────────────────────────────────────────┘
```

---

## ⚠️ Puntos Críticos Recordar

### 1. Workflow es obligatorio (no saltes pasos)
- Los agentes DEBEN seguir los 6 pasos
- Paso 4 (aprobación) es **bloqueante**

### 2. Auditoría es obligatoria (sin excepción)
- Registra: ubicación, problema, solución, impacto
- Incluye: **"QUÉ NO SE ROMPE"** (previene regresiones)
- Sin auditoría = cambio no se considera hecho

### 3. Documentación concisa
- Máximo 3-5 líneas por cambio
- Sin fluff, solo hechos
- Lenguaje directo

### 4. Protección del .env
- NUNCA mostrar valores (DATABASE_URL=...)
- SOLO enlister nombres (DATABASE_URL, API_KEY)

---

## 📊 Sistema de 3 Capas

### Capa 1: Protección
- ✅ `env-protection.mdc` - Protege secretos
- ✅ `request-workflow.mdc` - Requiere aprobación

### Capa 2: Proceso
- ✅ 6 pasos obligatorios (leer → analizar → planificar → aprobar → documentar → ejecutar)
- ✅ Auditoría en cada paso 5

### Capa 3: Historial
- ✅ CONSOLIDATED_STATUS.md - Auditoría técnica
- ✅ SESSION_LOG.md - Contexto de decisiones
- ✅ PLAN_AND_NEXT_STEP.md - Roadmap + qué está congelado

---

## 🔄 Flujo de Cambios Correcto

```
Tu petición
    ↓
Agente Lee docs (PASO 1)
    ↓
Agente Analiza (PASO 2)
    ↓
Agente Crea plan (PASO 3)
    ↓
Agente Pregunta: "¿Aprobado?" (PASO 4)
    ↓ (ESPERA TU RESPUESTA)
Tú Apruebas / Modificas / Cancelas
    ↓
Agente Actualiza auditoría (PASO 5)
    - CONSOLIDATED_STATUS.md (QUÉ)
    - SESSION_LOG.md (POR QUÉ)
    - PLAN_AND_NEXT_STEP.md (PROGRESO)
    ↓
Agente Ejecuta cambios (PASO 6)
    ↓
Cambio completado, documentado y auditado ✅
```

---

## 🧪 Verificar que Funciona

```bash
# 1. Verifica que existen los archivos
ls -la .cursor/rules/
# Deberías ver: env-protection.mdc, request-workflow.mdc, audit-and-history.mdc

# 2. Recarga workspace en Cursor
# Cmd+Shift+P → "Developer: Reload Window"

# 3. Haz una petición de prueba
# "Agrega una nueva feature X"

# 4. Verifica que el agente:
# ✓ Lee docs
# ✓ Analiza
# ✓ Crea plan
# ✓ Pregunta "¿Aprobado?"
# ✓ Registra cambios
# ✓ Ejecuta
```

Si no sucede así → Ver `.cursor/TESTING_RULES.md` para troubleshooting.

---

## 📚 Archivos Importantes del Proyecto

Después de leer este índice, consulta:

```
docs/ai-lcd/
├── CONSOLIDATED_STATUS.md     ← Auditoría técnica (QUÉ se hizo)
├── SESSION_LOG.md              ← Contexto de decisiones (POR QUÉ)
├── PLAN_AND_NEXT_STEP.md       ← Roadmap + qué está congelado
├── EVENT_DRIVEN_ARCHITECTURE.md ← Arquitectura técnica
├── INDEX.md                    ← Índice de documentación
└── 01-inception/, 02-construction/, 03-operations/
```

---

## 🎓 Orden de Lectura Recomendado

**Para entender el sistema (Primera vez)**:
1. Este archivo (README.md)
2. `SYSTEM_SUMMARY.md` (visión general)
3. `AUDIT_TEMPLATE.md` (ejemplos prácticos)

**Para usar el sistema (Cada petición)**:
1. Los agentes leen automáticamente
2. Tú apruebas en paso 4
3. Todo se registra automáticamente

**Para troubleshooting**:
1. `TESTING_RULES.md` (verificar que funciona)
2. `AGENTS.md` (qué deberían hacer)
3. Re-leer la sección relevante

---

## ✅ Checklist Final

Antes de usar el sistema, verifica:

- [ ] Existen los 3 archivos en `.cursor/rules/`
- [ ] Existen los 4 archivos en `.cursor/` (AGENTS.md, SYSTEM_SUMMARY.md, TESTING_RULES.md, AUDIT_TEMPLATE.md)
- [ ] Has recargado el workspace de Cursor
- [ ] Has leído SYSTEM_SUMMARY.md
- [ ] Entiendes el flujo de 6 pasos
- [ ] Entiendes qué incluye la auditoría
- [ ] Estás listo para empezar

---

## 📞 Resumen de Archivos

### Reglas (Obligatorias)
- **env-protection.mdc**: Protege secretos del .env
- **request-workflow.mdc**: Define flujo de 6 pasos
- **audit-and-history.mdc**: Define sistema de auditoría

### Guías (Referencia)
- **SYSTEM_SUMMARY.md**: Resumen ejecutivo (empezar aquí)
- **AGENTS.md**: Qué deben hacer los agentes
- **TESTING_RULES.md**: Cómo verificar que funciona
- **AUDIT_TEMPLATE.md**: Ejemplos de auditoría correcta

### Documentación del Proyecto (Donde se registra)
- **docs/ai-lcd/CONSOLIDATED_STATUS.md**: Auditoría técnica
- **docs/ai-lcd/SESSION_LOG.md**: Contexto de decisiones
- **docs/ai-lcd/PLAN_AND_NEXT_STEP.md**: Roadmap

---

**Creado**: 2026-03-05  
**Última actualización**: 2026-03-05  
**Status**: ✅ Sistema completo y operacional
