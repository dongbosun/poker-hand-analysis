"""Parsed hand model."""

from __future__ import annotations

from dataclasses import dataclass, field

from pokermda.model.action import Action
from pokermda.model.participant import Participant


@dataclass(slots=True)
class ParsedHand:
    hand_id: str
    hand_hash: str
    raw_text: str
    bovada_hand_number: str | None = None
    source_site: str = "bovada"
    game_type: str | None = None
    stakes: str | None = None
    table_name: str | None = None
    button_seat: int | None = None
    started_at_text: str | None = None
    board: str | None = None
    hero_name: str | None = None
    participants: list[Participant] = field(default_factory=list)
    actions: list[Action] = field(default_factory=list)
    parser_version: str = "bovada-parser-v1"

