"""Range matrix placeholder."""

from __future__ import annotations

from pokermda.ranges.combo_index import starting_hand_labels


def empty_range_matrix() -> dict[str, float]:
    return {label: 0.0 for label in starting_hand_labels()}

