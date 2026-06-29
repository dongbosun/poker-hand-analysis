"""Frequency aggregation placeholder."""

from __future__ import annotations


def aggregate_frequencies(numerator: float, denominator: float) -> float | None:
    if denominator == 0:
        return None
    return numerator / denominator

