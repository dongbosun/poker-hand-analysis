"""Board texture placeholders."""

from __future__ import annotations

from pokermda.model.cards import parse_cards


def classify_board_texture(board: str | None) -> str:
    cards = parse_cards(board or "")
    if len(cards) < 3:
        return "unknown"
    suits = {card[1] for card in cards[:3]}
    return "monotone" if len(suits) == 1 else "mixed"

