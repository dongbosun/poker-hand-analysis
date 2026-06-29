"""Enum values used by normalized hand history records."""

from __future__ import annotations

from enum import StrEnum


class Street(StrEnum):
    PREFLOP = "preflop"
    FLOP = "flop"
    TURN = "turn"
    RIVER = "river"
    SHOWDOWN = "showdown"
    SUMMARY = "summary"
    UNKNOWN = "unknown"


class ActionType(StrEnum):
    ANTE = "ante"
    POST_SMALL_BLIND = "post_small_blind"
    POST_BIG_BLIND = "post_big_blind"
    POST_CHIP = "post_chip"
    STRADDLE = "straddle"
    FOLD = "fold"
    CHECK = "check"
    CALL = "call"
    BET = "bet"
    RAISE = "raise"
    ALL_IN = "all_in"
    SHOW = "show"
    MUCK = "muck"
    COLLECT = "collect"
    RETURN_UNCALLED = "return_uncalled"
    UNKNOWN = "unknown"
