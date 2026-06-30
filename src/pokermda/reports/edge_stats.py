"""Edge-oriented poker statistics derived from normalized Bovada actions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pokermda.features.stake_levels import normalize_stake_level


POSITION_ORDER = ["UTG", "MP", "CO", "BTN", "SB", "BB", "UNKNOWN"]
NON_BB_POSITION_ORDER = ["UTG", "MP", "CO", "BTN", "SB", "UNKNOWN"]
GROUP_ORDER = ["hero", "pool_non_hero"]
POSTFLOP_POSITION_ORDER = ["SB", "BB", "UTG", "MP", "CO", "BTN"]
STEAL_OPEN_POSITIONS = {"CO", "BTN", "SB"}
LOW_SAMPLE_THRESHOLD = 20
MAX_HAND_IDS = 50

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
    stack: float | None = None

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
        self.count = 0
        self.net_bb = 0.0
        self.opportunity_net_bb = 0.0
        self.hand_ids: list[str] = []
        self.opportunity_hand_ids: list[str] = []

    def add(self, success: bool, *, net_bb: float = 0.0, hand_id: str | None = None) -> None:
        self.opportunities += 1
        self.opportunity_net_bb += net_bb
        _append_hand_id(self.opportunity_hand_ids, hand_id)
        if success:
            self.count += 1
            self.net_bb += net_bb
            _append_hand_id(self.hand_ids, hand_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunities": self.opportunities,
            "count": self.count,
            "successes": self.count,
            "frequency": _pct(self.count, self.opportunities),
            "pct": _pct(self.count, self.opportunities),
            "net_bb": round(self.net_bb, 2),
            "opportunity_net_bb": round(self.opportunity_net_bb, 2),
            "bb_per_opportunity": _per(self.opportunity_net_bb, self.opportunities),
            "bb_per_count": _per(self.net_bb, self.count),
            "bb_per_100": _per(self.opportunity_net_bb * 100, self.opportunities),
            "hand_ids": self.hand_ids,
            "opportunity_hand_ids": self.opportunity_hand_ids,
            "sample_warning": _sample_warning(self.opportunities),
        }


class EvCounter:
    def __init__(self) -> None:
        self.hands = 0
        self.total_net_bb = 0.0
        self.profitable_hands = 0
        self.hand_ids: list[str] = []

    def add(self, net_bb: float, *, hand_id: str | None = None) -> None:
        self.hands += 1
        self.total_net_bb += net_bb
        if net_bb > 0:
            self.profitable_hands += 1
        _append_hand_id(self.hand_ids, hand_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunities": self.hands,
            "count": self.hands,
            "frequency": 100.0 if self.hands else 0.0,
            "hands": self.hands,
            "net_bb": round(self.total_net_bb, 2),
            "total_net_bb": round(self.total_net_bb, 2),
            "bb_per_hand": round(self.total_net_bb / self.hands, 2) if self.hands else 0.0,
            "bb_per_opportunity": round(self.total_net_bb / self.hands, 2) if self.hands else 0.0,
            "avg_net_bb": round(self.total_net_bb / self.hands, 2) if self.hands else 0.0,
            "bb_per_100": round(100.0 * self.total_net_bb / self.hands, 1) if self.hands else 0.0,
            "profitable_pct": _pct(self.profitable_hands, self.hands),
            "hand_ids": self.hand_ids,
            "sample_warning": _sample_warning(self.hands),
        }


class RiverCallCounter:
    def __init__(self) -> None:
        self.calls = 0
        self.showdown_calls = 0
        self.winning_calls = 0
        self.total_call_bb = 0.0
        self.total_net_bb = 0.0
        self.showdown_net_bb = 0.0
        self.hand_ids: list[str] = []

    def add(
        self,
        call_bb: float,
        net_bb: float,
        went_showdown: bool,
        *,
        hand_id: str | None = None,
    ) -> None:
        self.calls += 1
        self.total_call_bb += call_bb
        self.total_net_bb += net_bb
        _append_hand_id(self.hand_ids, hand_id)
        if went_showdown:
            self.showdown_calls += 1
            self.showdown_net_bb += net_bb
            if net_bb > 0:
                self.winning_calls += 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunities": self.calls,
            "count": self.calls,
            "frequency": 100.0 if self.calls else 0.0,
            "calls": self.calls,
            "showdown_calls": self.showdown_calls,
            "winning_showdown_calls": self.winning_calls,
            "net_bb": round(self.total_net_bb, 2),
            "total_call_bb": round(self.total_call_bb, 2),
            "total_net_bb": round(self.total_net_bb, 2),
            "bb_per_opportunity": round(self.total_net_bb / self.calls, 2) if self.calls else 0.0,
            "bb_per_count": round(self.total_net_bb / self.calls, 2) if self.calls else 0.0,
            "bb_per_100": round(100.0 * self.total_net_bb / self.calls, 1) if self.calls else 0.0,
            "river_call_efficiency": round(self.total_net_bb / self.total_call_bb, 2)
            if self.total_call_bb
            else 0.0,
            "showdown_net_bb": round(self.showdown_net_bb, 2),
            "bluff_catch_win_pct": _pct(self.winning_calls, self.showdown_calls),
            "hand_ids": self.hand_ids,
            "sample_warning": _sample_warning(self.calls),
        }


class FrequencyEvCounter:
    def __init__(self) -> None:
        self.hands = 0
        self.net_bb = 0.0
        self.vpip = 0
        self.pfr = 0
        self.three_bet = 0
        self.hand_ids: list[str] = []

    def add(
        self,
        *,
        net_bb: float,
        vpip: bool = False,
        pfr: bool = False,
        three_bet: bool = False,
        hand_id: str | None = None,
    ) -> None:
        self.hands += 1
        self.net_bb += net_bb
        if vpip:
            self.vpip += 1
        if pfr:
            self.pfr += 1
        if three_bet:
            self.three_bet += 1
        _append_hand_id(self.hand_ids, hand_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunities": self.hands,
            "count": self.hands,
            "hands": self.hands,
            "frequency": 100.0 if self.hands else 0.0,
            "vpip_count": self.vpip,
            "vpip_frequency": _pct(self.vpip, self.hands),
            "pfr_count": self.pfr,
            "pfr_frequency": _pct(self.pfr, self.hands),
            "vpip_pfr_gap": round(_pct(self.vpip, self.hands) - _pct(self.pfr, self.hands), 1),
            "three_bet_count": self.three_bet,
            "three_bet_frequency": _pct(self.three_bet, self.hands),
            "net_bb": round(self.net_bb, 2),
            "bb_per_hand": round(self.net_bb / self.hands, 2) if self.hands else 0.0,
            "bb_per_opportunity": round(self.net_bb / self.hands, 2) if self.hands else 0.0,
            "bb_per_100": round(100.0 * self.net_bb / self.hands, 1) if self.hands else 0.0,
            "hand_ids": self.hand_ids,
            "sample_warning": _sample_warning(self.hands),
        }


def build_edge_stats(connection, level: str | None = None) -> dict[str, Any]:
    """Build edge-oriented stats from currently normalized Bovada actions."""
    normalized_level = normalize_stake_level(level)
    participants = _load_participants(connection, normalized_level)
    actions = _load_actions(connection, normalized_level)
    hands = _load_hands(connection, normalized_level)

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
        pot_before_by_action = _pot_before_by_action(hand_actions, hand_bb)
        hero = next((participant for participant in hand_participants if participant.is_hero), None)

        _accumulate_hand_level_reports(
            context,
            hand_id=hand_id,
            hand_participants=hand_participants,
            hand_actions=hand_actions,
            actor_map=actor_map,
            hand_board=hand_board,
            hand_bb=hand_bb,
            net_by_actor=net_by_actor,
            showdown_by_actor=showdown_by_actor,
            hero=hero,
        )
        _accumulate_preflop(
            context,
            hand_id=hand_id,
            hand_actions=hand_actions,
            actor_map=actor_map,
            net_by_actor=net_by_actor,
        )
        _accumulate_postflop_aggression(
            context,
            hand_id=hand_id,
            hand_actions=hand_actions,
            actor_map=actor_map,
            hand_bb=hand_bb,
            net_by_actor=net_by_actor,
            pot_before_by_action=pot_before_by_action,
        )
        _accumulate_postflop_response_reports(
            context,
            hand_id=hand_id,
            hand_actions=hand_actions,
            actor_map=actor_map,
            net_by_actor=net_by_actor,
            pot_before_by_action=pot_before_by_action,
        )
        _accumulate_showdown_quality(
            context,
            hand_id=hand_id,
            hand_participants=hand_participants,
            hand_actions=hand_actions,
            hand_board=hand_board,
            net_by_actor=net_by_actor,
            showdown_by_actor=showdown_by_actor,
            collected_by_actor=collected_by_actor,
        )
        _accumulate_river_calls(
            context,
            hand_id=hand_id,
            hand_actions=hand_actions,
            actor_map=actor_map,
            hand_bb=hand_bb,
            net_by_actor=net_by_actor,
            showdown_by_actor=showdown_by_actor,
            pot_before_by_action=pot_before_by_action,
        )

    return _build_output(
        context,
        level=normalized_level,
        hands=len(hands),
        participants=len(participants),
        actions=len(actions),
    )


def _load_participants(connection, level: str | None) -> list[ParticipantRow]:
    level_join = _level_join_sql(level, "p")
    level_where = _level_where_sql(level)
    rows = connection.execute(
        f"""
        SELECT p.participant_id, p.hand_id, p.player_name_raw, p.position, p.is_hero, p.hole_cards, p.stack
        FROM participants p
        {level_join}
        WHERE p.hole_cards IS NOT NULL
        {level_where}
        ORDER BY p.hand_id, p.seat_no
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
            stack=row[6],
        )
        for row in rows
    ]


def _load_actions(connection, level: str | None) -> list[ActionRow]:
    level_join = _level_join_sql(level, "a")
    level_where = _level_where_sql(level)
    rows = connection.execute(
        f"""
        SELECT a.hand_id, a.action_no_global, a.street, a.actor, a.action_type, a.amount, a.raise_to, a.raw_line
        FROM actions a
        {level_join}
        {level_where}
        ORDER BY a.hand_id, a.action_no_global
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


def _load_hands(connection, level: str | None) -> dict[str, dict[str, Any]]:
    level_where = _level_where_sql(level, alias="h", prefix="WHERE")
    rows = connection.execute(
        f"""
        SELECT h.hand_id, h.board_flop, h.board_turn, h.board_river, h.board,
               h.import_file_id, h.table_size, h.played_at,
               COALESCE(i.raw_file_path, i.source_path) AS raw_file_path,
               h.stake_level
        FROM hands h
        LEFT JOIN import_files i ON h.import_file_id = i.import_file_id
        {level_where}
        """
    ).fetchall()
    return {
        row[0]: {
            "board_flop": row[1],
            "board_turn": row[2],
            "board_river": row[3],
            "board": row[4],
            "import_file_id": row[5],
            "table_size": row[6],
            "played_at": row[7],
            "raw_file_path": row[8],
            "stake_level": row[9],
        }
        for row in rows
    }


def _build_output(
    context: dict[str, Any],
    *,
    level: str | None,
    hands: int,
    participants: int,
    actions: int,
) -> dict[str, Any]:
    return {
        "definitions": _definitions(),
        "profile": {
            "level": level or "ALL",
            "hands": hands,
            "participants_dealt": participants,
            "actions": actions,
        },
        "results": {
            "overall_winrate": _ev_rows(context["overall"]),
            "redline_blueline": _ev_rows(context["redline_blueline"]),
            "pot_type_ev": _generic_ev_rows(context["pot_type_ev"], ["group", "pot_type"]),
            "biggest_hands": _big_pot_rows(context["big_pots"]),
            "session_report": _generic_ev_rows(context["session_report"], ["group", "session"]),
            "table_size_report": _generic_ev_rows(
                context["table_size_report"],
                ["group", "table_size"],
            ),
        },
        "position": {
            "winrate_by_position": _frequency_ev_rows(
                context["winrate_by_position"],
                positions=POSITION_ORDER,
            ),
            "vpip_pfr_gap_by_position": _frequency_ev_rows(
                context["vpip_pfr_gap_by_position"],
                positions=POSITION_ORDER,
            ),
        },
        "preflop": {
            "rfi_by_position": _rate_rows(
                context["rfi_by_position"],
                positions=NON_BB_POSITION_ORDER,
            ),
            "rfi_hand_class_breakdown": _generic_ev_rows(
                context["rfi_hand_class"],
                ["group", "position", "hand_class"],
            ),
            "cold_call_by_position": _rate_rows(context["cold_call_by_position"]),
            "entry_action_ev_by_position": _generic_ev_rows(
                context["entry_action_ev_by_position"],
                ["group", "position", "entry_action"],
            ),
            "btn_cold_call_by_opener": _rate_vs_position_rows(
                context["btn_cold_call_by_opener"]
            ),
            "btn_cold_call_by_hand_class": _generic_ev_rows(
                context["btn_cold_call_by_hand_class"],
                ["group", "opener_position", "hand_class"],
            ),
            "three_bet_by_position": _rate_rows(context["three_bet_by_position"]),
            "three_bet_by_position_vs_open": _rate_vs_position_rows(
                context["three_bet_by_position_vs_open"]
            ),
            "three_bet_hand_class": _generic_ev_rows(
                context["three_bet_hand_class"],
                ["group", "position", "opener_position", "hand_class"],
            ),
            "three_bet_pot_result": _generic_ev_rows(
                context["three_bet_pot_result"],
                ["group", "spot"],
            ),
            "fold_to_three_bet_by_position": _rate_rows(
                context["fold_to_three_bet_by_position"]
            ),
            "facing_three_bet_response": _generic_rate_rows(
                context["facing_three_bet_response"],
                ["group", "position", "response"],
            ),
            "four_bet": _rate_vs_position_rows(context["four_bet"]),
            "squeeze": _rate_vs_position_rows(context["squeeze"]),
            "steal": _rate_rows(context["steal"], positions=["CO", "BTN", "SB", "UNKNOWN"]),
            "fold_to_steal": _generic_rate_rows(
                context["fold_to_steal"],
                ["group", "blind", "opener_position", "response"],
            ),
            "bb_defense_vs_steal": _generic_rate_rows(
                context["bb_defense_vs_steal"],
                ["group", "opener_position", "response"],
            ),
            "sb_first_action_vs_opener": _generic_ev_rows(
                context["sb_first_action_vs_opener"],
                ["group", "action", "opener_position"],
            ),
        },
        "postflop": {
            "aggression": _named_rate_rows(context["postflop_aggression"]),
            "cbet_deep": _generic_rate_rows(context["cbet_deep"], ["group", "stat", "bucket"]),
            "cbet_tree": _generic_ev_rows(context["cbet_tree"], ["group", "result"]),
            "turn_after_cbet": _generic_rate_rows(
                context["turn_after_cbet"],
                ["group", "spot"],
            ),
            "facing_cbet": _generic_rate_rows(
                context["facing_cbet"],
                ["group", "street", "ip_oop", "response"],
            ),
            "donk_bet_report": _generic_rate_rows(
                context["donk_bet_report"],
                ["group", "street", "position"],
            ),
            "stab_vs_missed_cbet": _generic_rate_rows(
                context["stab_vs_missed_cbet"],
                ["group", "street", "ip_oop"],
            ),
            "check_raise_report": _generic_rate_rows(
                context["check_raise_report"],
                ["group", "street", "position"],
            ),
            "postflop_sizing_report": _generic_ev_rows(
                context["postflop_sizing_report"],
                ["group", "street", "size_bucket"],
            ),
            "facing_bet_size_defense": _generic_rate_rows(
                context["facing_bet_size_defense"],
                ["group", "street", "size_bucket", "response"],
            ),
            "showdown_quality": _named_rate_rows(context["showdown_quality"]),
            "river_calls": _river_call_rows(context["river_calls"]),
        },
        "river": {
            "river_calls_by_size": _generic_river_call_rows(
                context["river_calls_by_size"],
                ["group", "size_bucket"],
            ),
            "river_calls_by_line": _generic_river_call_rows(
                context["river_calls_by_line"],
                ["group", "line"],
            ),
            "river_deep": _generic_rate_rows(context["river_deep"], ["group", "stat", "result"]),
        },
        "blind_play": {
            "sb_first_action_ev": _ev_rows(context["sb_first_action_ev"]),
            "sb_first_action_vs_opener": _generic_ev_rows(
                context["sb_first_action_vs_opener"],
                ["group", "action", "opener_position"],
            ),
            "bb_defense_vs_steal": _generic_rate_rows(
                context["bb_defense_vs_steal"],
                ["group", "opener_position", "response"],
            ),
        },
        "hand_classes": {
            "starting_hand_matrix": _frequency_ev_rows(context["starting_hand_matrix"]),
            "hand_class_ev_by_position": _generic_ev_rows(
                context["hand_class_ev_by_position"],
                ["group", "position", "hand_class"],
            ),
            "dominated_hand_leaks": _generic_ev_rows(
                context["dominated_hand_leaks"],
                ["group", "position", "hand_class"],
            ),
            "pocket_pair_report": _generic_ev_rows(
                context["pocket_pair_report"],
                ["group", "position", "pair_class"],
            ),
            "suited_connector_report": _generic_ev_rows(
                context["suited_connector_report"],
                ["group", "position", "hand_class"],
            ),
        },
        "special_spots": {
            "limped_pot_report": _generic_ev_rows(
                context["limped_pot_report"],
                ["group", "position", "action", "limper_bucket"],
            ),
            "isolation_raise_report": _generic_rate_rows(
                context["isolation_raise_report"],
                ["group", "position", "limper_bucket"],
            ),
            "multiway_pot_report": _generic_ev_rows(
                context["multiway_pot_report"],
                ["group", "role"],
            ),
            "stack_depth_report": _generic_ev_rows(
                context["stack_depth_report"],
                ["group", "stack_depth"],
            ),
        },
        "leak_flags": _leak_flags(context),
        "unsupported_or_approximate": _unsupported_or_approximate(),
    }


def _empty_context() -> dict[str, Any]:
    return {
        "overall": {},
        "redline_blueline": {},
        "winrate_by_position": {},
        "vpip_pfr_gap_by_position": {},
        "pot_type_ev": {},
        "entry_action_ev_by_position": {},
        "rfi_by_position": {},
        "rfi_hand_class": {},
        "cold_call_by_position": {},
        "btn_cold_call_by_opener": {},
        "btn_cold_call_by_hand_class": {},
        "three_bet_by_position": {},
        "three_bet_by_position_vs_open": {},
        "three_bet_hand_class": {},
        "three_bet_pot_result": {},
        "fold_to_three_bet_by_position": {},
        "facing_three_bet_response": {},
        "four_bet": {},
        "squeeze": {},
        "steal": {},
        "fold_to_steal": {},
        "bb_defense_vs_steal": {},
        "postflop_aggression": {},
        "cbet_deep": {},
        "cbet_tree": {},
        "facing_cbet": {},
        "turn_after_cbet": {},
        "donk_bet_report": {},
        "stab_vs_missed_cbet": {},
        "check_raise_report": {},
        "postflop_sizing_report": {},
        "facing_bet_size_defense": {},
        "river_deep": {},
        "showdown_quality": {},
        "river_calls": {},
        "river_calls_by_size": {},
        "river_calls_by_line": {},
        "sb_first_action_ev": {},
        "sb_first_action_vs_opener": {},
        "hand_class_ev_by_position": {},
        "starting_hand_matrix": {},
        "dominated_hand_leaks": {},
        "pocket_pair_report": {},
        "suited_connector_report": {},
        "limped_pot_report": {},
        "isolation_raise_report": {},
        "multiway_pot_report": {},
        "stack_depth_report": {},
        "session_report": {},
        "table_size_report": {},
        "big_pots": {
            "winning": [],
            "losing": [],
            "over_50bb": [],
            "over_100bb": [],
            "river_calls_over_20bb": [],
            "sb_call_vs_raise": [],
            "btn_cold_call": [],
        },
    }


def _accumulate_hand_level_reports(
    context: dict[str, Any],
    *,
    hand_id: str,
    hand_participants: list[ParticipantRow],
    hand_actions: list[ActionRow],
    actor_map: dict[str, ParticipantRow],
    hand_board: dict[str, Any],
    hand_bb: float,
    net_by_actor: dict[str, float],
    showdown_by_actor: dict[str, bool],
    hero: ParticipantRow | None,
) -> None:
    preflop = [action for action in hand_actions if action.street == "preflop"]
    raise_actions = [
        action for action in preflop if action.actor in actor_map and _is_raise_action(action)
    ]
    first_decisions = _first_decisions(preflop)
    saw_flop_actors = _saw_flop_actors(hand_participants, hand_actions, hand_board)
    pot_type = _classify_pot_type(hand_actions, actor_map, saw_flop_actors)
    players_bucket = "multiway" if len(saw_flop_actors) >= 3 else "heads_up"

    for participant in hand_participants:
        actor = participant.player_name_raw
        actor_net_bb = net_by_actor.get(actor, 0.0)
        vpip = any(
            action.actor == actor
            and action.street == "preflop"
            and action.action_type in ENTERING_ACTIONS
            for action in hand_actions
        )
        pfr = any(action.actor == actor and _is_raise_action(action) for action in preflop)
        three_bet = len(raise_actions) >= 2 and raise_actions[1].actor == actor
        hand_class = _hand_class(participant.hole_cards)
        combo = _starting_hand(participant.hole_cards)

        _freq_ev(context["winrate_by_position"], participant.group, participant.position).add(
            net_bb=actor_net_bb,
            vpip=vpip,
            pfr=pfr,
            three_bet=three_bet,
            hand_id=hand_id,
        )
        _freq_ev(context["vpip_pfr_gap_by_position"], participant.group, participant.position).add(
            net_bb=actor_net_bb,
            vpip=vpip,
            pfr=pfr,
            three_bet=three_bet,
            hand_id=hand_id,
        )
        _report_ev(
            context["hand_class_ev_by_position"],
            (participant.group, participant.position, hand_class),
        ).add(actor_net_bb, hand_id=hand_id)
        _freq_ev(context["starting_hand_matrix"], participant.group, combo).add(
            net_bb=actor_net_bb,
            vpip=vpip,
            pfr=pfr,
            three_bet=three_bet,
            hand_id=hand_id,
        )
        if _is_dominated_hand_class(hand_class):
            _report_ev(
                context["dominated_hand_leaks"],
                (participant.group, participant.position, hand_class),
            ).add(actor_net_bb, hand_id=hand_id)
        if hand_class in {"medium_pair", "small_pair"}:
            _report_ev(
                context["pocket_pair_report"],
                (participant.group, participant.position, hand_class),
            ).add(actor_net_bb, hand_id=hand_id)
        if hand_class in {"suited_connector", "suited_gapper"}:
            _report_ev(
                context["suited_connector_report"],
                (participant.group, participant.position, hand_class),
            ).add(actor_net_bb, hand_id=hand_id)

        if participant.stack is not None:
            stack_depth = _stack_depth_bucket(participant.stack / hand_bb)
            _report_ev(context["stack_depth_report"], (participant.group, stack_depth)).add(
                actor_net_bb,
                hand_id=hand_id,
            )

    if hero:
        hero_net = net_by_actor.get(hero.player_name_raw, 0.0)
        hero_showdown = showdown_by_actor.get(hero.player_name_raw, False)
        _ev(context["overall"], hero.group, "overall").add(hero_net, hand_id=hand_id)
        _ev(
            context["redline_blueline"],
            hero.group,
            "showdown_winnings" if hero_showdown else "non_showdown_winnings",
        ).add(hero_net, hand_id=hand_id)
        _report_ev(context["pot_type_ev"], (hero.group, pot_type)).add(hero_net, hand_id=hand_id)
        _report_ev(context["pot_type_ev"], (hero.group, players_bucket)).add(hero_net, hand_id=hand_id)
        if hero.player_name_raw in saw_flop_actors and players_bucket == "multiway":
            role = _hero_pot_role(hero, raise_actions, first_decisions)
            _report_ev(context["multiway_pot_report"], (hero.group, role)).add(
                hero_net,
                hand_id=hand_id,
            )
        _report_ev(
            context["session_report"],
            (hero.group, _session_label(hand_board)),
        ).add(hero_net, hand_id=hand_id)
        _report_ev(
            context["table_size_report"],
            (hero.group, _table_size_bucket(hand_board.get("table_size"))),
        ).add(hero_net, hand_id=hand_id)
        pot_bb = _total_collected_bb(hand_actions, hand_bb)
        candidate = {
            "hand_id": hand_id,
            "net_bb": round(hero_net, 2),
            "pot_bb": round(pot_bb, 2),
            "position": hero.position,
            "hero_cards": hero.hole_cards,
            "board": hand_board.get("board"),
        }
        _add_sorted_candidate(context["big_pots"]["winning"], candidate, reverse=True)
        _add_sorted_candidate(context["big_pots"]["losing"], candidate, reverse=False)
        if pot_bb >= 50:
            _add_sorted_candidate(context["big_pots"]["over_50bb"], candidate, reverse=True)
        if pot_bb >= 100:
            _add_sorted_candidate(context["big_pots"]["over_100bb"], candidate, reverse=True)


def _accumulate_preflop(
    context: dict[str, Any],
    *,
    hand_id: str,
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
    four_bet = raise_actions[2] if len(raise_actions) >= 3 else None
    opener = actor_map.get(open_raise.actor) if open_raise else None
    opener_position = opener.position if opener else None
    three_bettor = actor_map.get(three_bet.actor) if three_bet else None

    for actor, decision in first_decisions.items():
        participant = actor_map.get(actor)
        if not participant:
            continue
        actor_net_bb = net_by_actor.get(actor, 0.0)
        hand_class = _hand_class(participant.hole_cards)
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
        prior_calls_after_open = [
            action
            for action in prior_actions
            if open_raise
            and action.action_no > open_raise.action_no
            and action.action_type == "call"
            and action.actor in actor_map
        ]

        if not prior_entries and participant.position != "BB" and decision.action_type != "check":
            rfi_success = _is_raise_action(decision)
            _rate(context["rfi_by_position"], participant.group, participant.position).add(
                rfi_success,
                net_bb=actor_net_bb,
                hand_id=hand_id,
            )
            _entry_ev(context, participant.group, participant.position, "rfi").add(
                actor_net_bb,
                hand_id=hand_id,
            )
            if rfi_success:
                _report_ev(
                    context["rfi_hand_class"],
                    (participant.group, participant.position, hand_class),
                ).add(actor_net_bb, hand_id=hand_id)
            if participant.position in STEAL_OPEN_POSITIONS:
                _rate(context["steal"], participant.group, participant.position).add(
                    rfi_success,
                    net_bb=actor_net_bb,
                    hand_id=hand_id,
                )

        if prior_entries and not prior_raises:
            limper_bucket = "vs_1_limper" if len(prior_entries) == 1 else "vs_multiple_limpers"
            _report_rate(
                context["isolation_raise_report"],
                (participant.group, participant.position, limper_bucket),
            ).add(_is_raise_action(decision), net_bb=actor_net_bb, hand_id=hand_id)
            if decision.action_type == "call":
                limp_action = "sb_complete" if participant.position == "SB" else "overlimp"
                _report_ev(
                    context["limped_pot_report"],
                    (participant.group, participant.position, limp_action, limper_bucket),
                ).add(actor_net_bb, hand_id=hand_id)
            elif _is_raise_action(decision):
                _report_ev(
                    context["limped_pot_report"],
                    (participant.group, participant.position, "iso_raise", limper_bucket),
                ).add(actor_net_bb, hand_id=hand_id)

        if prior_raises:
            _rate(context["cold_call_by_position"], participant.group, participant.position).add(
                decision.action_type == "call",
                net_bb=actor_net_bb,
                hand_id=hand_id,
            )
            if participant.position == "BTN" and opener_position:
                _rate_vs(
                    context["btn_cold_call_by_opener"],
                    participant.group,
                    "BTN",
                    opener_position,
                ).add(decision.action_type == "call", net_bb=actor_net_bb, hand_id=hand_id)
            if decision.action_type == "call":
                _entry_ev(context, participant.group, participant.position, "cold_call").add(
                    actor_net_bb,
                    hand_id=hand_id,
                )
                if participant.position == "BTN" and opener_position:
                    _report_ev(
                        context["btn_cold_call_by_hand_class"],
                        (participant.group, opener_position, hand_class),
                    ).add(actor_net_bb, hand_id=hand_id)
                    _add_big_pot_candidate(
                        context["big_pots"]["btn_cold_call"],
                        hand_id=hand_id,
                        participant=participant,
                        net_bb=actor_net_bb,
                        extra={"opener_position": opener_position, "hand_class": hand_class},
                    )
                if participant.position == "SB" and opener_position:
                    _add_big_pot_candidate(
                        context["big_pots"]["sb_call_vs_raise"],
                        hand_id=hand_id,
                        participant=participant,
                        net_bb=actor_net_bb,
                        extra={"opener_position": opener_position, "hand_class": hand_class},
                    )

        if (
            open_raise
            and opener_position
            and actor != open_raise.actor
            and decision.action_no > open_raise.action_no
            and (three_bet is None or decision.action_no <= three_bet.action_no)
        ):
            success = _is_raise_action(decision)
            _rate(context["three_bet_by_position"], participant.group, participant.position).add(
                success,
                net_bb=actor_net_bb,
                hand_id=hand_id,
            )
            _rate_vs(
                context["three_bet_by_position_vs_open"],
                participant.group,
                participant.position,
                opener_position,
            ).add(success, net_bb=actor_net_bb, hand_id=hand_id)
            if success:
                _entry_ev(context, participant.group, participant.position, "three_bet").add(
                    actor_net_bb,
                    hand_id=hand_id,
                )
                _report_ev(
                    context["three_bet_hand_class"],
                    (participant.group, participant.position, opener_position, hand_class),
                ).add(actor_net_bb, hand_id=hand_id)
            if open_raise and prior_calls_after_open:
                _rate_vs(
                    context["squeeze"],
                    participant.group,
                    participant.position,
                    opener_position,
                ).add(success, net_bb=actor_net_bb, hand_id=hand_id)

        if participant.position == "SB":
            category = _sb_first_action_category(decision, bool(prior_raises))
            _ev(context["sb_first_action_ev"], participant.group, category).add(
                actor_net_bb,
                hand_id=hand_id,
            )
            facing = opener_position if prior_raises and opener_position else "limped_or_unopened"
            _report_ev(
                context["sb_first_action_vs_opener"],
                (participant.group, category, facing),
            ).add(actor_net_bb, hand_id=hand_id)

        if participant.position == "BB" and open_raise and opener_position in STEAL_OPEN_POSITIONS:
            action_category = _preflop_response_category(decision)
            for category in ("fold", "call", "3bet"):
                _report_rate(
                    context["bb_defense_vs_steal"],
                    (participant.group, opener_position, category),
                ).add(action_category == category, net_bb=actor_net_bb, hand_id=hand_id)
                _report_rate(
                    context["fold_to_steal"],
                    (participant.group, "BB", opener_position, category),
                ).add(action_category == category, net_bb=actor_net_bb, hand_id=hand_id)

    if open_raise and three_bet and opener:
        opener_response = _next_decision_after(preflop, open_raise.actor, three_bet.action_no)
        if opener_response:
            opener_net_bb = net_by_actor.get(open_raise.actor or "", 0.0)
            response_category = _preflop_response_category(opener_response)
            _rate(context["fold_to_three_bet_by_position"], opener.group, opener.position).add(
                opener_response.action_type == "fold",
                net_bb=opener_net_bb,
                hand_id=hand_id,
            )
            for category in ("fold", "call", "4bet"):
                _report_rate(
                    context["facing_three_bet_response"],
                    (opener.group, opener.position, category),
                ).add(response_category == category, net_bb=opener_net_bb, hand_id=hand_id)
            _rate_vs(
                context["four_bet"],
                opener.group,
                opener.position,
                three_bettor.position if three_bettor else "UNKNOWN",
            ).add(response_category == "4bet", net_bb=opener_net_bb, hand_id=hand_id)

    if three_bet and three_bettor:
        threebettor_net = net_by_actor.get(three_bet.actor or "", 0.0)
        ip_bucket = _ip_bucket(three_bettor, actor_map.values())
        _report_ev(
            context["three_bet_pot_result"],
            (three_bettor.group, f"threebettor_{ip_bucket}"),
        ).add(threebettor_net, hand_id=hand_id)
        if four_bet:
            fourbettor = actor_map.get(four_bet.actor)
            if fourbettor:
                _report_ev(
                    context["three_bet_pot_result"],
                    (fourbettor.group, "four_bet_pot"),
                ).add(net_by_actor.get(four_bet.actor or "", 0.0), hand_id=hand_id)


def _accumulate_postflop_aggression(
    context: dict[str, Any],
    *,
    hand_id: str,
    hand_actions: list[ActionRow],
    actor_map: dict[str, ParticipantRow],
    hand_bb: float,
    net_by_actor: dict[str, float],
    pot_before_by_action: dict[int, float],
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
        hand_id=hand_id,
        net_bb=net_by_actor.get(pfa_action.actor, 0.0),
        pot_before_by_action=pot_before_by_action,
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
        hand_id=hand_id,
        net_bb=net_by_actor.get(pfa_action.actor, 0.0),
        pot_before_by_action=pot_before_by_action,
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
        hand_id=hand_id,
        net_bb=net_by_actor.get(pfa_action.actor, 0.0),
        pot_before_by_action=pot_before_by_action,
    )


def _accumulate_postflop_response_reports(
    context: dict[str, Any],
    *,
    hand_id: str,
    hand_actions: list[ActionRow],
    actor_map: dict[str, ParticipantRow],
    net_by_actor: dict[str, float],
    pot_before_by_action: dict[int, float],
) -> None:
    pfa_action = _last_preflop_raise(hand_actions, actor_map)
    pfa_actor = pfa_action.actor if pfa_action else None
    pfa = actor_map.get(pfa_actor) if pfa_actor else None
    flop_cbet = _pfa_street_bet(hand_actions, pfa_actor, "flop")
    flop_cbet_called = bool(flop_cbet and _aggressive_action_result(flop_cbet, _street_actions(hand_actions, "flop"))["called"])

    for street in ("flop", "turn", "river"):
        street_actions = _street_actions(hand_actions, street)
        if not street_actions:
            continue
        first_aggressive = next(
            (
                action
                for action in street_actions
                if action.actor in actor_map and action.action_type in POSTFLOP_AGGRESSIVE_ACTIONS
            ),
            None,
        )
        if first_aggressive:
            aggressor = actor_map.get(first_aggressive.actor or "")
            size_bucket = _sizing_bucket(
                _safe_amount(first_aggressive),
                pot_before_by_action.get(first_aggressive.action_no, 0.0),
            )
            if aggressor:
                _report_ev(
                    context["postflop_sizing_report"],
                    (aggressor.group, street, size_bucket),
                ).add(net_by_actor.get(aggressor.player_name_raw, 0.0), hand_id=hand_id)

            if pfa and first_aggressive.actor != pfa_actor:
                pfa_first_decision = _first_street_decision(street_actions, pfa_actor)
                if not pfa_first_decision or first_aggressive.action_no < pfa_first_decision.action_no:
                    donk_actor = actor_map.get(first_aggressive.actor or "")
                    if donk_actor:
                        _report_rate(
                            context["donk_bet_report"],
                            (donk_actor.group, street, donk_actor.position),
                        ).add(True, net_bb=net_by_actor.get(donk_actor.player_name_raw, 0.0), hand_id=hand_id)

            if pfa and first_aggressive.actor == pfa_actor:
                for defender, response in _responses_to_aggression(
                    street_actions,
                    first_aggressive,
                    actor_map,
                ):
                    response_category = _postflop_response_category(response)
                    defender_net = net_by_actor.get(defender.player_name_raw, 0.0)
                    ip_bucket = _ip_bucket(defender, actor_map.values())
                    for category in ("fold", "call", "raise"):
                        _report_rate(
                            context["facing_cbet"],
                            (defender.group, street, ip_bucket, category),
                        ).add(
                            response_category == category,
                            net_bb=defender_net,
                            hand_id=hand_id,
                        )
                        _report_rate(
                            context["facing_bet_size_defense"],
                            (defender.group, street, size_bucket, category),
                        ).add(
                            response_category == category,
                            net_bb=defender_net,
                            hand_id=hand_id,
                        )

        if pfa:
            pfa_first = _first_street_decision(street_actions, pfa_actor)
            if pfa_first and pfa_first.action_type == "check":
                stab = next(
                    (
                        action
                        for action in street_actions
                        if action.action_no > pfa_first.action_no
                        and action.actor in actor_map
                        and action.actor != pfa_actor
                        and action.action_type in POSTFLOP_AGGRESSIVE_ACTIONS
                    ),
                    None,
                )
                if stab:
                    stabber = actor_map.get(stab.actor or "")
                    if stabber:
                        _report_rate(
                            context["stab_vs_missed_cbet"],
                            (stabber.group, street, _ip_bucket(stabber, actor_map.values())),
                        ).add(True, net_bb=net_by_actor.get(stabber.player_name_raw, 0.0), hand_id=hand_id)

        for participant in actor_map.values():
            check_action = next(
                (
                    action
                    for action in street_actions
                    if action.actor == participant.player_name_raw and action.action_type == "check"
                ),
                None,
            )
            if not check_action:
                continue
            later_raise = next(
                (
                    action
                    for action in street_actions
                    if action.actor == participant.player_name_raw
                    and action.action_no > check_action.action_no
                    and _is_raise_action(action)
                ),
                None,
            )
            faced_bet = any(
                action.actor != participant.player_name_raw
                and action.action_no > check_action.action_no
                and (not later_raise or action.action_no < later_raise.action_no)
                and action.action_type in {"bet", "all_in"}
                for action in street_actions
            )
            if faced_bet:
                _report_rate(
                    context["check_raise_report"],
                    (participant.group, street, participant.position),
                ).add(
                    later_raise is not None,
                    net_bb=net_by_actor.get(participant.player_name_raw, 0.0),
                    hand_id=hand_id,
                )

    if pfa and flop_cbet_called:
        turn_actions = _street_actions(hand_actions, "turn")
        pfa_turn = _first_street_decision(turn_actions, pfa_actor)
        if pfa_turn:
            pfa_net = net_by_actor.get(pfa.player_name_raw, 0.0)
            for category in ("bet", "check"):
                _report_rate(
                    context["turn_after_cbet"],
                    (pfa.group, f"turn_after_flop_cbet_called_{category}"),
                ).add(
                    (category == "bet" and pfa_turn.action_type in {"bet", "all_in"})
                    or (category == "check" and pfa_turn.action_type == "check"),
                    net_bb=pfa_net,
                    hand_id=hand_id,
                )


def _accumulate_showdown_quality(
    context: dict[str, Any],
    *,
    hand_id: str,
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
            saw_flop and went_showdown,
            net_bb=net_by_actor.get(participant.player_name_raw, 0.0),
            hand_id=hand_id,
        )
        if went_showdown:
            _named_rate(context["showdown_quality"], participant.group, "W$SD").add(
                won_money or collected,
                net_bb=net_by_actor.get(participant.player_name_raw, 0.0),
                hand_id=hand_id,
            )
        _named_rate(context["showdown_quality"], saw_flop_key, "WWSF").add(
            saw_flop and won_money,
            net_bb=net_by_actor.get(participant.player_name_raw, 0.0),
            hand_id=hand_id,
        )


def _accumulate_river_calls(
    context: dict[str, Any],
    *,
    hand_id: str,
    hand_actions: list[ActionRow],
    actor_map: dict[str, ParticipantRow],
    hand_bb: float,
    net_by_actor: dict[str, float],
    showdown_by_actor: dict[str, bool],
    pot_before_by_action: dict[int, float],
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
            hand_id=hand_id,
        )
        facing_bet = _previous_aggressive_action(hand_actions, action)
        size_bucket = _sizing_bucket(
            _safe_amount(facing_bet) if facing_bet else _safe_amount(action),
            pot_before_by_action.get((facing_bet or action).action_no, 0.0),
        )
        line_bucket = _river_line_bucket(hand_actions, facing_bet.actor if facing_bet else None)
        _river_call(
            context["river_calls_by_size"],
            participant.group,
            size_bucket,
        ).add(call_bb, net_bb, went_showdown, hand_id=hand_id)
        _river_call(
            context["river_calls_by_line"],
            participant.group,
            line_bucket,
        ).add(call_bb, net_bb, went_showdown, hand_id=hand_id)
        if participant.is_hero and call_bb >= 20:
            _add_big_pot_candidate(
                context["big_pots"]["river_calls_over_20bb"],
                hand_id=hand_id,
                participant=participant,
                net_bb=net_bb,
                extra={"call_bb": round(call_bb, 2), "size_bucket": size_bucket, "line": line_bucket},
            )


def _street_bet_opportunity(
    context: dict[str, Any],
    stat_name: str,
    participant: ParticipantRow,
    actor: str,
    hand_actions: list[ActionRow],
    street: str,
    *,
    hand_id: str,
    net_bb: float,
    pot_before_by_action: dict[int, float],
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
    _named_rate(context["postflop_aggression"], participant.group, stat_name).add(
        success,
        net_bb=net_bb,
        hand_id=hand_id,
    )
    pot_type = _postflop_pot_type(hand_actions)
    ip_bucket = _ip_bucket(participant, _active_participants_for_street(hand_actions, street, actor))
    players_bucket = _players_bucket(hand_actions)
    for bucket in (pot_type, ip_bucket, players_bucket):
        _report_rate(
            context["cbet_deep"],
            (participant.group, stat_name, bucket),
        ).add(success, net_bb=net_bb, hand_id=hand_id)
    if street == "flop" and success:
        result = _aggressive_action_result(first_decision, street_actions)
        size_bucket = _sizing_bucket(
            _safe_amount(first_decision),
            pot_before_by_action.get(first_decision.action_no, 0.0),
        )
        for tree_bucket in (
            result["primary"],
            f"size_{size_bucket}",
            f"{pot_type}_{ip_bucket}_{players_bucket}",
        ):
            _report_ev(context["cbet_tree"], (participant.group, tree_bucket)).add(
                net_bb,
                hand_id=hand_id,
            )
    if street in {"turn", "river"} and success:
        result = _aggressive_action_result(first_decision, street_actions)
        _report_rate(
            context["river_deep" if street == "river" else "turn_after_cbet"],
            (participant.group, stat_name, result["primary"]),
        ).add(True, net_bb=net_bb, hand_id=hand_id)
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


def _level_join_sql(level: str | None, source_alias: str) -> str:
    if level is None:
        return ""
    return f"JOIN hands h ON h.hand_id = {source_alias}.hand_id"


def _level_where_sql(level: str | None, prefix: str = "AND", alias: str = "h") -> str:
    if level is None:
        return ""
    return f"{prefix} {alias}.stake_level = '{level}'"


def _pot_before_by_action(actions: list[ActionRow], hand_bb: float) -> dict[int, float]:
    pot = 0.0
    pot_before: dict[int, float] = {}
    for action in actions:
        pot_before[action.action_no] = max(0.0, pot)
        amount_bb = _safe_amount(action) / hand_bb
        if action.action_type in COMMIT_ACTIONS:
            pot += amount_bb
        elif action.action_type == "return_uncalled":
            pot -= amount_bb
    return pot_before


def _report_rate(store: dict[tuple[Any, ...], RateCounter], key: tuple[Any, ...]) -> RateCounter:
    if key not in store:
        store[key] = RateCounter()
    return store[key]


def _report_ev(store: dict[tuple[Any, ...], EvCounter], key: tuple[Any, ...]) -> EvCounter:
    if key not in store:
        store[key] = EvCounter()
    return store[key]


def _freq_ev(
    store: dict[tuple[str, str], FrequencyEvCounter],
    group: str,
    key_value: str,
) -> FrequencyEvCounter:
    key = (group, key_value)
    if key not in store:
        store[key] = FrequencyEvCounter()
    return store[key]


def _entry_ev(
    context: dict[str, Any],
    group: str,
    position: str,
    action: str,
) -> EvCounter:
    return _report_ev(context["entry_action_ev_by_position"], (group, position, action))


def _generic_rate_rows(
    store: dict[tuple[Any, ...], RateCounter],
    columns: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(store, key=_sort_key):
        row = _row_from_key(columns, key)
        row.update(store[key].to_dict())
        rows.append(row)
    return rows


def _generic_ev_rows(
    store: dict[tuple[Any, ...], EvCounter],
    columns: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(store, key=_sort_key):
        row = _row_from_key(columns, key)
        row.update(store[key].to_dict())
        rows.append(row)
    return rows


def _frequency_ev_rows(
    store: dict[tuple[str, str], FrequencyEvCounter],
    *,
    positions: list[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if positions:
        for group in GROUP_ORDER:
            for position in positions:
                counter = store.get((group, position), FrequencyEvCounter())
                row = {"group": group, "position": position}
                row.update(counter.to_dict())
                rows.append(row)
        return rows
    for group, key_value in sorted(store, key=_sort_key):
        counter = store[(group, key_value)]
        row = {"group": group, "hand": key_value}
        row.update(counter.to_dict())
        rows.append(row)
    return rows


def _generic_river_call_rows(
    store: dict[tuple[str, str], RiverCallCounter],
    columns: list[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(store, key=_sort_key):
        row = _row_from_key(columns, key)
        row.update(store[key].to_dict())
        rows.append(row)
    return rows


def _row_from_key(columns: list[str], key: tuple[Any, ...]) -> dict[str, Any]:
    row = {column: value for column, value in zip(columns, key)}
    if len(key) > len(columns):
        for index, value in enumerate(key[len(columns) :], start=len(columns) + 1):
            row[f"key_{index}"] = value
    return row


def _sort_key(key: tuple[Any, ...]) -> tuple[tuple[int, str], ...]:
    translated: list[tuple[int, str]] = []
    for item in key:
        if item in GROUP_ORDER:
            translated.append((0, str(GROUP_ORDER.index(item))))
        elif item in POSITION_ORDER:
            translated.append((1, str(POSITION_ORDER.index(item))))
        else:
            translated.append((2, str(item)))
    return tuple(translated)


def _big_pot_rows(big_pots: dict[str, list[dict[str, Any]]]) -> dict[str, list[dict[str, Any]]]:
    output: dict[str, list[dict[str, Any]]] = {}
    for key, rows in big_pots.items():
        reverse = key != "losing"
        output[key] = sorted(rows, key=lambda row: row.get("net_bb", 0.0), reverse=reverse)[:20]
    return output


def _add_big_pot_candidate(
    rows: list[dict[str, Any]],
    *,
    hand_id: str,
    participant: ParticipantRow,
    net_bb: float,
    extra: dict[str, Any] | None = None,
) -> None:
    row = {
        "hand_id": hand_id,
        "position": participant.position,
        "hero_cards": participant.hole_cards,
        "net_bb": round(net_bb, 2),
    }
    if extra:
        row.update(extra)
    rows.append(row)


def _add_sorted_candidate(rows: list[dict[str, Any]], row: dict[str, Any], *, reverse: bool) -> None:
    rows.append(row)
    rows.sort(key=lambda candidate: candidate.get("net_bb", 0.0), reverse=reverse)
    del rows[20:]


def _saw_flop_actors(
    participants: list[ParticipantRow],
    actions: list[ActionRow],
    hand_board: dict[str, Any],
) -> set[str]:
    if not _hand_has_flop(actions, hand_board):
        return set()
    preflop_folders = {
        action.actor
        for action in actions
        if action.street == "preflop" and action.action_type == "fold" and action.actor
    }
    return {participant.player_name_raw for participant in participants if participant.player_name_raw not in preflop_folders}


def _classify_pot_type(
    actions: list[ActionRow],
    actor_map: dict[str, ParticipantRow],
    saw_flop_actors: set[str],
) -> str:
    preflop_raises = [
        action for action in actions if action.street == "preflop" and action.actor in actor_map and _is_raise_action(action)
    ]
    if len(preflop_raises) >= 3:
        return "4bet_pot"
    if len(preflop_raises) >= 2:
        return "3bet_pot"
    if len(preflop_raises) == 1:
        return "single_raised_pot_multiway" if len(saw_flop_actors) >= 3 else "single_raised_pot_heads_up"
    return "limped_pot_multiway" if len(saw_flop_actors) >= 3 else "limped_pot_heads_up"


def _hero_pot_role(
    hero: ParticipantRow,
    raise_actions: list[ActionRow],
    first_decisions: dict[str, ActionRow],
) -> str:
    if len(raise_actions) >= 2 and raise_actions[1].actor == hero.player_name_raw:
        return "hero_3bettor_multiway"
    if raise_actions and raise_actions[-1].actor == hero.player_name_raw:
        return "hero_pfr_multiway"
    first = first_decisions.get(hero.player_name_raw)
    if first and first.action_type == "call":
        return "hero_caller_multiway"
    return "hero_other_multiway"


def _session_label(hand_board: dict[str, Any]) -> str:
    raw_path = hand_board.get("raw_file_path")
    if raw_path:
        return str(raw_path).split("/")[-1]
    return str(hand_board.get("import_file_id") or "unknown_session")


def _table_size_bucket(table_size: Any) -> str:
    if table_size is None:
        return "unknown"
    try:
        size = int(table_size)
    except (TypeError, ValueError):
        return "unknown"
    if size >= 6:
        return "6-handed"
    if size == 5:
        return "5-handed"
    return "4-handed_or_less"


def _total_collected_bb(actions: list[ActionRow], hand_bb: float) -> float:
    return sum(_safe_amount(action) / hand_bb for action in actions if action.action_type == "collect")


def _stack_depth_bucket(stack_bb: float) -> str:
    if stack_bb < 50:
        return "<50bb"
    if stack_bb < 80:
        return "50-80bb"
    if stack_bb <= 120:
        return "80-120bb"
    if stack_bb <= 200:
        return "120-200bb"
    return "200bb+"


def _last_preflop_raise(actions: list[ActionRow], actor_map: dict[str, ParticipantRow]) -> ActionRow | None:
    raises = [
        action for action in actions if action.street == "preflop" and action.actor in actor_map and _is_raise_action(action)
    ]
    return raises[-1] if raises else None


def _street_actions(actions: list[ActionRow], street: str) -> list[ActionRow]:
    return [action for action in actions if action.street == street]


def _pfa_street_bet(actions: list[ActionRow], pfa_actor: str | None, street: str) -> ActionRow | None:
    if not pfa_actor:
        return None
    street_actions = _street_actions(actions, street)
    first_decision = _first_street_decision(street_actions, pfa_actor)
    if first_decision and first_decision.action_type in {"bet", "all_in"}:
        return first_decision
    return None


def _first_street_decision(actions: list[ActionRow], actor: str | None) -> ActionRow | None:
    if not actor:
        return None
    return next(
        (action for action in actions if action.actor == actor and action.action_type in DECISION_ACTIONS),
        None,
    )


def _responses_to_aggression(
    street_actions: list[ActionRow],
    aggressive_action: ActionRow,
    actor_map: dict[str, ParticipantRow],
) -> list[tuple[ParticipantRow, ActionRow]]:
    responses: list[tuple[ParticipantRow, ActionRow]] = []
    seen: set[str] = set()
    for action in street_actions:
        if action.action_no <= aggressive_action.action_no or not action.actor:
            continue
        if action.actor == aggressive_action.actor or action.actor in seen:
            continue
        if action.actor not in actor_map or action.action_type not in DECISION_ACTIONS:
            continue
        responses.append((actor_map[action.actor], action))
        seen.add(action.actor)
    return responses


def _postflop_response_category(action: ActionRow) -> str:
    if action.action_type == "fold":
        return "fold"
    if action.action_type == "call":
        return "call"
    if action.action_type in {"raise", "all_in"}:
        return "raise"
    return action.action_type


def _preflop_response_category(action: ActionRow) -> str:
    if action.action_type == "fold":
        return "fold"
    if action.action_type == "call":
        return "call"
    if _is_raise_action(action):
        return "4bet"
    return action.action_type


def _aggressive_action_result(action: ActionRow, street_actions: list[ActionRow]) -> dict[str, Any]:
    later = [
        later_action
        for later_action in street_actions
        if later_action.action_no > action.action_no and later_action.actor != action.actor
    ]
    called = any(later_action.action_type == "call" for later_action in later)
    raised = any(_is_raise_action(later_action) for later_action in later)
    folded = any(later_action.action_type == "fold" for later_action in later)
    if raised:
        primary = "villain_raises"
    elif called:
        primary = "villain_calls"
    elif folded:
        primary = "villain_folds"
    else:
        primary = "no_response_seen"
    return {"primary": primary, "called": called, "raised": raised, "folded": folded}


def _previous_aggressive_action(actions: list[ActionRow], response: ActionRow) -> ActionRow | None:
    candidates = [
        action
        for action in actions
        if action.street == response.street
        and action.action_no < response.action_no
        and action.actor != response.actor
        and action.action_type in POSTFLOP_AGGRESSIVE_ACTIONS
    ]
    return candidates[-1] if candidates else None


def _river_line_bucket(actions: list[ActionRow], bettor: str | None) -> str:
    if not bettor:
        return "unknown_line"
    street_bet = {
        street: any(
            action.actor == bettor and action.street == street and action.action_type in POSTFLOP_AGGRESSIVE_ACTIONS
            for action in actions
        )
        for street in ("flop", "turn", "river")
    }
    if street_bet["flop"] and street_bet["turn"] and street_bet["river"]:
        return "bet_bet_bet"
    if not street_bet["flop"] and street_bet["turn"] and street_bet["river"]:
        return "check_bet_bet"
    if street_bet["flop"] and not street_bet["turn"] and street_bet["river"]:
        return "bet_check_bet"
    if street_bet["river"]:
        return "river_bet_other_line"
    return "unknown_line"


def _sizing_bucket(amount_bb: float, pot_before_bb: float) -> str:
    if amount_bb <= 0:
        return "unknown"
    if pot_before_bb <= 0:
        return "no_pot_before"
    pct = amount_bb / pot_before_bb
    if pct <= 0.33:
        return "<=33pct_pot"
    if pct <= 0.50:
        return "34-50pct_pot"
    if pct <= 0.75:
        return "51-75pct_pot"
    if pct <= 1.0:
        return "76-100pct_pot"
    return "overbet"


def _postflop_pot_type(actions: list[ActionRow]) -> str:
    raise_count = sum(1 for action in actions if action.street == "preflop" and _is_raise_action(action))
    if raise_count >= 2:
        return "3bet_pot"
    if raise_count == 1:
        return "single_raised_pot"
    return "limped_pot"


def _players_bucket(actions: list[ActionRow]) -> str:
    flop_actors = {
        action.actor
        for action in actions
        if action.street == "flop" and action.actor and action.action_type in DECISION_ACTIONS
    }
    return "multiway" if len(flop_actors) >= 3 else "heads_up"


def _active_participants_for_street(
    actions: list[ActionRow],
    street: str,
    fallback_actor: str | None,
) -> list[ParticipantRow]:
    _ = street
    _ = fallback_actor
    actors = {
        action.actor
        for action in actions
        if action.actor and action.action_type in DECISION_ACTIONS
    }
    return [ParticipantRow("", "", actor, None, _normalize_position(actor), False, None) for actor in actors]


def _ip_bucket(participant: ParticipantRow, participants: Any) -> str:
    positions = [getattr(other, "position", "UNKNOWN") for other in participants]
    known = [position for position in positions if position in POSTFLOP_POSITION_ORDER]
    if participant.position not in POSTFLOP_POSITION_ORDER or not known:
        return "unknown_ip"
    max_position = max(known, key=POSTFLOP_POSITION_ORDER.index)
    return "IP" if participant.position == max_position else "OOP"


def _starting_hand(hole_cards: str | None) -> str:
    parsed = _parse_hole_cards(hole_cards)
    if not parsed:
        return "unknown"
    rank_1, suit_1, rank_2, suit_2 = parsed
    order = "AKQJT98765432"
    ranks = sorted([rank_1, rank_2], key=order.index)
    if rank_1 == rank_2:
        return rank_1 + rank_2
    suffix = "s" if suit_1 == suit_2 else "o"
    return "".join(ranks) + suffix


def _hand_class(hole_cards: str | None) -> str:
    parsed = _parse_hole_cards(hole_cards)
    if not parsed:
        return "unknown"
    rank_1, suit_1, rank_2, suit_2 = parsed
    combo = _starting_hand(hole_cards)
    suited = suit_1 == suit_2
    order = "AKQJT98765432"
    rank_values = sorted([order.index(rank_1), order.index(rank_2)])
    high_rank = combo[0]
    low_rank = combo[1]
    if rank_1 == rank_2:
        if high_rank in {"A", "K", "Q"}:
            return "premium_pair"
        if high_rank in {"J", "T", "9", "8"}:
            return "medium_pair"
        return "small_pair"
    if set([rank_1, rank_2]) <= set("AKQJT"):
        return "suited_broadway" if suited else "offsuit_broadway"
    if high_rank == "A":
        if low_rank in {"K", "Q"}:
            return "strong_ax"
        if suited and low_rank in {"J", "T", "9"}:
            return "medium_ax_suited"
        if suited and low_rank in {"5", "4", "3", "2"}:
            return "low_ax_suited"
        return "offsuit_ax" if not suited else "medium_ax_suited"
    if suited and abs(rank_values[0] - rank_values[1]) == 1:
        return "suited_connector"
    if suited and abs(rank_values[0] - rank_values[1]) == 2:
        return "suited_gapper"
    if suited and high_rank in {"K", "Q", "J"}:
        return "trash_suited"
    return "trash_offsuit"


def _parse_hole_cards(hole_cards: str | None) -> tuple[str, str, str, str] | None:
    if not hole_cards:
        return None
    cards = hole_cards.split()
    if len(cards) != 2 or len(cards[0]) < 2 or len(cards[1]) < 2:
        return None
    return cards[0][0], cards[0][1], cards[1][0], cards[1][1]


def _is_dominated_hand_class(hand_class: str) -> bool:
    return hand_class in {
        "offsuit_broadway",
        "offsuit_ax",
        "trash_suited",
        "trash_offsuit",
        "low_ax_suited",
    }


def _leak_flags(context: dict[str, Any]) -> list[dict[str, Any]]:
    flags: list[dict[str, Any]] = []
    hero_btn_cc = context["cold_call_by_position"].get(("hero", "BTN"))
    pool_btn_cc = context["cold_call_by_position"].get(("pool_non_hero", "BTN"))
    if hero_btn_cc and pool_btn_cc:
        hero_freq = _pct(hero_btn_cc.count, hero_btn_cc.opportunities)
        pool_freq = _pct(pool_btn_cc.count, pool_btn_cc.opportunities)
        if hero_freq > pool_freq + 5 and hero_btn_cc.net_bb <= 0:
            flags.append(
                {
                    "flag": "BTN cold call too high and not profitable",
                    "priority": 1,
                    "evidence": f"Hero {hero_freq}% vs pool {pool_freq}%, net {round(hero_btn_cc.net_bb, 2)}bb",
                    "hand_ids": hero_btn_cc.hand_ids,
                }
            )
    sb_call = context["sb_first_action_ev"].get(("hero", "call_vs_raise"))
    if sb_call and sb_call.hands and sb_call.total_net_bb / sb_call.hands < -1:
        flags.append(
            {
                "flag": "SB call vs raise losing",
                "priority": 1,
                "evidence": f"{round(sb_call.total_net_bb / sb_call.hands, 2)}bb/hand over {sb_call.hands} hands",
                "hand_ids": sb_call.hand_ids,
            }
        )
    bb_vs_btn_3bet = context["bb_defense_vs_steal"].get(("hero", "BTN", "3bet"))
    if bb_vs_btn_3bet and _pct(bb_vs_btn_3bet.count, bb_vs_btn_3bet.opportunities) < 5:
        flags.append(
            {
                "flag": "Low BB resteal vs BTN",
                "priority": 2,
                "evidence": f"{_pct(bb_vs_btn_3bet.count, bb_vs_btn_3bet.opportunities)}% 3bet",
                "hand_ids": bb_vs_btn_3bet.opportunity_hand_ids,
            }
        )
    hero_flop_cbet = context["postflop_aggression"].get(("hero", "flop_cbet"))
    hero_turn_barrel = context["postflop_aggression"].get(("hero", "turn_barrel"))
    if hero_flop_cbet and hero_turn_barrel:
        flop_freq = _pct(hero_flop_cbet.count, hero_flop_cbet.opportunities)
        turn_freq = _pct(hero_turn_barrel.count, hero_turn_barrel.opportunities)
        if flop_freq > 70 and turn_freq < 40:
            flags.append(
                {
                    "flag": "One-and-done c-bet pattern",
                    "priority": 2,
                    "evidence": f"Flop cbet {flop_freq}%, turn barrel {turn_freq}%",
                    "hand_ids": hero_turn_barrel.opportunity_hand_ids,
                }
            )
    flags.sort(key=lambda row: row["priority"])
    return flags[:5]


def _unsupported_or_approximate() -> list[dict[str, str]]:
    return [
        {
            "stat": "all_in_adjusted_bb_per_100",
            "status": "not_available_yet",
            "reason": "Requires all-in equity calculation from hole cards and board runout.",
        },
        {
            "stat": "rake_paid_or_estimated_rake",
            "status": "not_available_yet",
            "reason": "Current parser captures total pot but not reliable per-hand rake.",
        },
        {
            "stat": "value_vs_bluff_and_missed_river_value",
            "status": "approximation_only",
            "reason": "Requires hand-strength classification at showdown and range-aware labels.",
        },
        {
            "stat": "fish_in_blinds_or_player_type_filters",
            "status": "not_available_yet",
            "reason": "Bovada anonymous data has no persistent villain identity model yet.",
        },
    ]


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


def _per(numerator: int | float, denominator: int | float) -> float:
    return round(numerator / denominator, 2) if denominator else 0.0


def _sample_warning(sample_size: int) -> str | None:
    if sample_size == 0:
        return "no_sample"
    if sample_size < LOW_SAMPLE_THRESHOLD:
        return "low_sample"
    return None


def _append_hand_id(hand_ids: list[str], hand_id: str | None) -> None:
    if not hand_id or hand_id in hand_ids or len(hand_ids) >= MAX_HAND_IDS:
        return
    hand_ids.append(hand_id)
