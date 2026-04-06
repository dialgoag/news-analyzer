#!/usr/bin/env python3
"""
Sanity check for upload symlinks vs DB filenames.

Default mode is read-only (report only).

What it checks:
1) Symlink in uploads/{document_id}.pdf points to an existing file.
2) document_status.filename matches the basename referenced by the symlink target
   (ignoring the 8-char hash prefix in processed files).
3) For broken symlinks, suggest a deterministic candidate based on document_id prefix.

Optional fix flags:
- --apply-symlink-fix: repoint broken symlinks when there is exactly one deterministic candidate.
- --apply-db-filename-fix: normalize filename in document_status/processing_queue/
  document_stage_timing(metadata.filename) to match resolved symlink basename.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import psycopg2
from psycopg2.extras import RealDictCursor


HEX64_RE = re.compile(r"^[0-9a-f]{64}$")
HASH_PREFIX_RE = re.compile(r"^[0-9a-f]{8}_(.+)$")


@dataclass
class DocRow:
    document_id: str
    filename: str
    source: Optional[str]
    status: Optional[str]
    processing_stage: Optional[str]


@dataclass
class Finding:
    document_id: str
    kind: str
    detail: str


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


def _strip_hash_prefix(basename: str) -> str:
    m = HASH_PREFIX_RE.match(basename)
    if not m:
        return basename
    return m.group(1)


def _map_container_to_local(path: str, local_data_root: Optional[str]) -> str:
    if not local_data_root:
        return path
    root = os.path.abspath(local_data_root)
    if path.startswith("/app/uploads/"):
        return os.path.join(root, "uploads", path[len("/app/uploads/") :])
    if path.startswith("/app/inbox/processed/"):
        return os.path.join(root, "inbox", "processed", path[len("/app/inbox/processed/") :])
    if path.startswith("/app/inbox/"):
        return os.path.join(root, "inbox", path[len("/app/inbox/") :])
    return path


def _preferred_symlink_target(processed_basename: str, use_container_paths: bool, processed_dir: str) -> str:
    if use_container_paths:
        return f"/app/inbox/processed/{processed_basename}"
    return os.path.join(processed_dir, processed_basename)


def _fetch_documents(conn, document_ids: List[str]) -> Dict[str, DocRow]:
    if not document_ids:
        return {}
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(
            """
            SELECT document_id, filename, source, status, processing_stage
            FROM document_status
            WHERE document_id = ANY(%s)
            """,
            (document_ids,),
        )
        rows = cur.fetchall()
    return {
        r["document_id"]: DocRow(
            document_id=r["document_id"],
            filename=r.get("filename") or "",
            source=r.get("source"),
            status=r.get("status"),
            processing_stage=r.get("processing_stage"),
        )
        for r in rows
    }


def _update_db_filename(conn, document_id: str, normalized_filename: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE document_status
            SET filename = %s, updated_at = NOW()
            WHERE document_id = %s
            """,
            (normalized_filename, document_id),
        )
        cur.execute(
            """
            UPDATE processing_queue
            SET filename = %s
            WHERE document_id = %s
            """,
            (normalized_filename, document_id),
        )
        cur.execute(
            """
            UPDATE document_stage_timing
            SET metadata =
                CASE
                    WHEN metadata IS NULL THEN jsonb_build_object('filename', %s)
                    ELSE jsonb_set(metadata, '{filename}', to_jsonb(%s::text), true)
                END,
                updated_at = NOW()
            WHERE document_id = %s
              AND (metadata ? 'filename' OR stage = 'ocr')
            """,
            (normalized_filename, normalized_filename, document_id),
        )
    conn.commit()


def _candidate_by_prefix(processed_dir: str, document_id: str) -> List[str]:
    short = document_id[:8]
    try:
        entries = os.listdir(processed_dir)
    except FileNotFoundError:
        return []
    return sorted([e for e in entries if e.startswith(f"{short}_") and os.path.isfile(os.path.join(processed_dir, e))])


def run_check(
    dsn: str,
    uploads_dir: str,
    processed_dir: str,
    local_data_root: Optional[str],
    use_container_paths: bool,
    apply_symlink_fix: bool,
    apply_db_filename_fix: bool,
) -> int:
    uploads_local = _map_container_to_local(uploads_dir, local_data_root)
    processed_local = _map_container_to_local(processed_dir, local_data_root)

    if not os.path.isdir(uploads_local):
        print(f"ERROR: uploads dir not found: {uploads_local}")
        return 2
    if not os.path.isdir(processed_local):
        print(f"ERROR: processed dir not found: {processed_local}")
        return 2

    symlink_entries: List[Tuple[str, str]] = []
    for name in sorted(os.listdir(uploads_local)):
        link_path = os.path.join(uploads_local, name)
        if not os.path.islink(link_path):
            continue
        doc_id = name[:-4] if name.endswith(".pdf") else name
        if not HEX64_RE.match(doc_id):
            continue
        symlink_entries.append((doc_id, link_path))

    conn = psycopg2.connect(dsn)
    try:
        doc_map = _fetch_documents(conn, [doc_id for doc_id, _ in symlink_entries])
        findings: List[Finding] = []
        fixed_symlinks = 0
        fixed_db_names = 0

        for doc_id, link_path in symlink_entries:
            if doc_id not in doc_map:
                findings.append(Finding(doc_id, "MISSING_DB_RECORD", "symlink exists but document_status row missing"))
                continue

            doc = doc_map[doc_id]
            target_raw = os.readlink(link_path)
            target_local = _map_container_to_local(target_raw, local_data_root)
            target_exists = os.path.isfile(target_local)
            target_base = os.path.basename(target_raw)
            normalized_target_name = _strip_hash_prefix(target_base)

            if not target_exists:
                candidates = _candidate_by_prefix(processed_local, doc_id)
                if len(candidates) == 1:
                    findings.append(
                        Finding(
                            doc_id,
                            "BROKEN_SYMLINK_WITH_UNIQUE_CANDIDATE",
                            f"target={target_raw} -> candidate={candidates[0]}",
                        )
                    )
                    if apply_symlink_fix:
                        new_target = _preferred_symlink_target(candidates[0], use_container_paths, processed_dir)
                        os.unlink(link_path)
                        os.symlink(new_target, link_path)
                        fixed_symlinks += 1
                        target_raw = new_target
                        target_base = os.path.basename(target_raw)
                        normalized_target_name = _strip_hash_prefix(target_base)
                        target_local = _map_container_to_local(target_raw, local_data_root)
                        target_exists = os.path.isfile(target_local)
                else:
                    findings.append(
                        Finding(
                            doc_id,
                            "BROKEN_SYMLINK",
                            f"target={target_raw}; candidates={len(candidates)}",
                        )
                    )

            if target_exists and doc.filename != normalized_target_name:
                findings.append(
                    Finding(
                        doc_id,
                        "DB_FILENAME_MISMATCH",
                        f"db={doc.filename} vs target={normalized_target_name}",
                    )
                )
                if apply_db_filename_fix:
                    _update_db_filename(conn, doc_id, normalized_target_name)
                    fixed_db_names += 1

        by_kind: Dict[str, int] = {}
        for f in findings:
            by_kind[f.kind] = by_kind.get(f.kind, 0) + 1

        summary = {
            "symlinks_scanned": len(symlink_entries),
            "findings_total": len(findings),
            "findings_by_kind": by_kind,
            "fixed_symlinks": fixed_symlinks,
            "fixed_db_filenames": fixed_db_names,
            "apply_symlink_fix": apply_symlink_fix,
            "apply_db_filename_fix": apply_db_filename_fix,
        }
        print(json.dumps(summary, ensure_ascii=True, indent=2))
        for f in findings:
            print(f"- {f.kind} | {f.document_id} | {f.detail}")

        return 1 if findings else 0
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Check upload symlink and DB filename consistency.")
    parser.add_argument("--dsn", default=_default_dsn(), help="Database DSN or URL.")
    parser.add_argument("--uploads-dir", default="/app/uploads", help="Uploads directory path.")
    parser.add_argument("--processed-dir", default="/app/inbox/processed", help="Processed directory path.")
    parser.add_argument(
        "--local-data-root",
        default=None,
        help="Host local-data path for mapping /app/* paths (e.g. ./app/local-data).",
    )
    parser.add_argument(
        "--use-container-paths",
        action="store_true",
        help="When fixing symlinks, write /app/inbox/processed/... targets (recommended in Docker).",
    )
    parser.add_argument("--apply-symlink-fix", action="store_true", help="Apply safe symlink fixes.")
    parser.add_argument("--apply-db-filename-fix", action="store_true", help="Apply DB filename normalization.")

    args = parser.parse_args()
    exit_code = run_check(
        dsn=args.dsn,
        uploads_dir=args.uploads_dir,
        processed_dir=args.processed_dir,
        local_data_root=args.local_data_root,
        use_container_paths=args.use_container_paths,
        apply_symlink_fix=args.apply_symlink_fix,
        apply_db_filename_fix=args.apply_db_filename_fix,
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
