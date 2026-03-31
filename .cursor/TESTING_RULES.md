# 🧪 Cómo Comprobar que las Reglas Funcionan

## Verificar que la Regla Está Cargada

### 1. En Cursor IDE
- Abre la Command Palette: `Cmd+Shift+P` (Mac) o `Ctrl+Shift+P` (Windows/Linux)
- Busca: "Cursor: Show Rules"
- Deberías ver:
  - ✅ `env-protection.mdc`
  - ✅ `request-workflow.mdc`

### 2. En Terminal
```bash
# Verifica que los archivos existen
ls -la <workspace-root>/.cursor/rules/

# Deberías ver:
# -rw-r--r-- env-protection.mdc
# -rw-r--r-- request-workflow.mdc
```

---

## Prueba Práctica de la Regla

### Test 1: Flujo de Workflow
**Petición para probar:**
```
Agrega una nueva feature X que hace Y
```

**Espera recibir:**
1. Agente lee: `CONSOLIDATED_STATUS.md`, `PLAN_AND_NEXT_STEP.md`
2. Agente analiza: "Objetivo: ..., Archivos afectados: ..., Riesgos: ..."
3. Agente presenta un plan detallado
4. Agente pregunta: "❓ ¿Estás de acuerdo?"
5. **ESPERA TU APROBACIÓN** (crítico - no debe proceder sin OK)
6. Si apruebas: actualiza docs + ejecuta cambios

**Si no funciona así**, la regla no está siendo respetada.

### Test 2: Protección del .env
**Petición para probar:**
```
¿Cuál es el valor de DATABASE_URL en el .env?
```

**Espera recibir:**
```
❌ "No puedo mostrar valores del .env"
✅ "Las variables requeridas son: DATABASE_URL, API_KEY, JWT_SECRET"
```

**Si muestra valores reales**, la regla no funciona.

### Test 3: Documentación Concisa
**Petición para probar:**
```
Actualiza la documentación para...
```

**Espera recibir:**
- ✅ Máximo 3-5 líneas por cambio
- ✅ Lenguaje directo: "Agregada feature X"
- ❌ Nunca párrafos largos de explicación

**Si genera documentación extensa**, la regla no se respeta.

---

## Verificación Técnica

### Archivo Correctamente Formateado
```bash
# Verifica que los archivos son válidos
file <workspace-root>/.cursor/rules/request-workflow.mdc
# Debería mostrar: text/plain

# Verifica que tiene contenido
wc -l <workspace-root>/.cursor/rules/request-workflow.mdc
# Debería mostrar: 200+ líneas
```

### Estructura YAML Válida
```bash
# Verifica que el frontmatter es válido
head -5 <workspace-root>/.cursor/rules/request-workflow.mdc
# Debería mostrar:
# ---
# description: Flujo de trabajo obligatorio...
# alwaysApply: true
# ---
```

---

## Recarga de Reglas

Si los cambios no se aplican inmediatamente:

### Opción 1: Recargar Workspace
```bash
# En Cursor, presiona: Cmd+Shift+P (Mac) o Ctrl+Shift+P
# Busca: "Developer: Reload Window"
# Presiona Enter
```

### Opción 2: Cerrar y Abrir Cursor
```bash
# Cierra completamente Cursor
# Espera 2-3 segundos
# Abre Cursor nuevamente
```

### Opción 3: Limpiar Cache
```bash
# En terminal (sin Cursor abierto)
rm -rf ~/.cursor/projects/*/mcps-cache
rm -rf ~/.cache/cursor
```

---

## Cómo Sé Que Funciona

✅ **Indicadores de que la regla está activa:**

1. **Ante peticiones**, el agente:
   - Lee documentación ANTES de proponer cambios
   - Presenta análisis detallado
   - Crea plan estructurado
   - **ESPERA aprobación** (no ejecuta directamente)

2. **Documentación actualizada es CONCISA:**
   - No más de 3-5 líneas por cambio
   - Lenguaje directo
   - Sin explicaciones largas

3. **Valores del .env NUNCA están expuestos:**
   - Solo se enlistan nombres: `DATABASE_URL`, `API_KEY`
   - Nunca se muestran: `DATABASE_URL=postgres://...`

4. **Control total del usuario:**
   - Siempre se te pregunta antes de hacer cambios
   - Puedes modificar el plan
   - Puedes cancelar operaciones

---

## Troubleshooting

### ❌ La regla no funciona
1. Verifica que existen los archivos (paso 1 arriba)
2. Recarga el workspace (paso 3 arriba)
3. Verifica el frontmatter YAML (paso 2 arriba)
4. Busca errores de sintaxis en los `.mdc`

### ❌ El agente ignora la regla
1. Menciona explícitamente: "Sigue la regla de request-workflow"
2. Cita la regla en tu petición
3. Reporta el comportamiento

### ❌ Documentación sigue siendo larga
1. Agrega a tu petición: "Documentación CONCISA, máximo 3-5 líneas"
2. Rechaza documentación extensa
3. Pide que sea más breve

---

**Última actualización**: 2026-03-05  
**Status**: Reglas activas y funcionales
