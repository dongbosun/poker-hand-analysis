"""Stake-level normalization helpers."""

from __future__ import annotations


def stake_level_from_bb(bb_amount: float | None) -> str | None:
    """Return a compact stake label such as NL5 or NL10 from a big blind amount."""
    if bb_amount is None or bb_amount <= 0:
        return None
    return f"NL{int(round(bb_amount * 100))}"


def normalize_stake_level(level: str | None) -> str | None:
    """Normalize user input like nl5, 5, or all into the canonical level label."""
    if level is None:
        return None
    cleaned = level.strip().upper()
    if not cleaned or cleaned in {"ALL", "*"}:
        return None
    if cleaned.startswith("NL"):
        suffix = cleaned[2:].lstrip("0") or "0"
        if suffix.isdigit():
            return f"NL{int(suffix)}"
    if cleaned.isdigit():
        return f"NL{int(cleaned)}"
    try:
        amount = float(cleaned.replace("$", ""))
    except ValueError:
        return cleaned
    if amount <= 1:
        return stake_level_from_bb(amount)
    return f"NL{int(round(amount))}"
