from pathlib import Path

from pokermda.ingest.bovada_parser import BovadaParser
from pokermda.model.enums import ActionType, Street


FIXTURE = Path(__file__).parent / "fixtures" / "bovada" / "sample_single_hand.txt"


def test_bovada_parser_smoke():
    parsed = BovadaParser().parse(FIXTURE.read_text(encoding="utf-8"))

    assert parsed.bovada_hand_number == "1111111111"
    assert parsed.hand_id == "bovada:1111111111"
    assert parsed.table_name == "No.37279418"
    assert parsed.button_seat == 1
    assert parsed.hero_name == "Hero"
    assert parsed.board == "As 7d 2c Qh 3s"
    assert len(parsed.participants) == 3
    assert parsed.participants[0].hole_cards == "Ah Kh"
    assert any(action.action_type == ActionType.RAISE for action in parsed.actions)
    assert any(action.street == Street.RIVER for action in parsed.actions)
