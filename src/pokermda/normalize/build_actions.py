"""Insert hand actions."""

from __future__ import annotations

from pokermda.model.action import Action
from pokermda.utils.hashing import stable_id


def insert_actions(connection, hand_id: str, actions: list[Action]) -> int:
    inserted = 0
    participants = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT player_name_raw, participant_id FROM participants WHERE hand_id = ?",
            [hand_id],
        ).fetchall()
    }
    street_counts: dict[str, int] = {}
    for action in actions:
        action_id = stable_id("action", hand_id, action.sequence_no, action.raw_line)
        exists = connection.execute(
            "SELECT 1 FROM actions WHERE action_id = ?",
            [action_id],
        ).fetchone()
        if exists:
            continue
        street = str(action.street)
        street_counts[street] = street_counts.get(street, 0) + 1
        participant_id = participants.get(action.actor or "")
        connection.execute(
            """
            INSERT INTO actions (
                action_id, hand_id, participant_id, street,
                action_no_global, action_no_street, action_type,
                amount_bb, is_allin, raw_action_text,
                sequence_no, actor, amount, raise_to, raw_line
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                action_id,
                hand_id,
                participant_id,
                street,
                action.sequence_no,
                street_counts[street],
                str(action.action_type),
                action.amount,
                str(action.action_type) == "all_in",
                action.raw_line,
                action.sequence_no,
                action.actor,
                action.amount,
                action.raise_to,
                action.raw_line,
            ],
        )
        inserted += 1
    return inserted
