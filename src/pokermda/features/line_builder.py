"""Action line builders."""

from __future__ import annotations

from pokermda.model.action import Action


def build_action_line(actions: list[Action]) -> str:
    return " / ".join(f"{action.street}:{action.actor}:{action.action_type}" for action in actions)

