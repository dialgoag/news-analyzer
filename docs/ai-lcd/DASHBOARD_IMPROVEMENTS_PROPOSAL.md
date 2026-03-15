# 📊 Propuesta de Mejoras para el Dashboard

**Fecha**: 2026-03-14  
**Objetivo**: Reflejar todo el análisis realizado en el dashboard para identificar problemas sin usar línea de comandos

---

## 🎯 Análisis Actual del Dashboard

### Componentes Existentes:
1. **DashboardSummaryRow**: Métricas generales (archivos, OCR, chunking, indexing, insights, errores)
2. **WorkersTable**: Tabla de workers con estado básico (activo, idle, error)
3. **PipelineSankeyChart**: Visualización del flujo de la pipeline
4. **DocumentsTable**: Tabla de documentos con estados

### Limitaciones Identificadas:
- ❌ No muestra **tipos de errores** agrupados
- ❌ No diferencia **errores reales** vs **errores del shutdown**
- ❌ No muestra **análisis de pipeline** (por qué no hay tareas pendientes en ciertos stages)
- ❌ No detecta **workers stuck** (más de 20 minutos)
- ❌ No muestra **inconsistencias** (doc ocr_done pero worker activo)
- ❌ No muestra **tiempo de ejecución** de workers activos
- ❌ No muestra **causa raíz** de errores
- ❌ No muestra **estado de la base de datos** (processing_queue, worker_tasks)
- ❌ No muestra **tareas pendientes por tipo** con análisis de por qué están pendientes

---

## 🚀 Propuesta de Mejoras

### 1. **Panel de Análisis de Errores** (NUEVO)

**Ubicación**: Nueva sección en DashboardView  
**Componente**: `ErrorAnalysisPanel.jsx`

**Funcionalidades**:
- Agrupar errores por tipo y mostrar cantidad
- Diferenciar errores reales vs errores del shutdown
- Mostrar causa raíz de cada tipo de error
- Botón para limpiar errores específicos por tipo
- Filtros por stage (OCR, Chunking, Indexing, Insights)

**Datos a mostrar**:
```javascript
{
  errorGroups: [
    {
      errorMessage: "No OCR text found for chunking",
      count: 9,
      stage: "ocr",
      cause: "Documentos procesados antes del fix de guardado de OCR text",
      documents: [...],
      canAutoFix: true
    },
    {
      errorMessage: "Shutdown ordenado - tarea revertida a pending",
      count: 18,
      stage: "ocr",
      cause: "Shutdown ordenado ejecutado",
      documents: [...],
      canAutoFix: false // Esperado, no necesita fix
    }
  ],
  realErrors: 9,
  shutdownErrors: 18,
  totalErrors: 27
}
```

**UI**:
- Cards por tipo de error con badge de cantidad
- Expandible para ver documentos afectados
- Botón "Limpiar y Reprocesar" para errores auto-fixables
- Color coding: Rojo (real), Amarillo (shutdown), Verde (sin errores)

---

### 2. **Panel de Análisis de Pipeline** (NUEVO)

**Ubicación**: Nueva sección en DashboardView  
**Componente**: `PipelineAnalysisPanel.jsx`

**Funcionalidades**:
- Mostrar estado de cada stage de la pipeline
- Explicar por qué no hay tareas pendientes en ciertos stages
- Detectar documentos listos para siguiente etapa pero sin tarea creada
- Mostrar bloqueos en la pipeline

**Datos a mostrar**:
```javascript
{
  stages: [
    {
      name: "OCR",
      pendingTasks: 223,
      processingTasks: 5,
      completedTasks: 162,
      readyForNext: 0, // Documentos con ocr_done listos para chunking
      blockers: []
    },
    {
      name: "Chunking",
      pendingTasks: 0,
      processingTasks: 0,
      completedTasks: 11,
      readyForNext: 0, // Documentos con chunking_done listos para indexing
      blockers: [
        {
          reason: "No hay documentos con status='ocr_done'",
          count: 0,
          solution: "Esperando que documentos completen OCR"
        }
      ]
    },
    {
      name: "Indexing",
      pendingTasks: 0,
      processingTasks: 0,
      completedTasks: 0,
      readyForNext: 0,
      blockers: [
        {
          reason: "No hay documentos con chunking_done",
          count: 0,
          solution: "Esperando que documentos completen chunking"
        }
      ]
    }
  ]
}
```

**UI**:
- Timeline visual de la pipeline
- Indicadores de bloqueo con explicación
- Contadores de documentos listos para siguiente etapa
- Alertas cuando hay documentos listos pero sin tarea creada

---

### 3. **Panel de Workers Detallado** (MEJORAR)

**Ubicación**: Mejorar WorkersTable existente  
**Componente**: `WorkersTable.jsx` (mejorado)

**Nuevas Funcionalidades**:
- Columna de **tiempo de ejecución** para workers activos
- Indicador de **workers stuck** (>20 minutos)
- Filtro por tipo de error (real vs shutdown)
- Tooltip con detalles del error
- Agrupación por tipo de worker con estadísticas

**Datos adicionales a mostrar**:
```javascript
{
  worker: {
    worker_id: "ocr_1_12996",
    status: "started",
    task_type: "ocr",
    document_id: "...",
    execution_time_minutes: 13.7,
    is_stuck: false, // >20 minutos
    error_type: null, // "real" | "shutdown" | null
    error_message: null
  }
}
```

**UI Mejorada**:
- Columna "Tiempo" con formato "13.7 min"
- Badge "STUCK" para workers >20 minutos
- Filtro dropdown: "Todos", "Errores Reales", "Shutdown", "Activos"
- Tooltip al hover mostrando error_message completo

---

### 4. **Panel de Estado de Base de Datos** (NUEVO)

**Ubicación**: Nueva sección en DashboardView  
**Componente**: `DatabaseStatusPanel.jsx`

**Funcionalidades**:
- Mostrar estado de `processing_queue` por tipo y status
- Mostrar estado de `worker_tasks` por status
- Detectar inconsistencias (processing sin worker activo)
- Mostrar tareas huérfanas

**Datos a mostrar**:
```javascript
{
  processingQueue: {
    byType: {
      ocr: { pending: 223, processing: 5, completed: 162 },
      chunking: { pending: 0, processing: 0, completed: 11 },
      indexing: { pending: 0, processing: 0, completed: 0 },
      insights: { pending: 0, processing: 0, completed: 0 }
    },
    orphanedTasks: 0 // processing sin worker activo
  },
  workerTasks: {
    active: 5,
    completed: 78,
    errors: 18,
    realErrors: 0,
    shutdownErrors: 18
  },
  inconsistencies: [
    {
      type: "doc_ocr_done_but_worker_active",
      count: 1,
      documents: [...]
    }
  ]
}
```

**UI**:
- Tabla con estado de processing_queue
- Tabla con estado de worker_tasks
- Alertas para inconsistencias detectadas
- Botón "Corregir Inconsistencias" si hay

---

### 5. **Panel de Workers Stuck** (NUEVO)

**Ubicación**: Nueva sección en DashboardView  
**Componente**: `StuckWorkersPanel.jsx`

**Funcionalidades**:
- Detectar workers que llevan >20 minutos procesando
- Mostrar detalles del worker y documento
- Opción para cancelar/reiniciar workers stuck
- Historial de workers stuck resueltos

**Datos a mostrar**:
```javascript
{
  stuckWorkers: [
    {
      worker_id: "ocr_1_12996",
      task_type: "ocr",
      document_id: "...",
      filename: "...",
      started_at: "2026-03-14 15:50:13",
      minutes_running: 13.7,
      timeout_limit: 25, // minutos
      progress_percent: 54.8 // (13.7 / 25) * 100
    }
  ],
  totalStuck: 0 // Si >0, mostrar alerta
}
```

**UI**:
- Lista de workers stuck con barra de progreso
- Indicador visual de tiempo restante antes de timeout
- Botón "Cancelar y Reprocesar" para workers stuck
- Alertas cuando hay workers cerca del timeout

---

### 6. **Endpoint de Análisis** (BACKEND - NUEVO)

**Endpoint**: `GET /api/dashboard/analysis`

**Respuesta**:
```json
{
  "errors": {
    "groups": [...],
    "realErrors": 0,
    "shutdownErrors": 18,
    "totalErrors": 18
  },
  "pipeline": {
    "stages": [...],
    "blockers": [...],
    "readyForNext": {...}
  },
  "workers": {
    "active": 5,
    "stuck": 0,
    "byType": {...},
    "executionTimes": [...]
  },
  "database": {
    "processingQueue": {...},
    "workerTasks": {...},
    "inconsistencies": [...]
  }
}
```

---

## 📋 Plan de Ejecución

### FASE 1: Backend - Endpoint de Análisis (Prioridad ALTA)
**Tiempo estimado**: 2-3 horas

**Tareas**:
1. ✅ Crear endpoint `/api/dashboard/analysis` en `backend/app.py`
2. ✅ Implementar lógica de agrupación de errores
3. ✅ Implementar análisis de pipeline (detectar bloqueos)
4. ✅ Implementar detección de workers stuck
5. ✅ Implementar detección de inconsistencias
6. ✅ Implementar análisis de base de datos

**Archivos a modificar**:
- `backend/app.py` (nuevo endpoint)

---

### FASE 2: Frontend - Panel de Análisis de Errores (Prioridad ALTA)
**Tiempo estimado**: 3-4 horas

**Tareas**:
1. ✅ Crear componente `ErrorAnalysisPanel.jsx`
2. ✅ Integrar con endpoint `/api/dashboard/analysis`
3. ✅ Implementar UI con cards por tipo de error
4. ✅ Implementar filtros y agrupación
5. ✅ Implementar botones de acción (limpiar errores)
6. ✅ Agregar al DashboardView

**Archivos a crear**:
- `frontend/src/components/dashboard/ErrorAnalysisPanel.jsx`
- `frontend/src/components/dashboard/ErrorAnalysisPanel.css`

**Archivos a modificar**:
- `frontend/src/components/dashboard/DashboardView.jsx`
- `frontend/src/components/PipelineDashboard.jsx`

---

### FASE 3: Frontend - Panel de Análisis de Pipeline (Prioridad MEDIA)
**Tiempo estimado**: 3-4 horas

**Tareas**:
1. ✅ Crear componente `PipelineAnalysisPanel.jsx`
2. ✅ Implementar visualización de stages
3. ✅ Implementar detección y visualización de bloqueos
4. ✅ Implementar alertas para documentos listos sin tarea
5. ✅ Agregar al DashboardView

**Archivos a crear**:
- `frontend/src/components/dashboard/PipelineAnalysisPanel.jsx`
- `frontend/src/components/dashboard/PipelineAnalysisPanel.css`

**Archivos a modificar**:
- `frontend/src/components/dashboard/DashboardView.jsx`
- `frontend/src/components/PipelineDashboard.jsx`

---

### FASE 4: Frontend - Mejoras a WorkersTable (Prioridad MEDIA)
**Tiempo estimado**: 2-3 horas

**Tareas**:
1. ✅ Agregar columna "Tiempo de ejecución"
2. ✅ Agregar detección y badge de "STUCK"
3. ✅ Agregar filtros por tipo de error
4. ✅ Mejorar tooltips con detalles de errores
5. ✅ Agregar agrupación por tipo de worker

**Archivos a modificar**:
- `frontend/src/components/dashboard/WorkersTable.jsx`
- `frontend/src/components/dashboard/WorkersTable.css`

---

### FASE 5: Frontend - Panel de Estado de Base de Datos (Prioridad BAJA)
**Tiempo estimado**: 2-3 horas

**Tareas**:
1. ✅ Crear componente `DatabaseStatusPanel.jsx`
2. ✅ Implementar visualización de processing_queue
3. ✅ Implementar visualización de worker_tasks
4. ✅ Implementar detección de inconsistencias
5. ✅ Agregar al DashboardView (colapsable)

**Archivos a crear**:
- `frontend/src/components/dashboard/DatabaseStatusPanel.jsx`
- `frontend/src/components/dashboard/DatabaseStatusPanel.css`

**Archivos a modificar**:
- `frontend/src/components/dashboard/DashboardView.jsx`

---

### FASE 6: Frontend - Panel de Workers Stuck (Prioridad MEDIA)
**Tiempo estimado**: 2-3 horas

**Tareas**:
1. ✅ Crear componente `StuckWorkersPanel.jsx`
2. ✅ Implementar lista de workers stuck
3. ✅ Implementar barras de progreso de tiempo
4. ✅ Implementar botones de acción (cancelar/reprocesar)
5. ✅ Agregar al DashboardView (solo visible si hay stuck)

**Archivos a crear**:
- `frontend/src/components/dashboard/StuckWorkersPanel.jsx`
- `frontend/src/components/dashboard/StuckWorkersPanel.css`

**Archivos a modificar**:
- `frontend/src/components/dashboard/DashboardView.jsx`

---

## 🎨 Diseño UI Propuesto

### Layout del Dashboard Mejorado:

```
┌─────────────────────────────────────────────────────────┐
│ 📊 Dashboard Header (con refresh manual)               │
├─────────────────────────────────────────────────────────┤
│ 📊 RESUMEN GENERAL (DashboardSummaryRow - existente)   │
├─────────────────────────────────────────────────────────┤
│ 🔍 ANÁLISIS DE ERRORES (NUEVO - ErrorAnalysisPanel)    │
│   ┌─────────────┐ ┌─────────────┐ ┌─────────────┐     │
│   │ Error Tipo 1│ │ Error Tipo 2│ │ Error Tipo 3│     │
│   │ Count: 9    │ │ Count: 18   │ │ Count: 0   │     │
│   │ [Limpiar]   │ │ [Info]      │ │ [OK]       │     │
│   └─────────────┘ └─────────────┘ └─────────────┘     │
├─────────────────────────────────────────────────────────┤
│ 🔄 ANÁLISIS DE PIPELINE (NUEVO - PipelineAnalysisPanel)│
│   OCR → Chunking → Indexing → Insights                  │
│   [223 pending] [0 pending] [0 pending] [0 pending]   │
│   ⚠️ Bloqueos detectados: ...                          │
├─────────────────────────────────────────────────────────┤
│ 👷 WORKERS STATUS (MEJORADO - WorkersTable)            │
│   [Filtros: Todos | Errores Reales | Shutdown]         │
│   Tabla con columna "Tiempo" y badge "STUCK"           │
├─────────────────────────────────────────────────────────┤
│ ⚠️ WORKERS STUCK (NUEVO - solo si hay stuck)          │
│   Lista de workers >20 minutos con progreso            │
├─────────────────────────────────────────────────────────┤
│ 💾 ESTADO DE BASE DE DATOS (NUEVO - colapsable)        │
│   Processing Queue | Worker Tasks | Inconsistencias     │
└─────────────────────────────────────────────────────────┘
```

---

## 📊 Priorización

### Prioridad ALTA (Implementar primero):
1. ✅ **FASE 1**: Endpoint de análisis (backend)
2. ✅ **FASE 2**: Panel de análisis de errores (frontend)

**Razón**: Permite identificar y limpiar errores directamente desde el dashboard

### Prioridad MEDIA (Implementar después):
3. ✅ **FASE 3**: Panel de análisis de pipeline
4. ✅ **FASE 4**: Mejoras a WorkersTable
5. ✅ **FASE 6**: Panel de workers stuck

**Razón**: Mejora la visibilidad y diagnóstico del sistema

### Prioridad BAJA (Implementar al final):
6. ✅ **FASE 5**: Panel de estado de base de datos

**Razón**: Información técnica avanzada, útil pero no crítica

---

## 🎯 Beneficios Esperados

1. ✅ **Identificación rápida de problemas**: Sin necesidad de línea de comandos
2. ✅ **Acciones directas**: Limpiar errores, reprocesar desde el dashboard
3. ✅ **Visibilidad completa**: Estado de pipeline, workers, errores, base de datos
4. ✅ **Diagnóstico automático**: Detección de bloqueos, inconsistencias, workers stuck
5. ✅ **Mejor UX**: Información clara y accionable

---

## 📝 Notas de Implementación

- Usar React hooks para estado y efectos
- Implementar polling inteligente (deshabilitar después de errores consecutivos)
- Manejar errores gracefully (mostrar últimos datos disponibles)
- Usar CSS modules o styled-components para estilos
- Mantener consistencia con diseño existente
- Agregar tooltips y ayuda contextual
- Implementar loading states y skeletons

---

## ✅ Checklist de Validación

Después de implementar cada fase:
- [ ] Endpoint responde correctamente
- [ ] UI muestra datos correctamente
- [ ] Filtros funcionan
- [ ] Acciones (limpiar, reprocesar) funcionan
- [ ] Polling funciona sin errores
- [ ] Manejo de errores funciona
- [ ] Responsive en diferentes tamaños de pantalla
- [ ] Performance aceptable (no bloquea UI)
