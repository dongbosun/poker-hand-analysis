"""Sizing bucket helpers."""

from __future__ import annotations


def bucket_pot_fraction(fraction: float | None) -> str:
    if fraction is None:
        return "unknown"
    if fraction < 0.33:
        return "small"
    if fraction < 0.75:
        return "medium"
    if fraction < 1.25:
        return "large"
    return "overbet"

