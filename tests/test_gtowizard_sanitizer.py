from pathlib import Path

from pokermda.exporters.sanitizer import sanitize_bovada_hand


RAW = Path(__file__).parent / "fixtures" / "bovada" / "sample_single_hand.txt"
EXPECTED = Path(__file__).parent / "fixtures" / "gtowizard" / "sample_sanitized_expected.txt"


def test_sanitizer_hides_non_hero_cards_and_drops_summary():
    sanitized = sanitize_bovada_hand(RAW.read_text(encoding="utf-8"))

    assert sanitized == EXPECTED.read_text(encoding="utf-8")
    assert "[Qs Qd]" not in sanitized
    assert "SUMMARY" not in sanitized
    assert "Dealt to Hero [Ah Kh]" in sanitized

