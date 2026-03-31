"""
Runtime controls for the insights pipeline and other pausable pipeline steps.

Authoritative state lives in PostgreSQL (`pipeline_runtime_kv`); an in-process
cache is refreshed on startup, after admin updates, and after worker shutdown.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional

import pipeline_runtime_store as prs

logger = logging.getLogger(__name__)

_lock = threading.RLock()

KNOWN_IDS = ("openai", "perplexity", "ollama")

UNSET = object()

# Cache (mirrors DB); keys: pause.<step_id> -> bool, plus provider_mode / provider_order
_cache: Dict[str, Any] = {
    "pauses": {sid: False for sid, _ in prs.KNOWN_PAUSE_STEPS},
    "provider_mode": "auto",
    "provider_order": ["openai", "perplexity", "ollama"],
    "ollama_model": "",
}


def _normalize_provider_id(p: str) -> str:
    x = (p or "").strip().lower()
    if x in ("local", "ollama"):
        return "ollama"
    return x


def refresh_from_db() -> None:
    """Load all pipeline runtime flags from DB into the in-process cache."""
    global _cache
    try:
        snap = prs.load_full_snapshot()
    except Exception as e:
        logger.error("refresh_from_db: failed to load pipeline_runtime_kv: %s", e, exc_info=True)
        return
    with _lock:
        _cache["pauses"] = {p["id"]: bool(p["paused"]) for p in snap["pause_steps"]}
        llm = snap.get("insights_llm") or {}
        _cache["provider_mode"] = llm.get("mode", "auto")
        _cache["provider_order"] = list(llm.get("order") or ["openai", "perplexity", "ollama"])
        _cache["ollama_model"] = (llm.get("ollama_model") or "").strip()


def is_step_paused(step_id: str) -> bool:
    with _lock:
        return bool(_cache.get("pauses", {}).get(step_id, False))


def is_generation_paused() -> bool:
    return is_step_paused("insights")


def is_indexing_insights_paused() -> bool:
    return is_step_paused("indexing_insights")


def provider_order_for_rag() -> Optional[List[str]]:
    with _lock:
        if _cache.get("provider_mode") != "manual":
            return None
        raw = _cache.get("provider_order") or []
        out: List[str] = []
        for p in raw:
            n = _normalize_provider_id(str(p))
            if n in KNOWN_IDS and n not in out:
                out.append(n)
        return out or None


def ollama_model_for_insights() -> Optional[str]:
    """Runtime Ollama model name for insights; empty = let RAGPipeline pick (env / default)."""
    with _lock:
        s = (_cache.get("ollama_model") or "").strip()
        return s or None


def fetch_ollama_models(timeout_sec: float = 5.0) -> List[Dict[str, Any]]:
    """List models from Ollama /api/tags (name, size). Empty on failure."""
    host = (os.getenv("OLLAMA_HOST") or "localhost").strip()
    port = (os.getenv("OLLAMA_PORT") or "11434").strip()
    url = f"http://{host}:{port}/api/tags"
    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        models = data.get("models") or []
        out: List[Dict[str, Any]] = []
        for m in models:
            if not isinstance(m, dict):
                continue
            name = (m.get("name") or "").strip()
            if name:
                out.append({"name": name, "size": m.get("size")})
        out.sort(key=lambda x: x["name"].lower())
        return out
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, ValueError, json.JSONDecodeError) as e:
        logger.warning("fetch_ollama_models failed (%s): %s", url, e)
        return []


def list_available_providers() -> List[Dict[str, Any]]:
    openai_ok = bool(os.getenv("OPENAI_API_KEY", "").strip())
    pplx_ok = bool(os.getenv("PERPLEXITY_API_KEY", "").strip())
    return [
        {"id": "openai", "label": "OpenAI", "configured": openai_ok},
        {"id": "perplexity", "label": "Perplexity", "configured": pplx_ok},
        {"id": "ollama", "label": "Local (Ollama)", "configured": True},
    ]


def get_snapshot() -> Dict[str, Any]:
    with _lock:
        pause_steps = []
        for step_id, label in prs.KNOWN_PAUSE_STEPS:
            pause_steps.append(
                {
                    "id": step_id,
                    "label": label,
                    "paused": bool(_cache.get("pauses", {}).get(step_id, False)),
                }
            )
        om = (_cache.get("ollama_model") or "").strip()
        return {
            "pause_steps": pause_steps,
            "pause_generation": bool(_cache.get("pauses", {}).get("insights", False)),
            "pause_indexing_insights": bool(_cache.get("pauses", {}).get("indexing_insights", False)),
            "provider_mode": _cache["provider_mode"],
            "provider_order": list(_cache["provider_order"]),
            "available_providers": list_available_providers(),
            "env_llm_provider": os.getenv("LLM_PROVIDER", "ollama"),
            "env_llm_model": (os.getenv("LLM_MODEL") or "").strip(),
            "ollama_model": om or None,
            "ollama_models": fetch_ollama_models(),
        }


def update_settings(
    *,
    pause_generation: Optional[bool] = None,
    pause_indexing_insights: Optional[bool] = None,
    provider_mode: Optional[str] = None,
    provider_order: Optional[List[str]] = None,
    ollama_model: Any = UNSET,
    pause_steps: Optional[Dict[str, bool]] = None,
    pause_all: Optional[bool] = None,
    resume_all: Optional[bool] = None,
) -> Dict[str, Any]:
    if pause_all and resume_all:
        raise ValueError("pause_all and resume_all cannot both be set")

    if pause_all is True:
        prs.set_all_pauses(True)
    elif resume_all is True:
        prs.set_all_pauses(False)

    if pause_steps:
        valid = {s[0] for s in prs.KNOWN_PAUSE_STEPS}
        for step_id, paused in pause_steps.items():
            sid = (step_id or "").strip().lower()
            if sid not in valid:
                raise ValueError(f"Unknown pause step: {step_id}")
            prs.set_pause(sid, bool(paused))

    if pause_generation is not None:
        prs.set_pause("insights", bool(pause_generation))
    if pause_indexing_insights is not None:
        prs.set_pause("indexing_insights", bool(pause_indexing_insights))

    if provider_mode is not None or provider_order is not None or ollama_model is not UNSET:
        cur = prs.get_insights_llm()
        mode = cur["mode"]
        order = list(cur["order"])
        if provider_mode is not None:
            if provider_mode not in ("auto", "manual"):
                raise ValueError("provider_mode must be 'auto' or 'manual'")
            mode = provider_mode
        if provider_order is not None:
            seen = set()
            cleaned: List[str] = []
            for p in provider_order:
                n = _normalize_provider_id(str(p))
                if n not in KNOWN_IDS or n in seen:
                    continue
                seen.add(n)
                cleaned.append(n)
            order = cleaned
        if ollama_model is UNSET:
            prs.write_insights_llm(mode=mode, order=order)
        elif ollama_model is None or ollama_model == "":
            prs.write_insights_llm(mode=mode, order=order, ollama_model=None)
        else:
            prs.write_insights_llm(mode=mode, order=order, ollama_model=str(ollama_model).strip())

    refresh_from_db()
    return get_snapshot()


def apply_worker_shutdown_pauses() -> None:
    """Called after orderly worker shutdown: persist full pause and refresh cache."""
    prs.set_all_pauses(True)
    refresh_from_db()
