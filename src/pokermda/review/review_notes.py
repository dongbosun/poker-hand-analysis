"""Review note helpers."""

from __future__ import annotations

from pokermda.utils.hashing import stable_id


def add_review_note(connection, hand_id: str | None, export_id: str | None, note_text: str, tags: str | None = None) -> str:
    note_id = stable_id("note", hand_id, export_id, note_text)
    connection.execute(
        """
        INSERT INTO review_notes (note_id, hand_id, export_id, note_text, tags)
        VALUES (?, ?, ?, ?, ?)
        """,
        [note_id, hand_id, export_id, note_text, tags],
    )
    return note_id

