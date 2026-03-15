"""
Migration 005: Create news items schema

Domain: News & Content Extraction
Description: Tables for storing individual news items extracted from documents
Depends on: 002_document_status_schema, 004_document_insights_schema
"""

from yoyo import step

steps = [
    step(
        # News items - individual news items within a document
        """
        CREATE TABLE IF NOT EXISTS news_items (
            news_item_id VARCHAR(255) PRIMARY KEY,
            document_id VARCHAR(255) NOT NULL,
            filename TEXT NOT NULL,
            item_index INTEGER NOT NULL,
            title TEXT,
            status VARCHAR(50) NOT NULL,
            text_hash VARCHAR(64),
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP
        )
        """,
        "DROP TABLE IF EXISTS news_items"
    ),
    step(
        "CREATE INDEX idx_news_items_document ON news_items(document_id, item_index)",
        "DROP INDEX IF EXISTS idx_news_items_document"
    ),
    step(
        "CREATE INDEX idx_news_items_text_hash ON news_items(text_hash)",
        "DROP INDEX IF EXISTS idx_news_items_text_hash"
    ),
    step(
        # News item insights - LLM insights per news item
        """
        CREATE TABLE IF NOT EXISTS news_item_insights (
            news_item_id VARCHAR(255) PRIMARY KEY,
            document_id VARCHAR(255) NOT NULL,
            filename TEXT NOT NULL,
            item_index INTEGER NOT NULL,
            title TEXT,
            status VARCHAR(50) NOT NULL,
            content TEXT,
            error_message TEXT,
            text_hash VARCHAR(64),
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP
        )
        """,
        "DROP TABLE IF EXISTS news_item_insights"
    ),
    step(
        "CREATE INDEX idx_news_item_insights_doc_status ON news_item_insights(document_id, status)",
        "DROP INDEX IF EXISTS idx_news_item_insights_doc_status"
    ),
    step(
        "CREATE INDEX idx_news_item_insights_text_hash_status ON news_item_insights(text_hash, status)",
        "DROP INDEX IF EXISTS idx_news_item_insights_text_hash_status"
    ),
]
