"""DuckDB-backed import ledger."""

from __future__ import annotations

from pokermda.ingest.file_scanner import HandHistoryFile
from pokermda.utils.hashing import stable_id


class ImportLedger:
    def __init__(self, connection):
        self.connection = connection

    def import_file_id_for_record(self, record: HandHistoryFile) -> str:
        return stable_id("import_file", record.file_hash, str(record.path))

    def has_successful_file_hash(self, file_hash: str) -> bool:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM import_files WHERE sha256 = ? AND status = 'imported'",
            [file_hash],
        ).fetchone()
        return bool(row and row[0] > 0)

    def status_for_path(self, file_hash: str, source_path: str) -> str | None:
        row = self.connection.execute(
            "SELECT status FROM import_files WHERE sha256 = ? AND raw_file_path = ?",
            [file_hash, source_path],
        ).fetchone()
        return row[0] if row else None

    def record_seen(self, record: HandHistoryFile, status: str = "discovered") -> str:
        source_path = str(record.path)
        import_file_id = self.import_file_id_for_record(record)
        if self.status_for_path(record.file_hash, source_path):
            self.connection.execute(
                """
                UPDATE import_files
                SET last_seen_at = CURRENT_TIMESTAMP,
                    raw_file_size_bytes = ?,
                    raw_file_mtime_ns = ?,
                    file_size_bytes = ?,
                    modified_time = ?,
                    status = ?
                WHERE sha256 = ? AND raw_file_path = ?
                """,
                [
                    record.file_size_bytes,
                    record.modified_time_ns,
                    record.file_size_bytes,
                    record.modified_time,
                    status,
                    record.file_hash,
                    source_path,
                ],
            )
            return import_file_id

        self.connection.execute(
            """
            INSERT INTO import_files (
                import_file_id, source_site, raw_file_path, raw_file_realpath,
                raw_file_size_bytes, raw_file_mtime_ns, sha256, status,
                file_hash, source_path, file_size_bytes, modified_time
            )
            VALUES (?, 'bovada', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                import_file_id,
                source_path,
                str(record.realpath),
                record.file_size_bytes,
                record.modified_time_ns,
                record.file_hash,
                status,
                record.file_hash,
                source_path,
                record.file_size_bytes,
                record.modified_time,
            ],
        )
        return import_file_id

    def mark_importing(self, record: HandHistoryFile) -> str:
        return self.record_seen(record, status="importing")

    def mark_imported(
        self,
        record: HandHistoryFile,
        hands_seen: int,
        hands_inserted: int,
        hands_failed: int = 0,
        parser_version: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE import_files
            SET status = 'imported',
                imported_at = CURRENT_TIMESTAMP,
                last_seen_at = CURRENT_TIMESTAMP,
                hands_detected = ?,
                hands_imported = ?,
                hands_failed = ?,
                parser_version = COALESCE(?, parser_version),
                hands_seen = ?,
                hands_inserted = ?,
                error_message = NULL
            WHERE sha256 = ? AND raw_file_path = ?
            """,
            [
                hands_seen,
                hands_inserted,
                hands_failed,
                parser_version,
                hands_seen,
                hands_inserted,
                record.file_hash,
                str(record.path),
            ],
        )

    def mark_partial(
        self,
        record: HandHistoryFile,
        hands_seen: int,
        hands_inserted: int,
        hands_failed: int,
        parser_version: str | None = None,
        error_message: str | None = None,
    ) -> None:
        self.connection.execute(
            """
            UPDATE import_files
            SET status = 'partial',
                imported_at = CURRENT_TIMESTAMP,
                last_seen_at = CURRENT_TIMESTAMP,
                hands_detected = ?,
                hands_imported = ?,
                hands_failed = ?,
                parser_version = COALESCE(?, parser_version),
                hands_seen = ?,
                hands_inserted = ?,
                error_message = ?
            WHERE sha256 = ? AND raw_file_path = ?
            """,
            [
                hands_seen,
                hands_inserted,
                hands_failed,
                parser_version,
                hands_seen,
                hands_inserted,
                error_message,
                record.file_hash,
                str(record.path),
            ],
        )

    def mark_skipped_duplicate(self, record: HandHistoryFile) -> None:
        self.record_seen(record, status="skipped_duplicate")
        self.connection.execute(
            """
            UPDATE import_files
            SET last_seen_at = CURRENT_TIMESTAMP,
                error_message = 'File hash already imported from another path'
            WHERE sha256 = ? AND raw_file_path = ?
            """,
            [record.file_hash, str(record.path)],
        )

    def mark_failed(self, record: HandHistoryFile, error_message: str) -> None:
        if not self.status_for_path(record.file_hash, str(record.path)):
            self.record_seen(record, status="error")
        self.connection.execute(
            """
            UPDATE import_files
            SET status = 'error',
                last_seen_at = CURRENT_TIMESTAMP,
                error_message = ?
            WHERE sha256 = ? AND raw_file_path = ?
            """,
            [error_message, record.file_hash, str(record.path)],
        )

