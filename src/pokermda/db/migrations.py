"""Schema application helpers."""

from __future__ import annotations

from pathlib import Path


def schema_path() -> Path:
    return Path(__file__).with_name("schema.sql")


def apply_schema(connection) -> None:
    sql = schema_path().read_text(encoding="utf-8")
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)
    _ensure_hands_stake_level_column(connection)
    refresh_stake_levels(connection)


def refresh_stake_levels(connection) -> None:
    """Backfill hand blind amounts and stake levels from normalized blind actions."""
    _ensure_hands_stake_level_column(connection)
    connection.execute(
        """
        UPDATE hands
        SET
            sb_amount = blinds.sb_amount,
            bb_amount = blinds.bb_amount,
            stake_level = CASE
                WHEN blinds.bb_amount IS NULL THEN NULL
                ELSE 'NL' || CAST(CAST(ROUND(blinds.bb_amount * 100) AS BIGINT) AS VARCHAR)
            END
        FROM (
            SELECT
                hand_id,
                MAX(CASE WHEN action_type = 'post_small_blind' THEN amount END) AS sb_amount,
                MAX(CASE WHEN action_type = 'post_big_blind' THEN amount END) AS bb_amount
            FROM actions
            WHERE street = 'preflop'
              AND action_type IN ('post_small_blind', 'post_big_blind')
            GROUP BY hand_id
        ) AS blinds
        WHERE hands.hand_id = blinds.hand_id
        """
    )


def _ensure_hands_stake_level_column(connection) -> None:
    columns = {
        row[1]
        for row in connection.execute("PRAGMA table_info('hands')").fetchall()
    }
    if "stake_level" not in columns:
        connection.execute("ALTER TABLE hands ADD COLUMN stake_level TEXT")
