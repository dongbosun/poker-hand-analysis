"""Insert hand actions."""

from __future__ import annotations

from pokermda.model.action import Action
from pokermda.utils.hashing import stable_id


def insert_actions(connection, hand_id: str, actions: list[Action]) -> int:
    inserted = 0
    for action in actions:
        action_id = stable_id("action", hand_id, action.sequence_no, action.raw_line)
        exists = connection.execute(
            "SELECT 1 FROM actions WHERE action_id = ?",
            [action_id],
        ).fetchone()
        if exists:
            continue
        connection.execute(
            """
            INSERT INTO actions (
                action_id, hand_id, street, sequence_no, actor,
                action_type, amount, raise_to, raw_line
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                action_id,
                hand_id,
                str(action.street),
                action.sequence_no,
                action.actor,
                str(action.action_type),
                action.amount,
                action.raise_to,
                action.raw_line,
            ],
        )
        inserted += 1
    return inserted

