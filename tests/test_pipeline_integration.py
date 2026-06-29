import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "bovada" / "sample_bovada_actual_format.txt"


def run_cli(config_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "pokermda.cli", *args, "--config", str(config_path)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )


def test_full_local_pipeline_with_fixture(tmp_path):
    duckdb = pytest.importorskip("duckdb")

    raw_dir = tmp_path / "Bovada Hand History"
    raw_dir.mkdir()
    account_dir = raw_dir / "560082924242"
    account_dir.mkdir()
    shutil.copyfile(FIXTURE, account_dir / "HH sample - $0.02-$0.05 - TBL No.37279418.txt")

    dataset_dir = tmp_path / "dataset"
    config_path = tmp_path / "local.yaml"
    config_path.write_text(
        "\n".join(
            [
                f'project_root: "{ROOT}"',
                f'dataset_dir: "{dataset_dir}"',
                f'bovada_raw_hand_history_dir: "{raw_dir}"',
                f'duckdb_path: "{dataset_dir / "db" / "poker.duckdb"}"',
                "create_raw_symlink: false",
                "ingest:",
                '  file_glob: "*.txt"',
                '  encoding: "utf-8"',
                '  fallback_encoding: "latin-1"',
            ]
        ),
        encoding="utf-8",
    )

    run_cli(config_path, "init")
    dry_run = run_cli(config_path, "scan-raw", "--dry-run")
    assert "files_found" in dry_run.stdout

    run_cli(config_path, "scan-raw")
    run_cli(config_path, "ingest", "--new-only")
    second_ingest = run_cli(config_path, "ingest", "--new-only")
    assert "files_skipped" in second_ingest.stdout

    run_cli(config_path, "status", "imports")
    edge_stats = run_cli(config_path, "stats", "edge", "--json")
    edge_payload = json.loads(edge_stats.stdout)
    assert edge_payload["profile"]["hands"] == 1
    assert "rfi_by_position" in edge_payload["preflop"]
    assert "river_calls" in edge_payload["postflop"]
    assert "sb_first_action_ev" in edge_payload["blind_play"]

    run_cli(config_path, "queue-review", "--top", "1")
    export = run_cli(config_path, "export-gtowizard", "--limit", "1")
    assert "hands_gtowizard.txt" in export.stdout

    con = duckdb.connect(str(dataset_dir / "db" / "poker.duckdb"), read_only=True)
    assert con.execute("SELECT COUNT(*) FROM import_files WHERE status = 'imported'").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM raw_hand_blocks WHERE parse_status = 'parsed'").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM hands").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM gtowizard_export_batches").fetchone()[0] == 1
    assert con.execute("SELECT COUNT(*) FROM gtowizard_export_hands").fetchone()[0] == 1
    export_file = Path(
        con.execute("SELECT export_file_path FROM gtowizard_export_batches").fetchone()[0]
    )
    manifest_csv = Path(
        con.execute("SELECT manifest_csv_path FROM gtowizard_export_batches").fetchone()[0]
    )
    manifest_json = Path(
        con.execute("SELECT manifest_json_path FROM gtowizard_export_batches").fetchone()[0]
    )
    exported_text = export_file.read_text(encoding="utf-8")
    assert export_file.exists()
    assert manifest_csv.exists()
    assert manifest_json.exists()
    assert "Hero : Card dealt to a spot [5s Qs]" in exported_text
    assert "[4h Jc]" not in exported_text
    assert "[6s Ad]" not in exported_text
