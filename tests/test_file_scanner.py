from pokermda.ingest.file_scanner import scan_hand_history_files


def test_scan_hand_history_files_recurses_and_hashes_txt(tmp_path):
    nested = tmp_path / "account" / "session"
    nested.mkdir(parents=True)
    hand_path = nested / "HH20260626.txt"
    hand_path.write_text("Bovada Hand #1\n", encoding="utf-8")
    (nested / "ignore.csv").write_text("not a hand", encoding="utf-8")

    records = scan_hand_history_files(tmp_path)

    assert len(records) == 1
    assert records[0].path == hand_path
    assert len(records[0].file_hash) == 64
    assert records[0].file_size_bytes > 0

