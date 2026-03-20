# Revisión del Diseño de Base de Datos — Pipeline RAG

> **Fecha**: 2026-03-16  
> **Propósito**: Documentar el diseño actual, validar coherencia y detectar redundancias/inconsistencias.

---

## 1. Convención de Estados: `{etapa}_{estado}`

**Sí, es así.** El campo `document_status.status` usa el prefijo de la etapa + el estado:

```
{stage}_{state}
```

| Etapa   | Estados posibles                    | Ejemplo           |
|---------|-------------------------------------|-------------------|
| upload  | pending, processing, done          | `upload_done`     |
| ocr     | pending, processing, done          | `ocr_done`        |
| chunking| pending, processing, done          | `chunking_done`   |
| indexing| pending, processing, done         | `indexing_done`   |
| insights| pending, processing, done         | `insights_done`   |
| terminal| completed, error, paused           | `completed`       |

**Flujo** (definido en `pipeline_states.py`):

```
upload_pending → upload_processing → upload_done
  → ocr_pending → ocr_processing → ocr_done
  → chunking_pending → chunking_processing → chunking_done
  → indexing_pending → indexing_processing → indexing_done
  → insights_pending → insights_processing → insights_done
  → completed
```

Con `status` se sabe en todo momento:
- **Etapa**: prefijo (`ocr`, `chunking`, `indexing`, etc.)
- **Estado**: sufijo (`pending`, `processing`, `done`)

---

## 2. Tablas Principales

### 2.1 `document_status` — Estado del documento

| Columna          | Tipo    | Uso                                      |
|------------------|---------|------------------------------------------|
| document_id      | VARCHAR | PK, identificador único                  |
| filename         | TEXT    | Nombre del archivo                       |
| status           | VARCHAR | `{etapa}_{estado}` (fuente de verdad)    |
| processing_stage | VARCHAR | `ocr` \| `chunking` \| `indexing`        |
| ocr_text         | TEXT    | Texto extraído por OCR                    |
| num_chunks       | INT     | Chunks generados                         |
| indexed_at       | TIMESTAMP | Cuándo se indexó en Qdrant             |
| error_message    | TEXT    | Si status = error                        |

**Redundancia**: `processing_stage` es derivable de `status` (ej. `ocr_done` → stage=ocr). Se mantiene por compatibilidad y porque algunas queries lo usan explícitamente.

### 2.2 `processing_queue` — Cola de tareas por documento

| Columna     | Tipo    | Uso                                      |
|-------------|---------|------------------------------------------|
| document_id | VARCHAR | FK implícito a document_status           |
| task_type   | VARCHAR | `ocr` \| `chunking` \| `indexing` \| `insights` |
| status      | VARCHAR | `pending` \| `processing` \| `completed`  |
| priority    | INT     | Mayor = más urgente                      |

**UNIQUE(document_id, task_type)**: Un documento tiene como máximo una tarea por tipo.

### 2.3 `worker_tasks` — Workers activos

| Columna     | Tipo    | Uso                                      |
|-------------|---------|------------------------------------------|
| worker_id   | VARCHAR | Identificador del worker                 |
| document_id | VARCHAR | Documento asignado                        |
| task_type   | VARCHAR | Tipo de tarea                            |
| status      | VARCHAR | `assigned` \| `started` \| `completed` \| `error` |

### 2.4 `news_item_insights` — Insights por noticia

| Columna     | Tipo    | Uso                                      |
|-------------|---------|------------------------------------------|
| news_item_id| VARCHAR | PK                                       |
| document_id | VARCHAR | Documento padre                           |
| status      | VARCHAR | `pending` \| `queued` \| `generating` \| `done` \| `error` |

**Nota**: Insights no usan `processing_queue` de la misma forma; la cola de insights se gestiona vía `news_item_insights.status`.

---

## 3. Fuentes de Verdad y Coherencia

### 3.1 Dos fuentes para “dónde está el documento”

| Fuente            | Qué indica                          |
|-------------------|-------------------------------------|
| `document_status.status` | Estado real del documento en el pipeline |
| `processing_queue`       | Tareas encoladas o en proceso       |

Pueden desincronizarse:
- Un doc puede estar en `chunking_done` en `document_status` pero no tener fila en `processing_queue` para indexing (ej. si la tarea se borró).
- Un doc puede tener `processing_queue` con `ocr` completed pero nunca haber tenido fila en `document_status` si se creó por otro camino.

**Recomendación**: Usar `document_status` como fuente de verdad para el total de documentos y para el estado del pipeline. `processing_queue` es operativa (qué hay que procesar).

### 3.2 Coherencia de totales

Para que los totales cuadren en cada etapa:

```
total_documentos = COUNT(document_status)
Para cada etapa (OCR, Chunking, Indexing):
  pending + processing + completed = total_documentos
```

Si `processing_queue` tiene menos filas que `total_documentos` (ej. 244 vs 245), la diferencia son documentos que aún no tienen tarea en esa etapa o cuya tarea se perdió. El dashboard debe usar `total_documentos` como denominador y ajustar `pending` para que la suma sea correcta.

---

## 4. Posibles Mejoras (sin romper el diseño actual)

1. **Índice compuesto** en `document_status(status, processing_stage)` para queries que filtran por ambos.
2. **Vista materializada** o query única para “estado por etapa” que derive todo de `document_status` y evite desfases con `processing_queue`.
3. **Job de reconciliación** que detecte y corrija desfases entre `document_status` y `processing_queue` (docs en `*_done` sin tarea `completed` en la cola).
4. **Eliminar `processing_stage`** a largo plazo y derivar la etapa desde `status` (requiere migración y actualización de queries).

---

## 5. Resumen

| Pregunta                         | Respuesta                                                                 |
|----------------------------------|---------------------------------------------------------------------------|
| ¿Se usa prefijo de etapa + estado? | Sí. `status = "{etapa}_{estado}"` (ej. `ocr_done`, `chunking_processing`). |
| ¿El diseño es correcto?          | Sí. La convención es clara y consistente.                                |
| ¿Hay redundancia?                | Sí. `processing_stage` es derivable de `status`.                          |
| ¿Hay riesgo de incoherencia?     | Sí. `document_status` y `processing_queue` pueden desincronizarse.      |
| ¿Qué usar como fuente de verdad? | `document_status` para totales y estado; `processing_queue` para la cola. |
