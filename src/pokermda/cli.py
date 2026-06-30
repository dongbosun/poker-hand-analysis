"""Command-line interface for Poker MDA."""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from pokermda.config.settings import AppSettings, ensure_dataset_layout, load_settings
from pokermda.db.connect import connect_database
from pokermda.db.migrations import apply_schema
from pokermda.exporters.gtowizard_bovada import export_bovada_records
from pokermda.ingest.bovada_parser import BovadaParser, PARSER_VERSION
from pokermda.ingest.file_scanner import read_text_with_fallback, scan_hand_history_files
from pokermda.ingest.import_ledger import ImportLedger
from pokermda.ingest.hand_splitter import split_hand_blocks_with_lines
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
from pokermda.reports.database_profile import DatabaseProfile, build_database_profile
from pokermda.reports.edge_stats import build_edge_stats
from pokermda.reports.stats_summary import build_stats_summary

console = Console()
app = typer.Typer(no_args_is_help=True)
queue_app = typer.Typer(no_args_is_help=True)
gtowizard_app = typer.Typer(no_args_is_help=True)
gtow_app = typer.Typer(no_args_is_help=True)
status_app = typer.Typer(no_args_is_help=True)
review_app = typer.Typer(no_args_is_help=True)
nodes_app = typer.Typer(no_args_is_help=True)
stats_app = typer.Typer(no_args_is_help=True)

app.add_typer(queue_app, name="queue")
app.add_typer(gtowizard_app, name="gtowizard")
app.add_typer(gtow_app, name="gtow")
app.add_typer(status_app, name="status")
app.add_typer(review_app, name="review")
app.add_typer(nodes_app, name="nodes")
app.add_typer(stats_app, name="stats")


def _settings(config: Path | None) -> AppSettings:
    return load_settings(config)


def _connection(settings: AppSettings):
    connection = connect_database(settings.duckdb_path)
    apply_schema(connection)
    return connection


def _scan_raw(
    settings: AppSettings,
    connection,
    source_dir: Path | None,
    dry_run: bool = False,
) -> dict[str, int]:
    ledger = ImportLedger(connection)
    root = source_dir or settings.bovada_raw_hand_history_dir
    records = scan_hand_history_files(root, pattern=settings.ingest.file_glob)
    summary = {
        "files_found": len(records),
        "new_files": 0,
        "known_paths": 0,
        "already_imported_hash": 0,
        "skipped_duplicate_hash": 0,
        "written": 0,
    }
    for record in records:
        current_status = ledger.status_for_path(record.file_hash, str(record.path))
        if current_status:
            summary["known_paths"] += 1
            if current_status == "imported":
                summary["already_imported_hash"] += 1
            continue
        if ledger.has_successful_file_hash(record.file_hash):
            summary["skipped_duplicate_hash"] += 1
            if not dry_run:
                ledger.mark_skipped_duplicate(record)
                summary["written"] += 1
            continue
        summary["new_files"] += 1
        if not dry_run:
            ledger.record_seen(record, status="discovered")
            summary["written"] += 1
    return summary


def _ingest_raw(
    settings: AppSettings,
    connection,
    source_dir: Path | None,
    limit_files: int | None,
    new_only: bool,
) -> dict[str, int]:
    ledger = ImportLedger(connection)
    parser = BovadaParser()

    root = source_dir or settings.bovada_raw_hand_history_dir
    records = scan_hand_history_files(root, pattern=settings.ingest.file_glob)
    if limit_files:
        records = records[:limit_files]

    summary = {
        "files_imported": 0,
        "files_partial": 0,
        "files_error": 0,
        "files_skipped": 0,
        "hands_seen": 0,
        "hands_inserted": 0,
        "hands_failed": 0,
    }

    for record in records:
        current_status = ledger.status_for_path(record.file_hash, str(record.path))
        if new_only and current_status == "imported":
            summary["files_skipped"] += 1
            continue
        if new_only and ledger.has_successful_file_hash(record.file_hash):
            if current_status != "imported":
                ledger.mark_skipped_duplicate(record)
            summary["files_skipped"] += 1
            continue

        import_file_id = ledger.mark_importing(record)
        try:
            connection.execute("BEGIN TRANSACTION")
            text = read_text_with_fallback(
                record.path,
                encoding=settings.ingest.encoding,
                fallback=settings.ingest.fallback_encoding,
            )
            blocks = split_hand_blocks_with_lines(text)
            hands_seen = len(blocks)
            hands_inserted = 0
            hands_failed = 0

            for block in blocks:
                raw_hand_id, _ = insert_bronze_raw_block(
                    connection,
                    file_hash=record.file_hash,
                    source_path=str(record.path),
                    block_index=block.block_index,
                    raw_text=block.raw_text,
                    import_file_id=import_file_id,
                    hand_start_line=block.start_line,
                    hand_end_line=block.end_line,
                )
                try:
                    parsed = parser.parse(block.raw_text)
                    hand_id, inserted = insert_hand(
                        connection,
                        parsed,
                        raw_hand_id=raw_hand_id,
                        source_file_hash=record.file_hash,
                        import_file_id=import_file_id,
                    )
                    if inserted:
                        insert_participants(connection, hand_id, parsed.participants)
                        insert_actions(connection, hand_id, parsed.actions)
                        hands_inserted += 1
                    update_bronze_parse_status(connection, raw_hand_id, "parsed")
                except BovadaParseError as exc:
                    hands_failed += 1
                    update_bronze_parse_status(connection, raw_hand_id, "error", exc.message)
                    record_parse_error(
                        connection,
                        ParseErrorRecord(
                            hand_hash=None,
                            file_hash=record.file_hash,
                            source_path=str(record.path),
                            block_index=block.block_index,
                            error_code=exc.code,
                            message=exc.message,
                            raw_excerpt=block.raw_text[:1000],
                        ),
                    )
                    if settings.ingest.stop_on_parse_error:
                        raise

            if hands_failed:
                ledger.mark_partial(
                    record,
                    hands_seen=hands_seen,
                    hands_inserted=hands_inserted,
                    hands_failed=hands_failed,
                    parser_version=PARSER_VERSION,
                    error_message=f"{hands_failed} hand blocks failed to parse",
                )
                summary["files_partial"] += 1
            else:
                ledger.mark_imported(
                    record,
                    hands_seen=hands_seen,
                    hands_inserted=hands_inserted,
                    hands_failed=0,
                    parser_version=PARSER_VERSION,
                )
                summary["files_imported"] += 1
            connection.execute("COMMIT")
            summary["hands_seen"] += hands_seen
            summary["hands_inserted"] += hands_inserted
            summary["hands_failed"] += hands_failed
        except Exception as exc:
            connection.execute("ROLLBACK")
            ledger.mark_failed(record, str(exc))
            summary["files_error"] += 1
            if settings.ingest.stop_on_parse_error:
                raise
    return summary


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
def scan_raw(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    source_dir: Path | None = typer.Option(None, "--source-dir", help="Override Bovada source dir."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Scan without writing import ledger rows."),
) -> None:
    """Scan raw Bovada txt files and update the import ledger."""
    settings = _settings(config)
    ensure_dataset_layout(settings)
    connection = _connection(settings)
    summary = _scan_raw(settings, connection, source_dir, dry_run=dry_run)
    connection.close()
    _print_summary("Raw scan", summary)


@app.command()
def ingest(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    source_dir: Path | None = typer.Option(None, "--source-dir", help="Override Bovada source dir."),
    limit_files: int | None = typer.Option(None, "--limit-files", min=1),
    new_only: bool = typer.Option(True, "--new-only/--all-files", help="Only ingest files not already imported."),
) -> None:
    """Ingest raw Bovada txt files into DuckDB."""
    settings = _settings(config)
    ensure_dataset_layout(settings)
    connection = _connection(settings)
    summary = _ingest_raw(settings, connection, source_dir, limit_files, new_only)
    connection.close()
    _print_summary("Ingest complete", summary)


@app.command()
def profile(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    source_dir: Path | None = typer.Option(None, "--source-dir", help="Override Bovada source dir."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Print a compact database and Bovada raw-file profile."""
    settings = _settings(config)
    connection = _connection(settings)
    profile_data = build_database_profile(settings, connection, source_dir=source_dir)
    connection.close()

    if json_output:
        print(json.dumps(profile_data.to_dict(), ensure_ascii=False, indent=2))
        return

    _print_profile_table(profile_data)


@status_app.command("imports")
def status_imports(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
) -> None:
    """Show import ledger, raw hand block status, and recent parse errors."""
    settings = _settings(config)
    connection = _connection(settings)
    import_rows = connection.execute(
        "SELECT status, COUNT(*) FROM import_files GROUP BY status ORDER BY status"
    ).fetchall()
    block_rows = connection.execute(
        "SELECT parse_status, COUNT(*) FROM raw_hand_blocks GROUP BY parse_status ORDER BY parse_status"
    ).fetchall()
    error_rows = connection.execute(
        """
        SELECT created_at, error_code, message, raw_file_path, block_index
        FROM parse_errors
        ORDER BY created_at DESC
        LIMIT 20
        """
    ).fetchall()
    connection.close()

    import_table = Table("Import Status", "Files")
    for status, count in import_rows:
        import_table.add_row(str(status), str(count))
    console.print(import_table)

    block_table = Table("Raw Block Status", "Blocks")
    for status, count in block_rows:
        block_table.add_row(str(status), str(count))
    console.print(block_table)

    error_table = Table("Created", "Code", "Message", "Path", "Block")
    for row in error_rows:
        error_table.add_row(*(str(value) for value in row))
    console.print(error_table)


@app.command("queue-review")
def queue_review(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    top: int = typer.Option(50, "--top", min=1),
    scope: str = typer.Option("hero", "--scope"),
    date: str | None = typer.Option(None, "--date"),
) -> None:
    """Build the daily review queue using the MVP local scorer."""
    _ = scope
    _ = date
    settings = _settings(config)
    connection = _connection(settings)
    inserted = build_study_queue(connection, limit=top)
    connection.close()
    console.print(f"[green]Added {inserted} hands to study_queue[/green]")


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
    table = Table("queue_id", "hand_id", "status", "score", "bucket", "tags", "created_at")
    for row in rows:
        table.add_row(*(str(value) for value in row))
    console.print(table)


@app.command("export-gtowizard")
def export_gtowizard(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    hand_id: str | None = typer.Option(None, "--hand-id", help="Export one hand id."),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    """Export sanitized queued hands for manual GTOWizard upload."""
    _export_gtowizard(config=config, hand_id=hand_id, limit=limit)


@gtowizard_app.command("export")
def gtowizard_export(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    hand_id: str | None = typer.Option(None, "--hand-id", help="Export one hand id."),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    """Export sanitized hands and a manifest for manual GTOWizard upload."""
    _export_gtowizard(config=config, hand_id=hand_id, limit=limit)


def _export_gtowizard(config: Path | None, hand_id: str | None, limit: int) -> None:
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
    console.print(f"Hands file: {batch.export_file_path}")
    console.print(f"Manifest CSV: {batch.manifest_csv_path}")
    console.print(f"Manifest JSON: {batch.manifest_path}")
    console.print("Next: manually upload hands_gtowizard.txt to GTOWizard, then run gtow mark-uploaded.")


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


@gtow_app.command("batches")
def gtow_batches(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    """List GTOWizard export batches and upload statuses."""
    settings = _settings(config)
    connection = _connection(settings)
    rows = connection.execute(
        """
        SELECT export_batch_id, export_name, n_hands, upload_status,
               export_file_path, created_at, uploaded_at
        FROM gtowizard_export_batches
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    connection.close()
    table = Table("batch", "name", "hands", "status", "file", "created", "uploaded")
    for row in rows:
        table.add_row(*(str(value) for value in row))
    console.print(table)


@gtow_app.command("mark-uploaded")
def gtow_mark_uploaded(
    batch: str = typer.Option(..., "--batch", help="Export batch id/name."),
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    """Mark a GTOWizard batch as manually uploaded."""
    _mark_gtow_batch(config, batch, "uploaded", notes)


@gtow_app.command("mark-analyzed")
def gtow_mark_analyzed(
    batch: str = typer.Option(..., "--batch", help="Export batch id/name."),
    status: str = typer.Option("analyzed", "--status", help="analyzed, partial, or error."),
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    notes: str | None = typer.Option(None, "--notes"),
) -> None:
    """Mark a GTOWizard batch as analyzed, partial, or error."""
    _mark_gtow_batch(config, batch, status, notes)


@gtow_app.command("add-result")
def gtow_add_result(
    hand_id: str | None = typer.Option(None, "--hand-id"),
    exported_hand_no: str | None = typer.Option(None, "--exported-hand-no"),
    batch: str | None = typer.Option(None, "--batch"),
    gtow_status: str = typer.Option("analyzed", "--status"),
    label: str | None = typer.Option(None, "--label"),
    ev_loss_bb: float | None = typer.Option(None, "--ev-loss-bb"),
    accuracy_score: float | None = typer.Option(None, "--accuracy-score"),
    mistake_street: str | None = typer.Option(None, "--mistake-street"),
    note: str | None = typer.Option(None, "--note"),
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
) -> None:
    """Manually record a GTOWizard result for one exported hand."""
    settings = _settings(config)
    connection = _connection(settings)
    lookup = _lookup_export_hand(connection, hand_id, exported_hand_no, batch)
    if not lookup:
        connection.close()
        console.print("[red]Could not find matching exported hand.[/red]")
        raise typer.Exit(1)
    export_hand_id, export_batch_id, resolved_hand_id = lookup
    result_id = f"gtow_result_{export_hand_id}"
    connection.execute(
        """
        INSERT OR REPLACE INTO gtowizard_review_results (
            result_id, hand_id, export_hand_id, export_batch_id, gtow_status,
            gtow_ev_loss_bb, gtow_accuracy_score, biggest_mistake_street,
            gtow_label, solution_match_notes, result_source
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'manual')
        """,
        [
            result_id,
            resolved_hand_id,
            export_hand_id,
            export_batch_id,
            gtow_status,
            ev_loss_bb,
            accuracy_score,
            mistake_street,
            label,
            note,
        ],
    )
    connection.close()
    console.print(f"[green]Recorded GTOWizard result for {resolved_hand_id}[/green]")


@review_app.command("todo")
def review_todo(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    limit: int = typer.Option(20, "--limit", min=1),
) -> None:
    """Show hands still waiting for review."""
    settings = _settings(config)
    connection = _connection(settings)
    rows = connection.execute(
        """
        SELECT q.hand_id, q.queue_status, q.priority_score, q.reason_tags,
               r.gtow_ev_loss_bb, r.gtow_label, q.created_at
        FROM study_queue q
        LEFT JOIN gtowizard_review_results r ON q.hand_id = r.hand_id
        WHERE q.queue_status IN ('queued', 'exported', 'uploaded', 'analyzed')
        ORDER BY COALESCE(r.gtow_ev_loss_bb, q.priority_score, 0) DESC, q.created_at DESC
        LIMIT ?
        """,
        [limit],
    ).fetchall()
    connection.close()
    table = Table("hand_id", "status", "score", "tags", "gtow_ev_loss", "gtow_label", "created")
    for row in rows:
        table.add_row(*(str(value) for value in row))
    console.print(table)


@review_app.command("mark-done")
def review_mark_done(
    hand_id: str = typer.Option(..., "--hand-id"),
    tag: str | None = typer.Option(None, "--tag"),
    note: str = typer.Option("", "--note"),
    severity: str | None = typer.Option(None, "--severity"),
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
) -> None:
    """Mark one hand as reviewed and save a review note."""
    settings = _settings(config)
    connection = _connection(settings)
    note_id = f"review_note_{hand_id}_{abs(hash(note))}"
    connection.execute(
        """
        INSERT INTO review_notes (
            note_id, hand_id, source_tool, reviewed_at, concept_tag,
            severity, user_note, note_text, tags
        )
        VALUES (?, ?, 'self_review', CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
        """,
        [note_id, hand_id, tag, severity, note, note, tag],
    )
    connection.execute(
        """
        UPDATE study_queue
        SET queue_status = 'reviewed', status = 'reviewed', reviewed_at = CURRENT_TIMESTAMP
        WHERE hand_id = ?
        """,
        [hand_id],
    )
    connection.close()
    console.print(f"[green]Marked {hand_id} reviewed[/green]")


@app.command("daily")
def daily(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    top: int = typer.Option(20, "--top", min=1),
) -> None:
    """Run the local daily workflow without uploading to external services."""
    settings = _settings(config)
    ensure_dataset_layout(settings)
    connection = _connection(settings)
    scan_summary = _scan_raw(settings, connection, None, dry_run=False)
    ingest_summary = _ingest_raw(settings, connection, None, None, new_only=True)
    queued = build_study_queue(connection, limit=top)
    records = get_export_candidates(connection, limit=top)
    if records:
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
        upload_path = batch.export_file_path
    else:
        upload_path = None
    connection.close()
    _print_summary("Daily scan", scan_summary)
    _print_summary("Daily ingest", ingest_summary)
    console.print(f"[green]Queued {queued} review hands[/green]")
    if upload_path:
        console.print(f"Next: manually upload this GTOWizard file: {upload_path}")
    else:
        console.print("[yellow]No GTOWizard export candidates found.[/yellow]")


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


@stats_app.command("summary")
def stats_summary(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Print currently supported aggregate poker stats."""
    settings = _settings(config)
    connection = _connection(settings)
    summary = build_stats_summary(connection)
    connection.close()

    if json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    _print_stats_summary(summary)


@stats_app.command("edge")
def stats_edge(
    config: Path | None = typer.Option(None, "--config", help="Path to local YAML config."),
    json_output: bool = typer.Option(False, "--json", help="Print machine-readable JSON."),
) -> None:
    """Print edge-oriented stats for preflop, postflop, showdown, river calls, and SB play."""
    settings = _settings(config)
    connection = _connection(settings)
    summary = build_edge_stats(connection)
    connection.close()

    if json_output:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    _print_edge_stats(summary)


def _mark_gtow_batch(config: Path | None, batch: str, status: str, notes: str | None) -> None:
    settings = _settings(config)
    connection = _connection(settings)
    row = connection.execute(
        """
        SELECT export_batch_id
        FROM gtowizard_export_batches
        WHERE export_batch_id = ? OR export_name = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        [batch, batch],
    ).fetchone()
    if not row:
        connection.close()
        console.print(f"[red]Batch not found: {batch}[/red]")
        raise typer.Exit(1)
    batch_id = row[0]
    mark_export_status(connection, batch_id, status, notes=notes)
    queue_status = "uploaded" if status == "uploaded" else status
    connection.execute(
        """
        UPDATE study_queue
        SET queue_status = ?, status = ?
        WHERE hand_id IN (
            SELECT hand_id FROM gtowizard_export_hands WHERE export_batch_id = ?
        )
        """,
        [queue_status, queue_status, batch_id],
    )
    connection.close()
    console.print(f"[green]Marked {batch_id} as {status}[/green]")


def _lookup_export_hand(
    connection,
    hand_id: str | None,
    exported_hand_no: str | None,
    batch: str | None,
) -> tuple[str, str, str] | None:
    if hand_id:
        row = connection.execute(
            """
            SELECT export_hand_id, export_batch_id, hand_id
            FROM gtowizard_export_hands
            WHERE hand_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            [hand_id],
        ).fetchone()
        return row if row else None
    if exported_hand_no:
        params: list[str] = [exported_hand_no]
        batch_filter = ""
        if batch:
            batch_filter = "AND (export_batch_id = ? OR export_batch_id IN (SELECT export_batch_id FROM gtowizard_export_batches WHERE export_name = ?))"
            params.extend([batch, batch])
        row = connection.execute(
            f"""
            SELECT export_hand_id, export_batch_id, hand_id
            FROM gtowizard_export_hands
            WHERE exported_hand_no = ?
            {batch_filter}
            ORDER BY created_at DESC
            LIMIT 1
            """,
            params,
        ).fetchone()
        return row if row else None
    return None


def _print_summary(title: str, summary: dict[str, int]) -> None:
    table = Table(title, "Count")
    for key, value in summary.items():
        table.add_row(key, str(value))
    console.print(table)


def _print_profile_table(profile_data: DatabaseProfile) -> None:
    table = Table("Metric", "Value")
    labels = {
        "hands_in_database": "Hands in database",
        "bronze_raw_hand_blocks": "Bronze raw hand blocks",
        "parsed_raw_hand_blocks": "Parsed raw hand blocks",
        "parse_errors": "Parse errors",
        "raw_bovada_files": "Raw Bovada txt files",
        "raw_bovada_unique_file_hashes": "Raw unique file hashes",
        "raw_bovada_files_completed_by_hash": "Raw files completed by hash",
        "raw_bovada_files_not_imported_by_hash": "Raw files not imported by hash",
        "ledger_file_paths": "Ledger file paths",
        "ledger_imported_file_paths": "Ledger imported file paths",
        "ledger_skipped_duplicate_file_paths": "Ledger skipped duplicate paths",
        "ledger_failed_file_paths": "Ledger failed file paths",
        "duckdb_path": "DuckDB path",
        "bovada_raw_hand_history_dir": "Bovada raw dir",
    }
    for key, label in labels.items():
        table.add_row(label, str(getattr(profile_data, key)))
    console.print(table)


def _print_edge_stats(summary: dict[str, object]) -> None:
    profile = summary["profile"]
    profile_table = Table("Metric", "Value")
    for key in ("hands", "participants_dealt", "actions"):
        profile_table.add_row(key, str(profile[key]))
    console.print(profile_table)

    results = summary["results"]
    _print_ev_table("Overall Winrate", results["overall_winrate"])
    _print_ev_table("Redline / Blueline", results["redline_blueline"])
    _print_ev_table("Pot Type EV", results["pot_type_ev"])

    position = summary["position"]
    _print_frequency_ev_table("Winrate By Position", position["winrate_by_position"])

    preflop = summary["preflop"]
    _print_rate_table("RFI By Position", preflop["rfi_by_position"])
    _print_rate_table("Cold Call By Position", preflop["cold_call_by_position"])
    _print_rate_table("3bet By Position", preflop["three_bet_by_position"])
    _print_rate_vs_table("3bet By Position vs Open Position", preflop["three_bet_by_position_vs_open"])
    _print_rate_table("Fold To 3bet By Open Position", preflop["fold_to_three_bet_by_position"])
    _print_ev_table("Entry Action EV By Position", preflop["entry_action_ev_by_position"])
    _print_rate_vs_table("BTN Cold Call By Opener", preflop["btn_cold_call_by_opener"])
    _print_ev_table("BTN Cold Call By Hand Class", preflop["btn_cold_call_by_hand_class"])
    _print_ev_table("SB First Action Vs Opener", preflop["sb_first_action_vs_opener"])
    _print_rate_table("BB Defense Vs Steal", preflop["bb_defense_vs_steal"])

    postflop = summary["postflop"]
    _print_named_rate_table("Postflop Aggression", postflop["aggression"])
    _print_rate_table("C-bet Deep", postflop["cbet_deep"])
    _print_rate_table("Facing C-bet", postflop["facing_cbet"])
    _print_rate_table("Turn After C-bet", postflop["turn_after_cbet"])
    _print_named_rate_table("Showdown Quality", postflop["showdown_quality"])
    _print_river_call_table("River Call / Bluff Catch", postflop["river_calls"])

    river = summary["river"]
    _print_river_call_table("River Calls By Size", river["river_calls_by_size"])
    _print_river_call_table("River Calls By Line", river["river_calls_by_line"])

    blind_play = summary["blind_play"]
    _print_ev_table("SB First Action EV", blind_play["sb_first_action_ev"])
    _print_leak_flags(summary["leak_flags"])


def _print_rate_table(title: str, rows: list[dict[str, object]]) -> None:
    table = Table(title, "Spot", "Count/Opps", "Freq", "Net bb", "bb/Opp")
    for row in rows:
        if row.get("opportunities") == 0:
            continue
        table.add_row(
            str(row["group"]),
            _spot_label(row),
            f"{row.get('count', row.get('successes'))}/{row['opportunities']}",
            f"{row.get('frequency', row.get('pct'))}%",
            str(row.get("net_bb", "")),
            str(row.get("bb_per_opportunity", "")),
        )
    console.print(table)


def _print_rate_vs_table(title: str, rows: list[dict[str, object]]) -> None:
    table = Table(title, "Pos", "Vs Open", "Count/Opps", "Freq", "Net bb")
    for row in rows:
        if row.get("opportunities") == 0:
            continue
        table.add_row(
            str(row["group"]),
            str(row["position"]),
            str(row["vs_open_position"]),
            f"{row.get('count', row.get('successes'))}/{row['opportunities']}",
            f"{row.get('frequency', row.get('pct'))}%",
            str(row.get("net_bb", "")),
        )
    console.print(table)


def _print_named_rate_table(title: str, rows: list[dict[str, object]]) -> None:
    table = Table(title, "Stat", "Count/Opps", "Freq", "Net bb", "bb/Opp")
    for row in rows:
        table.add_row(
            str(row["group"]),
            str(row["stat"]),
            f"{row.get('count', row.get('successes'))}/{row['opportunities']}",
            f"{row.get('frequency', row.get('pct'))}%",
            str(row.get("net_bb", "")),
            str(row.get("bb_per_opportunity", "")),
        )
    console.print(table)


def _print_river_call_table(title: str, rows: list[dict[str, object]]) -> None:
    table = Table(
        title,
        "Spot",
        "Calls",
        "Call bb",
        "Net bb",
        "RCE",
        "SD Calls",
        "Bluff Catch Win",
    )
    for row in rows:
        if row.get("position") != "ALL" and row["calls"] == 0:
            continue
        table.add_row(
            str(row["group"]),
            _spot_label(row),
            str(row["calls"]),
            str(row["total_call_bb"]),
            str(row["total_net_bb"]),
            str(row["river_call_efficiency"]),
            str(row["showdown_calls"]),
            f"{row['bluff_catch_win_pct']}%",
        )
    console.print(table)


def _print_ev_table(title: str, rows: list[dict[str, object]]) -> None:
    table = Table(title, "Spot", "Hands", "Net bb", "bb/Hand", "bb/100")
    for row in rows:
        table.add_row(
            str(row["group"]),
            _spot_label(row),
            str(row.get("hands", row.get("count"))),
            str(row.get("net_bb", row.get("total_net_bb"))),
            str(row.get("bb_per_hand", row.get("avg_net_bb"))),
            str(row.get("bb_per_100", "")),
        )
    console.print(table)


def _print_frequency_ev_table(title: str, rows: list[dict[str, object]]) -> None:
    table = Table(title, "Spot", "Hands", "VPIP", "PFR", "3bet", "Net bb", "bb/100")
    for row in rows:
        if row.get("hands") == 0:
            continue
        table.add_row(
            str(row["group"]),
            _spot_label(row),
            str(row["hands"]),
            f"{row['vpip_frequency']}%",
            f"{row['pfr_frequency']}%",
            f"{row['three_bet_frequency']}%",
            str(row["net_bb"]),
            str(row["bb_per_100"]),
        )
    console.print(table)


def _print_leak_flags(rows: list[dict[str, object]]) -> None:
    table = Table("Leak Flags", "Priority", "Evidence", "Hand IDs")
    for row in rows:
        table.add_row(
            str(row["flag"]),
            str(row["priority"]),
            str(row["evidence"]),
            ", ".join(str(hand_id) for hand_id in row.get("hand_ids", [])[:8]),
        )
    console.print(table)


def _spot_label(row: dict[str, object]) -> str:
    skip = {
        "group",
        "opportunities",
        "count",
        "successes",
        "frequency",
        "pct",
        "net_bb",
        "opportunity_net_bb",
        "bb_per_opportunity",
        "bb_per_count",
        "bb_per_hand",
        "bb_per_100",
        "hands",
        "total_net_bb",
        "avg_net_bb",
        "profitable_pct",
        "hand_ids",
        "opportunity_hand_ids",
        "sample_warning",
        "vpip_count",
        "vpip_frequency",
        "pfr_count",
        "pfr_frequency",
        "vpip_pfr_gap",
        "three_bet_count",
        "three_bet_frequency",
        "calls",
        "showdown_calls",
        "winning_showdown_calls",
        "total_call_bb",
        "river_call_efficiency",
        "showdown_net_bb",
        "bluff_catch_win_pct",
    }
    labels = [str(value) for key, value in row.items() if key not in skip and value not in (None, "")]
    return " / ".join(labels) if labels else "overall"


def _print_stats_summary(summary: dict[str, object]) -> None:
    profile = summary["profile"]
    profile_table = Table("Metric", "Value")
    for key in ("hands", "participants", "actions", "parse_errors", "import_files"):
        profile_table.add_row(key, str(profile[key]))
    console.print(profile_table)

    core_table = Table(
        "Group",
        "Opps",
        "VPIP",
        "PFR",
        "VPIP-PFR",
        "Call",
        "Fold",
        "Flop Act",
        "Showdown",
        "Collected",
    )
    for row in summary["core"]:
        core_table.add_row(
            row["group"],
            str(row["opportunities"]),
            f"{row['vpip_n']}/{row['opportunities']} ({row['vpip_pct']}%)",
            f"{row['pfr_n']}/{row['opportunities']} ({row['pfr_pct']}%)",
            f"{row['vpip_minus_pfr_pct']}%",
            f"{row['preflop_call_pct']}%",
            f"{row['preflop_fold_pct']}%",
            f"{row['flop_action_pct']}%",
            f"{row['showdown_pct']}%",
            f"{row['collected_pct']}%",
        )
    console.print(core_table)

    for title, key in (("Hero By Position", "hero_by_position"), ("Pool By Position", "pool_by_position")):
        table = Table(title, "Opps", "VPIP", "PFR", "Call", "Fold", "Flop Act", "Showdown", "Collected")
        for row in summary[key]:
            table.add_row(
                row["position"],
                str(row["opportunities"]),
                f"{row['vpip_n']}/{row['opportunities']} ({row['vpip_pct']}%)",
                f"{row['pfr_n']}/{row['opportunities']} ({row['pfr_pct']}%)",
                f"{row['preflop_call_pct']}%",
                f"{row['preflop_fold_pct']}%",
                f"{row['flop_action_pct']}%",
                f"{row['showdown_pct']}%",
                f"{row['collected_pct']}%",
            )
        console.print(table)

    action_table = Table("Action Type", "Count", "Pct")
    for row in summary["action_type_counts"]:
        action_table.add_row(row["action_type"], str(row["count"]), f"{row['pct']}%")
    console.print(action_table)

    street_table = Table("Street", "Actions", "Hands With Action")
    for row in summary["street_action_counts"]:
        street_table.add_row(row["street"], str(row["actions"]), str(row["hands_with_action"]))
    console.print(street_table)


if __name__ == "__main__":
    app()
