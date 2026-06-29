from pathlib import Path

from pokermda.ingest.hand_splitter import extract_hand_number, split_hand_blocks


FIXTURE = Path(__file__).parent / "fixtures" / "bovada" / "sample_multiple_hands.txt"


def test_split_hand_blocks_multiple_hands():
    text = FIXTURE.read_text(encoding="utf-8")
    blocks = split_hand_blocks(text)

    assert len(blocks) == 2
    assert extract_hand_number(blocks[0]) == "1111111111"
    assert extract_hand_number(blocks[1]) == "2222222222"

