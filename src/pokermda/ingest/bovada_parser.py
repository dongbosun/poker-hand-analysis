"""Pragmatic Bovada hand history parser.

The MVP parser intentionally covers the common text shapes and records raw lines
for future parser upgrades. Unknown action lines are ignored instead of failing.
"""

from __future__ import annotations

import re

from pokermda.ingest.hand_splitter import extract_hand_number
from pokermda.ingest.parse_errors import BovadaParseError
from pokermda.model.action import Action
from pokermda.model.cards import cards_to_text, parse_cards
from pokermda.model.enums import ActionType, Street
from pokermda.model.hand import ParsedHand
from pokermda.model.participant import Participant
from pokermda.utils.hashing import sha256_text

PARSER_VERSION = "bovada-parser-v1"

SEAT_RE = re.compile(
    r"^Seat\s+(?P<seat>\d+):\s+(?P<name>.+?)\s+\(\$?(?P<stack>[\d,.]+)\s+in chips\)",
    re.IGNORECASE,
)
BUTTON_RE = re.compile(
    r"Table\s+(?:'(?P<quoted_table>[^']+)'|(?P<plain_table>.*?))\s+.*Seat\s+#(?P<button>\d+)\s+is\s+the\s+button",
    re.IGNORECASE,
)
DEALT_RE = re.compile(r"^Dealt\s+to\s+(?P<name>.+?)\s+\[(?P<cards>[^\]]+)\]", re.IGNORECASE)
SPOT_DEALT_RE = re.compile(
    r"^(?P<name>.+?)\s*:\s*Card dealt to a spot\s+\[(?P<cards>[^\]]+)\]",
    re.IGNORECASE,
)
SET_DEALER_RE = re.compile(
    r"^(?P<name>.+?)?\s*:?\s*Set dealer\s+\[(?P<seat>\d+)\]",
    re.IGNORECASE,
)
AMOUNT_RE = re.compile(r"\$?(-?[\d,]+(?:\.\d+)?)")


class BovadaParser:
    def parse(self, raw_text: str) -> ParsedHand:
        hand_hash = sha256_text(raw_text)
        hand_number = extract_hand_number(raw_text)
        if not hand_number:
            raise BovadaParseError("missing_hand_number", "Could not find a hand number.")

        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        header = lines[0] if lines else ""

        participants: dict[str, Participant] = {}
        ordered_participants: list[Participant] = []
        actions: list[Action] = []
        current_street = Street.PREFLOP
        board_cards: list[str] = []
        table_name: str | None = None
        button_seat: int | None = None
        hero_name: str | None = None

        game_type = self._parse_game_type(header)
        stakes = self._parse_stakes(header)
        started_at_text = self._parse_started_at_text(header)

        for line in lines:
            seat_match = SEAT_RE.match(line)
            if seat_match:
                participant = Participant(
                    seat_no=int(seat_match.group("seat")),
                    player_name=seat_match.group("name").strip(),
                    stack=self._to_amount(seat_match.group("stack")),
                )
                if self._is_hero_name(participant.player_name):
                    participant.is_hero = True
                    hero_name = participant.player_name
                participants[participant.player_name] = participant
                ordered_participants.append(participant)
                continue

            button_match = BUTTON_RE.search(line)
            if button_match:
                table_name = (
                    button_match.group("quoted_table") or button_match.group("plain_table") or ""
                ).strip()
                button_seat = int(button_match.group("button"))
                continue

            set_dealer_match = SET_DEALER_RE.match(line)
            if set_dealer_match:
                button_seat = int(set_dealer_match.group("seat"))
                continue

            dealt_match = DEALT_RE.match(line)
            if dealt_match:
                hero_name = dealt_match.group("name").strip()
                cards = cards_to_text(parse_cards(dealt_match.group("cards")))
                participant = participants.get(hero_name)
                if participant:
                    participant.is_hero = True
                    participant.hole_cards = cards
                continue

            spot_dealt_match = SPOT_DEALT_RE.match(line)
            if spot_dealt_match:
                player_name = spot_dealt_match.group("name").strip()
                cards = cards_to_text(parse_cards(spot_dealt_match.group("cards")))
                participant = participants.get(player_name)
                if participant:
                    participant.hole_cards = cards
                    if self._is_hero_name(player_name):
                        participant.is_hero = True
                        hero_name = player_name
                elif self._is_hero_name(player_name):
                    hero_name = player_name
                continue

            next_street = self._street_from_marker(line)
            if next_street:
                current_street = next_street
                marker_cards = parse_cards(line)
                if marker_cards:
                    board_cards = marker_cards
                continue

            if current_street == Street.SUMMARY:
                continue

            action = self._parse_action_line(line, current_street, len(actions) + 1)
            if action:
                actions.append(action)
                if action.actor in participants and action.action_type == ActionType.COLLECT:
                    participant = participants[action.actor]
                    participant.net_result = (participant.net_result or 0) + (action.amount or 0)

        if not table_name:
            table_name = self._parse_table_from_header(header)

        return ParsedHand(
            hand_id=f"bovada:{hand_number}",
            bovada_hand_number=hand_number,
            hand_hash=hand_hash,
            raw_text=raw_text,
            source_site="bovada",
            game_type=game_type,
            stakes=stakes,
            table_name=table_name,
            button_seat=button_seat,
            started_at_text=started_at_text,
            board=cards_to_text(board_cards) if board_cards else None,
            hero_name=hero_name,
            participants=ordered_participants,
            actions=actions,
            parser_version=PARSER_VERSION,
        )

    def _street_from_marker(self, line: str) -> Street | None:
        upper = line.upper()
        if upper.startswith("*** HOLE CARDS ***"):
            return Street.PREFLOP
        if upper.startswith("*** FLOP ***"):
            return Street.FLOP
        if upper.startswith("*** TURN ***"):
            return Street.TURN
        if upper.startswith("*** RIVER ***"):
            return Street.RIVER
        if upper.startswith("*** SHOW DOWN ***"):
            return Street.SHOWDOWN
        if upper.startswith("*** SUMMARY ***"):
            return Street.SUMMARY
        return None

    def _parse_action_line(self, line: str, street: Street, sequence_no: int) -> Action | None:
        if ":" not in line:
            return self._parse_non_actor_action(line, street, sequence_no)

        actor, text = line.split(":", 1)
        actor = actor.strip()
        text = text.strip()
        lowered = text.lower()

        if lowered.startswith("posts small blind"):
            return self._action(sequence_no, street, actor, ActionType.POST_SMALL_BLIND, text, line)
        if lowered.startswith("small blind"):
            return self._action(sequence_no, street, actor, ActionType.POST_SMALL_BLIND, text, line)
        if lowered.startswith("posts big blind"):
            return self._action(sequence_no, street, actor, ActionType.POST_BIG_BLIND, text, line)
        if lowered.startswith("big blind"):
            return self._action(sequence_no, street, actor, ActionType.POST_BIG_BLIND, text, line)
        if lowered.startswith("posts chip"):
            return self._action(sequence_no, street, actor, ActionType.POST_CHIP, text, line)
        if lowered.startswith("posts the ante") or lowered.startswith("posts ante"):
            return self._action(sequence_no, street, actor, ActionType.ANTE, text, line)
        if lowered.startswith("posts straddle"):
            return self._action(sequence_no, street, actor, ActionType.STRADDLE, text, line)
        if lowered.startswith("folds"):
            return Action(sequence_no, street, actor, ActionType.FOLD, raw_line=line)
        if lowered.startswith("checks"):
            return Action(sequence_no, street, actor, ActionType.CHECK, raw_line=line)
        if lowered.startswith("calls"):
            return self._action(sequence_no, street, actor, ActionType.CALL, text, line)
        if lowered.startswith("bets"):
            return self._action(sequence_no, street, actor, ActionType.BET, text, line)
        if lowered.startswith("raises"):
            amount, raise_to = self._parse_raise(text)
            return Action(sequence_no, street, actor, ActionType.RAISE, amount, raise_to, line)
        if "all-in" in lowered or "all in" in lowered:
            amount, raise_to = self._parse_raise(text)
            return Action(sequence_no, street, actor, ActionType.ALL_IN, amount, raise_to, line)
        if lowered.startswith("shows"):
            return Action(sequence_no, street, actor, ActionType.SHOW, raw_line=line)
        if lowered.startswith("showdown"):
            return Action(sequence_no, street, actor, ActionType.SHOW, raw_line=line)
        if lowered.startswith("mucks"):
            return Action(sequence_no, street, actor, ActionType.MUCK, raw_line=line)
        if lowered.startswith("does not show"):
            return Action(sequence_no, street, actor, ActionType.MUCK, raw_line=line)
        if lowered.startswith("return uncalled portion of bet"):
            return self._action(sequence_no, street, actor, ActionType.RETURN_UNCALLED, text, line)
        if lowered.startswith("hand result"):
            return self._action(sequence_no, street, actor, ActionType.COLLECT, text, line)
        if lowered.startswith("collected") or " collected " in lowered:
            return self._action(sequence_no, street, actor, ActionType.COLLECT, text, line)
        return None

    def _parse_non_actor_action(self, line: str, street: Street, sequence_no: int) -> Action | None:
        lowered = line.lower()
        if lowered.startswith("uncalled bet"):
            amount = self._first_amount(line)
            return Action(sequence_no, street, None, ActionType.RETURN_UNCALLED, amount, None, line)
        if " collected " in lowered and "from pot" in lowered:
            actor = line.split(" collected ", 1)[0].strip()
            amount = self._first_amount(line)
            return Action(sequence_no, street, actor, ActionType.COLLECT, amount, None, line)
        return None

    def _action(
        self,
        sequence_no: int,
        street: Street,
        actor: str | None,
        action_type: ActionType,
        text: str,
        raw_line: str,
    ) -> Action:
        return Action(sequence_no, street, actor, action_type, self._first_amount(text), None, raw_line)

    def _parse_raise(self, text: str) -> tuple[float | None, float | None]:
        amounts = [self._to_amount(value) for value in AMOUNT_RE.findall(text)]
        if len(amounts) >= 2:
            return amounts[0], amounts[1]
        if len(amounts) == 1:
            return None, amounts[0]
        return None, None

    def _first_amount(self, text: str) -> float | None:
        match = AMOUNT_RE.search(text)
        return self._to_amount(match.group(1)) if match else None

    def _to_amount(self, value: str | None) -> float | None:
        if value is None:
            return None
        return float(value.replace(",", ""))

    def _parse_game_type(self, header: str) -> str | None:
        lowered = header.lower()
        if "hold" in lowered and "no limit" in lowered:
            return "holdem_no_limit"
        if "hold" in lowered:
            return "holdem"
        return None

    def _parse_stakes(self, header: str) -> str | None:
        match = re.search(r"\(\$?[\d.]+/\$?[\d.]+[^)]*\)", header)
        return match.group(0).strip("()") if match else None

    def _parse_started_at_text(self, header: str) -> str | None:
        if " - " not in header:
            return None
        return header.rsplit(" - ", 1)[-1].strip()

    def _parse_table_from_header(self, header: str) -> str | None:
        match = re.search(r"\bTBL\s*#?([\w.-]+)", header, re.IGNORECASE)
        return match.group(1) if match else None

    def _is_hero_name(self, name: str) -> bool:
        return "[ME]" in name.upper()
