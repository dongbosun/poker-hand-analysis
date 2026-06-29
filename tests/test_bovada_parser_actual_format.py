from pathlib import Path

from pokermda.exporters.sanitizer import sanitize_bovada_hand
from pokermda.ingest.bovada_parser import BovadaParser
from pokermda.model.enums import ActionType, Street


FIXTURE = Path(__file__).parent / "fixtures" / "bovada" / "sample_bovada_actual_format.txt"


def test_bovada_parser_handles_actual_revealed_format():
    parsed = BovadaParser().parse(FIXTURE.read_text(encoding="utf-8"))
    hero = next(player for player in parsed.participants if player.is_hero)

    assert parsed.bovada_hand_number == "4899483639"
    assert parsed.table_name == "37279418"
    assert parsed.button_seat == 2
    assert parsed.hero_name == "UTG [ME]"
    assert parsed.board == "6h 7c Jd Tc 5d"
    assert hero.hole_cards == "5s Qs"
    assert hero.net_result == 0.38
    assert any(action.action_type == ActionType.POST_BIG_BLIND for action in parsed.actions)
    assert any(action.action_type == ActionType.POST_CHIP for action in parsed.actions)
    assert any(action.action_type == ActionType.RETURN_UNCALLED for action in parsed.actions)
    assert any(action.action_type == ActionType.COLLECT for action in parsed.actions)
    assert any(action.street == Street.RIVER for action in parsed.actions)


def test_sanitizer_drops_actual_non_hero_hole_cards():
    sanitized = sanitize_bovada_hand(FIXTURE.read_text(encoding="utf-8"))

    assert "Hero : Card dealt to a spot [5s Qs]" in sanitized
    assert "[4h Jc]" not in sanitized
    assert "[6s Ad]" not in sanitized
    assert "[8s Ah]" not in sanitized
    assert "*** SUMMARY ***" not in sanitized

