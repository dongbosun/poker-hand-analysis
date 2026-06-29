"""Study queue builders."""

from __future__ import annotations

from pokermda.review.hand_scorer import score_hand
from pokermda.utils.hashing import stable_id


def build_study_queue(connection, limit: int = 50) -> int:
    rows = connection.execute(
        """
        SELECT h.hand_id, h.board, COUNT(a.action_id) AS action_count
        FROM hands h
        LEFT JOIN actions a ON h.hand_id = a.hand_id
        LEFT JOIN study_queue q ON h.hand_id = q.hand_id
        WHERE q.hand_id IS NULL
        GROUP BY h.hand_id, h.board, h.created_at
        ORDER BY h.created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    inserted = 0
    for hand_id, board, action_count in rows:
        score = score_hand(int(action_count or 0), board)
        queue_id = stable_id("queue", hand_id)
        connection.execute(
            """
            INSERT INTO study_queue (
                queue_id, hand_id, reason, score, priority, status, tags
            )
            VALUES (?, ?, ?, ?, ?, 'queued', ?)
            """,
            [
                queue_id,
                hand_id,
                "MVP review candidate",
                score,
                int(max(1, min(100, 100 - score))),
                "mvp",
            ],
        )
        inserted += 1
    return inserted


def list_queue(connection, limit: int = 20) -> list[tuple]:
    return connection.execute(
        """
        SELECT queue_id, hand_id, status, score, priority, created_at
        FROM study_queue
        ORDER BY status, priority, created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

