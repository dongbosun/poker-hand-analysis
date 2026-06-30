"""Database profile output for quick project status checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from pokermda.config.settings import AppSettings
from pokermda.ingest.file_scanner import scan_hand_history_files


@dataclass(frozen=True)
class DatabaseLevelProfile:
    stake_level: str
    bb_amount: float | None
    hands: int
    participants_dealt: int
    actions: int
    raw_hand_blocks: int
    import_files: int


@dataclass(frozen=True)
class DatabaseProfile:
    duckdb_path: str
    bovada_raw_hand_history_dir: str
    hands_in_database: int
    bronze_raw_hand_blocks: int
    parsed_raw_hand_blocks: int
    parse_errors: int
    raw_bovada_files: int
    raw_bovada_unique_file_hashes: int
    raw_bovada_files_completed_by_hash: int
    raw_bovada_files_not_imported_by_hash: int
    ledger_file_paths: int
    ledger_imported_file_paths: int
    ledger_skipped_duplicate_file_paths: int
    ledger_failed_file_paths: int
    levels: list[DatabaseLevelProfile]

    def to_dict(self) -> dict[str, int | str | list[dict[str, int | str | float | None]]]:
        return asdict(self)


def build_database_profile(
    settings: AppSettings,
    connection,
    source_dir: Path | None = None,
) -> DatabaseProfile:
    raw_dir = source_dir or settings.bovada_raw_hand_history_dir
    raw_files = scan_hand_history_files(raw_dir, pattern=settings.ingest.file_glob)
    raw_hashes = {record.file_hash for record in raw_files}

    imported_hashes = {
        row[0]
        for row in connection.execute(
            "SELECT DISTINCT sha256 FROM import_files WHERE status = 'imported'"
        ).fetchall()
    }
    status_counts = {
        row[0]: int(row[1])
        for row in connection.execute(
            "SELECT status, COUNT(*) FROM import_files GROUP BY status"
        ).fetchall()
    }

    raw_completed_by_hash = sum(1 for record in raw_files if record.file_hash in imported_hashes)
    raw_pending_by_hash = sum(1 for record in raw_files if record.file_hash not in imported_hashes)

    return DatabaseProfile(
        duckdb_path=str(settings.duckdb_path),
        bovada_raw_hand_history_dir=str(raw_dir),
        hands_in_database=_count(connection, "hands"),
        bronze_raw_hand_blocks=_count(connection, "raw_hand_blocks"),
        parsed_raw_hand_blocks=_count_where(connection, "raw_hand_blocks", "parse_status = 'parsed'"),
        parse_errors=_count(connection, "parse_errors"),
        raw_bovada_files=len(raw_files),
        raw_bovada_unique_file_hashes=len(raw_hashes),
        raw_bovada_files_completed_by_hash=raw_completed_by_hash,
        raw_bovada_files_not_imported_by_hash=raw_pending_by_hash,
        ledger_file_paths=sum(status_counts.values()),
        ledger_imported_file_paths=status_counts.get("imported", 0),
        ledger_skipped_duplicate_file_paths=status_counts.get("skipped_duplicate", 0),
        ledger_failed_file_paths=status_counts.get("error", 0) + status_counts.get("failed", 0),
        levels=_level_profiles(connection),
    )


def _count(connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _count_where(connection, table_name: str, where_sql: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {where_sql}").fetchone()[0])


def _level_profiles(connection) -> list[DatabaseLevelProfile]:
    rows = connection.execute(
        """
        WITH hand_levels AS (
            SELECT
                hand_id,
                raw_hand_id,
                import_file_id,
                COALESCE(stake_level, 'UNKNOWN') AS stake_level,
                bb_amount
            FROM hands
        ),
        hand_counts AS (
            SELECT
                stake_level,
                MAX(bb_amount) AS bb_amount,
                COUNT(*) AS hands,
                COUNT(DISTINCT raw_hand_id) AS raw_hand_blocks,
                COUNT(DISTINCT import_file_id) AS import_files
            FROM hand_levels
            GROUP BY 1
        ),
        participant_counts AS (
            SELECT h.stake_level, COUNT(*) AS participants_dealt
            FROM hand_levels h
            JOIN participants p ON p.hand_id = h.hand_id
            WHERE p.hole_cards IS NOT NULL
            GROUP BY 1
        ),
        action_counts AS (
            SELECT h.stake_level, COUNT(*) AS actions
            FROM hand_levels h
            JOIN actions a ON a.hand_id = h.hand_id
            GROUP BY 1
        )
        SELECT
            h.stake_level,
            h.bb_amount,
            h.hands,
            COALESCE(p.participants_dealt, 0) AS participants_dealt,
            COALESCE(a.actions, 0) AS actions,
            h.raw_hand_blocks,
            h.import_files
        FROM hand_counts h
        LEFT JOIN participant_counts p USING (stake_level)
        LEFT JOIN action_counts a USING (stake_level)
        ORDER BY
            COALESCE(TRY_CAST(REPLACE(h.stake_level, 'NL', '') AS INTEGER), 999)
        """
    ).fetchall()
    return [
        DatabaseLevelProfile(
            stake_level=row[0],
            bb_amount=row[1],
            hands=int(row[2]),
            participants_dealt=int(row[3]),
            actions=int(row[4]),
            raw_hand_blocks=int(row[5]),
            import_files=int(row[6]),
        )
        for row in rows
    ]
