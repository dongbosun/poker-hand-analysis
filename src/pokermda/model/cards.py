"""Card parsing helpers."""

from __future__ import annotations

import re

CARD_RE = re.compile(r"\b([2-9TJQKA][cdhs])\b", re.IGNORECASE)


def parse_cards(text: str) -> list[str]:
    return [card[0].upper() + card[1].lower() for card in CARD_RE.findall(text)]


def cards_to_text(cards: list[str]) -> str:
    return " ".join(cards)

