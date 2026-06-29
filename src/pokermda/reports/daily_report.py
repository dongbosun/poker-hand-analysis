"""Daily report helper."""

from __future__ import annotations


def daily_summary(connection) -> dict[str, int]:
    hands = connection.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
    queued = connection.execute("SELECT COUNT(*) FROM study_queue WHERE status = 'queued'").fetchone()[0]
    return {"hands": int(hands), "queued": int(queued)}

