"""MVP placeholder for player hand fact generation."""

from __future__ import annotations


def rebuild_player_hand_facts(connection) -> int:
    """Populate derived per-player facts.

    The MVP leaves advanced poker logic for later. Returning zero keeps the CLI
    contract stable while the schema and module boundary are already present.
    """
    _ = connection
    return 0

