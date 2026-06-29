"""Time helpers used by ingestion and manifests."""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Return a compact UTC timestamp suitable for metadata fields."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

