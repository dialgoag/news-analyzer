"""
Migration 019: Standardize news_item_insights.status to prefixed canon.

Old values:
- pending, queued, generating, indexing, done, error

New values:
- insights_pending, insights_queued, insights_generating,
  insights_indexing, insights_done, insights_error
"""

from yoyo import step


steps = [
    step(
        """
        UPDATE news_item_insights
        SET status = CASE status
            WHEN 'pending' THEN 'insights_pending'
            WHEN 'queued' THEN 'insights_queued'
            WHEN 'generating' THEN 'insights_generating'
            WHEN 'indexing' THEN 'insights_indexing'
            WHEN 'done' THEN 'insights_done'
            WHEN 'error' THEN 'insights_error'
            ELSE status
        END
        WHERE status IN ('pending', 'queued', 'generating', 'indexing', 'done', 'error')
        """,
        """
        UPDATE news_item_insights
        SET status = CASE status
            WHEN 'insights_pending' THEN 'pending'
            WHEN 'insights_queued' THEN 'queued'
            WHEN 'insights_generating' THEN 'generating'
            WHEN 'insights_indexing' THEN 'indexing'
            WHEN 'insights_done' THEN 'done'
            WHEN 'insights_error' THEN 'error'
            ELSE status
        END
        WHERE status IN (
            'insights_pending', 'insights_queued', 'insights_generating',
            'insights_indexing', 'insights_done', 'insights_error'
        )
        """,
    ),
]
