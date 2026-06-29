"""Participant model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Participant:
    seat_no: int
    player_name: str
    stack: float | None = None
    is_hero: bool = False
    hole_cards: str | None = None
    position: str | None = None
    net_result: float | None = None

