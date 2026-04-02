"""
Pydantic models for Admin API (insights pipeline runtime controls).

Backup request bodies live in `backup_models`.
"""

from typing import Dict, List, Optional

from pydantic import BaseModel


class InsightsPipelineUpdate(BaseModel):
    """Partial update for pipeline runtime controls (admin); persisted in pipeline_runtime_kv."""

    pause_generation: Optional[bool] = None
    pause_indexing_insights: Optional[bool] = None
    pause_steps: Optional[Dict[str, bool]] = None
    pause_all: Optional[bool] = None
    resume_all: Optional[bool] = None
    provider_mode: Optional[str] = None
    provider_order: Optional[List[str]] = None
    ollama_model: Optional[str] = None  # empty/null clears override (use env / default)
