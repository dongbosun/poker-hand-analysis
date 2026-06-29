"""Command-line interface for Poker MDA."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pokermda.config.settings import AppSettings, ensure_dataset_layout, load_settings
from pokermda.db.connect import connect_database
from pokermda.db.migrations import apply_schema
from pokermda.exporters.gtowizard_bovada import export_bovada_records
from pokermda.ingest.bovada_parser import BovadaParser
from pokermda.ingest.file_scanner import read_text_with_fallback, scan_hand_history_files
from pokermda.ingest.import_ledger import ImportLedger
from pokermda.ingest.hand_splitter import split_hand_blocks
from pokermda.ingest.parse_errors import BovadaParseError, ParseErrorRecord, record_parse_error
from pokermda.normalize.build_actions import insert_actions
from pokermda.normalize.build_hands import (
    insert_bronze_raw_block,
    insert_hand,
    update_bronze_parse_status,
)
from pokermda.normalize.build_participants import insert_participants
from pokermda.nodes.node_registry import load_node_registry
from pokermda.review.gtowizard_tracker import (
    get_export_candidates,
    mark_export_status,
    record_export_batch,
)
from pokermda.review.study_queue import build_study_queue, list_queue

console = Console()
app = typer.Typer(no_args_is_help=True)
queue_app = typer.Typer(no_args_is_help=True)
gtowizard_app = typer.Typer(no_args_is_help=True)
nodes_app = typer.Typer(no_args_is_help=True)

app.add_typer(queue_app, name="queue")
app.add_typer(gtowizard_app, name="gtowizard")
app.add_typer(nodes_app, name="nodes")


def _settings(config: Path | None) -> AppSettings:
    return load_settings(config)


def _connection(settings: AppSettings):
    connection = connect_database(settings.duckdb_path)
    apply_schema(connection)
    return connection


@app.command()
def init(config: Path | None = typer.Option(None, "--config", help="Path to local YAML config.")) -> None:
    """Create dataset directories and initialize DuckDB schema."""
    settings = _settings(config)
    messages = ensure_dataset_layout(settings)
    for message in messages:
        console.print(message)
    try:
        connection = _connection(settings)
        connection.close()
    except RuntimeError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(1) from exc
    console.print(f"[green]Initialized dataset at {settings.dataset_dir}[/green]")


@app.command()
def ingest(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    source_dir: Path | None = typer.Option(None, "--source-dir", help="Override Bovada source dir."),
    limit_files: int | None = typer.Option(None, "--limit-files", min=1),
) -> None:
    """Scan Bovada hand history txt files and import new hands."""
    settings = _settings(config)
    ensure_dataset_layout(settings)
    connection = _connection(settings)
    ledger = ImportLedger(connection)
    parser = BovadaParser()

    root = source_dir or settings.bovada_raw_hand_history_dir
    records = scan_hand_history_files(root, pattern=settings.ingest.file_glob)
    if limit_files:
        records = records[:limit_files]

    files_imported = 0
    files_skipped = 0
    hands_seen_total = 0
    hands_inserted_total = 0

    for record in records:
        current_status = ledger.status_for_path(record.file_hash, str(record.path))
        if current_status == "imported":
            files_skipped += 1
            continue
        if ledger.has_successful_file_hash(record.file_hash):
            ledger.mark_skipped_duplicate(record)
            files_skipped += 1
            continue

        ledger.mark_importing(record)
        try:
            text = read_text_with_fallback(
                record.path,
                encoding=settings.ingest.encoding,
                fallback=settings.ingest.fallback_encoding,
            )
            blocks = split_hand_blocks(text)
            hands_seen = len(blocks)
            hands_inserted = 0

            for block_index, block in enumerate(blocks, start=1):
                raw_hand_id, _ = insert_bronze_raw_block(
                    connection,
                    file_hash=record.file_hash,
                    source_path=str(record.path),
                    block_index=block_index,
                    raw_text=block,
                )
                try:
                    parsed = parser.parse(block)
                    hand_id, inserted = insert_hand(
                        connection,
                        parsed,
                        raw_hand_id=raw_hand_id,
                        source_file_hash=record.file_hash,
                    )
                    if inserted:
                        insert_participants(connection, hand_id, parsed.participants)
                        insert_actions(connection, hand_id, parsed.actions)
                        hands_inserted += 1
                    update_bronze_parse_status(connection, raw_hand_id, "parsed")
                except BovadaParseError as exc:
                    update_bronze_parse_status(connection, raw_hand_id, "parse_error", exc.message)
                    record_parse_error(
                        connection,
                        ParseErrorRecord(
                            hand_hash=None,
                            file_hash=record.file_hash,
                            source_path=str(record.path),
                            block_index=block_index,
                            error_code=exc.code,
                            message=exc.message,
                            raw_excerpt=block[:1000],
                        ),
                    )
                    if settings.ingest.stop_on_parse_error:
                        raise

            ledger.mark_imported(record, hands_seen=hands_seen, hands_inserted=hands_inserted)
            files_imported += 1
            hands_seen_total += hands_seen
            hands_inserted_total += hands_inserted
        except Exception as exc:
            ledger.mark_failed(record, str(exc))
            raise

    connection.close()
    console.print(
        f"[green]Ingest complete[/green]: files_imported={files_imported}, "
        f"files_skipped={files_skipped}, hands_seen={hands_seen_total}, "
        f"hands_inserted={hands_inserted_total}"
    )


@queue_app.command("build")
def queue_build(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    limit: int = typer.Option(50, "--limit", min=1),
) -> None:
    """Build review queue from newly imported hands."""
    settings = _settings(config)
    connection = _connection(settings)
    inserted = build_study_queue(connection, limit=limit)
    connection.close()
    console.print(f"[green]Added {inserted} hands to study_queue[/green]")


@queue_app.command("list")
def queue_list(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    """List study queue rows."""
    settings = _settings(config)
    connection = _connection(settings)
    rows = list_queue(connection, limit=limit)
    connection.close()
    table = Table("queue_id", "hand_id", "status", "score", "priority", "created_at")
    for row in rows:
        table.add_row(*(str(value) for value in row))
    console.print(table)


@gtowizard_app.command("export")
def gtowizard_export(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    hand_id: str | None = typer.Option(None, "--hand-id", help="Export one hand id."),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    """Export sanitized hands and a manifest for manual GTOWizard upload."""
    settings = _settings(config)
    connection = _connection(settings)
    records = get_export_candidates(connection, hand_id=hand_id, limit=limit)
    if not records:
        console.print("[yellow]No export candidates found.[/yellow]")
        connection.close()
        return

    output_root = settings.dataset_dir / "exports" / "gtowizard"
    batch = export_bovada_records(
        records,
        output_root=output_root,
        sanitizer_version=settings.gtowizard.sanitizer_version,
        export_format=settings.gtowizard.export_format,
    )
    record_export_batch(
        connection,
        batch,
        export_format=settings.gtowizard.export_format,
        sanitizer_version=settings.gtowizard.sanitizer_version,
    )
    connection.close()
    console.print(f"[green]Exported {len(batch.items)} hands[/green]: {batch.output_dir}")
    console.print(f"Manifest: {batch.manifest_path}")


@gtowizard_app.command("mark")
def gtowizard_mark(
    export_id: str = typer.Option(..., "--export-id"),
    status: str = typer.Option(..., "--status"),
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    notes: str | None = typer.Option(None, "--notes"),
    manual_result_path: Path | None = typer.Option(None, "--manual-result-path"),
) -> None:
    """Manually mark GTOWizard export status after upload or review."""
    settings = _settings(config)
    connection = _connection(settings)
    mark_export_status(connection, export_id, status, notes=notes, manual_result_path=manual_result_path)
    connection.close()
    console.print(f"[green]Marked {export_id} as {status}[/green]")


@nodes_app.command("list")
def nodes_list(config: Path | None = typer.Option(None, "--config", help="Path to local YAML config.")) -> None:
    """List YAML node definition templates."""
    settings = _settings(config)
    node_dir = settings.project_root / "config" / "node_definitions"
    specs = load_node_registry(node_dir)
    table = Table("node_id", "street", "metrics", "path")
    for spec in specs:
        table.add_row(spec.node_id, spec.street, ", ".join(spec.metrics), str(spec.source_path))
    console.print(table)


if __name__ == "__main__":
    app()

