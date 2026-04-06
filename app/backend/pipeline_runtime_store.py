"""
Persistent pipeline runtime settings (PostgreSQL).

Keys:
  pause.<task_type>  — value {"paused": bool}  task_type ∈ ocr, chunking, indexing, insights, indexing_insights
  insights.llm       — value {"mode", "order", optional "ollama_model"} (modelo Ollama solo para insights)
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import psycopg2.extras

from adapters.driven.persistence.postgres.base import BasePostgresRepository

logger = logging.getLogger(__name__)

# (step_id matches processing_queue.task_type / worker pool)
KNOWN_PAUSE_STEPS: List[Tuple[str, str]] = [
    ("ocr", "OCR"),
    ("chunking", "Chunking"),
    ("indexing", "Indexado documentos (vectores)"),
    ("insights", "Insights (LLM)"),
    ("indexing_insights", "Indexado insights en Qdrant"),
]

INSIGHTS_LLM_KEY = "insights.llm"

_DEFAULT_LLM = {"mode": "auto", "order": ["openai", "perplexity", "ollama"]}

_UNSET = object()


def _norm_ollama_model(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _pause_key(step_id: str) -> str:
    return f"pause.{step_id}"


def _row_get(row: Any, key: str, idx: int) -> Any:
    """Read value from dict-like or tuple-like DB row."""
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    try:
        return row[idx]
    except Exception:
        return None


class _PipelineRuntimeRepository(BasePostgresRepository):
    """Lightweight helper to access pipeline_runtime_kv without legacy stores."""
    pass


_runtime_repo = _PipelineRuntimeRepository()


def _conn():
    return _runtime_repo.get_connection()


def _release(conn):
    _runtime_repo.release_connection(conn)


def get_pause(step_id: str) -> bool:
    key = _pause_key(step_id)
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT value FROM pipeline_runtime_kv WHERE key = %s",
            (key,),
        )
        row = cur.fetchone()
        value = _row_get(row, "value", 0)
        if value is None:
            return False
        v = value
        if isinstance(v, dict):
            return bool(v.get("paused"))
        return False
    finally:
        _release(conn)


def set_pause(step_id: str, paused: bool) -> None:
    key = _pause_key(step_id)
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO pipeline_runtime_kv (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = NOW()
            """,
            (key, psycopg2.extras.Json({"paused": bool(paused)})),
        )
        conn.commit()
    finally:
        _release(conn)


def set_all_pauses(paused: bool) -> None:
    for step_id, _ in KNOWN_PAUSE_STEPS:
        set_pause(step_id, paused)
    logger.info("pipeline_runtime_kv: set_all_pauses(%s) for %d steps", paused, len(KNOWN_PAUSE_STEPS))


def get_insights_llm() -> Dict[str, Any]:
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT value FROM pipeline_runtime_kv WHERE key = %s",
            (INSIGHTS_LLM_KEY,),
        )
        row = cur.fetchone()
        value = _row_get(row, "value", 0)
        if not value:
            return dict(_DEFAULT_LLM)
        v = value
        if not isinstance(v, dict):
            return dict(_DEFAULT_LLM)
        mode = v.get("mode") if v.get("mode") in ("auto", "manual") else "auto"
        order = v.get("order")
        if not isinstance(order, list):
            order = list(_DEFAULT_LLM["order"])
        om = _norm_ollama_model(v.get("ollama_model"))
        out = {"mode": mode, "order": order}
        if om:
            out["ollama_model"] = om
        return out
    finally:
        _release(conn)


def write_insights_llm(
    *,
    mode: Optional[str] = None,
    order: Optional[List[str]] = None,
    ollama_model: Any = _UNSET,
) -> None:
    """Merge-write insights.llm JSON. Use ollama_model=_UNSET to leave unchanged."""
    cur = get_insights_llm()
    m = mode if mode is not None else cur["mode"]
    o = order if order is not None else cur["order"]
    if m not in ("auto", "manual"):
        raise ValueError("mode must be auto or manual")
    if ollama_model is _UNSET:
        om = _norm_ollama_model(cur.get("ollama_model"))
    elif ollama_model is None or ollama_model == "":
        om = None
    else:
        om = _norm_ollama_model(ollama_model)
    payload: Dict[str, Any] = {"mode": m, "order": o}
    if om:
        payload["ollama_model"] = om
    conn = _conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO pipeline_runtime_kv (key, value, updated_at)
            VALUES (%s, %s, NOW())
            ON CONFLICT (key) DO UPDATE SET
                value = EXCLUDED.value,
                updated_at = NOW()
            """,
            (INSIGHTS_LLM_KEY, psycopg2.extras.Json(payload)),
        )
        conn.commit()
    finally:
        _release(conn)


def set_insights_llm(mode: str, order: List[str]) -> None:
    """Backward-compatible: replace mode/order, preserve ollama_model in DB."""
    write_insights_llm(mode=mode, order=order, ollama_model=_UNSET)


def load_full_snapshot() -> Dict[str, Any]:
    """Read all pipeline_runtime rows relevant to UI / cache (single round-trip)."""
    conn = _conn()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT key, value FROM pipeline_runtime_kv
            WHERE key LIKE %s OR key = %s
            """,
            ("pause.%", INSIGHTS_LLM_KEY),
        )
        rows = cur.fetchall()
    finally:
        _release(conn)

    by_key: Dict[str, Any] = {}
    for r in rows:
        k = _row_get(r, "key", 0)
        v = _row_get(r, "value", 1)
        if k:
            by_key[k] = v
    pause_steps = []
    for step_id, label in KNOWN_PAUSE_STEPS:
        pk = _pause_key(step_id)
        raw = by_key.get(pk)
        paused = bool(raw.get("paused")) if isinstance(raw, dict) else False
        pause_steps.append({"id": step_id, "label": label, "paused": paused})

    llm_raw = by_key.get(INSIGHTS_LLM_KEY)
    if isinstance(llm_raw, dict) and llm_raw.get("mode") in ("auto", "manual"):
        om = _norm_ollama_model(llm_raw.get("ollama_model"))
        llm = {
            "mode": llm_raw["mode"],
            "order": llm_raw.get("order")
            if isinstance(llm_raw.get("order"), list)
            else list(_DEFAULT_LLM["order"]),
        }
        if om:
            llm["ollama_model"] = om
    else:
        llm = dict(_DEFAULT_LLM)

    return {"pause_steps": pause_steps, "insights_llm": llm}
