"""Hero-perspective sanitizer for GTOWizard exports."""

from __future__ import annotations

import re

DEALT_RE = re.compile(r"^Dealt\s+to\s+(?P<name>.+?)\s+\[(?P<cards>[^\]]+)\]", re.IGNORECASE)
SPOT_DEALT_RE = re.compile(
    r"^(?P<name>.+?)\s*:\s*Card dealt to a spot\s+\[(?P<cards>[^\]]+)\]",
    re.IGNORECASE,
)
SEAT_NAME_RE = re.compile(r"^Seat\s+\d+:\s+(?P<name>.+?)\s+\(", re.IGNORECASE)
ACTION_NAME_RE = re.compile(r"^(?P<name>[^:]+):\s+")
CARD_BRACKET_RE = re.compile(r"\[[^\]]+\]")
HERO_LINE_RE = re.compile(r"^(?:Hero\s*:|Dealt\s+to\s+Hero\b)", re.IGNORECASE)


def sanitize_bovada_hand(raw_text: str, hero_name: str | None = None) -> str:
    """Return a GTOWizard-friendly hand history with non-hero private cards hidden."""
    hero = hero_name or _detect_hero(raw_text)
    names = _discover_player_names(raw_text)
    mapping = _build_name_mapping(names, hero)

    sanitized_lines: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.upper().startswith("*** SUMMARY ***"):
            break

        dealt_match = DEALT_RE.match(stripped)
        if dealt_match and hero and dealt_match.group("name").strip() != hero:
            continue

        spot_dealt_match = SPOT_DEALT_RE.match(stripped)
        if spot_dealt_match and hero and spot_dealt_match.group("name").strip() != hero:
            continue

        line = _replace_names(line, mapping)
        line = _hide_non_hero_showdown_cards(line)
        sanitized_lines.append(line)

    return "\n".join(sanitized_lines).strip() + "\n"


def _detect_hero(raw_text: str) -> str | None:
    for line in raw_text.splitlines():
        stripped = line.strip()
        if "[ME]" in stripped.upper():
            seat_match = SEAT_NAME_RE.match(stripped)
            if seat_match:
                return seat_match.group("name").strip()
            action_match = ACTION_NAME_RE.match(stripped)
            if action_match:
                return action_match.group("name").strip()
        match = DEALT_RE.match(stripped)
        if match:
            return match.group("name").strip()
    return None


def _discover_player_names(raw_text: str) -> list[str]:
    names: list[str] = []
    for line in raw_text.splitlines():
        stripped = line.strip()
        seat_match = SEAT_NAME_RE.match(stripped)
        if seat_match:
            _append_unique(names, seat_match.group("name").strip())
            continue
        dealt_match = DEALT_RE.match(stripped)
        if dealt_match:
            _append_unique(names, dealt_match.group("name").strip())
            continue
        spot_dealt_match = SPOT_DEALT_RE.match(stripped)
        if spot_dealt_match:
            _append_unique(names, spot_dealt_match.group("name").strip())
            continue
        action_match = ACTION_NAME_RE.match(stripped)
        if action_match and not stripped.startswith("***"):
            candidate = action_match.group("name").strip()
            if not _looks_like_header(candidate):
                _append_unique(names, candidate)
    return names


def _append_unique(values: list[str], value: str) -> None:
    if value and value not in values:
        values.append(value)


def _build_name_mapping(names: list[str], hero_name: str | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    villain_index = 1
    for name in names:
        if hero_name and name == hero_name:
            mapping[name] = "Hero"
        else:
            mapping[name] = f"Villain{villain_index}"
            villain_index += 1
    return mapping


def _replace_names(line: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return line
    pattern = re.compile("|".join(re.escape(name) for name in sorted(mapping, key=len, reverse=True)))
    return pattern.sub(lambda match: mapping[match.group(0)], line)


def _hide_non_hero_showdown_cards(line: str) -> str:
    lowered = line.lower()
    if HERO_LINE_RE.match(line):
        return line
    if (
        ": shows " in lowered
        or ": mucks " in lowered
        or " showed " in lowered
        or ": showdown " in lowered
        or ": does not show " in lowered
    ):
        return CARD_BRACKET_RE.sub("[hidden]", line)
    return line


def _looks_like_header(candidate: str) -> bool:
    lowered = candidate.lower()
    return "hand #" in lowered or lowered.startswith(("bovada hand", "ignition hand", "pokerstars hand"))
