"""Weekly report helper."""

from __future__ import annotations


def weekly_summary(connection) -> dict[str, int]:
    hands = connection.execute("SELECT COUNT(*) FROM hands").fetchone()[0]
    exports = connection.execute("SELECT COUNT(*) FROM gtowizard_exports").fetchone()[0]
    return {"hands": int(hands), "gtowizard_exports": int(exports)}

