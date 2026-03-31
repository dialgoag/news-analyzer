# Comparar insights: Ollama (local) vs OpenAI — proceso manual

> **Spike / trazabilidad**: narrativa completa del análisis → [`../02-construction/SPIKE_REQ021_LOCAL_LLM_INSIGHTS_QUALITY.md`](../02-construction/SPIKE_REQ021_LOCAL_LLM_INSIGHTS_QUALITY.md) (**REQ-021**). Utilidad con **prompt alineado al backend**: `app/benchmark/compare_insights_models.py`.
>
> Sin endpoint en la app: tú ejecutas cada variante y guardas las salidas para decidir si quedarte en local o en API.

## 1. Mismo texto para ambas pruebas

- Copia un bloque de texto de una noticia (OCR, PDF, o chunks desde el dashboard / DB).
- Límite práctico ~80k caracteres (igual que el pipeline de insights).

## 2. Ollama (local)

```bash
# Modelo (una vez)
docker exec -it rag-ollama ollama pull mistral

# Probar generación (sustituye el prompt; "stream":false devuelve JSON único)
curl -sS http://127.0.0.1:11434/api/generate -d '{
  "model": "mistral",
  "prompt": "Eres analista de noticias. Con SOLO el texto siguiente, redacta en Markdown: Tema, Autor, Fuente, Postura, Resumen, Contexto IA.\n\n---\nTEXTO_AQUI\n---",
  "stream": false
}' | jq -r '.response' > /tmp/insights_ollama.md
```

Ajusta `model` al nombre exacto de `docker exec rag-ollama ollama list`.

## 3. OpenAI (API)

Desde tu máquina (necesitas la clave en el entorno; no la pegues en el repo):

```bash
export OPENAI_API_KEY="..."   # tu clave
curl -sS https://api.openai.com/v1/chat/completions \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-4o",
    "temperature": 0,
    "messages": [
      {"role": "system", "content": "Eres analista de noticias. Usa solo el contexto del usuario."},
      {"role": "user", "content": "Con SOLO el texto siguiente, redacta en Markdown: Tema, Autor, Fuente, Postura, Resumen, Contexto IA.\n\n---\nTEXTO_AQUI\n---"}
    ]
  }' | jq -r '.choices[0].message.content' > /tmp/insights_openai.md
```

Sustituye `TEXTO_AQUI` por el mismo bloque que usaste en Ollama (o usa un fichero y `jq`/`@file` según prefieras).

## 4. Probar el stack Docker como en producción (opcional)

Sin añadir código: alternar **solo variables** y reiniciar backend.

**Rama local**

- En `.env` / `docker-compose`: `LLM_PROVIDER=ollama`, `LLM_MODEL=mistral` (o el modelo que hayas descargado).
- `docker compose up -d backend`
- Deja que un ítem genere insights (o reencola uno) y revisa el markdown en BD / UI.

**Rama API**

- `LLM_PROVIDER=openai`, `OPENAI_API_KEY` configurada, `LLM_MODEL=gpt-4o` (o el que uses).
- Reinicia backend y repite con el **mismo documento** si quieres comparación parecida (mismo contexto de chunks).

El dashboard admin (orden manual de proveedores) también permite forzar **solo Ollama** o **solo OpenAI** en la cadena de insights, sin cambiar `.env`, para una prueba rápida tras reinicio.

## 5. Qué mirar al decidir

- Calidad del Markdown, alucinaciones, tono.
- Latitud y coste (OpenAI) vs hardware y tiempo (Ollama).
- Si necesitáis **fuentes web**, ninguno de los dos sustituye una búsqueda aparte; la comparación es sobre el **texto que ya tenéis**.
