# Spike REQ-021 — Análisis: LLM local vs API para insights de noticia

> **Tipo**: Spike de análisis (sin entrega de producto obligatoria)  
> **Fecha**: 2026-03-30  
> **Petición**: Evaluar si conviene operar **insights por noticia** en local (Ollama) frente a API (OpenAI / otros), priorizando **calidad** sobre latencia.  
> **Fuente única de contrato de salida**: `app/backend/rag_pipeline.py` → `generate_insights_with_fallback` (prompt con seis secciones Markdown).

---

## 1. Objetivo del spike

- Decidir con evidencia si **generar insights** (mismo contrato que producción) puede hacerse **en local** con calidad aceptable.
- **No** es objetivo optimizar tiempo de respuesta: se aceptan **minutos** por inferencia si la calidad es la variable de decisión.
- **No** formaba parte del spike integrar un endpoint de comparación en la aplicación (ver Fix #101): el análisis es **manual** o vía **script de benchmark**.

---

## 2. Contrato que debe cumplir el modelo (alineado con código)

El LLM recibe **extractos** de una noticia (hasta **80 000** caracteres) y una **etiqueta** (`filename` / título). Debe producir **Markdown** con:

1. **Tema** — Tema principal (solo del contexto).
2. **Autor** — Si es identificable en el texto; no inventar.
3. **Periódico/Fuente** — Medio o fuente si aparece; no inventar.
4. **Postura** — Lectura editorial (neutral, crítica, etc.) inferida **solo** del texto.
5. **Resumen** — Síntesis breve.
6. **Contexto IA** — Meta: verificable vs opinión, relevancia, sesgo vs hechos.

Restricciones explícitas en prompt: **solo información del contexto**; **no inventar**; **mismo idioma que la fuente**.

**Referencia en código**: `RAGPipeline.generate_insights_with_fallback` (`app/backend/rag_pipeline.py`).

---

## 3. Metodología aplicada

| Paso | Descripción |
|------|-------------|
| **Contexto** | Mismo texto para local y API (OCR recortado, chunks exportados desde Qdrant/BD, o archivo `.txt`). |
| **OpenAI** | Chat Completions, `temperature: 0`, modelo de referencia p. ej. `gpt-4o` (ajustable). |
| **Ollama** | `POST /api/chat` (recomendado para scripts) o `ollama run` por CLI; modelo local según hardware. |
| **Script** | `app/benchmark/compare_insights_models.py` — mismo **PROMPT_TEMPLATE** que el spike; salidas en `benchmark/insights_results/runs` con checklist de secciones. |

---

## 4. Hallazgos técnicos (entorno Docker / macOS)

| Hallazgo | Detalle |
|----------|---------|
| **Mistral 7B + HTTP** | En el contenedor `rag-ollama` probado, **`mistral:latest`** con `/api/generate` y `/api/chat` devolvía **`500`** con `llama runner process has terminated`. **No** implicaba necesariamente fallo del CLI: `ollama run mistral "…"` pudo responder en casos puntuales. |
| **Modelo pequeño + HTTP** | **`llama3.2:1b`** respondió **`200`** con `/api/chat` — útil para **validar** la API; **insuficiente** como modelo de decisión de **calidad** frente a `gpt-4o`. |
| **Contexto y memoria** | `num_ctx` alto (p. ej. 8192) + modelo grande aumenta RAM (KV + pesos); en VMs Docker/CVM con poca RAM el runner puede **terminarse** (`Load failed`). |
| **Timeouts** | Inferencia CPU larga: clientes (`curl`, IDE) con **timeout ~60–180 s** pueden cortar y provocar **500** o “0 bytes received”; usar **`--max-time` ≥ 600–1200 s** o ejecutar en terminal interactiva. |
| **Docker Desktop / rutas** | `-v /tmp:/tmp` en Mac **no** siempre corresponde al `/tmp` del host para `docker run`; usar **ruta del repo** para montajes (`app/.ollama-cmp` o similar). |
| **`pwd`** | Desde `.../news-analyzer/app` el volumen es **`$PWD/.ollama-cmp`**, no `$PWD/app/.ollama-cmp`. |

---

## 5. Implicaciones para la decisión “local sí/no”

- **Calidad**: Comparar con modelos **>= ~3B** (p. ej. `llama3.2:3b`, `llama3.1:8b`) o variantes **Q4 7B/14B** si el runner HTTP es estable; re-evaluar **Mistral** tras `ollama rm` + `pull` o **pin** de imagen `ollama/ollama:<versión>`.
- **Operación**: Local exige vigilar **RAM**, **versión de imagen**, y **modelos**; la API externaliza eso a cambio de coste.
- **Privacidad**: Texto no sale del perímetro si todo corre en local; spike no sustituye revisión legal/compliance.

---

## 6. Entregables del spike

| Entregable | Ubicación |
|-----------|-----------|
| Guía operativa manual | `docs/ai-lcd/03-operations/LOCAL_LLM_VS_OPENAI_INSIGHTS.md` |
| Script de comparación | `app/benchmark/compare_insights_models.py` |
| Glosario pipeline (insights) | `docs/ai-lcd/PIPELINE_GLOSARIO.md` § Insights |

---

## 7. Próximos pasos sugeridos (fuera del spike)

- [ ] Fijar **modelo local** candidato a calidad (p. ej. 3b/8b) y repetir comparación con **mismo** recorte que OpenAI.
- [ ] Si `mistral` sigue fallando por HTTP: **issue**/pin de imagen o generación solo vía **CLI** para esa etiqueta.
- [ ] Opcional: ampliar `TROUBLESHOOTING_GUIDE.md` con un apartado “Ollama runner terminated” enlazando a este spike.

---

## 8. Referencias

- `app/backend/rag_pipeline.py` — prompt canónico de insights.
- `docs/ai-lcd/03-operations/LOCAL_LLM_VS_OPENAI_INSIGHTS.md`
- `docs/ai-lcd/PIPELINE_GLOSARIO.md`
- `REQUESTS_REGISTRY.md` — **REQ-021**
