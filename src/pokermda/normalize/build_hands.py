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
    import_file_id: str | None = None,
    hand_start_line: int | None = None,
    hand_end_line: int | None = None,
) -> tuple[str, bool]:
    hand_hash = sha256_text(raw_text)
    existing = connection.execute(
        "SELECT raw_hand_block_id FROM raw_hand_blocks WHERE raw_hand_hash = ?",
        [hand_hash],
    ).fetchone()
    if existing:
        return existing[0], False

    raw_hand_id = stable_id("raw_hand", hand_hash)
    connection.execute(
        """
        INSERT INTO raw_hand_blocks (
            raw_hand_block_id, import_file_id, source_site, raw_hand_hash,
            site_hand_no, hand_start_line, hand_end_line, raw_text,
            raw_hand_id, hand_hash, file_hash, source_path, block_index,
            bovada_hand_number
        )
        VALUES (?, ?, 'bovada', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            raw_hand_id,
            import_file_id,
            hand_hash,
            extract_hand_number(raw_text),
            hand_start_line,
            hand_end_line,
            raw_text,
            raw_hand_id,
            hand_hash,
            file_hash,
            source_path,
            block_index,
            extract_hand_number(raw_text),
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
        UPDATE raw_hand_blocks
        SET parse_status = ?, parse_error_message = ?, parse_error = ?
        WHERE raw_hand_block_id = ?
        """,
        [status, parse_error, parse_error, raw_hand_id],
    )


def insert_hand(
    connection,
    parsed: ParsedHand,
    raw_hand_id: str,
    source_file_hash: str,
    import_file_id: str | None = None,
) -> tuple[str, bool]:
    existing = connection.execute(
        """
        SELECT hand_id FROM hands
        WHERE raw_hand_hash = ?
           OR (site_hand_no IS NOT NULL AND site_hand_no = ?)
        """,
        [parsed.hand_hash, parsed.bovada_hand_number],
    ).fetchone()
    if existing:
        return existing[0], False

    connection.execute(
        """
        INSERT INTO hands (
            hand_id, source_site, site_hand_no, raw_hand_hash, import_file_id,
            played_at, game_type, stake, table_name, button_seat,
            board_flop, board_turn, board_river,
            bovada_hand_number, hand_hash, raw_hand_id, source_file_hash,
            stakes, started_at_text, board, hero_name, parser_version
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            parsed.hand_id,
            parsed.source_site,
            parsed.bovada_hand_number,
            parsed.hand_hash,
            import_file_id,
            parsed.started_at_text,
            parsed.game_type,
            parsed.stakes,
            parsed.table_name,
            parsed.button_seat,
            _board_street(parsed.board, 3),
            _board_street(parsed.board, 4),
            _board_street(parsed.board, 5),
            parsed.bovada_hand_number,
            parsed.hand_hash,
            raw_hand_id,
            source_file_hash,
            parsed.stakes,
            parsed.started_at_text,
            parsed.board,
            parsed.hero_name,
            parsed.parser_version,
        ],
    )
    return parsed.hand_id, True


def _board_street(board: str | None, cards_count: int) -> str | None:
    if not board:
        return None
    cards = board.split()
    if len(cards) < cards_count:
        return None
    return " ".join(cards[:cards_count])
