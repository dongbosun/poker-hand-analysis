"""Position helpers."""

from __future__ import annotations


def infer_position(seat_no: int, button_seat: int | None, max_players: int | None = None) -> str | None:
    if button_seat is None:
        return None
    seats = max_players or 6
    offset = (seat_no - button_seat) % seats
    return {
        0: "BTN",
        1: "SB",
        2: "BB",
        3: "UTG",
        4: "HJ",
        5: "CO",
    }.get(offset, f"SEAT_{seat_no}")

