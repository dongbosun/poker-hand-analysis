"""Node query helpers."""

from __future__ import annotations


def list_node_instances(connection, limit: int = 20) -> list[tuple]:
    return connection.execute(
        """
        SELECT node_instance_id, node_id, hand_id, player_name, street, created_at
        FROM node_instances
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

