"""
Migration 003: Create event-driven processing schema

Domain: Event-Driven Architecture & Task Management
Description: Tables for semaphore-based worker task management and processing queues
Depends on: 002_document_status_schema
"""

from yoyo import step

steps = [
    step(
        # Worker tasks table - semaphore for preventing duplicate processing
        """
        CREATE TABLE IF NOT EXISTS worker_tasks (
            id SERIAL PRIMARY KEY,
            worker_id VARCHAR(255) NOT NULL,
            worker_type VARCHAR(50) NOT NULL,
            document_id VARCHAR(255) NOT NULL,
            task_type VARCHAR(50) NOT NULL,
            status VARCHAR(50) NOT NULL,
            assigned_at TIMESTAMP NOT NULL,
            started_at TIMESTAMP,
            completed_at TIMESTAMP,
            error_message TEXT,
            UNIQUE(worker_id, document_id, task_type)
        )
        """,
        "DROP TABLE IF EXISTS worker_tasks"
    ),
    step(
        "CREATE INDEX idx_worker_tasks_status ON worker_tasks(status)",
        "DROP INDEX IF EXISTS idx_worker_tasks_status"
    ),
    step(
        "CREATE INDEX idx_worker_tasks_worker ON worker_tasks(worker_id, status)",
        "DROP INDEX IF EXISTS idx_worker_tasks_worker"
    ),
    step(
        "CREATE INDEX idx_worker_tasks_document ON worker_tasks(document_id, task_type)",
        "DROP INDEX IF EXISTS idx_worker_tasks_document"
    ),
    step(
        # Processing queue - event-driven task queue
        """
        CREATE TABLE IF NOT EXISTS processing_queue (
            id SERIAL PRIMARY KEY,
            document_id VARCHAR(255) NOT NULL,
            filename TEXT NOT NULL,
            task_type VARCHAR(50) NOT NULL,
            priority INTEGER DEFAULT 0,
            created_at TIMESTAMP NOT NULL,
            processed_at TIMESTAMP,
            status VARCHAR(50) NOT NULL,
            UNIQUE(document_id, task_type)
        )
        """,
        "DROP TABLE IF EXISTS processing_queue"
    ),
    step(
        "CREATE INDEX idx_processing_queue_status ON processing_queue(status, priority DESC)",
        "DROP INDEX IF EXISTS idx_processing_queue_status"
    ),
    step(
        "CREATE INDEX idx_processing_queue_document ON processing_queue(document_id)",
        "DROP INDEX IF EXISTS idx_processing_queue_document"
    ),
]
