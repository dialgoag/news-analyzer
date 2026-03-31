"""
Migration 016: Key-value store for pipeline runtime controls (persistent pauses, LLM prefs).

Extensible: new pause.* or config keys without schema churn.
"""

from yoyo import step

steps = [
    step(
        """
        CREATE TABLE IF NOT EXISTS pipeline_runtime_kv (
            key VARCHAR(160) PRIMARY KEY,
            value JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        DROP TABLE IF EXISTS pipeline_runtime_kv
        """
    ),
    step(
        """
        CREATE INDEX IF NOT EXISTS idx_pipeline_runtime_kv_updated
        ON pipeline_runtime_kv (updated_at DESC)
        """,
        """
        DROP INDEX IF EXISTS idx_pipeline_runtime_kv_updated
        """
    ),
]
