"""Split raw Bovada txt files into hand blocks."""

from __future__ import annotations

import re
from dataclasses import dataclass

HAND_START_RE = re.compile(
    r"(?im)^(?:Bovada\s+|Ignition\s+|PokerStars\s+|Game\s+)?Hand\s+#?\d+"
)
HAND_NUMBER_RE = re.compile(r"(?i)\bHand\s+#?(\d+)\b")


@dataclass(frozen=True, slots=True)
class HandBlock:
    raw_text: str
    start_line: int
    end_line: int
    block_index: int


def split_hand_blocks(text: str) -> list[str]:
    return [block.raw_text for block in split_hand_blocks_with_lines(text)]


def split_hand_blocks_with_lines(text: str) -> list[HandBlock]:
    if not text.strip():
        return []

    starts = list(HAND_START_RE.finditer(text))
    if not starts:
        stripped = text.strip()
        if not stripped:
            return []
        return [HandBlock(stripped, 1, len(stripped.splitlines()), 1)]

    blocks: list[HandBlock] = []
    line_starts = _line_start_offsets(text)
    for index, match in enumerate(starts):
        start = match.start()
        end = starts[index + 1].start() if index + 1 < len(starts) else len(text)
        block = text[start:end].strip()
        if block:
            start_line = _line_number_for_offset(line_starts, start)
            end_line = start_line + len(block.splitlines()) - 1
            blocks.append(HandBlock(block, start_line, end_line, index + 1))
    return blocks


def extract_hand_number(block: str) -> str | None:
    match = HAND_NUMBER_RE.search(block)
    return match.group(1) if match else None


def _line_start_offsets(text: str) -> list[int]:
    offsets = [0]
    for index, char in enumerate(text):
        if char == "\n":
            offsets.append(index + 1)
    return offsets


def _line_number_for_offset(line_starts: list[int], offset: int) -> int:
    line_no = 1
    for index, line_start in enumerate(line_starts, start=1):
        if line_start > offset:
            break
        line_no = index
    return line_no
