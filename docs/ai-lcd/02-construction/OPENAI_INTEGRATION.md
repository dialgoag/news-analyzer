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
- `LLM_PROVIDER`: `"openai"` o `"ollama"` (default: `"ollama"`)
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

## 5. Compatibilidad

La modificación es **aditiva**: el comportamiento por defecto (Ollama) no cambia.
Solo se activa OpenAI si `LLM_PROVIDER=openai` está explícitamente configurado.

---

| Fecha | Versión | Cambios | Autor |
|-------|---------|---------|-------|
| 2026-03-02 | 1.0 | Diseño de la integración (pre-implementación) | AI-DLC |
