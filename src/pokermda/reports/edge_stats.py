"""Edge-oriented poker statistics derived from normalized Bovada actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


POSITION_ORDER = ["UTG", "MP", "CO", "BTN", "SB", "BB", "UNKNOWN"]
NON_BB_POSITION_ORDER = ["UTG", "MP", "CO", "BTN", "SB", "UNKNOWN"]
GROUP_ORDER = ["hero", "pool_non_hero"]

DECISION_ACTIONS = {"fold", "check", "call", "bet", "raise", "all_in"}
COMMIT_ACTIONS = {
    "ante",
    "post_small_blind",
    "post_big_blind",
    "post_chip",
    "straddle",
    "call",
    "bet",
    "raise",
    "all_in",
}
ENTERING_ACTIONS = {"call", "bet", "raise", "all_in"}
POSTFLOP_AGGRESSIVE_ACTIONS = {"bet", "raise", "all_in"}


@dataclass(slots=True)
class ParticipantRow:
    participant_id: str
    hand_id: str
    player_name_raw: str
    position_raw: str | None
    position: str
    is_hero: bool
    hole_cards: str | None

    @property
    def group(self) -> str:
        return "hero" if self.is_hero else "pool_non_hero"


@dataclass(slots=True)
class ActionRow:
    hand_id: str
    action_no: int
    street: str
    actor: str | None
    action_type: str
    amount: float | None
    raise_to: float | None
    raw_line: str


class RateCounter:
    def __init__(self) -> None:
        self.opportunities = 0
        self.successes = 0

    def add(self, success: bool) -> None:
        self.opportunities += 1
        if success:
            self.successes += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunities": self.opportunities,
            "successes": self.successes,
            "pct": _pct(self.successes, self.opportunities),
        }


class EvCounter:
    def __init__(self) -> None:
        self.hands = 0
        self.total_net_bb = 0.0
        self.profitable_hands = 0

    def add(self, net_bb: float) -> None:
        self.hands += 1
        self.total_net_bb += net_bb
        if net_bb > 0:
            self.profitable_hands += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "hands": self.hands,
            "total_net_bb": round(self.total_net_bb, 2),
            "avg_net_bb": round(self.total_net_bb / self.hands, 2) if self.hands else 0.0,
            "profitable_pct": _pct(self.profitable_hands, self.hands),
        }


class RiverCallCounter:
    def __init__(self) -> None:
        self.calls = 0
        self.showdown_calls = 0
        self.winning_calls = 0
        self.total_call_bb = 0.0
        self.total_net_bb = 0.0
        self.showdown_net_bb = 0.0

    def add(self, call_bb: float, net_bb: float, went_showdown: bool) -> None:
        self.calls += 1
        self.total_call_bb += call_bb
        self.total_net_bb += net_bb
        if went_showdown:
            self.showdown_calls += 1
            self.showdown_net_bb += net_bb
            if net_bb > 0:
                self.winning_calls += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "calls": self.calls,
            "showdown_calls": self.showdown_calls,
            "winning_showdown_calls": self.winning_calls,
            "total_call_bb": round(self.total_call_bb, 2),
            "total_net_bb": round(self.total_net_bb, 2),
            "river_call_efficiency": round(self.total_net_bb / self.total_call_bb, 2)
            if self.total_call_bb
            else 0.0,
            "showdown_net_bb": round(self.showdown_net_bb, 2),
            "bluff_catch_win_pct": _pct(self.winning_calls, self.showdown_calls),
        }


def build_edge_stats(connection) -> dict[str, Any]:
    """Build edge-oriented stats from currently normalized Bovada actions."""
    participants = _load_participants(connection)
    actions = _load_actions(connection)
    hands = _load_hands(connection)

    participants_by_hand: dict[str, list[ParticipantRow]] = {}
    participant_by_actor: dict[str, dict[str, ParticipantRow]] = {}
    for participant in participants:
        participants_by_hand.setdefault(participant.hand_id, []).append(participant)
        participant_by_actor.setdefault(participant.hand_id, {})[participant.player_name_raw] = participant

    actions_by_hand: dict[str, list[ActionRow]] = {}
    for action in actions:
        actions_by_hand.setdefault(action.hand_id, []).append(action)

    context = _empty_context()
    for hand_id, hand_participants in participants_by_hand.items():
        hand_actions = actions_by_hand.get(hand_id, [])
        actor_map = participant_by_actor.get(hand_id, {})
        hand_board = hands.get(hand_id, {})
        hand_bb = _hand_big_blind(hand_actions)
        net_by_actor = _net_bb_by_actor(hand_actions, hand_bb)
        showdown_by_actor = _showdown_by_actor(hand_actions)
        collected_by_actor = _collected_by_actor(hand_actions)

        _accumulate_preflop(
            context,
            hand_actions=hand_actions,
            actor_map=actor_map,
            net_by_actor=net_by_actor,
        )
        _accumulate_postflop_aggression(context, hand_actions=hand_actions, actor_map=actor_map)
        _accumulate_showdown_quality(
            context,
            hand_participants=hand_participants,
            hand_actions=hand_actions,
            hand_board=hand_board,
            net_by_actor=net_by_actor,
            showdown_by_actor=showdown_by_actor,
            collected_by_actor=collected_by_actor,
        )
        _accumulate_river_calls(
            context,
            hand_actions=hand_actions,
            actor_map=actor_map,
            hand_bb=hand_bb,
            net_by_actor=net_by_actor,
            showdown_by_actor=showdown_by_actor,
        )

    return {
        "definitions": _definitions(),
        "profile": {
            "hands": len(hands),
            "participants_dealt": len(participants),
            "actions": len(actions),
        },
        "preflop": {
            "rfi_by_position": _rate_rows(
                context["rfi_by_position"],
                positions=NON_BB_POSITION_ORDER,
            ),
            "cold_call_by_position": _rate_rows(context["cold_call_by_position"]),
            "three_bet_by_position": _rate_rows(context["three_bet_by_position"]),
            "three_bet_by_position_vs_open": _rate_vs_position_rows(
                context["three_bet_by_position_vs_open"]
            ),
            "fold_to_three_bet_by_position": _rate_rows(
                context["fold_to_three_bet_by_position"]
            ),
        },
        "postflop": {
            "aggression": _named_rate_rows(context["postflop_aggression"]),
            "showdown_quality": _named_rate_rows(context["showdown_quality"]),
            "river_calls": _river_call_rows(context["river_calls"]),
        },
        "blind_play": {
            "sb_first_action_ev": _ev_rows(context["sb_first_action_ev"]),
        },
    }


def _load_participants(connection) -> list[ParticipantRow]:
    rows = connection.execute(
        """
        SELECT participant_id, hand_id, player_name_raw, position, is_hero, hole_cards
        FROM participants
        WHERE hole_cards IS NOT NULL
        ORDER BY hand_id, seat_no
        """
    ).fetchall()
    return [
        ParticipantRow(
            participant_id=row[0],
            hand_id=row[1],
            player_name_raw=row[2],
            position_raw=row[3],
            position=_normalize_position(row[3]),
            is_hero=bool(row[4]),
            hole_cards=row[5],
        )
        for row in rows
    ]


def _load_actions(connection) -> list[ActionRow]:
    rows = connection.execute(
        """
        SELECT hand_id, action_no_global, street, actor, action_type, amount, raise_to, raw_line
        FROM actions
        ORDER BY hand_id, action_no_global
        """
    ).fetchall()
    return [
        ActionRow(
            hand_id=row[0],
            action_no=int(row[1]),
            street=row[2],
            actor=row[3],
            action_type=row[4],
            amount=row[5],
            raise_to=row[6],
            raw_line=row[7] or "",
        )
        for row in rows
    ]


def _load_hands(connection) -> dict[str, dict[str, Any]]:
    rows = connection.execute(
        """
        SELECT hand_id, board_flop, board_turn, board_river, board
        FROM hands
        """
    ).fetchall()
    return {
        row[0]: {
            "board_flop": row[1],
            "board_turn": row[2],
            "board_river": row[3],
            "board": row[4],
        }
        for row in rows
    }


def _empty_context() -> dict[str, Any]:
    return {
        "rfi_by_position": {},
        "cold_call_by_position": {},
        "three_bet_by_position": {},
        "three_bet_by_position_vs_open": {},
        "fold_to_three_bet_by_position": {},
        "postflop_aggression": {},
        "showdown_quality": {},
        "river_calls": {},
        "sb_first_action_ev": {},
    }


def _accumulate_preflop(
    context: dict[str, Any],
    *,
    hand_actions: list[ActionRow],
    actor_map: dict[str, ParticipantRow],
    net_by_actor: dict[str, float],
) -> None:
    preflop = [action for action in hand_actions if action.street == "preflop"]
    first_decisions = _first_decisions(preflop)
    raise_actions = [
        action for action in preflop if action.actor in actor_map and _is_raise_action(action)
    ]
    open_raise = raise_actions[0] if raise_actions else None
    three_bet = raise_actions[1] if len(raise_actions) >= 2 else None
    opener = actor_map.get(open_raise.actor) if open_raise else None
    opener_position = opener.position if opener else None

    for actor, decision in first_decisions.items():
        participant = actor_map.get(actor)
        if not participant:
            continue
        prior_actions = [action for action in preflop if action.action_no < decision.action_no]
        prior_entries = [
            action
            for action in prior_actions
            if action.actor in actor_map and _is_voluntary_entry(action)
        ]
        prior_raises = [
            action
            for action in prior_actions
            if action.actor in actor_map and _is_raise_action(action)
        ]

        if not prior_entries and participant.position != "BB" and decision.action_type != "check":
            _rate(context["rfi_by_position"], participant.group, participant.position).add(
                _is_raise_action(decision)
            )

        if prior_raises:
            _rate(context["cold_call_by_position"], participant.group, participant.position).add(
                decision.action_type == "call"
            )

        if (
            open_raise
            and opener_position
            and actor != open_raise.actor
            and decision.action_no > open_raise.action_no
            and (three_bet is None or decision.action_no <= three_bet.action_no)
        ):
            success = _is_raise_action(decision)
            _rate(context["three_bet_by_position"], participant.group, participant.position).add(success)
            _rate_vs(
                context["three_bet_by_position_vs_open"],
                participant.group,
                participant.position,
                opener_position,
            ).add(success)

        if participant.position == "SB":
            category = _sb_first_action_category(decision, bool(prior_raises))
            _ev(context["sb_first_action_ev"], participant.group, category).add(
                net_by_actor.get(actor, 0.0)
            )

    if open_raise and three_bet and opener:
        opener_response = _next_decision_after(preflop, open_raise.actor, three_bet.action_no)
        if opener_response:
            _rate(context["fold_to_three_bet_by_position"], opener.group, opener.position).add(
                opener_response.action_type == "fold"
            )


def _accumulate_postflop_aggression(
    context: dict[str, Any],
    *,
    hand_actions: list[ActionRow],
    actor_map: dict[str, ParticipantRow],
) -> None:
    preflop_raises = [
        action
        for action in hand_actions
        if action.street == "preflop" and action.actor in actor_map and _is_raise_action(action)
    ]
    if not preflop_raises:
        return
    pfa_action = preflop_raises[-1]
    pfa = actor_map.get(pfa_action.actor)
    if not pfa:
        return

    flop_success = _street_bet_opportunity(
        context,
        "flop_cbet",
        pfa,
        pfa_action.actor,
        hand_actions,
        "flop",
    )
    if not flop_success:
        return
    turn_success = _street_bet_opportunity(
        context,
        "turn_barrel",
        pfa,
        pfa_action.actor,
        hand_actions,
        "turn",
    )
    if not turn_success:
        return
    _street_bet_opportunity(
        context,
        "river_barrel",
        pfa,
        pfa_action.actor,
        hand_actions,
        "river",
    )


def _accumulate_showdown_quality(
    context: dict[str, Any],
    *,
    hand_participants: list[ParticipantRow],
    hand_actions: list[ActionRow],
    hand_board: dict[str, Any],
    net_by_actor: dict[str, float],
    showdown_by_actor: dict[str, bool],
    collected_by_actor: dict[str, bool],
) -> None:
    hand_has_flop = _hand_has_flop(hand_actions, hand_board)
    if not hand_has_flop:
        return
    preflop_folded = {
        action.actor
        for action in hand_actions
        if action.street == "preflop" and action.action_type == "fold" and action.actor
    }
    for participant in hand_participants:
        if participant.player_name_raw in preflop_folded:
            continue
        saw_flop_key = participant.group
        saw_flop = True
        went_showdown = showdown_by_actor.get(participant.player_name_raw, False)
        won_money = net_by_actor.get(participant.player_name_raw, 0.0) > 0
        collected = collected_by_actor.get(participant.player_name_raw, False)

        _named_rate(context["showdown_quality"], saw_flop_key, "WTSD").add(
            saw_flop and went_showdown
        )
        if went_showdown:
            _named_rate(context["showdown_quality"], participant.group, "W$SD").add(
                won_money or collected
            )
        _named_rate(context["showdown_quality"], saw_flop_key, "WWSF").add(saw_flop and won_money)


def _accumulate_river_calls(
    context: dict[str, Any],
    *,
    hand_actions: list[ActionRow],
    actor_map: dict[str, ParticipantRow],
    hand_bb: float,
    net_by_actor: dict[str, float],
    showdown_by_actor: dict[str, bool],
) -> None:
    for action in hand_actions:
        if action.street != "river" or action.action_type != "call" or not action.actor:
            continue
        participant = actor_map.get(action.actor)
        if not participant:
            continue
        call_bb = _safe_amount(action) / hand_bb
        net_bb = net_by_actor.get(action.actor, 0.0)
        went_showdown = showdown_by_actor.get(action.actor, False)
        _river_call(context["river_calls"], participant.group, participant.position).add(
            call_bb,
            net_bb,
            went_showdown,
        )


def _street_bet_opportunity(
    context: dict[str, Any],
    stat_name: str,
    participant: ParticipantRow,
    actor: str,
    hand_actions: list[ActionRow],
    street: str,
) -> bool:
    street_actions = [action for action in hand_actions if action.street == street]
    first_decision = next(
        (
            action
            for action in street_actions
            if action.actor == actor and action.action_type in DECISION_ACTIONS
        ),
        None,
    )
    if not first_decision:
        return False
    prior_aggression = any(
        action.actor != actor
        and action.action_no < first_decision.action_no
        and action.action_type in POSTFLOP_AGGRESSIVE_ACTIONS
        for action in street_actions
    )
    if prior_aggression:
        return False
    success = first_decision.action_type in {"bet", "all_in"}
    _named_rate(context["postflop_aggression"], participant.group, stat_name).add(success)
    return success


def _first_decisions(actions: list[ActionRow]) -> dict[str, ActionRow]:
    first: dict[str, ActionRow] = {}
    for action in actions:
        if not action.actor or action.actor in first or action.action_type not in DECISION_ACTIONS:
            continue
        first[action.actor] = action
    return first


def _next_decision_after(actions: list[ActionRow], actor: str | None, action_no: int) -> ActionRow | None:
    if not actor:
        return None
    for action in actions:
        if (
            action.actor == actor
            and action.action_no > action_no
            and action.action_type in DECISION_ACTIONS
        ):
            return action
    return None


def _is_raise_action(action: ActionRow) -> bool:
    if action.action_type == "raise":
        return True
    return action.action_type == "all_in" and "raise" in action.raw_line.lower()


def _is_voluntary_entry(action: ActionRow) -> bool:
    if action.action_type in {"call", "bet"}:
        return True
    if action.action_type == "raise":
        return True
    return action.action_type == "all_in"


def _sb_first_action_category(decision: ActionRow, facing_prior_raise: bool) -> str:
    if decision.action_type == "call":
        return "call_vs_raise" if facing_prior_raise else "limp_complete"
    if decision.action_type == "raise" or _is_raise_action(decision):
        return "raise"
    if decision.action_type == "fold":
        return "fold"
    if decision.action_type == "check":
        return "check_option"
    return decision.action_type


def _hand_big_blind(actions: list[ActionRow]) -> float:
    amounts = [
        _safe_amount(action)
        for action in actions
        if action.street == "preflop" and action.action_type == "post_big_blind"
    ]
    return max(amounts) if amounts else 1.0


def _net_bb_by_actor(actions: list[ActionRow], hand_bb: float) -> dict[str, float]:
    net_by_actor: dict[str, float] = {}
    for action in actions:
        if not action.actor:
            continue
        amount = _safe_amount(action)
        if action.action_type in COMMIT_ACTIONS:
            net_by_actor[action.actor] = net_by_actor.get(action.actor, 0.0) - amount / hand_bb
        elif action.action_type in {"collect", "return_uncalled"}:
            net_by_actor[action.actor] = net_by_actor.get(action.actor, 0.0) + amount / hand_bb
    return net_by_actor


def _showdown_by_actor(actions: list[ActionRow]) -> dict[str, bool]:
    return {
        action.actor: True
        for action in actions
        if action.actor and action.action_type == "show"
    }


def _collected_by_actor(actions: list[ActionRow]) -> dict[str, bool]:
    return {
        action.actor: True
        for action in actions
        if action.actor and action.action_type == "collect"
    }


def _hand_has_flop(actions: list[ActionRow], hand_board: dict[str, Any]) -> bool:
    if any(action.street in {"flop", "turn", "river", "showdown"} for action in actions):
        return True
    board = hand_board.get("board") or ""
    return len(board.split()) >= 3 or bool(hand_board.get("board_flop"))


def _safe_amount(action: ActionRow) -> float:
    if action.amount is not None:
        return float(action.amount)
    if action.raise_to is not None:
        return float(action.raise_to)
    return 0.0


def _normalize_position(position: str | None) -> str:
    if not position:
        return "UNKNOWN"
    clean = position.replace(" [ME]", "").strip()
    mapping = {
        "Dealer": "BTN",
        "Small Blind": "SB",
        "Big Blind": "BB",
        "UTG": "UTG",
        "UTG+1": "MP",
        "UTG+2": "CO",
    }
    return mapping.get(clean, clean)


def _rate(store: dict[tuple[str, str], RateCounter], group: str, position: str) -> RateCounter:
    key = (group, position)
    if key not in store:
        store[key] = RateCounter()
    return store[key]


def _rate_vs(
    store: dict[tuple[str, str, str], RateCounter],
    group: str,
    position: str,
    vs_position: str,
) -> RateCounter:
    key = (group, position, vs_position)
    if key not in store:
        store[key] = RateCounter()
    return store[key]


def _named_rate(
    store: dict[tuple[str, str], RateCounter],
    group: str,
    stat_name: str,
) -> RateCounter:
    key = (group, stat_name)
    if key not in store:
        store[key] = RateCounter()
    return store[key]


def _ev(store: dict[tuple[str, str], EvCounter], group: str, category: str) -> EvCounter:
    key = (group, category)
    if key not in store:
        store[key] = EvCounter()
    return store[key]


def _river_call(
    store: dict[tuple[str, str], RiverCallCounter],
    group: str,
    position: str,
) -> RiverCallCounter:
    key = (group, position)
    if key not in store:
        store[key] = RiverCallCounter()
    return store[key]


def _rate_rows(
    store: dict[tuple[str, str], RateCounter],
    *,
    positions: list[str] | None = None,
) -> list[dict[str, Any]]:
    allowed_positions = positions or POSITION_ORDER
    rows: list[dict[str, Any]] = []
    for group in GROUP_ORDER:
        for position in allowed_positions:
            counter = store.get((group, position), RateCounter())
            row = {"group": group, "position": position}
            row.update(counter.to_dict())
            rows.append(row)
    return rows


def _rate_vs_position_rows(store: dict[tuple[str, str, str], RateCounter]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    keys = sorted(
        store,
        key=lambda item: (
            GROUP_ORDER.index(item[0]) if item[0] in GROUP_ORDER else 99,
            POSITION_ORDER.index(item[1]) if item[1] in POSITION_ORDER else 99,
            POSITION_ORDER.index(item[2]) if item[2] in POSITION_ORDER else 99,
        ),
    )
    for group, position, vs_position in keys:
        counter = store[(group, position, vs_position)]
        row = {"group": group, "position": position, "vs_open_position": vs_position}
        row.update(counter.to_dict())
        rows.append(row)
    return rows


def _named_rate_rows(store: dict[tuple[str, str], RateCounter]) -> list[dict[str, Any]]:
    stat_order = ["flop_cbet", "turn_barrel", "river_barrel", "WTSD", "W$SD", "WWSF"]
    rows: list[dict[str, Any]] = []
    keys = sorted(
        store,
        key=lambda item: (
            GROUP_ORDER.index(item[0]) if item[0] in GROUP_ORDER else 99,
            stat_order.index(item[1]) if item[1] in stat_order else 99,
            item[1],
        ),
    )
    for group, stat_name in keys:
        counter = store[(group, stat_name)]
        row = {"group": group, "stat": stat_name}
        row.update(counter.to_dict())
        rows.append(row)
    return rows


def _river_call_rows(store: dict[tuple[str, str], RiverCallCounter]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group in GROUP_ORDER:
        total = RiverCallCounter()
        for position in POSITION_ORDER:
            counter = store.get((group, position))
            if counter:
                total.calls += counter.calls
                total.showdown_calls += counter.showdown_calls
                total.winning_calls += counter.winning_calls
                total.total_call_bb += counter.total_call_bb
                total.total_net_bb += counter.total_net_bb
                total.showdown_net_bb += counter.showdown_net_bb
        row = {"group": group, "position": "ALL"}
        row.update(total.to_dict())
        rows.append(row)
        for position in POSITION_ORDER:
            counter = store.get((group, position), RiverCallCounter())
            row = {"group": group, "position": position}
            row.update(counter.to_dict())
            rows.append(row)
    return rows


def _ev_rows(store: dict[tuple[str, str], EvCounter]) -> list[dict[str, Any]]:
    category_order = ["limp_complete", "call_vs_raise", "raise", "fold", "check_option"]
    rows: list[dict[str, Any]] = []
    keys = sorted(
        store,
        key=lambda item: (
            GROUP_ORDER.index(item[0]) if item[0] in GROUP_ORDER else 99,
            category_order.index(item[1]) if item[1] in category_order else 99,
            item[1],
        ),
    )
    for group, category in keys:
        counter = store[(group, category)]
        row = {"group": group, "category": category}
        row.update(counter.to_dict())
        rows.append(row)
    return rows


def _definitions() -> dict[str, str]:
    return {
        "position_map": "Dealer=BTN, Small Blind=SB, Big Blind=BB, UTG+1=MP, UTG+2=CO.",
        "bb_conversion": "Each hand is converted to bb using that hand's posted big blind amount.",
        "net_bb": "Approximate hand net: collect + returned uncalled - committed chips, divided by the hand big blind.",
        "rfi": "First voluntary preflop decision in an unopened pot; raise/all-in(raise) counts as RFI.",
        "cold_call": "First voluntary preflop decision after a prior raise; call counts as cold call.",
        "three_bet": "First voluntary preflop decision after the open raise and before any 3bet; raise/all-in(raise) counts as 3bet.",
        "fold_to_three_bet": "Open raiser's first response after the first 3bet; fold counts as fold to 3bet.",
        "flop_cbet": "Last preflop raiser's first flop decision when no one has bet before them; bet/all-in counts.",
        "turn_barrel": "Turn bet opportunity after the same player c-bet flop and no one donked before them.",
        "river_barrel": "River bet opportunity after the same player c-bet flop and barreled turn.",
        "WTSD": "Went to showdown among seats that saw a flop.",
        "W$SD": "Won money or collected after showing down.",
        "WWSF": "Won money when saw flop.",
        "river_call_efficiency": "Total hand net bb for river-call hands divided by total river call amount in bb.",
        "bluff_catch_result": "Showdown subset of river calls; win rate and net are a proxy for bluff-catch result.",
        "sb_first_action_ev": "Small Blind first voluntary preflop action bucket with approximate hand net bb.",
    }


def _pct(numerator: int | float, denominator: int | float) -> float:
    return round(100.0 * numerator / denominator, 1) if denominator else 0.0
