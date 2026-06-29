import pytest

from pokermda.db.migrations import apply_schema
from pokermda.ingest.file_scanner import scan_hand_history_files
from pokermda.ingest.import_ledger import ImportLedger


def test_import_ledger_tracks_successful_file_hash(tmp_path):
    duckdb = pytest.importorskip("duckdb")
    db = duckdb.connect(":memory:")
    apply_schema(db)

    hand_path = tmp_path / "HH20260626.txt"
    hand_path.write_text("Bovada Hand #1\n", encoding="utf-8")
    record = scan_hand_history_files(tmp_path)[0]

    ledger = ImportLedger(db)
    ledger.record_seen(record)
    assert not ledger.has_successful_file_hash(record.file_hash)

    ledger.mark_importing(record)
    ledger.mark_imported(record, hands_seen=1, hands_inserted=1)

    assert ledger.has_successful_file_hash(record.file_hash)
    assert ledger.status_for_path(record.file_hash, str(record.path)) == "imported"

