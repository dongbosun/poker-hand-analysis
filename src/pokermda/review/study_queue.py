"""Study queue builders."""

from __future__ import annotations

from pokermda.review.hand_scorer import score_hand
from pokermda.utils.hashing import stable_id


def build_study_queue(connection, limit: int = 50) -> int:
    rows = connection.execute(
        """
        SELECT
            h.hand_id,
            h.board,
            hp.participant_id AS hero_participant_id,
            COUNT(a.action_id) AS action_count,
            SUM(CASE WHEN a.action_type = 'all_in' THEN 1 ELSE 0 END) AS allin_count,
            SUM(CASE WHEN a.street = 'river' THEN 1 ELSE 0 END) AS river_actions,
            SUM(CASE WHEN a.street = 'preflop' AND a.action_type = 'raise' THEN 1 ELSE 0 END) AS preflop_raises
        FROM hands h
        LEFT JOIN actions a ON h.hand_id = a.hand_id
        LEFT JOIN participants hp ON h.hand_id = hp.hand_id AND hp.is_hero
        LEFT JOIN study_queue q ON h.hand_id = q.hand_id
        WHERE q.hand_id IS NULL
        GROUP BY h.hand_id, h.board, hp.participant_id, h.created_at
        ORDER BY h.created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()

    inserted = 0
    for hand_id, board, hero_participant_id, action_count, allin_count, river_actions, preflop_raises in rows:
        score = score_hand(int(action_count or 0), board)
        tags = ["mvp"]
        if allin_count:
            score += 25
            tags.append("allin")
        if river_actions:
            score += 15
            tags.append("river")
        if preflop_raises and preflop_raises >= 2:
            score += 10
            tags.append("multi_raise_pot")
        priority = int(max(1, min(100, 100 - score)))
        queue_id = stable_id("queue", hand_id)
        connection.execute(
            """
            INSERT INTO study_queue (
                queue_id, hand_id, hero_participant_id, source,
                priority_score, priority_bucket, reason_tags, queue_status,
                reason, score, priority, status, tags
            )
            VALUES (?, ?, ?, 'local_scorer', ?, ?, ?, 'queued', ?, ?, ?, 'queued', ?)
            """,
            [
                queue_id,
                hand_id,
                hero_participant_id,
                score,
                _priority_bucket(score),
                ",".join(tags),
                "MVP review candidate",
                score,
                priority,
                ",".join(tags),
            ],
        )
        inserted += 1
    return inserted


def list_queue(connection, limit: int = 20) -> list[tuple]:
    return connection.execute(
        """
        SELECT queue_id, hand_id, queue_status, priority_score, priority_bucket, reason_tags, created_at
        FROM study_queue
        ORDER BY queue_status, priority_score DESC, created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()


def _priority_bucket(score: float) -> str:
    if score >= 60:
        return "high"
    if score >= 30:
        return "medium"
    return "low"
