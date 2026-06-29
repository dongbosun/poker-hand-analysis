"""SPR helpers."""

from __future__ import annotations


def calculate_spr(effective_stack: float | None, pot: float | None) -> float | None:
    if effective_stack is None or pot in (None, 0):
        return None
    return effective_stack / pot

