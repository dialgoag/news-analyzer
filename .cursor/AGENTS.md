# 🤖 Instrucciones para Agentes - NewsAnalyzer-RAG

## Flujo de Trabajo Obligatorio

**IMPORTANTE**: Cualquier petición debe seguir exactamente estos 6 pasos:

### 1. Leer documentación de `docs/ai-lcd/`
- Consulta archivos relevantes (CONSOLIDATED_STATUS.md, PLAN_AND_NEXT_STEP.md, etc.)
- Entiende el estado actual del proyecto
- Identifica qué ya existe

### 2. Analizar la petición
- Desglosa: ¿Qué se pide? ¿Qué archivos se afectan? ¿Qué riesgos hay?
- Resume el análisis para el usuario

### 3. Crear un plan detallado
- Define pasos específicos (en orden)
- Incluye cambios de documentación
- Presenta con claridad total

### 4. Solicitar aprobación del usuario
- **ALTO**: No avances sin aprobación explícita
- Presenta el plan y pregunta si está de acuerdo

### 5. Actualizar documentación
- Modifica `docs/ai-lcd/CONSOLIDATED_STATUS.md`, `SESSION_LOG.md`, etc.
- Mantén la documentación sincronizada con cambios

### 6. Ejecutar cambios
- Sigue el plan aprobado
- Realiza modificaciones de código
- Reporta resultados

---

## Reglas Importantes

### Protección del .env
- **NUNCA** leas o expongas valores del `.env`
- **SOLO** puedes enlister nombres de variables
- Ver: `.cursor/rules/env-protection.mdc`

### Documentación Concisa
- Máximo 3-5 líneas por cambio
- Lenguaje directo, sin fluff
- Ver: `.cursor/rules/request-workflow.mdc`

### Auditoría e Historial (CRÍTICO)
- **SIEMPRE** registra cambios en `CONSOLIDATED_STATUS.md`
- **SIEMPRE** registra decisión en `SESSION_LOG.md`
- **SIEMPRE** documenta qué NO debe romperse
- Ver: `.cursor/rules/audit-and-history.mdc`

### Decisiones
- Documenta decisiones en `SESSION_LOG.md` con contexto
- Incluye: qué se decidió, por qué, alternativas consideradas

---

## Comandos Útiles

```bash
# Ver estado actual
cat docs/ai-lcd/CONSOLIDATED_STATUS.md

# Ver plan
cat docs/ai-lcd/PLAN_AND_NEXT_STEP.md

# Ver decisiones previas
cat docs/ai-lcd/SESSION_LOG.md

# Ver arquitectura
cat docs/ai-lcd/EVENT_DRIVEN_ARCHITECTURE.md
```

---

## Estructura de Proyecto

```
/
├── docs/ai-lcd/              # 📚 Documentación (actualiza siempre)
│   ├── CONSOLIDATED_STATUS.md
│   ├── PLAN_AND_NEXT_STEP.md
│   ├── SESSION_LOG.md
│   ├── EVENT_DRIVEN_ARCHITECTURE.md
│   ├── 01-inception/
│   ├── 02-construction/
│   └── 03-operations/
├── app/                      # 🏗️ Código principal (backend + frontend)
├── .cursor/
│   ├── rules/
│   │   ├── env-protection.mdc
│   │   └── request-workflow.mdc
│   └── AGENTS.md (este archivo)
└── ... (otros)
```

---

## Preguntas Frecuentes para Agentes

**P: ¿Puedo saltarme pasos?**  
R: No, el flujo de 6 pasos es obligatorio para mantener consistencia.

**P: ¿Qué hago si el usuario dice "hazlo sin plan"?**  
R: Aun así, debes leer la docs (paso 1) y analizar (paso 2), pero puedes acelerar paso 3 (plan) y 4 (aprobación).

**P: ¿Cuándo actualizo la documentación?**  
R: En el paso 5, ANTES de ejecutar cambios (paso 6).

**P: ¿Qué cambios en documentación debo hacer siempre?**  
R: Como mínimo: actualiza `CONSOLIDATED_STATUS.md` (qué se hizo) y `SESSION_LOG.md` (por qué se hizo).

---

## Recordatorios de Seguridad

✅ **SÍ puedo**:
- Leer documentación
- Proponer cambios
- Modificar código
- Crear planes
- Solicitar aprobación

❌ **NO puedo**:
- Exponer valores del .env
- Saltarme pasos del workflow
- Hacer cambios sin documentar
- Proceder sin aprobación del usuario

---

**Última actualización**: 2026-03-05  
**Status**: Activo y obligatorio para todos los agentes
