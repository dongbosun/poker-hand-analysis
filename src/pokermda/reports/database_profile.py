"""Database profile output for quick project status checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

from pokermda.config.settings import AppSettings
from pokermda.ingest.file_scanner import scan_hand_history_files


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

    def to_dict(self) -> dict[str, int | str]:
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
    )


def _count(connection, table_name: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])


def _count_where(connection, table_name: str, where_sql: str) -> int:
    return int(connection.execute(f"SELECT COUNT(*) FROM {table_name} WHERE {where_sql}").fetchone()[0])
