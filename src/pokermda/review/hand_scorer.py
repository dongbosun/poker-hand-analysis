"""Simple MVP hand scoring."""

from __future__ import annotations


def score_hand(action_count: int, board: str | None = None) -> float:
    score = float(action_count)
    if board:
        score += 2.0
    return score

