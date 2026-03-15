# Sesión 18: Sistema de Logging de Errores OCR

> **Fecha**: 2026-03-14  
> **Duración**: ~3 horas  
> **Estado**: ✅ COMPLETADO

---

## 🎯 Objetivos

1. ✅ Implementar sistema de logging para capturar TODOS los errores de OCR
2. ✅ Guardar datos para análisis post-mortem
3. ✅ Aumentar timeout conservador basándose en datos reales
4. ✅ Preparar sistema de aprendizaje adaptativo

---

## 📊 Resumen Ejecutivo

### Problema Detectado
- PDFs de 15-17MB tardaban >15 min en procesarse con OCRmyPDF
- Fallaban con `HTTP_408` (timeout del servicio OCR)
- No había datos para analizar por qué fallaban ni cómo optimizar

### Solución Implementada
1. **Tabla `ocr_performance_log`** en PostgreSQL
   - Registra éxitos, timeouts, errores HTTP, excepciones
   - 4 índices para queries rápidas
   - 2 registros ya capturados (HTTP_408)

2. **Método `_log_to_db()`** en adaptador OCRmyPDF
   - Conexión directa a PostgreSQL
   - No bloquea OCR si falla el logging
   - Registra 7 campos por evento

3. **Fix crítico**: Migraciones PostgreSQL
   - `migration_runner.py` usaba SQLite (incorrecto)
   - Corregido a PostgreSQL
   - Todas las migraciones ahora funcionan

4. **Timeout aumentado**: 15 min → 20 min
   - Justificado por datos capturados
   - Máximo aumentado a 25 min
   - Sistema listo para aprender y optimizar

### Resultados
- ✅ Sistema de logging funcional
- ✅ 2 errores capturados y analizados
- ✅ Timeout aumentado para prevenir fallos
- ✅ 5 tareas OCR en progreso con nuevo timeout
- ⏳ Esperando resultados para calibrar aprendizaje

---

## 📁 Archivos Modificados

### Nuevos Archivos

1. **`backend/migrations/011_ocr_performance_log.py`**
   - Tabla + 4 índices
   - Formato yoyo-migrations
   - Compatible con PostgreSQL

2. **`docs/ai-lcd/OCR_PERFORMANCE_ANALYSIS.md`**
   - Guía completa de análisis
   - 5 queries SQL útiles
   - Estrategia de optimización adaptativa

### Archivos Modificados

1. **`backend/ocr_service_ocrmypdf.py`** (+50 líneas)
   - Método `_log_to_db()` implementado
   - Timeout: 900s → 1200s
   - Max timeout: 960s → 1500s
   - Registra todos los tipos de evento

2. **`backend/migration_runner.py`** (~10 líneas)
   - Connection string: SQLite → PostgreSQL
   - Credenciales correctas (POSTGRES_USER, POSTGRES_PASSWORD)

3. **`docs/ai-lcd/SESSION_LOG.md`** (+184 líneas)
   - Sesión 18 documentada completamente
   - Queries de análisis incluidas
   - Próximos pasos definidos

4. **`docs/ai-lcd/CONSOLIDATED_STATUS.md`** (+150 líneas)
   - Entrada #27 agregada
   - Queries de análisis
   - Estado de FASE 3

5. **`docs/ai-lcd/PLAN_AND_NEXT_STEP.md`** (+70 líneas)
   - Actualizado con Sesión 18
   - FASE 3 definida
   - Checklist de monitoreo

---

## 📊 Datos Capturados (Primeros Resultados)

### Registros en `ocr_performance_log`

| ID | Filename | Size (MB) | Success | Timeout (s) | Error Type | Timestamp |
|----|----------|-----------|---------|-------------|------------|-----------|
| 1 | 25-02-26-El Periodico Catalunya.pdf | 15.34 | ❌ | 900 | HTTP_408 | 2026-03-14 09:21:41 |
| 2 | 03-03-26-El Pais.pdf | 17.17 | ❌ | 900 | HTTP_408 | 2026-03-14 09:21:41 |

**Interpretación**:
- PDFs de ~15-17MB exceden 15 min de timeout
- Servicio OCR necesita más tiempo
- ✅ Justifica aumento a 20 min

### Estado Base de Datos General

**News Items**:
- 1,526 noticias extraídas
- 27 documentos con noticias
- 89 noticias/doc (máximo)

**Worker Tasks (última hora)**:
- 5 OCR en progreso (con timeout 20 min)
- 2 OCR error (timeouts antiguos)
- 72 insights completados (histórico)

---

## 🔍 Queries de Análisis Implementadas

### 1. Tasa de Éxito por Tamaño
```sql
SELECT 
  CASE 
    WHEN file_size_mb < 5 THEN '< 5MB'
    WHEN file_size_mb < 10 THEN '5-10MB'
    WHEN file_size_mb < 20 THEN '10-20MB'
    ELSE '> 20MB'
  END as size_range,
  COUNT(*) as total,
  SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
  ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM ocr_performance_log
GROUP BY size_range;
```

### 2. Errores Más Comunes
```sql
SELECT 
  error_type,
  COUNT(*) as count,
  ROUND(AVG(file_size_mb), 2) as avg_file_size_mb
FROM ocr_performance_log
WHERE success = false
GROUP BY error_type
ORDER BY count DESC;
```

### 3. Tiempo Promedio por Rango
```sql
SELECT 
  ROUND(file_size_mb / 5) * 5 as size_bucket_mb,
  COUNT(*) as samples,
  ROUND(AVG(processing_time_sec) / 60, 1) as avg_time_min,
  ROUND(MAX(processing_time_sec) / 60, 1) as max_time_min
FROM ocr_performance_log
WHERE success = true
GROUP BY size_bucket_mb
ORDER BY size_bucket_mb;
```

Ver documento completo: `docs/ai-lcd/OCR_PERFORMANCE_ANALYSIS.md`

---

## 🚀 Próximos Pasos (FASE 3)

### Inmediato (Hoy)
1. ⏳ **Monitorear tareas OCR en progreso**
   - 5 tareas con timeout 20 min
   - Esperando primeros éxitos (~10-20 min)

2. 📊 **Verificar registros de éxito**
   ```sql
   SELECT * FROM ocr_performance_log WHERE success = true ORDER BY timestamp DESC LIMIT 10;
   ```

3. 🎯 **Analizar tiempo promedio**
   - Ejecutar Query 3 (tiempo por rango)
   - Calibrar aprendizaje adaptativo

### Corto Plazo (Esta Semana)
4. 🔍 **Análisis post-mortem completo**
   - Tasa de éxito por tamaño (Query 1)
   - Errores más comunes (Query 2)
   - Identificar patrones

5. ⚙️ **Optimizar configuración OCR service**
   - Investigar por qué PDFs grandes tardan tanto
   - Ajustar `OCR_THREADS` si es necesario
   - Considerar `--fast` mode para PDFs grandes

6. 📈 **Implementar timeout adaptativo basado en BD**
   - Método `_calculate_timeout_learned()`
   - Query a BD para obtener avg_time por bucket
   - Ajuste automático: `avg_time * 1.3`

### Mediano Plazo (Próximas 2 Semanas)
7. 🎛️ **Dashboard de métricas OCR**
   - Visualización en tiempo real
   - Alertas si `timeout_rate > 20%`
   - Gráficas de tendencias

8. 🔄 **FASE 4: Migration Completa**
   - Cambiar default: `OCR_ENGINE=ocrmypdf`
   - Aumentar workers: 5 → 8
   - Deprecar Tika

---

## 📚 Documentación Generada

### Archivos de Documentación

1. **`docs/ai-lcd/SESSION_LOG.md`**
   - Sesión 18 completa
   - Implementación detallada
   - Bugs encontrados y solucionados

2. **`docs/ai-lcd/CONSOLIDATED_STATUS.md`**
   - Entrada #27
   - Estado actual del sistema
   - Verificación completa

3. **`docs/ai-lcd/PLAN_AND_NEXT_STEP.md`**
   - REQ-012 actualizado
   - FASE 3 definida
   - Checklist de monitoreo

4. **`docs/ai-lcd/OCR_PERFORMANCE_ANALYSIS.md`** (NUEVO)
   - Guía completa de análisis
   - 5 queries SQL detalladas
   - Estrategia de optimización adaptativa
   - Alertas y monitoreo

5. **`docs/ai-lcd/SESSION_18_README.md`** (Este archivo)
   - Resumen ejecutivo
   - Archivos modificados
   - Próximos pasos

---

## 🎯 Métricas de Éxito

### Implementación
- ✅ **Tabla creada**: `ocr_performance_log` con 4 índices
- ✅ **Logging funcional**: 2 registros capturados
- ✅ **Migraciones estables**: PostgreSQL correctamente configurado
- ✅ **Timeout aumentado**: 15 min → 20 min
- ✅ **Sistema robusto**: No bloquea OCR si falla logging

### Documentación
- ✅ **5 archivos actualizados**: SESSION_LOG, CONSOLIDATED_STATUS, PLAN_AND_NEXT_STEP, OCR_PERFORMANCE_ANALYSIS, README
- ✅ **5 queries SQL**: Listas para análisis
- ✅ **Estrategia de optimización**: Documentada paso a paso

### Sistema
- ✅ **Backend estable**: 25 workers activos
- ✅ **OCR funcionando**: 5 tareas en progreso
- ✅ **Sin regresiones**: Dashboard, master scheduler, workers OK

---

## 🔗 Referencias

- **Sesión Log**: `docs/ai-lcd/SESSION_LOG.md` § Sesión 18
- **Status**: `docs/ai-lcd/CONSOLIDATED_STATUS.md` § 27
- **Plan**: `docs/ai-lcd/PLAN_AND_NEXT_STEP.md` § REQ-012
- **Análisis**: `docs/ai-lcd/OCR_PERFORMANCE_ANALYSIS.md`
- **Código**: 
  - `backend/ocr_service_ocrmypdf.py` (método `_log_to_db`)
  - `backend/migrations/011_ocr_performance_log.py`
  - `backend/migration_runner.py`

---

## 🙏 Agradecimientos

Sistema implementado exitosamente gracias a:
- Datos reales capturados (2 timeouts) que justificaron el aumento de timeout
- Arquitectura modular que facilitó agregar logging sin romper nada
- PostgreSQL como base sólida para análisis post-mortem

---

**Fecha de finalización**: 2026-03-14 09:30  
**Status**: ✅ COMPLETADO  
**Próxima sesión**: Monitoreo OCR Performance + Optimización basada en datos
