# 📊 Guía de Uso del Dashboard Mejorado

**Fecha**: 2026-03-14  
**Versión**: Dashboard v2.0 con análisis completo

---

## 🎯 Visión General

El dashboard ahora incluye análisis completo del sistema que permite identificar problemas directamente desde la interfaz, sin necesidad de usar línea de comandos.

---

## 📋 Componentes del Dashboard

### 1. **Panel de Análisis de Errores** 🔍

**Ubicación**: Parte superior del dashboard

**Funcionalidades**:
- Agrupa errores por tipo y muestra causa raíz
- Diferencia errores reales vs errores del shutdown ordenado
- Muestra documentos afectados
- Botones para limpiar errores auto-fixables

**Cómo usar**:
1. Revisa el resumen de errores en la parte superior (Reales, Shutdown, Total)
2. Cada tarjeta de error muestra:
   - Tipo de error y cantidad
   - Stage donde ocurrió
   - Causa identificada
   - Lista de documentos afectados (expandible)
3. Si el error es auto-fixable, aparece botón "🔄 Limpiar y Reprocesar"
4. Click en el botón para limpiar y reprocesar automáticamente

**Tipos de errores comunes**:
- **"No OCR text found for chunking"**: Documentos procesados antes del fix. Auto-fixable ✅
- **"Shutdown ordenado"**: Esperado después de shutdown. No requiere acción ℹ️
- **"OCR returned empty text"**: OCR falló o timeout. Auto-fixable ✅

---

### 2. **Panel de Análisis de Pipeline** 🔄

**Ubicación**: Debajo del panel de errores

**Funcionalidades**:
- Muestra estado de cada stage (OCR, Chunking, Indexing, Insights)
- Detecta y explica bloqueos
- Muestra documentos listos para siguiente etapa
- Barras de progreso por stage

**Cómo usar**:
1. Revisa cada stage:
   - **Pendientes**: Tareas en cola
   - **Procesando**: Tareas en ejecución
   - **Completados**: Tareas finalizadas
   - **Progreso**: Porcentaje de completitud
2. Si hay bloqueos, aparecerá una sección "⚠️ Bloqueos detectados" con:
   - Razón del bloqueo
   - Solución sugerida
3. Si hay documentos listos para siguiente etapa, aparecerá indicador verde

**Ejemplo de bloqueo**:
- **Razón**: "No hay documentos con status='ocr_done' y texto OCR válido"
- **Solución**: "Esperando que documentos completen OCR correctamente"

---

### 3. **Panel de Workers Stuck** ⚠️

**Ubicación**: Solo aparece si hay workers stuck (>20 minutos)

**Funcionalidades**:
- Lista workers que llevan más de 20 minutos ejecutándose
- Muestra tiempo de ejecución y tiempo restante antes de timeout
- Barras de progreso visuales (verde → amarillo → rojo)
- Botón para cancelar y reprocesar

**Cómo usar**:
1. Si aparece este panel, hay workers que pueden estar atascados
2. Revisa cada worker:
   - Tiempo ejecutándose (ej: 13.7 min / 25 min)
   - Progreso visual con color:
     - 🟢 Verde: <60% (normal)
     - 🟡 Amarillo: 60-80% (atención)
     - 🔴 Rojo: >80% (cerca de timeout)
   - Tiempo restante antes de timeout
3. Si un worker está cerca del timeout o atascado, click en "🛑 Cancelar y Reprocesar"

**Cuándo cancelar**:
- Worker >20 minutos sin progreso aparente
- Worker cerca del timeout (rojo)
- Worker con tiempo restante negativo (ya timeout)

---

### 4. **Panel de Estado de Base de Datos** 💾

**Ubicación**: Panel colapsable (colapsado por defecto)

**Funcionalidades**:
- Muestra estado de `processing_queue` por tipo y status
- Muestra resumen de `worker_tasks` por status
- Detecta tareas huérfanas (processing sin worker activo)
- Detecta inconsistencias

**Cómo usar**:
1. Click en el header para expandir/colapsar
2. Revisa las tablas:
   - **Processing Queue**: Estado de tareas por tipo (OCR, Chunking, etc.)
   - **Worker Tasks**: Resumen de workers por status
3. Si hay problemas:
   - **Tareas huérfanas**: Aparece advertencia amarilla
   - **Inconsistencias**: Aparecen con severidad (alta/media/baja)

**Cuándo revisar**:
- Después de un shutdown ordenado
- Si hay errores inesperados
- Para diagnóstico avanzado

---

### 5. **WorkersTable Mejorado** 👷

**Ubicación**: Tabla de workers (derecha del dashboard)

**Nuevas funcionalidades**:
- Columna "Duration" mejorada con tiempo en minutos
- Badge "STUCK" para workers >20 minutos
- Barra de progreso visual del tiempo restante
- Filtro dropdown para análisis específico

**Filtros disponibles**:
- **Todos**: Muestra todos los workers
- **Activos**: Solo workers activos/started
- **Stuck**: Solo workers >20 minutos
- **Errores Reales**: Solo errores reales (excluye shutdown)
- **Errores Shutdown**: Solo errores del shutdown ordenado

**Cómo usar**:
1. Selecciona filtro del dropdown para análisis específico
2. Revisa columna "Duration":
   - Tiempo en minutos (ej: 13.7m)
   - Badge "STUCK" si >20 minutos
   - Barra de progreso visual
3. Click en fila para filtrar otras visualizaciones
4. Click en "🔄" para reintentar worker con error

---

## 🚀 Flujo de Trabajo Recomendado

### Monitoreo Diario:
1. Abre el dashboard
2. Revisa **Panel de Análisis de Errores**:
   - Si hay errores reales, limpia los auto-fixables
   - Revisa errores shutdown (esperados, no requieren acción)
3. Revisa **Panel de Análisis de Pipeline**:
   - Verifica que no hay bloqueos críticos
   - Confirma que stages están progresando
4. Si aparece **Panel de Workers Stuck**:
   - Revisa workers atascados
   - Cancela y reprocesa si es necesario

### Diagnóstico de Problemas:
1. Si hay errores inesperados:
   - Revisa **ErrorAnalysisPanel** para causa raíz
   - Revisa **PipelineAnalysisPanel** para bloqueos
   - Usa filtros en **WorkersTable** para análisis específico
2. Si hay workers atascados:
   - Revisa **StuckWorkersPanel**
   - Cancela workers problemáticos
3. Para diagnóstico avanzado:
   - Expande **DatabaseStatusPanel**
   - Revisa tareas huérfanas e inconsistencias

---

## 💡 Tips y Mejores Prácticas

1. **Auto-refresh**: El dashboard se actualiza automáticamente cada 30 segundos
2. **Cache**: Los datos se cachean 5 segundos para reducir carga del backend
3. **Errores Shutdown**: Son esperados después de un shutdown ordenado, no requieren acción
4. **Workers Stuck**: Si un worker lleva >20 minutos, revisa si está progresando antes de cancelar
5. **Bloqueos de Pipeline**: Normalmente se resuelven automáticamente cuando documentos completan stages anteriores

---

## 🔧 Acciones Disponibles

### Desde ErrorAnalysisPanel:
- **Limpiar y Reprocesar**: Limpia errores auto-fixables y los marca para reprocesamiento

### Desde StuckWorkersPanel:
- **Cancelar y Reprocesar**: Cancela worker stuck y marca documento para reprocesamiento

### Desde WorkersTable:
- **Reintentar Worker**: Reintenta un worker específico con error
- **Reintentar Todos**: Reintenta todos los workers con errores

---

## ⚠️ Errores Comunes y Soluciones

### "No OCR text found for chunking"
- **Causa**: Documento procesado antes del fix de guardado de OCR text
- **Solución**: Click en "Limpiar y Reprocesar" (auto-fixable)

### "Shutdown ordenado - tarea revertida a pending"
- **Causa**: Shutdown ordenado ejecutado
- **Solución**: No requiere acción, es esperado

### Worker stuck >20 minutos
- **Causa**: Worker procesando documento grande o atascado
- **Solución**: 
  1. Revisa si está cerca del timeout (25 min para OCR)
  2. Si está cerca o sin progreso, cancela y reprocesa
  3. Si tiene tiempo restante, espera un poco más

### Bloqueo en Pipeline
- **Causa**: No hay documentos listos para siguiente etapa
- **Solución**: Normalmente se resuelve automáticamente cuando documentos completan stages anteriores

---

## 📊 Interpretación de Métricas

### Barras de Progreso:
- **Verde**: <60% completado (normal)
- **Amarillo**: 60-80% completado (atención)
- **Rojo**: >80% completado (cerca de timeout)

### Badges de Error:
- **Rojo (❌)**: Error real que requiere atención
- **Amarillo (ℹ️)**: Error del shutdown (esperado)

### Severidad de Inconsistencias:
- **Alta**: Requiere atención inmediata
- **Media**: Revisar cuando sea posible
- **Baja**: Puede ser normal (ej: worker finalizando)

---

## 🎯 Próximos Pasos

Después de revisar el dashboard:
1. Si hay errores reales → Limpia los auto-fixables
2. Si hay workers stuck → Cancela los problemáticos
3. Si hay bloqueos → Espera a que se resuelvan automáticamente
4. Si hay inconsistencias → Revisa DatabaseStatusPanel para detalles

---

**Última actualización**: 2026-03-14
