"""Action model."""

from __future__ import annotations

from dataclasses import dataclass

from pokermda.model.enums import ActionType, Street


@dataclass(slots=True)
class Action:
    sequence_no: int
    street: Street
    actor: str | None
    action_type: ActionType
    amount: float | None = None
    raise_to: float | None = None
    raw_line: str = ""

