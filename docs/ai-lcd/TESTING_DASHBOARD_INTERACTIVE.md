# 🧪 Testing Plan - Dashboard Interactivo

**Fecha**: 2026-03-13  
**Versión**: v1.3 (Dashboard Refactor - FASE 3)  
**Status**: ✅ Frontend rebuilt y desplegado

---

## ✅ Pre-requisitos Completados

- [x] Frontend build exitoso (dist generado)
- [x] Docker image frontend recreada
- [x] Contenedor frontend reiniciado
- [x] Sistema completo corriendo

## 🗂️ Histórico 2026-04-06 (smoke fallido)

- Intento remoto desde el entorno de Codex (`curl http://localhost:{8000,3000}/api/...`) sin acceso a los puertos host ⇒ `curl: (7) Failed to connect`.
- Se mantiene este bloque solo como referencia histórica; los pasos listados se completaron el 2026-04-07 desde la máquina host y **PEND-012 quedó cerrado**.
- Próximos smokes deben ejecutarse localmente o dentro del contenedor backend para evitar el mismo bloqueo de red.

---

## 📌 Resultados de humo 2026-04-07 (post-routers legacy, desde host)

Comando ejecutado: `TOKEN=<jwt admin> ./scripts/run_api_smoke.sh` (registro completo en `smoke_1.log`).

| Endpoint | HTTP | Resumen clave |
|----------|------|---------------|
| `GET /api/documents` | 200 | `total=331`, todos los documentos activos en `indexing_done`, sin errores pendientes. |
| `GET /api/workers/status` | 200 | Servicios: `tika_service=unreachable`, `qdrant_service=healthy`; `pending_tasks.insights=25005`, `stuck=0`. |
| `GET /api/dashboard/summary` | 200 | `files.total=331`, `completed=331`, `errors=0`, `chunks_total=123545`, `insights.pending=25005`. |
| `GET /api/dashboard/analysis` | 200 | Sin grupos de error; stages completas salvo Insights (`pending_tasks=25005`, `docs_with_pending_insights=321`). |
| `GET /api/admin/data-integrity` | 200 | `match=75.8%`, `orphaned_count=80`, `overall_status=error` (tal como se esperaba antes de limpiar uploads legacy). |

Evidencia JSON: `docs/ai-lcd/artifacts/dashboard_2026-04-07_after.json` (contiene los campos resumidos arriba y referencia a `smoke_1.log` con el payload completo).

Notas:
- El token proviene de `/api/auth/login` (admin). Esta corrida confirma que los routers v2 responden y reemplaza el snapshot fallido anterior (404).
- Los valores relevantes para PEND‑011/012 quedaron capturados: `files.total=331`, `insights.pending=25005`, `workers.stuck=0`, `data_integrity.files.match=75.8%`.
- Snapshot “before” **no es requerido** por acuerdo del 2026-04-07; este archivo “after” es la referencia oficial mientras no se toquen los routers.

## 🔁 Checklist PEND-011 (Snapshots previos/post)

1. **Capturar snapshot inicial** — _No aplica_. Se documentó que basta con snapshot “after” porque los endpoints legacy ya están deshabilitados.
2. **Registrar migración** — ✅ `docs/ai-lcd/artifacts/dashboard_2026-04-07_after.json` + `smoke_1.log` (ver tabla anterior).
3. **Publicar comparativa** — _Pendiente sólo si se genera un nuevo before_. Para esta iteración se dejó constancia en esta sección y en `CONSOLIDATED_STATUS.md`.

---

## 📋 Checklist de Testing

### 1. Verificación Visual Básica

**URL**: http://localhost:3000

- [ ] Frontend carga sin errores
- [ ] Dashboard tab visible y accesible
- [ ] Sin errores en consola del navegador (F12)
- [ ] CSS cargando correctamente

### 2. Componentes Individuales

#### DashboardFilters
- [ ] Componente renderiza correctamente
- [ ] Sin filtros activos muestra texto "Sin filtros activos"
- [ ] Contador de filtros funciona
- [ ] Botón "Limpiar todo" visible cuando hay filtros

#### PipelineSankeyChart
- [ ] Sankey diagram renderiza con nodos y links
- [ ] Nodos tienen colores correctos por stage
- [ ] Hover muestra tooltip con información
- [ ] Click en nodo/link actualiza filtro global

#### ProcessingTimeline
- [ ] Timeline renderiza con ejes X e Y
- [ ] Líneas de múltiples stages visibles
- [ ] Brush aparece y es interactivo
- [ ] Selección de brush actualiza filtro timeRange

#### WorkersTable
- [ ] Tabla renderiza con headers sticky
- [ ] Mini chart D3 stacked bars visible
- [ ] Datos de workers se muestran correctamente
- [ ] Click en fila actualiza filtro workerId
- [ ] Fila seleccionada tiene highlight visual
- [ ] Footer con estadísticas muestra números correctos

#### DocumentsTable
- [ ] Tabla renderiza con headers sticky
- [ ] Progress bars visuales en cada fila
- [ ] Status badges con colores correctos
- [ ] Click en fila actualiza filtros (stage + documentId)
- [ ] Paginación funciona (top 50 docs)

### 3. Brushing & Linking (CRÍTICO)

#### Test 1: Sankey → Filtrar Todo
1. Click en nodo "OCR" del Sankey
2. **Verificar**:
   - [ ] DashboardFilters muestra chip "Stage: ocr"
   - [ ] Timeline solo muestra línea de OCR
   - [ ] WorkersTable solo muestra workers OCR
   - [ ] DocumentsTable solo muestra docs en stage OCR

#### Test 2: Timeline → Filtrar Todo
1. Hacer brush en Timeline seleccionando rango (ej: 10/03 - 12/03)
2. **Verificar**:
   - [ ] DashboardFilters muestra chip "Período: 10/03 - 12/03"
   - [ ] Sankey se actualiza solo con docs de ese rango
   - [ ] WorkersTable muestra solo workers activos en ese rango
   - [ ] DocumentsTable muestra solo docs subidos en ese rango

#### Test 3: WorkersTable → Filtrar Todo
1. Click en fila de worker en WorkersTable
2. **Verificar**:
   - [ ] DashboardFilters muestra chip "Worker: [id]"
   - [ ] Fila seleccionada tiene highlight
   - [ ] Otras visualizaciones filtran por ese worker
   - [ ] Click nuevamente deselecciona

#### Test 4: DocumentsTable → Filtrar Todo
1. Click en fila de documento en DocumentsTable
2. **Verificar**:
   - [ ] DashboardFilters muestra chips "Stage: [stage]" y "Documento: [id]"
   - [ ] Fila seleccionada tiene highlight
   - [ ] Sankey resalta ese stage
   - [ ] WorkersTable muestra workers procesando ese doc

#### Test 5: Clear Filters
1. Aplicar múltiples filtros
2. Click en "Limpiar todo"
3. **Verificar**:
   - [ ] Todos los chips desaparecen
   - [ ] Todas las visualizaciones vuelven a datos completos
   - [ ] Highlights removidos de tablas
   - [ ] Brush removido de Timeline

### 4. Responsive Design

- [ ] Desktop (1920x1080): Layout correcto, 2 columnas en tablas
- [ ] Tablet (1024x768): Layout ajustado, 1 columna en tablas
- [ ] Mobile (375x667): Todo apilado verticalmente, funcional

### 5. Performance

- [ ] Render inicial < 2 segundos
- [ ] Transiciones suaves (no lag)
- [ ] Filtros responden instantáneamente
- [ ] Sin warnings en consola React
- [ ] Sin memory leaks (monitoring en DevTools)

### 6. Accessibility

- [ ] Navegación por teclado funciona
- [ ] Tab order lógico
- [ ] Enter/Space activan botones
- [ ] Tooltips visibles en hover
- [ ] Contraste de colores adecuado

---

## 🐛 Bugs Encontrados

### Bug #1: stageColors is not defined
- **Severidad**: 🔴 ALTA
- **Componente**: PipelineSankeyChart
- **Pasos para reproducir**:
  1. Cargar página Dashboard
  2. Abrir DevTools Console
- **Comportamiento esperado**: Componente renderiza correctamente
- **Comportamiento actual**: Error "ReferenceError: stageColors is not defined"
- **Screenshot/Error**: 
```
ReferenceError: stageColors is not defined
    at K2 (index-4d91c990.js:48:17002)
```
- **Fix Aplicado**: ✅ Movido `stageColors` fuera del componente como constante
- **Archivo**: `dashboard/PipelineSankeyChart.jsx`
- **Status**: ✅ RESUELTO (desplegado)

---

## 📊 Resultados del Testing

### Componentes Funcionando
- ✅ [Lista de componentes que funcionan correctamente]

### Componentes con Issues
- ⚠️ [Lista de componentes con problemas menores]

### Componentes Rotos
- ❌ [Lista de componentes que no funcionan]

---

## 🔧 Fixes Aplicados Durante Testing

### Fix #1: stageColors scope issue (MÚLTIPLES ARCHIVOS)
- **Problema**: `stageColors` estaba definido dentro de componentes pero se accedía desde closures D3 donde no estaba disponible después de minificación
- **Solución**: Movido como constante **fuera de todos los componentes** para evitar problemas de scope y re-creación
- **Archivos afectados**:
  1. `dashboard/PipelineSankeyChart.jsx` (línea 15)
  2. `dashboard/ProcessingTimeline.jsx` (línea 7) - estaba dentro del useEffect
  3. `PipelineDashboard.jsx` (línea 12) - no estaba definido, solo referenciado

- **Cambio**:
```javascript
// ANTES (dentro del componente o useEffect)
export function ComponentName({ data }) {
  useEffect(() => {
    const stageColors = { ... }; // ❌ PROBLEMA
  }, []);
}

// DESPUÉS (fuera de todos los componentes)
const stageColors = { ... }; // ✅ CORRECTO
export function ComponentName({ data }) {
  // ...
}
```

- **Razón técnica**: Los closures de D3 dentro de `.attr()` capturan referencias a `stageColors`, pero si está definido dentro del componente/useEffect, al minificar con Vite el scope se pierde y genera `ReferenceError: stageColors is not defined`

- **Beneficio adicional**: Mejor performance (no se recrea en cada render) y consistencia en minified bundles

- **Build hash**:
  - Antes: `index-10383b41.js` (con error)
  - Después: `index-090dba48.js` (fix aplicado)

- **Testing**: ✅ Verificar que NO aparece `ReferenceError: stageColors is not defined` en consola del navegador

---

## 🧪 2026-04-06 — Backend API Smoke (Fase 5E)

| Paso | Resultado | Evidencia |
|------|-----------|-----------|
| `cd app/backend && pytest` | ✅ 100 tests pasaron en 1.19 s | Ver salida capturada en la terminal (pytest 9.0.2, Python 3.12). |
| `/api/documents`, `/api/workers`, `/api/dashboard`, `/api/admin/data-integrity` (curl) | ⏳ Pendiente | El entorno de CLI no permite conexiones HTTP locales (curl falla con *Operation not permitted*), por lo que los curls deben ejecutarse desde la máquina del desarrollador antes de cerrar PEND‑012. |

**Notas**:
- Pytest cubre entidades, repositorios y el nuevo `DashboardMetricsService` respaldado por `PostgresDashboardReadRepository`, validando que la migración eliminó dependencias del `document_status_store` sin romper lógica.
- Cuando se ejecuten los curls, actualizar esta tabla con la respuesta HTTP y timestamp correspondientes.

---

## ✅ Testing Completado

**Fecha**: ___________  
**Tester**: ___________  
**Resultado General**: PASS / FAIL  

**Comentarios finales**:
___________________________________________
___________________________________________

---

## 🚀 Próximos Pasos

Después de completar testing:

1. **Si PASS**:
   - Marcar FASE 3 como ✅ COMPLETADA en REQUESTS_REGISTRY
   - Proceder con FASE 4 (Dashboard Insights)
   - Actualizar CONSOLIDATED_STATUS

2. **Si FAIL**:
   - Aplicar fixes necesarios
   - Re-testear componentes afectados
   - Repetir testing hasta PASS
