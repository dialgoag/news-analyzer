"""Reusable helpers to guard retries/requeues for legacy uploads."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional


LEGACY_SOURCE_CHANNELS = {
    item.strip().lower()
    for item in os.getenv("LEGACY_UPLOAD_CHANNELS", "upload").split(",")
    if item.strip()
}

LEGACY_UPLOAD_MAX_DAYS = int(os.getenv("LEGACY_UPLOAD_MAX_DAYS", "2"))


@dataclass
class LegacyRetryDecision:
    is_legacy: bool
    reason: Optional[str] = None


def _parse_datetime(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            return None
    return None


def evaluate_document(doc: dict) -> LegacyRetryDecision:
    """Return whether the document should be treated as legacy for retries."""
    reasons = []
    source = (doc.get("source") or "").lower()
    if source and source in LEGACY_SOURCE_CHANNELS:
        reasons.append(f"source='{source}'")

    ingested_at = _parse_datetime(doc.get("ingested_at"))
    if ingested_at:
        age_days = (datetime.now(timezone.utc) - ingested_at).days
        if LEGACY_UPLOAD_MAX_DAYS >= 0 and age_days >= LEGACY_UPLOAD_MAX_DAYS:
            reasons.append(f"age={age_days}d>=cutoff({LEGACY_UPLOAD_MAX_DAYS}d)")
    elif doc.get("ingested_at"):
        # Value existed but no parse → treat as legacy for safety
        reasons.append("ingested_at_unparseable")

    if reasons:
        return LegacyRetryDecision(True, ", ".join(reasons))
    return LegacyRetryDecision(False, None)


def legacy_block_detail(decision: LegacyRetryDecision) -> str:
    if not decision.is_legacy:
        return ""
    return f"Legacy ingestion detected ({decision.reason})."
