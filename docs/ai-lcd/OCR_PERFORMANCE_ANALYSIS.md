# Sistema de Logging de Performance OCR

> Análisis post-mortem y optimización adaptativa de timeouts
>
> **Implementado**: 2026-03-14
> **Versión**: 1.0
> **Ubicación**: `backend/migrations/011_ocr_performance_log.py`

---

## 📊 Overview

Sistema de registro completo de eventos OCR (éxitos, timeouts, errores) para:
1. **Análisis post-mortem**: Entender patrones de fallo
2. **Optimización adaptativa**: Ajustar timeouts basándose en datos reales
3. **Monitoreo**: Detectar problemas de rendimiento temprano
4. **Debugging**: Trazabilidad completa de errores

---

## 🗄️ Estructura de Datos

### Tabla: `ocr_performance_log`

```sql
CREATE TABLE ocr_performance_log (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) NOT NULL,
    file_size_mb DECIMAL(10, 2) NOT NULL,
    success BOOLEAN NOT NULL,
    processing_time_sec DECIMAL(10, 2),     -- NULL si falló
    timeout_used_sec INT NOT NULL,
    error_type VARCHAR(100),                -- TIMEOUT, HTTP_408, ConnectionError, etc
    error_detail TEXT,                      -- Mensaje completo (max 500 chars)
    timestamp TIMESTAMP DEFAULT NOW() NOT NULL
);

-- Índices para queries rápidas
CREATE INDEX idx_ocr_perf_timestamp ON ocr_performance_log(timestamp);
CREATE INDEX idx_ocr_perf_success ON ocr_performance_log(success);
CREATE INDEX idx_ocr_perf_error_type ON ocr_performance_log(error_type);
CREATE INDEX idx_ocr_perf_file_size ON ocr_performance_log(file_size_mb);
```

### Campos

| Campo | Tipo | Descripción | Ejemplo |
|-------|------|-------------|---------|
| `id` | SERIAL | ID autoincremental | 1, 2, 3... |
| `filename` | VARCHAR(500) | Nombre del archivo PDF | `03-03-26-El Pais.pdf` |
| `file_size_mb` | DECIMAL(10,2) | Tamaño en MB | 17.17 |
| `success` | BOOLEAN | ¿OCR exitoso? | `true` / `false` |
| `processing_time_sec` | DECIMAL(10,2) | Tiempo real procesamiento (si éxito) | 342.50 (5.7 min) |
| `timeout_used_sec` | INT | Timeout configurado usado | 1200 (20 min) |
| `error_type` | VARCHAR(100) | Tipo de error si falló | `HTTP_408`, `TIMEOUT`, `ConnectionError` |
| `error_detail` | TEXT | Mensaje de error completo | `Processing timeout for...` |
| `timestamp` | TIMESTAMP | Cuándo ocurrió | `2026-03-14 09:21:41` |

---

## 🔧 Implementación

### Método `_log_to_db()` en `ocr_service_ocrmypdf.py`

```python
def _log_to_db(self, filename: str, file_size_mb: float, success: bool,
               processing_time_sec: float = None, timeout_used_sec: int = None,
               error_type: str = None, error_detail: str = None):
    """
    Registra resultado (éxito o error) en PostgreSQL para análisis post-mortem
    
    IMPORTANTE: No falla silenciosamente - errores de DB no afectan OCR
    """
    try:
        import psycopg2
        
        # Conectar a PostgreSQL
        conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "postgres"),
            port=os.getenv("POSTGRES_PORT", "5432"),
            database=os.getenv("POSTGRES_DB", "rag_enterprise"),
            user=os.getenv("POSTGRES_USER", "raguser"),
            password=os.getenv("POSTGRES_PASSWORD", "ragpassword")
        )
        
        cursor = conn.cursor()
        
        # Insertar en tabla de logs
        query = """
            INSERT INTO ocr_performance_log 
            (filename, file_size_mb, success, processing_time_sec, 
             timeout_used_sec, error_type, error_detail, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        """
        
        cursor.execute(query, (
            filename,
            file_size_mb,
            success,
            processing_time_sec,
            timeout_used_sec,
            error_type,
            error_detail
        ))
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        # No fallar el OCR si falla el logging
        logger.warning(f"⚠️  Could not log to DB (non-critical): {e}")
```

### Integración en `extract_text()`

```python
def extract_text(self, file_path: str) -> str:
    filename = Path(file_path).name
    file_size = os.path.getsize(file_path)
    size_mb = file_size / (1024 * 1024)
    timeout = self._calculate_timeout(file_size)
    
    try:
        # ... (código de OCR) ...
        
        if response.status_code == 200:
            result = response.json()
            processing_time = result.get('processing_time_seconds', 0)
            
            # ✅ REGISTRAR ÉXITO
            self._log_to_db(
                filename=filename,
                file_size_mb=size_mb,
                success=True,
                processing_time_sec=processing_time,
                timeout_used_sec=timeout,
                error_type=None,
                error_detail=None
            )
            return result.get('text', '')
        else:
            # ❌ REGISTRAR ERROR HTTP
            error_detail = response.json().get('detail', 'Unknown error')
            self._log_to_db(
                filename=filename,
                file_size_mb=size_mb,
                success=False,
                processing_time_sec=None,
                timeout_used_sec=timeout,
                error_type=f"HTTP_{response.status_code}",
                error_detail=error_detail[:500]
            )
            return ""
            
    except requests.exceptions.Timeout:
        # ⏱️ REGISTRAR TIMEOUT
        self._update_learning_timeout()
        self._log_to_db(
            filename=filename,
            file_size_mb=size_mb,
            success=False,
            processing_time_sec=None,
            timeout_used_sec=timeout,
            error_type="TIMEOUT",
            error_detail=f"Exceeded {timeout}s timeout"
        )
        return ""
        
    except Exception as e:
        # 🐛 REGISTRAR EXCEPCIÓN GENÉRICA
        self._log_to_db(
            filename=filename,
            file_size_mb=size_mb,
            success=False,
            processing_time_sec=None,
            timeout_used_sec=timeout,
            error_type=type(e).__name__,
            error_detail=str(e)[:500]
        )
        return ""
```

---

## 📊 Queries de Análisis

### 1. Tasa de Éxito por Rango de Tamaño

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
  SUM(CASE WHEN NOT success THEN 1 ELSE 0 END) as failures,
  ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate
FROM ocr_performance_log
WHERE timestamp > NOW() - INTERVAL '7 days'
GROUP BY size_range
ORDER BY size_range;
```

**Ejemplo de output**:
```
 size_range | total | successes | failures | success_rate 
------------|-------|-----------|----------|-------------
 < 5MB      |   150 |       148 |        2 |        98.67
 5-10MB     |   320 |       312 |        8 |        97.50
 10-20MB    |   180 |       165 |       15 |        91.67
 > 20MB     |    50 |        38 |       12 |        76.00
```

**Interpretación**: PDFs >20MB tienen menor tasa de éxito → considerar timeout mayor

### 2. Errores Más Comunes

```sql
SELECT 
  error_type,
  COUNT(*) as count,
  ROUND(AVG(file_size_mb), 2) as avg_file_size_mb,
  ROUND(AVG(timeout_used_sec), 0) as avg_timeout_used,
  ARRAY_AGG(DISTINCT filename ORDER BY filename LIMIT 5) as example_files
FROM ocr_performance_log
WHERE success = false AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY error_type
ORDER BY count DESC;
```

**Ejemplo de output**:
```
 error_type | count | avg_file_size_mb | avg_timeout_used | example_files 
------------|-------|------------------|------------------|---------------
 HTTP_408   |    25 |            16.34 |             1200 | {file1.pdf, file2.pdf...}
 TIMEOUT    |    10 |            22.50 |             1500 | {file3.pdf, file4.pdf...}
 HTTP_500   |     3 |            12.10 |             1200 | {file5.pdf}
```

**Interpretación**: 
- `HTTP_408` dominante → servicio OCR tarda mucho (considerar aumentar timeout)
- `TIMEOUT` en archivos grandes → necesita timeout adaptativo por tamaño

### 3. Tiempo Promedio por Rango de Tamaño (Solo Éxitos)

```sql
SELECT 
  ROUND(file_size_mb / 5) * 5 as size_bucket_mb,
  COUNT(*) as samples,
  ROUND(AVG(processing_time_sec), 1) as avg_time_sec,
  ROUND(AVG(processing_time_sec) / 60, 1) as avg_time_min,
  ROUND(MAX(processing_time_sec), 1) as max_time_sec,
  ROUND(MAX(processing_time_sec) / 60, 1) as max_time_min,
  ROUND(AVG(timeout_used_sec) / 60, 1) as avg_timeout_min
FROM ocr_performance_log
WHERE success = true AND timestamp > NOW() - INTERVAL '7 days'
GROUP BY size_bucket_mb
ORDER BY size_bucket_mb;
```

**Ejemplo de output**:
```
 size_bucket_mb | samples | avg_time_sec | avg_time_min | max_time_sec | max_time_min | avg_timeout_min 
----------------|---------|--------------|--------------|--------------|--------------|----------------
              0 |     150 |        180.5 |          3.0 |        240.0 |          4.0 |            20.0
              5 |     320 |        420.3 |          7.0 |        580.0 |          9.7 |            20.0
             10 |     180 |        680.2 |         11.3 |        920.0 |         15.3 |            20.0
             15 |      80 |        920.5 |         15.3 |       1180.0 |         19.7 |            20.0
             20 |      50 |       1150.8 |         19.2 |       1380.0 |         23.0 |            25.0
```

**Interpretación**:
- PDFs de 0-5MB tardan ~3 min promedio → timeout de 20 min es excesivo
- PDFs de 15-20MB tardan ~15 min promedio → timeout de 20 min es adecuado
- Algunos PDFs de 20+MB tardan ~23 min → necesitan timeout de 25 min

**Optimización sugerida**:
```python
def _calculate_timeout(self, file_size_bytes: int) -> int:
    size_mb = file_size_bytes / (1024 * 1024)
    
    # Basándose en datos reales de la tabla
    if size_mb < 5:
        return 300   # 5 min (avg 3 min + 67% buffer)
    elif size_mb < 10:
        return 600   # 10 min (avg 7 min + 43% buffer)
    elif size_mb < 15:
        return 900   # 15 min (avg 11 min + 36% buffer)
    elif size_mb < 20:
        return 1200  # 20 min (avg 15 min + 33% buffer)
    else:
        return 1500  # 25 min (avg 19 min + 32% buffer)
```

### 4. Evolución Temporal (Últimas 24h)

```sql
SELECT 
  DATE_TRUNC('hour', timestamp) as hour,
  COUNT(*) as total_attempts,
  SUM(CASE WHEN success THEN 1 ELSE 0 END) as successes,
  ROUND(100.0 * SUM(CASE WHEN success THEN 1 ELSE 0 END) / COUNT(*), 2) as success_rate,
  ROUND(AVG(CASE WHEN success THEN processing_time_sec END), 1) as avg_success_time_sec
FROM ocr_performance_log
WHERE timestamp > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC
LIMIT 24;
```

**Uso**: Detectar degradación de performance a lo largo del día

### 5. Top 10 Archivos Más Lentos (Éxitos)

```sql
SELECT 
  filename,
  file_size_mb,
  processing_time_sec,
  ROUND(processing_time_sec / 60, 1) as processing_time_min,
  timeout_used_sec,
  timestamp
FROM ocr_performance_log
WHERE success = true
ORDER BY processing_time_sec DESC
LIMIT 10;
```

**Uso**: Identificar archivos problemáticos específicos para investigación manual

---

## 🎯 Estrategia de Optimización Adaptativa

### Fase 1: Recolección de Datos (Actual)
- ✅ Sistema de logging implementado
- ✅ Primeros registros capturados
- ⏳ Esperando ~100 registros para análisis estadístico

### Fase 2: Análisis Post-Mortem
- Ejecutar queries 1, 2, 3
- Identificar patrones:
  - ¿Qué tamaños de archivo tienen mayor tasa de fallo?
  - ¿Cuál es el tiempo promedio por rango?
  - ¿Qué errores son más comunes?

### Fase 3: Ajuste de Timeouts
Basándose en `avg_time_min` de Query 3:
```python
optimal_timeout = avg_processing_time * 1.3  # 30% buffer
```

### Fase 4: Implementación Adaptativa
```python
class OCRServiceOCRmyPDF:
    def _calculate_timeout_learned(self, file_size_bytes: int) -> int:
        """
        Calcula timeout basándose en datos históricos de la BD
        """
        size_mb = file_size_bytes / (1024 * 1024)
        
        # Query a la BD para obtener avg_time del bucket de tamaño
        avg_time = self._get_avg_time_for_size(size_mb)
        
        if avg_time:
            # Usar dato real + 30% buffer
            return int(avg_time * 1.3)
        else:
            # Fallback a timeout conservador si no hay datos
            return self.INITIAL_TIMEOUT
    
    def _get_avg_time_for_size(self, size_mb: float) -> float:
        """
        Consulta BD para obtener tiempo promedio de bucket de tamaño
        """
        try:
            conn = psycopg2.connect(...)
            cursor = conn.cursor()
            
            query = """
                SELECT AVG(processing_time_sec)
                FROM ocr_performance_log
                WHERE success = true 
                  AND file_size_mb BETWEEN %s AND %s
                  AND timestamp > NOW() - INTERVAL '7 days'
            """
            
            # Bucket de ±2MB
            cursor.execute(query, (size_mb - 2, size_mb + 2))
            result = cursor.fetchone()
            
            cursor.close()
            conn.close()
            
            return result[0] if result[0] else None
        except:
            return None
```

### Fase 5: Monitoreo Continuo
- Dashboard con métricas de OCR en tiempo real
- Alertas si `timeout_rate > 10%`
- Ajuste automático semanal basándose en datos

---

## 🚨 Alertas y Monitoreo

### Alert 1: Timeout Rate Alto
```sql
-- Ejecutar cada 10 minutos
SELECT 
  COUNT(*) FILTER (WHERE error_type IN ('TIMEOUT', 'HTTP_408')) as timeouts,
  COUNT(*) as total,
  ROUND(100.0 * COUNT(*) FILTER (WHERE error_type IN ('TIMEOUT', 'HTTP_408')) / COUNT(*), 2) as timeout_rate
FROM ocr_performance_log
WHERE timestamp > NOW() - INTERVAL '1 hour';

-- Si timeout_rate > 20%: ⚠️ ALERTA - Considerar aumentar timeout
```

### Alert 2: Performance Degradation
```sql
-- Comparar última hora vs promedio histórico
WITH current_hour AS (
  SELECT AVG(processing_time_sec) as avg_time
  FROM ocr_performance_log
  WHERE success = true AND timestamp > NOW() - INTERVAL '1 hour'
),
historical AS (
  SELECT AVG(processing_time_sec) as avg_time
  FROM ocr_performance_log
  WHERE success = true AND timestamp > NOW() - INTERVAL '7 days'
)
SELECT 
  c.avg_time as current_avg,
  h.avg_time as historical_avg,
  ROUND(100.0 * (c.avg_time - h.avg_time) / h.avg_time, 2) as degradation_percent
FROM current_hour c, historical h;

-- Si degradation_percent > 50%: ⚠️ ALERTA - Investigar causa
```

### Alert 3: Error Spike
```sql
-- Detectar aumento repentino de errores
SELECT 
  DATE_TRUNC('hour', timestamp) as hour,
  COUNT(*) FILTER (WHERE success = false) as errors
FROM ocr_performance_log
WHERE timestamp > NOW() - INTERVAL '6 hours'
GROUP BY hour
HAVING COUNT(*) FILTER (WHERE success = false) > 10
ORDER BY hour DESC;

-- Si más de 10 errores en una hora: ⚠️ ALERTA - Revisar servicio OCR
```

---

## 📁 Archivos Relacionados

| Archivo | Propósito |
|---------|-----------|
| `backend/migrations/011_ocr_performance_log.py` | Migración de tabla |
| `backend/ocr_service_ocrmypdf.py` | Implementación de logging |
| `backend/migration_runner.py` | Runner de migraciones (fix PostgreSQL) |
| `docs/ai-lcd/OCR_PERFORMANCE_ANALYSIS.md` | Este archivo |

---

## 🔗 Referencias

- Sesión 18: `SESSION_LOG.md` línea 1355+
- Consolidated Status: `CONSOLIDATED_STATUS.md` § 27
- Plan: `PLAN_AND_NEXT_STEP.md` § REQ-012 FASE 3

---

**Última actualización**: 2026-03-14 09:30  
**Autor**: Sistema NewsAnalyzer-RAG  
**Versión**: 1.0
