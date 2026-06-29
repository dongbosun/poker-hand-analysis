"""DuckDB-backed import ledger."""

from __future__ import annotations

from pokermda.ingest.file_scanner import HandHistoryFile


class ImportLedger:
    def __init__(self, connection):
        self.connection = connection

    def has_successful_file_hash(self, file_hash: str) -> bool:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM import_files WHERE file_hash = ? AND status = 'imported'",
            [file_hash],
        ).fetchone()
        return bool(row and row[0] > 0)

    def status_for_path(self, file_hash: str, source_path: str) -> str | None:
        row = self.connection.execute(
            "SELECT status FROM import_files WHERE file_hash = ? AND source_path = ?",
            [file_hash, source_path],
        ).fetchone()
        return row[0] if row else None

    def record_seen(self, record: HandHistoryFile, status: str = "seen") -> None:
        source_path = str(record.path)
        if self.status_for_path(record.file_hash, source_path):
            self.connection.execute(
                """
                UPDATE import_files
                SET last_seen_at = CURRENT_TIMESTAMP,
                    file_size_bytes = ?,
                    modified_time = ?,
                    status = ?
                WHERE file_hash = ? AND source_path = ?
                """,
                [
                    record.file_size_bytes,
                    record.modified_time,
                    status,
                    record.file_hash,
                    source_path,
                ],
            )
            return

        self.connection.execute(
            """
            INSERT INTO import_files (
                file_hash, source_path, file_size_bytes, modified_time, status
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            [
                record.file_hash,
                source_path,
                record.file_size_bytes,
                record.modified_time,
                status,
            ],
        )

    def mark_importing(self, record: HandHistoryFile) -> None:
        self.record_seen(record, status="importing")

    def mark_imported(
        self,
        record: HandHistoryFile,
        hands_seen: int,
        hands_inserted: int,
    ) -> None:
        self.connection.execute(
            """
            UPDATE import_files
            SET status = 'imported',
                imported_at = CURRENT_TIMESTAMP,
                last_seen_at = CURRENT_TIMESTAMP,
                hands_seen = ?,
                hands_inserted = ?,
                error_message = NULL
            WHERE file_hash = ? AND source_path = ?
            """,
            [hands_seen, hands_inserted, record.file_hash, str(record.path)],
        )

    def mark_skipped_duplicate(self, record: HandHistoryFile) -> None:
        self.record_seen(record, status="skipped_duplicate")
        self.connection.execute(
            """
            UPDATE import_files
            SET last_seen_at = CURRENT_TIMESTAMP,
                error_message = 'File hash already imported from another path'
            WHERE file_hash = ? AND source_path = ?
            """,
            [record.file_hash, str(record.path)],
        )

    def mark_failed(self, record: HandHistoryFile, error_message: str) -> None:
        self.connection.execute(
            """
            UPDATE import_files
            SET status = 'failed',
                last_seen_at = CURRENT_TIMESTAMP,
                error_message = ?
            WHERE file_hash = ? AND source_path = ?
            """,
            [error_message, record.file_hash, str(record.path)],
        )

