"""
Migration 002: Create document processing schema

Domain: Document Processing & Status Tracking
Description: Tables for tracking document ingestion, OCR, and processing status
Depends on: 001_authentication_schema
"""

from yoyo import step

steps = [
    step(
        # Document status table - tracks processing pipeline
        """
        CREATE TABLE IF NOT EXISTS document_status (
            id SERIAL PRIMARY KEY,
            document_id VARCHAR(255) UNIQUE NOT NULL,
            filename TEXT NOT NULL,
            source TEXT NOT NULL,
            status VARCHAR(50) NOT NULL,
            ingested_at TIMESTAMP NOT NULL,
            indexed_at TIMESTAMP,
            error_message TEXT,
            num_chunks INTEGER,
            news_date TIMESTAMP,
            processing_stage VARCHAR(50),
            ocr_text TEXT,
            reprocess_requested INTEGER DEFAULT 0,
            doc_type VARCHAR(50) DEFAULT 'unknown',
            file_hash VARCHAR(64)
        )
        """,
        "DROP TABLE IF EXISTS document_status"
    ),
    step(
        "CREATE INDEX idx_document_status_status ON document_status(status)",
        "DROP INDEX IF EXISTS idx_document_status_status"
    ),
    step(
        "CREATE INDEX idx_document_status_ingested ON document_status(ingested_at)",
        "DROP INDEX IF EXISTS idx_document_status_ingested"
    ),
    step(
        "CREATE INDEX idx_document_status_news_date ON document_status(news_date)",
        "DROP INDEX IF EXISTS idx_document_status_news_date"
    ),
    step(
        "CREATE INDEX idx_document_status_reprocess ON document_status(reprocess_requested)",
        "DROP INDEX IF EXISTS idx_document_status_reprocess"
    ),
    step(
        "CREATE INDEX idx_document_status_file_hash ON document_status(file_hash)",
        "DROP INDEX IF EXISTS idx_document_status_file_hash"
    ),
]
