"""
Migration 014: Add indexed_in_qdrant_at to news_item_insights

Tracks when each insight was vectorized and inserted into Qdrant.
NULL = pending indexing; NOT NULL = indexed.
"""

from yoyo import step

steps = [
    step(
        """
        ALTER TABLE news_item_insights
        ADD COLUMN IF NOT EXISTS indexed_in_qdrant_at TIMESTAMP
        """,
        """
        ALTER TABLE news_item_insights DROP COLUMN IF EXISTS indexed_in_qdrant_at
        """
    ),
]
