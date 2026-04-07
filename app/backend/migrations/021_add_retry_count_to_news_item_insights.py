"""
Add retry_count column to news_item_insights table

This enables tracking retry attempts for insights that fail due to LLM refusals
or other errors, preventing infinite retry loops.
"""
from yoyo import step

__depends__ = {'020_add_retry_count_to_news_items'}

steps = [
    step(
        # Add retry_count column with default 0
        """
        ALTER TABLE news_item_insights
        ADD COLUMN IF NOT EXISTS retry_count INTEGER NOT NULL DEFAULT 0;
        """,
        # Rollback: remove column
        """
        ALTER TABLE news_item_insights
        DROP COLUMN IF EXISTS retry_count;
        """
    ),
    step(
        # Add index for efficient queries on error status with retry count
        """
        CREATE INDEX IF NOT EXISTS idx_news_item_insights_status_retry
        ON news_item_insights (status, retry_count)
        WHERE status = 'error';
        """,
        # Rollback: drop index
        """
        DROP INDEX IF EXISTS idx_news_item_insights_status_retry;
        """
    ),
]
