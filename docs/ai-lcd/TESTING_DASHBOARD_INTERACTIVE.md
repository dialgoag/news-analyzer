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

## 🚧 Estado 2026-04-06 (smoke pendiente)

- Se intentó correr el smoke suite desde el entorno remoto de Codex usando el token temporal (`curl -H "Authorization: Bearer <token>" http://localhost:{8000,3000}/api/...`).
- Todos los intentos respondieron `curl: (7) Failed to connect to localhost port XXXX` porque el entorno no tiene acceso directo a los puertos publicados por Docker en la máquina host.
- Acciones pendientes:
  1. Ejecutar los mismos comandos **desde la máquina host o dentro del contenedor backend** para capturar las respuestas reales.
  2. Pegar en esta sección los outputs de:  
     ```bash
     curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/documents
     curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/workers/status
     curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/dashboard/summary
     curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/admin/data-integrity
     ```  
     (Agregar también `/api/dashboard/analysis` si se valida el payload completo).
  3. Actualizar la checklist inferior marcando qué endpoints ya tienen evidencia.
- Hasta ejecutar los pasos anteriores, el ítem **PEND-012** sigue abierto.

---

## 📌 Resultados de humo 2026-04-07 (desde host)

Comando ejecutado: `TOKEN=<jwt admin> ./scripts/run_api_smoke.sh`

| Endpoint | HTTP | Resumen |
|----------|------|---------|
| `GET /api/documents` | 404 | `{"detail":"Not Found"}` — el backend sigue atendiendo esta ruta con los handlers legacy porque los routers v2 no se registraron (ver PEND-017). Requiere reiniciar backend tras exportar `TaskType`. |
| `GET /api/workers/status` | 200 | Payload extenso con 5 workers activos, 50 en error y detalle de cada documento/ocr. (Ver logs en `scripts/run_api_smoke.sh` output 2026-04-07 00:07). |
| `GET /api/dashboard/summary` | 200 | `files.total=332`, `completed=305`, `news_items.total=28029`, etc. |
| `GET /api/dashboard/analysis` | 200 | Incluye grupos de error para `testfile.pdf` y workers stuck. |
| `GET /api/admin/data-integrity` | 200 | (Salida guardada en la terminal; pendiente documentarla aquí cuando reinicie el backend y repita la corrida definitiva). |

Notas:
- El token usado se generó con `/api/auth/login` (`user_id=1, username=admin, role=admin`). Los endpoints devolvieron 200 salvo `/api/documents`.
- Para cerrar PEND‑012 necesitamos repetir el script después de reiniciar el backend (ver siguiente sección) y pegar las respuestas finales completas.

## 🔁 Checklist PEND-011 (Snapshots previos/post)

1. **Capturar snapshot inicial**
   - Ejecutar `TOKEN=... ./scripts/run_api_smoke.sh --output docs/ai-lcd/artifacts/dashboard_<fecha>_before.json`.
   - Extraer también `/api/dashboard/parallel-data?limit=50&max_news_per_doc=10` y guardarlo como `_parallel_before.json` para validar `news_items_total` y `meta`.
   - Registrar en esta sección los valores clave (`files.total`, `insights.pending`, `workers.stuck`, `data_integrity.files.match`).
2. **Registrar migración**
   - Tras mover los routers hacia `DashboardMetricsService`/`AdminDataIntegrityService`, repetir los mismos comandos y guardar `_after.json`.
   - Documentar diferencias y anotar si superan la tolerancia (±1 % en totales, ±5 documentos por stage, tolerancia 0 para `insights.link_percentage`).
3. **Publicar comparativa**
   - Añadir tabla “Antes vs Después” en este archivo y enlazar las rutas de los JSON generados.
   - Adjuntar hash (ej. `shasum dashboard_<fecha>_before.json`) para trazabilidad.

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
