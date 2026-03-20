"""
Migration 013: Add llm_source to news_item_insights

Records which LLM provider generated each insight (openai, perplexity, ollama).
"""

from yoyo import step

steps = [
    step(
        """
        ALTER TABLE news_item_insights
        ADD COLUMN IF NOT EXISTS llm_source VARCHAR(50)
        """,
        """
        ALTER TABLE news_item_insights DROP COLUMN IF EXISTS llm_source
        """
    ),
]
