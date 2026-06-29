"""GTOWizard export tracking."""

from __future__ import annotations

from pathlib import Path

from pokermda.exporters.gtowizard_base import GtoExportBatch, GtoExportRecord


def get_export_candidates(connection, hand_id: str | None = None, limit: int = 20) -> list[GtoExportRecord]:
    if hand_id:
        rows = connection.execute(
            """
            SELECT h.hand_id, h.hand_hash, b.raw_text, h.hero_name
            FROM hands h
            JOIN bronze_raw_hand_blocks b ON h.raw_hand_id = b.raw_hand_id
            WHERE h.hand_id = ?
            """,
            [hand_id],
        ).fetchall()
    else:
        rows = connection.execute(
            """
            SELECT h.hand_id, h.hand_hash, b.raw_text, h.hero_name
            FROM hands h
            JOIN bronze_raw_hand_blocks b ON h.raw_hand_id = b.raw_hand_id
            LEFT JOIN study_queue q ON h.hand_id = q.hand_id
            WHERE COALESCE(q.status, 'queued') IN ('queued', 'exported')
              AND h.hand_id NOT IN (
                SELECT hand_id FROM gtowizard_export_items
              )
            ORDER BY COALESCE(q.priority, 50), h.created_at DESC
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
            INSERT INTO gtowizard_export_items (
                export_id, hand_id, hand_hash, file_name
            )
            VALUES (?, ?, ?, ?)
            """,
            [batch.export_id, item.hand_id, item.hand_hash, item.file_name],
        )
        connection.execute(
            "UPDATE study_queue SET status = 'exported' WHERE hand_id = ?",
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

