# OpenAI API: Límites de tasa, uso y mitigación 429

> Cómo saber cuántas peticiones permite OpenAI, interpretar el uso y evitar errores 429 (Too Many Requests).

**Última actualización**: 2026-03-02  
**Fase AI-DLC**: 03-operations  
**Audiencia**: DevOps, desarrollo backend

---

## 0. Tarea prioritaria AI-DLC: ingesta, insights y optimización OpenAI

Todo lo siguiente forma **la tarea prioritaria AI-DLC** (documentada en `docs/ai-dlc/README.md` y puesta como siguiente paso en `PLAN_AND_NEXT_STEP.md` y `STATUS_AND_HISTORY.md`):

| Pilar | Qué incluye |
|-------|-------------|
| **Barra de estado** | Dashboard: progreso global "X de Y noticias procesadas" y columna por documento (progreso `done/total`) con enlace "Ver" para abrir la lista de noticias e insights. |
| **Algoritmo de indexado** | Pipeline de ingesta: OCR → segmentación en noticias → chunking → embedding → Qdrant; workers paralelos (`INGEST_PARALLEL_WORKERS`), throttle del reporte diario (`INGEST_REPORT_THROTTLE_MINUTES`, `INGEST_DEFER_REPORT_GENERATION`). |
| **Ingesta con LLM (insights por noticia)** | Cola de trabajos que genera un insight por **noticia** (news item) dentro de un PDF multi-noticia. Worker cada 2 min, procesa 1 item a la vez; encolado al terminar la indexación. |
| **Optimización del uso de la API key OpenAI** | Respetar RPM/TPM: cola en lugar de llamadas masivas, reintentos con backoff ante 429, variables `INSIGHTS_THROTTLE_SECONDS` e `INSIGHTS_MAX_RETRIES`. |

**Documentación**: este documento (§0 y §4), `docs/ai-dlc/README.md`, `ENVIRONMENT_CONFIGURATION.md`, `INGEST_GUIDE.md`; estado en `PLAN_AND_NEXT_STEP.md` y `STATUS_AND_HISTORY.md`.

---

## 1. Dónde ver tus límites

- **Panel**: [Settings → Organization → Limits](https://platform.openai.com/settings/organization/limits).
- Ahí ves por modelo:
  - **RPM** (requests per minute)
  - **RPD** (requests per day)
  - **TPM** (tokens per minute)
  - **TPD** (tokens per day, batch)
- Los límites dependen del **tier** de la organización (según gasto acumulado).

---

## 2. Cabeceras HTTP (límites en tiempo real)

Cada respuesta de la API puede incluir cabeceras de rate limit:

| Cabecera | Ejemplo | Descripción |
|----------|---------|-------------|
| `x-ratelimit-limit-requests` | 60 | Máximo de peticiones en la ventana |
| `x-ratelimit-remaining-requests` | 59 | Peticiones restantes |
| `x-ratelimit-reset-requests` | 1s | Tiempo hasta que se reinicia el límite |
| `x-ratelimit-limit-tokens` | 150000 | Límite de tokens (TPM) |
| `x-ratelimit-remaining-tokens` | 149984 | Tokens restantes |

---

## 3. Export de uso (CSV)

OpenAI permite exportar uso (p. ej. **Usage → Export** en el dashboard). El CSV típico incluye:

- `start_time_iso`, `end_time_iso`
- `num_model_requests`
- `model`
- `input_tokens`, `output_tokens`

---

## 4. Mitigación de 429 en NewsAnalyzer-RAG

### 4.1 Ya implementado

- **INGEST_DEFER_REPORT_GENERATION**: no generar reporte diario tras cada documento; solo el job de las 23:00.
- **INGEST_REPORT_THROTTLE_MINUTES**: regenerar el reporte diario de una fecha como máximo cada N minutos (evita muchas llamadas al LLM por la misma fecha).

### 4.2 Insights por noticia (PDF multi-noticia) — prioridad

Para **insights generado por el LLM por cada noticia** (news item) dentro de un PDF:

1. **Segmentación**: tras OCR, dividir el texto en *news items* (heurística de títulos + fallback por páginas). Se crean `news_item_id = document_id::idx`.
2. **Indexación en Qdrant**: cada chunk se indexa con metadata `news_item_id`, `news_title`, `news_item_index` y siempre `document_id`/`filename` para referencia al origen.
3. **Cola de trabajos**: no llamar al LLM en el hilo de indexación; encolar el `news_item_id` para “generar insights”.
4. **Worker dedicado**: job cada 2 min, procesa la cola de uno en uno.
5. **Reintentos con backoff**: ante 429, esperar `INSIGHTS_THROTTLE_SECONDS * 2^intento` y reintentar hasta `INSIGHTS_MAX_RETRIES`.
6. **Deduplicación**: calcular `text_hash` (SHA-256 del texto normalizado del item). Si existe un `news_item_insights` DONE con el mismo `text_hash`, reutilizar el contenido sin volver a llamar al LLM.

Implementación (referencias):
- SQLite: `news_items`, `news_item_insights` (con `text_hash`).
- Backend: `_process_document_sync` segmenta/indexa; `run_news_item_insights_queue_job` procesa la cola; endpoints `GET /api/documents/{document_id}/news-items` y `GET /api/news-items/{news_item_id}/insights`.

---

## 5. Referencias

- [Rate limits (OpenAI)](https://platform.openai.com/docs/guides/rate-limits)
- [How to handle rate limits (OpenAI Cookbook)](https://cookbook.openai.com/examples/how_to_handle_rate_limits)

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación: límites, cabeceras, CSV, mitigación 429, diseño cola insights | AI-DLC |
| 2026-03-02 | 1.1 | Ajuste a PDF multi-noticia: segmentación, insights por item, dedupe por `text_hash`, endpoints | AI-DLC |

# OpenAI API: Límites de tasa, uso y mitigación 429

> Cómo saber cuántas peticiones permite OpenAI, interpretar el uso y evitar errores 429 (Too Many Requests).

**Última actualización**: 2026-03-02  
**Fase AI-DLC**: 03-operations  
**Audiencia**: DevOps, desarrollo backend

---

## 0. Tarea prioritaria AI-DLC: ingesta, insights y optimización OpenAI

Todo lo siguiente forma **la tarea prioritaria AI-DLC** (documentada en `docs/ai-dlc/README.md` y puesta como siguiente paso en `PLAN_AND_NEXT_STEP.md` y `STATUS_AND_HISTORY.md`):

| Pilar | Qué incluye |
|-------|-------------|
| **Barra de estado** | Dashboard: progreso global "X de Y noticias procesadas" y columna por documento (0/1 o 1/1) con enlace "Ver" a los insights. Refleja cuántas noticias ya tienen insights generados por el LLM. |
| **Algoritmo de indexado** | Pipeline de ingesta: OCR → chunking → embedding → Qdrant; workers paralelos (`INGEST_PARALLEL_WORKERS`), throttle del reporte diario (`INGEST_REPORT_THROTTLE_MINUTES`, `INGEST_DEFER_REPORT_GENERATION`). |
| **Ingesta con LLM (insights por noticia)** | Cola de trabajos que genera un reporte/insight por archivo (no solo reporte diario agregado). Worker cada 2 min, un documento a la vez; encolado al indexar. Mejora la base para reportes diarios y semanales por temas. |
| **Optimización del uso de la API key OpenAI** | Respetar RPM/TPM: cola en lugar de llamadas masivas, reintentos con backoff ante 429, variables `INSIGHTS_THROTTLE_SECONDS` e `INSIGHTS_MAX_RETRIES`. Ver §1–§3 para límites y cabeceras. |

**Documentación de la tarea prioritaria AI-DLC**: este documento (§0 y §4), `docs/ai-dlc/README.md`, `ENVIRONMENT_CONFIGURATION.md`, `INGEST_GUIDE.md`; estado en `PLAN_AND_NEXT_STEP.md` y `STATUS_AND_HISTORY.md`.

---

## 1. Dónde ver tus límites

- **Panel**: [Settings → Organization → Limits](https://platform.openai.com/settings/organization/limits).
- Ahí ves por modelo:
  - **RPM** (requests per minute)
  - **RPD** (requests per day)
  - **TPM** (tokens per minute)
  - **TPD** (tokens per day, batch)
- Los límites dependen del **tier** de la organización (según gasto acumulado).

### 1.1 Ejemplo de límites (gpt-4o)

Para **gpt-4o** suele aparecer algo como:

- **500 RPM**
- **30.000 TPM**
- **90.000 TPD** (batch queue)

Si disparas muchas peticiones en poco tiempo (p. ej. reportes al indexar muchos documentos), puedes alcanzar 500 RPM o 30k TPM y recibir **429 Too Many Requests** aunque el gasto mensual sea bajo.

---

## 2. Cabeceras HTTP (límites en tiempo real)

Cada respuesta de la API puede incluir cabeceras de rate limit:

| Cabecera | Ejemplo | Descripción |
|----------|---------|-------------|
| `x-ratelimit-limit-requests` | 60 | Máximo de peticiones en la ventana |
| `x-ratelimit-remaining-requests` | 59 | Peticiones restantes |
| `x-ratelimit-reset-requests` | 1s | Tiempo hasta que se reinicia el límite (p. ej. por minuto) |
| `x-ratelimit-limit-tokens` | 150000 | Límite de tokens (TPM) |
| `x-ratelimit-remaining-tokens` | 149984 | Tokens restantes |

Se pueden leer en el backend para mostrar uso o para decidir cuándo reintentar tras un 429.

> **Novedad**: el cliente `OpenAIChatClient` ahora registra automáticamente estas cabeceras
> cuando estamos cerca del límite o recibimos un 429. Ajusta los umbrales con
> `LLM_RATELIMIT_WARN_REQUESTS`, `LLM_RATELIMIT_WARN_TOKENS` y, si quieres siempre ver los
> valores, habilita `LLM_LOG_RATE_LIMIT_SUCCESS=true`.

---

## 3. Export de uso (CSV)

OpenAI permite exportar uso (p. ej. **Usage → Export** en el dashboard). El CSV típico incluye:

- `start_time_iso`, `end_time_iso`: ventana (p. ej. por día).
- `num_model_requests`: número de peticiones.
- `model`: modelo usado (gpt-4o-2024-08-06, gpt-5.1-*, etc.).
- `input_tokens`, `output_tokens`: tokens de entrada y salida.

Con eso puedes:

- Ver qué días hubo uso y con qué modelos.
- Sumar peticiones y tokens para comprobar que el gasto coincide con el dashboard.
- Confirmar que los 429 no vienen de cuota mensual agotada, sino de **picos de RPM/TPM**.

---

## 4. Mitigación de 429 en NewsAnalyzer-RAG

### 4.1 Ya implementado

- **INGEST_DEFER_REPORT_GENERATION**: no generar reporte diario tras cada documento; solo el job de las 23:00.
- **INGEST_REPORT_THROTTLE_MINUTES**: regenerar el reporte diario de una fecha como máximo cada N minutos (evita muchas llamadas al LLM por la misma fecha en ingesta masiva).

### 4.2 Reporte por archivo (insights) — prioridad

Para **reporte/insights generado por el LLM por cada archivo** (no solo reporte diario agregado), dentro de la **misma tarea** que la barra de estado y la optimización OpenAI (§0):

1. **Cola de trabajos**: no llamar al LLM en el mismo hilo de indexación; encolar el `document_id` para “generar insights”.
2. **Worker dedicado**: un job (cada 2 min) procesa la cola de uno en uno para no disparar RPM.
3. **Reintentos con backoff**: ante 429, esperar `INSIGHTS_THROTTLE_SECONDS * 2^intento` y reintentar hasta `INSIGHTS_MAX_RETRIES`.
4. **Barra de estado en el dashboard**: global "X de Y noticias procesadas" y columna "Insights LLM" por documento (barra 0/1 o 1/1, botón "Ver").
5. **Deduplicación por contenido**: calcular un `content_hash` (SHA-256 de los bytes del archivo) al indexar; si ya existe un `document_insights` en estado DONE con el mismo `content_hash`, se reutiliza el contenido (STATUS_DONE + `content`) para el nuevo `document_id` sin volver a llamar al LLM.

Así se respetan los límites de OpenAI y se muestra el progreso de insights por archivo, evitando recalcular insights para el mismo PDF subido varias veces. Los insights granulares por noticia mejoran la generación de reportes diarios y semanales por temas. Implementación: tabla `document_insights` (columna `content_hash` + índice), `DocumentInsightsStore` (método `get_done_by_content_hash`), cómputo de hash y reutilización/enqueue en `_process_document_sync` y `run_insights_queue_job` en `app.py`; variables en `ENVIRONMENT_CONFIGURATION.md`.

---

## 5. Referencias

- [Rate limits (OpenAI)](https://platform.openai.com/docs/guides/rate-limits)
- [How to handle rate limits (OpenAI Cookbook)](https://cookbook.openai.com/examples/how_to_handle_rate_limits)
- Variables de entorno relacionadas: `INGEST_DEFER_REPORT_GENERATION`, `INGEST_REPORT_THROTTLE_MINUTES`, `INSIGHTS_QUEUE_ENABLED`, `INSIGHTS_THROTTLE_SECONDS`, `INSIGHTS_MAX_RETRIES` en `ENVIRONMENT_CONFIGURATION.md` e `INGEST_GUIDE.md`.

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación: límites, cabeceras, CSV, mitigación 429, diseño cola insights | AI-DLC |
| 2026-03-02 | 1.1 | §0 Una sola tarea: barra de estado, indexado, ingesta LLM (insights), optimización API key OpenAI | AI-DLC |
| 2026-03-02 | 1.2 | §4.2: deduplicación de insights por `content_hash` (evitar recalcular para PDFs idénticos) | AI-DLC |

# OpenAI API: Límites de tasa, uso y mitigación 429

> Cómo saber cuántas peticiones permite OpenAI, interpretar el uso y evitar errores 429 (Too Many Requests).

**Última actualización**: 2026-03-02  
**Fase AI-DLC**: 03-operations  
**Audiencia**: DevOps, desarrollo backend

---

## 0. Tarea prioritaria AI-DLC: ingesta, insights y optimización OpenAI

Todo lo siguiente forma **la tarea prioritaria AI-DLC** (documentada en `docs/ai-dlc/README.md` y puesta como siguiente paso en `PLAN_AND_NEXT_STEP.md` y `STATUS_AND_HISTORY.md`):

| Pilar | Qué incluye |
|-------|-------------|
| **Barra de estado** | Dashboard: progreso global "X de Y noticias procesadas" y columna por documento (0/1 o 1/1) con enlace "Ver" a los insights. Refleja cuántas noticias ya tienen insights generados por el LLM. |
| **Algoritmo de indexado** | Pipeline de ingesta: OCR → chunking → embedding → Qdrant; workers paralelos (`INGEST_PARALLEL_WORKERS`), throttle del reporte diario (`INGEST_REPORT_THROTTLE_MINUTES`, `INGEST_DEFER_REPORT_GENERATION`). |
| **Ingesta con LLM (insights por noticia)** | Cola de trabajos que genera un reporte/insight por archivo (no solo reporte diario agregado). Worker cada 2 min, un documento a la vez; encolado al indexar. Mejora la base para reportes diarios y semanales por temas. |
| **Optimización del uso de la API key OpenAI** | Respetar RPM/TPM: cola en lugar de llamadas masivas, reintentos con backoff ante 429, variables `INSIGHTS_THROTTLE_SECONDS` e `INSIGHTS_MAX_RETRIES`. Ver §1–§3 para límites y cabeceras. |

**Documentación de la tarea prioritaria AI-DLC**: este documento (§0 y §4), `docs/ai-dlc/README.md`, `ENVIRONMENT_CONFIGURATION.md`, `INGEST_GUIDE.md`; estado en `PLAN_AND_NEXT_STEP.md` y `STATUS_AND_HISTORY.md`.

---

## 1. Dónde ver tus límites

- **Panel**: [Settings → Organization → Limits](https://platform.openai.com/settings/organization/limits).
- Ahí ves por modelo:
  - **RPM** (requests per minute)
  - **RPD** (requests per day)
  - **TPM** (tokens per minute)
  - **TPD** (tokens per day, batch)
- Los límites dependen del **tier** de la organización (según gasto acumulado).

### 1.1 Ejemplo de límites (gpt-4o)

Para **gpt-4o** suele aparecer algo como:

- **500 RPM**
- **30.000 TPM**
- **90.000 TPD** (batch queue)

Si disparas muchas peticiones en poco tiempo (p. ej. reportes al indexar muchos documentos), puedes alcanzar 500 RPM o 30k TPM y recibir **429 Too Many Requests** aunque el gasto mensual sea bajo.

---

## 2. Cabeceras HTTP (límites en tiempo real)

Cada respuesta de la API puede incluir cabeceras de rate limit:

| Cabecera | Ejemplo | Descripción |
|----------|---------|-------------|
| `x-ratelimit-limit-requests` | 60 | Máximo de peticiones en la ventana |
| `x-ratelimit-remaining-requests` | 59 | Peticiones restantes |
| `x-ratelimit-reset-requests` | 1s | Tiempo hasta que se reinicia el límite (p. ej. por minuto) |
| `x-ratelimit-limit-tokens` | 150000 | Límite de tokens (TPM) |
| `x-ratelimit-remaining-tokens` | 149984 | Tokens restantes |

Se pueden leer en el backend para mostrar uso o para decidir cuándo reintentar tras un 429.

---

## 3. Export de uso (CSV)

OpenAI permite exportar uso (p. ej. **Usage → Export** en el dashboard). El CSV típico incluye:

- `start_time_iso`, `end_time_iso`: ventana (p. ej. por día).
- `num_model_requests`: número de peticiones.
- `model`: modelo usado (gpt-4o-2024-08-06, gpt-5.1-*, etc.).
- `input_tokens`, `output_tokens`: tokens de entrada y salida.

Con eso puedes:

- Ver qué días hubo uso y con qué modelos.
- Sumar peticiones y tokens para comprobar que el gasto coincide con el dashboard.
- Confirmar que los 429 no vienen de cuota mensual agotada, sino de **picos de RPM/TPM**.

---

## 4. Mitigación de 429 en NewsAnalyzer-RAG

### 4.1 Ya implementado

- **INGEST_DEFER_REPORT_GENERATION**: no generar reporte diario tras cada documento; solo el job de las 23:00.
- **INGEST_REPORT_THROTTLE_MINUTES**: regenerar el reporte diario de una fecha como máximo cada N minutos (evita muchas llamadas al LLM por la misma fecha en ingesta masiva).

### 4.2 Reporte por archivo (insights) — prioridad

Para **reporte/insights generado por el LLM por cada archivo** (no solo reporte diario agregado), dentro de la **misma tarea** que la barra de estado y la optimización OpenAI (§0):

1. **Cola de trabajos**: no llamar al LLM en el mismo hilo de indexación; encolar el `document_id` para “generar insights”.
2. **Worker dedicado**: un job (cada 2 min) procesa la cola de uno en uno para no disparar RPM.
3. **Reintentos con backoff**: ante 429, esperar `INSIGHTS_THROTTLE_SECONDS * 2^intento` y reintentar hasta `INSIGHTS_MAX_RETRIES`.
4. **Barra de estado en el dashboard**: global "X de Y noticias procesadas" y columna "Insights LLM" por documento (barra 0/1 o 1/1, botón "Ver").

Así se respetan los límites de OpenAI y se muestra el progreso de insights por archivo. Los insights granulares por noticia mejoran la generación de reportes diarios y semanales por temas. Implementación: tabla `document_insights`, `DocumentInsightsStore`, job de cola y API en `app.py`; variables en `ENVIRONMENT_CONFIGURATION.md`.

---

## 5. Referencias

- [Rate limits (OpenAI)](https://platform.openai.com/docs/guides/rate-limits)
- [How to handle rate limits (OpenAI Cookbook)](https://cookbook.openai.com/examples/how_to_handle_rate_limits)
- Variables de entorno relacionadas: `INGEST_DEFER_REPORT_GENERATION`, `INGEST_REPORT_THROTTLE_MINUTES`, `INSIGHTS_QUEUE_ENABLED`, `INSIGHTS_THROTTLE_SECONDS`, `INSIGHTS_MAX_RETRIES` en `ENVIRONMENT_CONFIGURATION.md` e `INGEST_GUIDE.md`.

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Creación: límites, cabeceras, CSV, mitigación 429, diseño cola insights | AI-DLC |
| 2026-03-02 | 1.1 | §0 Una sola tarea: barra de estado, indexado, ingesta LLM (insights), optimización API key OpenAI | AI-DLC |
