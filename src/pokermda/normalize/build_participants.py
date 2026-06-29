"""Insert participants."""

from __future__ import annotations

from pokermda.model.participant import Participant


def insert_participants(connection, hand_id: str, participants: list[Participant]) -> int:
    inserted = 0
    for participant in participants:
        exists = connection.execute(
            "SELECT 1 FROM participants WHERE hand_id = ? AND seat_no = ?",
            [hand_id, participant.seat_no],
        ).fetchone()
        if exists:
            continue
        connection.execute(
            """
            INSERT INTO participants (
                hand_id, seat_no, player_name, stack, is_hero,
                hole_cards, position, net_result
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                hand_id,
                participant.seat_no,
                participant.player_name,
                participant.stack,
                participant.is_hero,
                participant.hole_cards,
                participant.position,
                participant.net_result,
            ],
        )
        inserted += 1
    return inserted

