# OpenAI Integration - NewsAnalyzer-RAG

> Detalles de la integración de OpenAI API como LLM provider

**Última actualización**: 2026-03-02
**Fase AI-DLC**: 02-construction
**Audiencia**: Desarrolladores

---

## 1. Problema

RAG Enterprise original solo soporta Ollama (modelos locales). El usuario requiere
usar su API key de OpenAI (ChatGPT) para respuestas de mayor calidad con GPT-4o.

## 2. Solución

Agregar un LLM provider configurable vía variables de entorno:

```
LLM_PROVIDER=openai    → Usa OpenAI API
LLM_PROVIDER=ollama    → Usa Ollama local (default, comportamiento original)
```

## 3. Archivos Modificados

### 3.1 `rag_pipeline.py`

**Cambio**: Agregar clase `OpenAIChatClient` junto a `OllamaChatDirect`

```python
class OpenAIChatClient:
    """OpenAI API client compatible with RAG pipeline interface."""

    def __init__(self, model: str, api_key: str, temperature: float = 0.0,
                 timeout: int = 120):
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.timeout = timeout

    def __call__(self, prompt: str) -> str:
        return self.invoke(prompt)

    def invoke(self, prompt: str) -> str:
        import requests
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": self.temperature,
            },
            timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]
```

**Cambio en RAGPipeline.__init__**: Recibir `llm_provider` y `openai_api_key` opcionales.

### 3.2 `app.py`

**Cambio**: Leer nuevas variables de entorno y pasar al pipeline.

Nuevas variables:
- `LLM_PROVIDER`: `"openai"`, `"perplexity"` o `"ollama"` (default: `"ollama"`)
- `OPENAI_API_KEY`: API key de OpenAI (requerido si provider es openai)
- `OPENAI_MODEL`: Modelo de OpenAI (default: `"gpt-4o"`)

### 3.3 `docker-compose.yml`

**Cambio**: Agregar variables de entorno al servicio backend.

### 3.4 `.env.example`

**Cambio**: Documentar las nuevas variables.

## 4. Flujo de Decisión

```
Startup
  │
  ├── LLM_PROVIDER == "openai"?
  │     ├── Sí → Verificar OPENAI_API_KEY existe
  │     │         ├── Existe → Crear OpenAIChatClient(model, api_key)
  │     │         └── No existe → ERROR: "OPENAI_API_KEY required when LLM_PROVIDER=openai"
  │     └── No (default "ollama") → wait_for_ollama() → ensure_model() → OllamaChatDirect()
  │
  └── Crear RAGPipeline(llm=client_seleccionado)
```

## 5. Perplexity (alternativa a OpenAI)

Si sufres 429 con OpenAI, puedes usar Perplexity como alternativa:

```
LLM_PROVIDER=perplexity
PERPLEXITY_API_KEY=pplx-...
PERPLEXITY_MODEL=sonar-pro   # o sonar, sonar-reasoning-pro
```

Modelos: `sonar`, `sonar-pro`, `sonar-reasoning-pro`, `sonar-deep-research`.
Límites por tier: 50–4,000 req/min según gasto acumulado.

## 6. Insights: OpenAI por defecto, Perplexity fallback

- `LLM_PROVIDER=openai` (default) — Insights con GPT
- `LLM_FALLBACK_PROVIDERS=perplexity` (default) — Si OpenAI devuelve 429, usa Perplexity
- Los LLM vía API son **solo para Insights**; embeddings siguen siendo HuggingFace local (o Perplexity si `EMBEDDING_PROVIDER=perplexity`)

## 7. Manejo de 429 (Rate Limit)

Variables para ajustar reintentos ante 429:
- `LLM_429_QUICK_RETRIES`: reintentos rápidos en el cliente (default: 3)
- `LLM_429_BASE_WAIT`: espera base en segundos (default: 5)
- `INSIGHTS_THROTTLE_SECONDS`: espera entre reintentos en workers (default: 60)
- `INSIGHTS_MAX_RETRIES`: máx. reintentos por insight (default: 5)

El cliente usa `Retry-After` del header cuando OpenAI lo envía.

## 8. Compatibilidad

La modificación es **aditiva**: el comportamiento por defecto (Ollama) no cambia.
Solo se activa OpenAI/Perplexity si `LLM_PROVIDER` está explícitamente configurado.

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Diseño de la integración (pre-implementación) | AI-DLC |
| 2026-03-16 | 1.1 | Perplexity, mejor manejo 429, Retry-After | AI-DLC |
