from datetime import datetime
from unittest.mock import Mock
import sys

# Mock psycopg2 dependencies before importing the script module
psycopg2_mock = Mock()
psycopg2_extras_mock = Mock()
psycopg2_mock.extras = psycopg2_extras_mock
sys.modules.setdefault("psycopg2", psycopg2_mock)
sys.modules.setdefault("psycopg2.extras", psycopg2_extras_mock)

from scripts.backfill_upload_stage_timing import (  # noqa: E402
    BackfillRecord,
    build_backfill_record,
    determine_upload_stage_status,
)


def test_determine_upload_stage_status_variants():
    assert determine_upload_stage_status("upload_pending") == "pending"
    assert determine_upload_stage_status("upload_processing") == "processing"
    assert determine_upload_stage_status("upload_done") == "done"
    assert determine_upload_stage_status("ocr_pending") == "done"
    assert determine_upload_stage_status("completed") == "done"
    assert determine_upload_stage_status("error") == "error"
    assert determine_upload_stage_status(None) == "done"


def test_build_backfill_record_defaults_done():
    base_time = datetime(2026, 3, 1, 12, 0, 0)
    row = {
        "document_id": "doc-123",
        "status": "indexing_done",
        "ingested_at": base_time,
        "created_at": base_time,
        "updated_at": base_time,
    }
    record = build_backfill_record(row, reference_time=base_time)
    assert isinstance(record, BackfillRecord)
    assert record.document_id == "doc-123"
    assert record.status == "done"
    assert record.created_at == base_time
    assert record.updated_at == base_time
    assert "indexing_done" in record.metadata_json


def test_build_backfill_record_pending_uses_created_time():
    base_time = datetime(2026, 3, 1, 12, 0, 0)
    later = datetime(2026, 3, 2, 12, 0, 0)
    row = {
        "document_id": "doc-456",
        "status": "upload_pending",
        "ingested_at": base_time,
        "created_at": base_time,
        "updated_at": later,
    }
    record = build_backfill_record(row, reference_time=later)
    assert record.status == "pending"
    assert record.created_at == base_time
    # For pending, updated_at should equal created_at (stage still open)
    assert record.updated_at == base_time


def test_build_backfill_record_error_status():
    now = datetime(2026, 3, 3, 10, 0, 0)
    row = {
        "document_id": "doc-error",
        "status": "error",
        "ingested_at": None,
        "created_at": None,
        "updated_at": None,
    }
    record = build_backfill_record(row, reference_time=now)
    assert record.status == "error"
    assert record.created_at == now
    assert record.updated_at == now
