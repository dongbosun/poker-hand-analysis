"""Bovada to GTOWizard local export."""

from __future__ import annotations

from pathlib import Path

from pokermda.exporters.gtowizard_base import GtoExportBatch, GtoExportItem, GtoExportRecord
from pokermda.exporters.manifest import ManifestHand, write_manifest, write_manifest_csv
from pokermda.exporters.sanitizer import sanitize_bovada_hand
from pokermda.utils.hashing import sha256_text, stable_id
from pokermda.utils.time import utc_now_iso


def export_bovada_records(
    records: list[GtoExportRecord],
    output_root: Path,
    sanitizer_version: str,
    export_format: str = "bovada_sanitized",
) -> GtoExportBatch:
    timestamp = utc_now_iso().replace(":", "").replace("+", "Z")
    export_id = stable_id("gto_export", timestamp, len(records), sanitizer_version)
    output_dir = output_root / export_id
    output_dir.mkdir(parents=True, exist_ok=True)

    items: list[GtoExportItem] = []
    manifest_hands: list[ManifestHand] = []
    combined_parts: list[str] = []
    offset = 0
    for index, record in enumerate(records, start=1):
        safe_hand_id = record.hand_id.replace(":", "_").replace("/", "_")
        file_name = f"{index:03d}_{safe_hand_id}.txt"
        sanitized = sanitize_bovada_hand(record.raw_text, hero_name=record.hero_name)
        (output_dir / file_name).write_text(sanitized, encoding="utf-8")
        separator = "\n\n"
        start_offset = offset
        combined_parts.append(sanitized.rstrip() + separator)
        offset += len(combined_parts[-1])
        end_offset = offset
        exported_hand_no = f"GTOW-{index:04d}"
        original_site_hand_no = record.hand_id.split(":", 1)[-1] if ":" in record.hand_id else record.hand_id
        sanitized_hash = sha256_text(sanitized)
        export_hand_id = stable_id("gto_export_hand", export_id, record.hand_id)
        items.append(
            GtoExportItem(
                export_hand_id=export_hand_id,
                hand_id=record.hand_id,
                hand_hash=record.hand_hash,
                file_name=file_name,
                exported_hand_no=exported_hand_no,
                original_site_hand_no=original_site_hand_no,
                file_order=index,
                file_offset_start=start_offset,
                file_offset_end=end_offset,
                sanitized_export_hash=sanitized_hash,
            )
        )
        manifest_hands.append(
            ManifestHand(
                hand_id=record.hand_id,
                hand_hash=record.hand_hash,
                file_name=file_name,
                sanitizer_version=sanitizer_version,
                exported_hand_no=exported_hand_no,
                original_site_hand_no=original_site_hand_no,
                file_order=index,
                file_offset_start=start_offset,
                file_offset_end=end_offset,
                sanitized_export_hash=sanitized_hash,
            )
        )

    export_file_path = output_dir / "hands_gtowizard.txt"
    combined_text = "".join(combined_parts)
    export_file_path.write_text(combined_text, encoding="utf-8")
    export_file_sha256 = sha256_text(combined_text)
    manifest_csv_path = write_manifest_csv(output_dir, manifest_hands)
    manifest_path = write_manifest(
        output_dir,
        export_id,
        manifest_hands,
        export_format=export_format,
        sanitizer_version=sanitizer_version,
    )
    return GtoExportBatch(
        export_id=export_id,
        output_dir=output_dir,
        export_file_path=export_file_path,
        export_file_sha256=export_file_sha256,
        manifest_csv_path=manifest_csv_path,
        manifest_path=manifest_path,
        items=items,
    )
