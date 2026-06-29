"""Split raw Bovada txt files into hand blocks."""

from __future__ import annotations

import re

HAND_START_RE = re.compile(
    r"(?im)^(?:Bovada\s+|Ignition\s+|PokerStars\s+|Game\s+)?Hand\s+#?\d+"
)
HAND_NUMBER_RE = re.compile(r"(?i)\bHand\s+#?(\d+)\b")


def split_hand_blocks(text: str) -> list[str]:
    if not text.strip():
        return []

    starts = list(HAND_START_RE.finditer(text))
    if not starts:
        return [text.strip()]

    blocks: list[str] = []
    for index, match in enumerate(starts):
        start = match.start()
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[start:end].strip()
        if block:
            blocks.append(block)
    return blocks


def extract_hand_number(block: str) -> str | None:
    match = HAND_NUMBER_RE.search(block)
    return match.group(1) if match else None

