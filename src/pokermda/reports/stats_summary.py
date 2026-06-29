"""Runnable database stats summaries."""

from __future__ import annotations

import math
from typing import Any


SEAT_FLAGS_CTE = r"""
WITH seat_base AS (
    SELECT
        p.hand_id,
        p.seat_no,
        p.player_name,
        p.is_hero,
        replace(p.player_name, ' [ME]', '') AS position_label,
        p.stack,
        p.hole_cards,
        p.net_result
    FROM participants p
    WHERE p.hole_cards IS NOT NULL
), flags AS (
    SELECT
        sb.*,
        EXISTS (
            SELECT 1 FROM actions a
            WHERE a.hand_id = sb.hand_id
              AND a.actor = sb.player_name
              AND a.street = 'preflop'
              AND a.action_type IN ('call','raise','bet','all_in')
        ) AS vpip,
        EXISTS (
            SELECT 1 FROM actions a
            WHERE a.hand_id = sb.hand_id
              AND a.actor = sb.player_name
              AND a.street = 'preflop'
              AND (
                  a.action_type = 'raise'
                  OR (a.action_type = 'all_in' AND lower(a.raw_line) LIKE '%raise%')
              )
        ) AS pfr,
        EXISTS (
            SELECT 1 FROM actions a
            WHERE a.hand_id = sb.hand_id
              AND a.actor = sb.player_name
              AND a.action_type = 'call'
              AND a.street = 'preflop'
        ) AS preflop_call,
        EXISTS (
            SELECT 1 FROM actions a
            WHERE a.hand_id = sb.hand_id
              AND a.actor = sb.player_name
              AND a.action_type = 'fold'
              AND a.street = 'preflop'
        ) AS preflop_fold,
        EXISTS (
            SELECT 1 FROM actions a
            WHERE a.hand_id = sb.hand_id
              AND a.actor = sb.player_name
              AND a.street = 'flop'
        ) AS flop_action,
        EXISTS (
            SELECT 1 FROM actions a
            WHERE a.hand_id = sb.hand_id
              AND a.actor = sb.player_name
              AND a.street = 'turn'
        ) AS turn_action,
        EXISTS (
            SELECT 1 FROM actions a
            WHERE a.hand_id = sb.hand_id
              AND a.actor = sb.player_name
              AND a.street = 'river'
        ) AS river_action,
        EXISTS (
            SELECT 1 FROM actions a
            WHERE a.hand_id = sb.hand_id
              AND a.actor = sb.player_name
              AND a.action_type = 'show'
        ) AS showdown,
        EXISTS (
            SELECT 1 FROM actions a
            WHERE a.hand_id = sb.hand_id
              AND a.actor = sb.player_name
              AND a.action_type = 'collect'
        ) AS collected
    FROM seat_base sb
)
"""

POSITION_ORDER_SQL = """
CASE position_label
    WHEN 'Dealer' THEN 1
    WHEN 'Small Blind' THEN 2
    WHEN 'Big Blind' THEN 3
    WHEN 'UTG' THEN 4
    WHEN 'UTG+1' THEN 5
    WHEN 'UTG+2' THEN 6
    ELSE 99
END
"""


def build_stats_summary(connection) -> dict[str, Any]:
    """Build the stats that the current normalized schema can support reliably."""
    return {
        "definitions": {
            "vpip": "Seat was dealt cards and made a voluntary preflop call/raise/bet/all-in. Blinds, posts chip, ante, and straddle are excluded.",
            "pfr": "Seat was dealt cards and made a preflop raise or all-in(raise).",
            "pool": "All non-hero seats in the Bovada anonymous data, aggregated as a population sample.",
            "collected": "Any hand result/collected action. This is not net profit or bb/100.",
        },
        "profile": _profile(connection),
        "core": _core_stats(connection),
        "hero_by_position": _position_stats(connection, is_hero=True),
        "pool_by_position": _position_stats(connection, is_hero=False),
        "action_type_counts": _action_type_counts(connection),
        "street_action_counts": _street_action_counts(connection),
        "hand_runouts": _hand_runouts(connection),
        "preflop_raise_count_per_hand": _preflop_raise_count_per_hand(connection),
    }


def _profile(connection) -> dict[str, int]:
    tables = ["hands", "participants", "actions", "parse_errors", "import_files"]
    return {table: _count(connection, table) for table in tables}


def _core_stats(connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        SEAT_FLAGS_CTE
        + """
        SELECT
            CASE WHEN is_hero THEN 'hero' ELSE 'pool_non_hero' END AS group_name,
            COUNT(*) AS opportunities,
            SUM(vpip::INT) AS vpip_n,
            SUM(pfr::INT) AS pfr_n,
            SUM(preflop_call::INT) AS preflop_call_n,
            SUM(preflop_fold::INT) AS preflop_fold_n,
            SUM(flop_action::INT) AS flop_action_n,
            SUM(turn_action::INT) AS turn_action_n,
            SUM(river_action::INT) AS river_action_n,
            SUM(showdown::INT) AS showdown_n,
            SUM(collected::INT) AS collected_n
        FROM flags
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()
    keys = [
        "group",
        "opportunities",
        "vpip_n",
        "pfr_n",
        "preflop_call_n",
        "preflop_fold_n",
        "flop_action_n",
        "turn_action_n",
        "river_action_n",
        "showdown_n",
        "collected_n",
    ]
    return [_enrich_core_row(dict(zip(keys, row, strict=True))) for row in rows]


def _enrich_core_row(row: dict[str, Any]) -> dict[str, Any]:
    opportunities = row["opportunities"]
    row["vpip_pct"] = _pct(row["vpip_n"], opportunities)
    row["vpip_95ci_pct"] = _wilson_interval_percent(row["vpip_n"], opportunities)
    row["pfr_pct"] = _pct(row["pfr_n"], opportunities)
    row["pfr_95ci_pct"] = _wilson_interval_percent(row["pfr_n"], opportunities)
    row["vpip_minus_pfr_pct"] = round(row["vpip_pct"] - row["pfr_pct"], 1)
    for name in (
        "preflop_call",
        "preflop_fold",
        "flop_action",
        "turn_action",
        "river_action",
        "showdown",
        "collected",
    ):
        row[f"{name}_pct"] = _pct(row[f"{name}_n"], opportunities)
    return row


def _position_stats(connection, is_hero: bool) -> list[dict[str, Any]]:
    rows = connection.execute(
        SEAT_FLAGS_CTE
        + f"""
        SELECT
            position_label,
            COUNT(*) AS opportunities,
            SUM(vpip::INT) AS vpip_n,
            ROUND(100.0 * SUM(vpip::INT) / COUNT(*), 1) AS vpip_pct,
            SUM(pfr::INT) AS pfr_n,
            ROUND(100.0 * SUM(pfr::INT) / COUNT(*), 1) AS pfr_pct,
            ROUND(100.0 * SUM(preflop_call::INT) / COUNT(*), 1) AS preflop_call_pct,
            ROUND(100.0 * SUM(preflop_fold::INT) / COUNT(*), 1) AS preflop_fold_pct,
            ROUND(100.0 * SUM(flop_action::INT) / COUNT(*), 1) AS flop_action_pct,
            ROUND(100.0 * SUM(showdown::INT) / COUNT(*), 1) AS showdown_pct,
            ROUND(100.0 * SUM(collected::INT) / COUNT(*), 1) AS collected_pct
        FROM flags
        WHERE {"is_hero" if is_hero else "NOT is_hero"}
        GROUP BY 1
        ORDER BY {POSITION_ORDER_SQL}
        """
    ).fetchall()
    keys = [
        "position",
        "opportunities",
        "vpip_n",
        "vpip_pct",
        "pfr_n",
        "pfr_pct",
        "preflop_call_pct",
        "preflop_fold_pct",
        "flop_action_pct",
        "showdown_pct",
        "collected_pct",
    ]
    return [dict(zip(keys, row, strict=True)) for row in rows]


def _action_type_counts(connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            action_type,
            COUNT(*) AS count,
            ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM actions), 1) AS pct
        FROM actions
        GROUP BY 1
        ORDER BY count DESC
        """
    ).fetchall()
    return [{"action_type": row[0], "count": row[1], "pct": row[2]} for row in rows]


def _street_action_counts(connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT street, COUNT(*) AS actions, COUNT(DISTINCT hand_id) AS hands_with_action
        FROM actions
        GROUP BY 1
        ORDER BY CASE street
            WHEN 'preflop' THEN 1
            WHEN 'flop' THEN 2
            WHEN 'turn' THEN 3
            WHEN 'river' THEN 4
            ELSE 99
        END
        """
    ).fetchall()
    return [{"street": row[0], "actions": row[1], "hands_with_action": row[2]} for row in rows]


def _hand_runouts(connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT
            CASE
                WHEN board IS NULL THEN 'preflop_only'
                WHEN array_length(regexp_extract_all(board, '[2-9TJQKA][cdhs]')) = 3 THEN 'flop_only'
                WHEN array_length(regexp_extract_all(board, '[2-9TJQKA][cdhs]')) = 4 THEN 'turn'
                WHEN array_length(regexp_extract_all(board, '[2-9TJQKA][cdhs]')) = 5 THEN 'river'
                ELSE 'unknown'
            END AS runout,
            COUNT(*) AS hands,
            ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM hands), 1) AS pct
        FROM hands
        GROUP BY 1
        ORDER BY hands DESC
        """
    ).fetchall()
    return [{"runout": row[0], "hands": row[1], "pct": row[2]} for row in rows]


def _preflop_raise_count_per_hand(connection) -> list[dict[str, Any]]:
    rows = connection.execute(
        """
        WITH r AS (
            SELECT hand_id, COUNT(*) AS raises
            FROM actions
            WHERE street = 'preflop' AND action_type = 'raise'
            GROUP BY hand_id
        )
        SELECT
            COALESCE(raises, 0) AS preflop_raises,
            COUNT(*) AS hands,
            ROUND(100.0 * COUNT(*) / (SELECT COUNT(*) FROM hands), 1) AS pct
        FROM hands h
        LEFT JOIN r USING(hand_id)
        GROUP BY 1
        ORDER BY 1
        """
    ).fetchall()
    return [{"preflop_raises": row[0], "hands": row[1], "pct": row[2]} for row in rows]


def _count(connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _pct(numerator: int | float, denominator: int | float) -> float:
    return round(100.0 * numerator / denominator, 1) if denominator else 0.0


def _wilson_interval_percent(successes: int, trials: int, z: float = 1.96) -> tuple[float, float] | None:
    if trials <= 0:
        return None
    p = successes / trials
    denom = 1 + z * z / trials
    center = (p + z * z / (2 * trials)) / denom
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * trials)) / trials) / denom
    return round(100 * max(0.0, center - margin), 1), round(100 * min(1.0, center + margin), 1)

