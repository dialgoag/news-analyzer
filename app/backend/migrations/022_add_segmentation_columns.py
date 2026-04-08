"""
Add segmentation confidence columns

Adds columns to track LLM-based segmentation quality:
- news_items.segmentation_confidence: Confidence score for each article (0.0-1.0)
- document_status.segmentation_items_count: Number of articles detected
- document_status.segmentation_avg_confidence: Average confidence across all articles

Migration: 022_add_segmentation_columns.py
"""

from yoyo import step

__depends__ = ['021_add_retry_count_to_news_item_insights']

steps = [
    step(
        """
        ALTER TABLE news_items 
        ADD COLUMN IF NOT EXISTS segmentation_confidence FLOAT;
        """,
        """
        ALTER TABLE news_items 
        DROP COLUMN IF EXISTS segmentation_confidence;
        """
    ),
    step(
        """
        ALTER TABLE document_status 
        ADD COLUMN IF NOT EXISTS segmentation_items_count INT;
        """,
        """
        ALTER TABLE document_status 
        DROP COLUMN IF EXISTS segmentation_items_count;
        """
    ),
    step(
        """
        ALTER TABLE document_status 
        ADD COLUMN IF NOT EXISTS segmentation_avg_confidence FLOAT;
        """,
        """
        ALTER TABLE document_status 
        DROP COLUMN IF EXISTS segmentation_avg_confidence;
        """
    ),
]
