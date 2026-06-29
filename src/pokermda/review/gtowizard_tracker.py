"""GTOWizard export tracking."""

from __future__ import annotations

from pathlib import Path

from pokermda.exporters.gtowizard_base import GtoExportBatch, GtoExportRecord


def get_export_candidates(connection, hand_id: str | None = None, limit: int = 20) -> list[GtoExportRecord]:
    if hand_id:
        rows = connection.execute(
            """
            SELECT h.hand_id, h.raw_hand_hash, b.raw_text, h.hero_name
            FROM hands h
            JOIN raw_hand_blocks b ON h.raw_hand_id = b.raw_hand_id
            WHERE h.hand_id = ?
            """,
            [hand_id],
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT h.hand_id, h.raw_hand_hash, b.raw_text, h.hero_name
            FROM hands h
            JOIN raw_hand_blocks b ON h.raw_hand_id = b.raw_hand_id
            LEFT JOIN study_queue q ON h.hand_id = q.hand_id
            WHERE COALESCE(q.queue_status, 'queued') IN ('queued', 'exported')
              AND h.hand_id NOT IN (
                SELECT hand_id FROM gtowizard_export_hands WHERE export_status = 'exported'
              )
            ORDER BY COALESCE(q.priority_score, 0) DESC, h.created_at DESC
            LIMIT ?
            """,
            [limit],
        ).fetchall()

    return [
        GtoExportRecord(hand_id=row[0], hand_hash=row[1], raw_text=row[2], hero_name=row[3])
        for row in rows
    ]


def record_export_batch(
    connection,
    batch: GtoExportBatch,
    export_format: str,
    sanitizer_version: str,
) -> None:
    connection.execute(
        """
        INSERT INTO gtowizard_export_batches (
            export_batch_id, tool_name, export_name, export_format,
            export_file_path, export_file_sha256, manifest_csv_path, manifest_json_path,
            n_hands, upload_status
        )
        VALUES (?, 'gtowizard', ?, ?, ?, ?, ?, ?, ?, 'not_uploaded')
        """,
        [
            batch.export_id,
            export_format,
            export_format,
            str(batch.export_file_path),
            batch.export_file_sha256,
            str(batch.manifest_csv_path),
            str(batch.manifest_path),
            len(batch.items),
        ],
    )
    connection.execute(
        """
        INSERT INTO gtowizard_exports (
            export_id, export_path, manifest_path, export_format, sanitizer_version, status
        )
        VALUES (?, ?, ?, ?, ?, 'created')
        """,
        [
            batch.export_id,
            str(batch.output_dir),
            str(batch.manifest_path),
            export_format,
            sanitizer_version,
        ],
    )
    for item in batch.items:
        connection.execute(
            """
            INSERT INTO gtowizard_export_hands (
                export_hand_id, export_batch_id, hand_id, original_site_hand_no,
                exported_hand_no, hand_fingerprint, file_order,
                file_offset_start, file_offset_end, sanitized_export_hash, export_status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'exported')
            """,
            [
                item.export_hand_id,
                batch.export_id,
                item.hand_id,
                item.original_site_hand_no,
                item.exported_hand_no,
                item.hand_hash,
                item.file_order,
                item.file_offset_start,
                item.file_offset_end,
                item.sanitized_export_hash,
            ],
        )
        connection.execute(
            """
            INSERT INTO gtowizard_export_items (
                export_id, hand_id, hand_hash, file_name
            )
            VALUES (?, ?, ?, ?)
            """,
            [batch.export_id, item.hand_id, item.hand_hash, item.exported_hand_no],
        )
        connection.execute(
            """
            UPDATE study_queue
            SET queue_status = 'exported', status = 'exported'
            WHERE hand_id = ?
            """,
            [item.hand_id],
        )


def mark_export_status(
    connection,
    export_id: str,
    status: str,
    notes: str | None = None,
    manual_result_path: Path | None = None,
) -> None:
    connection.execute(
        """
        UPDATE gtowizard_export_batches
        SET upload_status = ?,
            notes = COALESCE(?, notes),
            uploaded_at = CASE WHEN ? = 'uploaded' THEN CURRENT_TIMESTAMP ELSE uploaded_at END
        WHERE export_batch_id = ?
        """,
        [status, notes, status, export_id],
    )
    connection.execute(
        """
        UPDATE gtowizard_exports
        SET status = ?,
            notes = COALESCE(?, notes),
            manual_result_path = COALESCE(?, manual_result_path),
            uploaded_at = CASE WHEN ? = 'uploaded' THEN CURRENT_TIMESTAMP ELSE uploaded_at END
        WHERE export_id = ?
        """,
        [
            status,
            notes,
            str(manual_result_path) if manual_result_path else None,
            status,
            export_id,
        ],
    )
