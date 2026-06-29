"""Pot type helpers."""

from __future__ import annotations


def classify_pot_type(preflop_raiser_count: int) -> str:
    if preflop_raiser_count <= 0:
        return "limped"
    if preflop_raiser_count == 1:
        return "single_raised"
    if preflop_raiser_count == 2:
        return "three_bet"
    return "four_bet_plus"

