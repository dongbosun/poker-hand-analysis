"""Hand classifier placeholders."""

from __future__ import annotations


def classify_hole_cards(hole_cards: str | None) -> str:
    if not hole_cards:
        return "unknown"
    cards = hole_cards.split()
    if len(cards) != 2:
        return "unknown"
    if cards[0][0] == cards[1][0]:
        return "pair"
    if cards[0][1] == cards[1][1]:
        return "suited"
    return "offsuit"

