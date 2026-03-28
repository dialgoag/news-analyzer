"""
Migration 015: At most one active worker per (document_id, task_type)

The original UNIQUE(worker_id, document_id, task_type) allowed two different
worker_ids to run the same task for the same document (race on first assign).

Steps:
1. Mark duplicate active rows (keep earliest by assigned_at, id) as error.
2. Add partial unique index on (document_id, task_type) for active statuses.
"""

from yoyo import step

steps = [
    step(
        """
        UPDATE worker_tasks wt
        SET status = 'error',
            completed_at = COALESCE(completed_at, NOW()),
            error_message = 'Duplicate active worker (cleaned by migration 015)'
        WHERE wt.id IN (
            SELECT id FROM (
                SELECT id,
                    ROW_NUMBER() OVER (
                        PARTITION BY document_id, task_type
                        ORDER BY assigned_at NULLS LAST, id
                    ) AS rn
                FROM worker_tasks
                WHERE status IN ('assigned', 'started')
            ) sub
            WHERE sub.rn > 1
        )
        """,
        """
        -- Data cleanup is not reversible; down migration only drops the index.
        SELECT 1
        """
    ),
    step(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_worker_tasks_active_document_task
        ON worker_tasks (document_id, task_type)
        WHERE status IN ('assigned', 'started')
        """,
        """
        DROP INDEX IF EXISTS uq_worker_tasks_active_document_task
        """
    ),
]
