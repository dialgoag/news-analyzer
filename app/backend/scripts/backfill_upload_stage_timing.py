"""
Backfill script for document_stage_timing (stage='upload').

Usage:
    python backfill_upload_stage_timing.py --limit 1000
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, List, Optional, Sequence, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor

logger = logging.getLogger("backfill_upload_stage_timing")


def _default_dsn() -> str:
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    host = os.getenv("POSTGRES_HOST", "localhost")
    port = os.getenv("POSTGRES_PORT", "5432")
    db = os.getenv("POSTGRES_DB", "news_analyzer")
    user = os.getenv("POSTGRES_USER", "postgres")
    password = os.getenv("POSTGRES_PASSWORD", "postgres")
    return f"host={host} port={port} dbname={db} user={user} password={password}"


def determine_upload_stage_status(document_status: str) -> str:
    """
    Map document_status.status to upload stage timing status.

    Returns one of: pending, processing, done, error.
    """
    if not document_status:
        return "done"
    status = document_status.lower()
    if status.startswith("upload_"):
        suffix = status.split("_", 1)[1]
        if suffix in {"pending", "processing", "done"}:
            return suffix
    if status == "error":
        return "error"
    return "done"


@dataclass
class BackfillRecord:
    document_id: str
    status: str
    created_at: datetime
    updated_at: datetime
    metadata_json: str


def build_backfill_record(row: dict, *, reference_time: Optional[datetime] = None) -> BackfillRecord:
    """Create a BackfillRecord from a document_status row."""
    reference = reference_time or datetime.utcnow()
    created_at = row.get("ingested_at") or row.get("created_at") or reference
    if isinstance(created_at, str):
        created_at = datetime.fromisoformat(created_at)

    stage_status = determine_upload_stage_status(row.get("status") or "")

    updated_source = row.get("ingested_at") or row.get("updated_at") or created_at
    if isinstance(updated_source, str):
        updated_source = datetime.fromisoformat(updated_source)

    if stage_status in {"pending", "processing", "error"}:
        updated_at = created_at
    else:
        updated_at = updated_source

    metadata = {
        "backfill": "upload_stage",
        "document_status_at_insert": row.get("status"),
    }

    return BackfillRecord(
        document_id=row["document_id"],
        status=stage_status,
        created_at=created_at,
        updated_at=updated_at,
        metadata_json=json.dumps(metadata),
    )


def fetch_documents_missing_upload_stage(
    conn,
    batch_size: int,
) -> List[dict]:
    """Fetch a batch of documents without upload stage timing entries."""
    with conn.cursor(cursor_factory=RealDictCursor) as cursor:
        cursor.execute(
            """
            SELECT document_id, status, ingested_at, created_at, updated_at
            FROM document_status ds
            WHERE NOT EXISTS (
                SELECT 1 FROM document_stage_timing dst
                WHERE dst.document_id = ds.document_id
                  AND dst.stage = 'upload'
                  AND dst.news_item_id IS NULL
            )
            ORDER BY ds.ingested_at NULLS LAST, ds.created_at
            LIMIT %s
            """,
            (batch_size,),
        )
        return list(cursor.fetchall())


def insert_stage_timing_rows(conn, records: Sequence[BackfillRecord]) -> int:
    if not records:
        return 0
    with conn.cursor() as cursor:
        cursor.executemany(
            """
            INSERT INTO document_stage_timing
            (document_id, news_item_id, stage, status, created_at, updated_at, metadata)
            VALUES (%s, NULL, 'upload', %s, %s, %s, %s::jsonb)
            ON CONFLICT (document_id, COALESCE(news_item_id, ''), stage) DO NOTHING
            """,
            [
                (
                    record.document_id,
                    record.status,
                    record.created_at,
                    record.updated_at,
                    record.metadata_json,
                )
                for record in records
            ],
        )
    conn.commit()
    return len(records)


def backfill_upload_stage_timing(
    conn,
    *,
    batch_size: int = 500,
    limit: Optional[int] = None,
    dry_run: bool = False,
) -> int:
    """Perform the backfill. Returns number of rows inserted (or would insert)."""
    processed = 0
    remaining = limit
    while True:
        current_batch = batch_size
        if remaining is not None:
            current_batch = min(current_batch, remaining)
            if current_batch <= 0:
                break
        rows = fetch_documents_missing_upload_stage(conn, current_batch)
        if not rows:
            break
        records = [build_backfill_record(row) for row in rows]
        if dry_run:
            processed += len(records)
        else:
            inserted = insert_stage_timing_rows(conn, records)
            processed += inserted
        if remaining is not None:
            remaining -= len(records)
    return processed


def main():
    parser = argparse.ArgumentParser(description="Backfill upload stage timing entries.")
    parser.add_argument("--dsn", default=_default_dsn(), help="Database DSN or URL.")
    parser.add_argument("--batch-size", type=int, default=500, help="Batch size per query.")
    parser.add_argument("--limit", type=int, default=None, help="Optional max rows to backfill.")
    parser.add_argument("--dry-run", action="store_true", help="Only count rows without inserting.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    conn = psycopg2.connect(args.dsn)
    try:
        count = backfill_upload_stage_timing(
            conn,
            batch_size=args.batch_size,
            limit=args.limit,
            dry_run=args.dry_run,
        )
        if args.dry_run:
            logger.info("Dry run: %s rows would be inserted.", count)
        else:
            logger.info("Inserted %s upload stage timing rows.", count)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
