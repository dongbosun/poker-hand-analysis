"""Hold'em combo index helpers."""

from __future__ import annotations

RANKS = "AKQJT98765432"


def starting_hand_labels() -> list[str]:
    labels: list[str] = []
    for i, first in enumerate(RANKS):
        for j, second in enumerate(RANKS):
            if i == j:
                labels.append(first + second)
            elif i < j:
                labels.append(first + second + "s")
            else:
                labels.append(second + first + "o")
    return labels

