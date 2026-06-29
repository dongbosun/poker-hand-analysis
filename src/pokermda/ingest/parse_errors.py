"""Parse error types and persistence helpers."""

from __future__ import annotations

from dataclasses import dataclass

from pokermda.utils.hashing import stable_id


class BovadaParseError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ParseErrorRecord:
    hand_hash: str | None
    file_hash: str | None
    source_path: str | None
    block_index: int | None
    error_code: str
    message: str
    raw_excerpt: str | None


def record_parse_error(connection, record: ParseErrorRecord) -> str:
    error_id = stable_id(
        "parse_error",
        record.hand_hash,
        record.file_hash,
        record.source_path,
        record.block_index,
        record.error_code,
        record.message,
    )
    connection.execute(
        """
        INSERT INTO parse_errors (
            error_id, hand_hash, raw_hand_hash, file_hash, source_path, raw_file_path, block_index,
            error_code, message, raw_excerpt
        )
        SELECT ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
        WHERE NOT EXISTS (SELECT 1 FROM parse_errors WHERE error_id = ?)
        """,
        [
            error_id,
            record.hand_hash,
            record.hand_hash,
            record.file_hash,
            record.source_path,
            record.source_path,
            record.block_index,
            record.error_code,
            record.message,
            record.raw_excerpt,
            error_id,
        ],
    )
    return error_id
