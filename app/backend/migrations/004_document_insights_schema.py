"""
Migration 004: Create document insights schema

Domain: LLM Insights & AI-Generated Content
Description: Tables for storing LLM-generated insights with deduplication support
Depends on: 002_document_status_schema
"""

from yoyo import step

steps = [
    step(
        # Document insights - LLM generated insights per document
        """
        CREATE TABLE IF NOT EXISTS document_insights (
            document_id VARCHAR(255) PRIMARY KEY,
            filename TEXT NOT NULL,
            status VARCHAR(50) NOT NULL,
            content TEXT,
            error_message TEXT,
            content_hash VARCHAR(64),
            created_at TIMESTAMP NOT NULL,
            updated_at TIMESTAMP
        )
        """,
        "DROP TABLE IF EXISTS document_insights"
    ),
    step(
        "CREATE INDEX idx_document_insights_status ON document_insights(status)",
        "DROP INDEX IF EXISTS idx_document_insights_status"
    ),
    step(
        "CREATE INDEX idx_document_insights_hash_status ON document_insights(content_hash, status)",
        "DROP INDEX IF EXISTS idx_document_insights_hash_status"
    ),
]
