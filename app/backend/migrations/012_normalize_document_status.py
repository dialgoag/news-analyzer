"""
Migration 012: Normalize document_status.status to DocStatus schema

Domain: Document Processing
Description: One-time data migration. Maps legacy status values to DocStatus.*
             so dashboard and queries use a single schema.
Depends on: 002_document_status_schema

Mappings (legacy -> new):
  pending, queued -> upload_pending
  processing -> ocr_processing
  chunked -> chunking_done
  indexed -> indexing_done
"""

from yoyo import step

steps = [
    step(
        "UPDATE document_status SET status = 'upload_pending' WHERE status IN ('pending', 'queued')",
        "SELECT 1",
    ),
    step(
        "UPDATE document_status SET status = 'ocr_processing' WHERE status = 'processing'",
        "SELECT 1",
    ),
    step(
        "UPDATE document_status SET status = 'chunking_done' WHERE status = 'chunked'",
        "SELECT 1",
    ),
    step(
        "UPDATE document_status SET status = 'indexing_done' WHERE status = 'indexed'",
        "SELECT 1",
    ),
]
