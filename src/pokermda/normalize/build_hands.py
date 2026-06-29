"""Insert bronze blocks and parsed hands."""

from __future__ import annotations

from pokermda.ingest.hand_splitter import extract_hand_number
from pokermda.model.hand import ParsedHand
from pokermda.utils.hashing import sha256_text, stable_id


def insert_bronze_raw_block(
    connection,
    file_hash: str,
    source_path: str,
    block_index: int,
    raw_text: str,
) -> tuple[str, bool]:
    hand_hash = sha256_text(raw_text)
    existing = connection.execute(
        "SELECT raw_hand_id FROM bronze_raw_hand_blocks WHERE hand_hash = ?",
        [hand_hash],
    ).fetchone()
    if existing:
        return existing[0], False

    raw_hand_id = stable_id("raw_hand", hand_hash)
    connection.execute(
        """
        INSERT INTO bronze_raw_hand_blocks (
            raw_hand_id, hand_hash, file_hash, source_path, block_index,
            bovada_hand_number, raw_text
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            raw_hand_id,
            hand_hash,
            file_hash,
            source_path,
            block_index,
            extract_hand_number(raw_text),
            raw_text,
        ],
    )
    return raw_hand_id, True


def update_bronze_parse_status(
    connection,
    raw_hand_id: str,
    status: str,
    parse_error: str | None = None,
) -> None:
    connection.execute(
        """
        UPDATE bronze_raw_hand_blocks
        SET parse_status = ?, parse_error = ?
        WHERE raw_hand_id = ?
        """,
        [status, parse_error, raw_hand_id],
    )


def insert_hand(
    connection,
    parsed: ParsedHand,
    raw_hand_id: str,
    source_file_hash: str,
) -> tuple[str, bool]:
    existing = connection.execute(
        """
        SELECT hand_id FROM hands
        WHERE hand_hash = ?
           OR (bovada_hand_number IS NOT NULL AND bovada_hand_number = ?)
        """,
        [parsed.hand_hash, parsed.bovada_hand_number],
    ).fetchone()
    if existing:
        return existing[0], False

    connection.execute(
        """
        INSERT INTO hands (
            hand_id, bovada_hand_number, hand_hash, raw_hand_id, source_file_hash,
            source_site, game_type, stakes, table_name, button_seat,
            started_at_text, board, hero_name, parser_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            parsed.hand_id,
            parsed.bovada_hand_number,
            parsed.hand_hash,
            raw_hand_id,
            source_file_hash,
            parsed.source_site,
            parsed.game_type,
            parsed.stakes,
            parsed.table_name,
            parsed.button_seat,
            parsed.started_at_text,
            parsed.board,
            parsed.hero_name,
            parsed.parser_version,
        ],
    )
    return parsed.hand_id, True

