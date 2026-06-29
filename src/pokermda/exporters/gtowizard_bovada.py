"""Bovada to GTOWizard local export."""

from __future__ import annotations

from pathlib import Path

from pokermda.exporters.gtowizard_base import GtoExportBatch, GtoExportItem, GtoExportRecord
from pokermda.exporters.manifest import ManifestHand, write_manifest
from pokermda.exporters.sanitizer import sanitize_bovada_hand
from pokermda.utils.hashing import stable_id
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
    for index, record in enumerate(records, start=1):
        safe_hand_id = record.hand_id.replace(":", "_").replace("/", "_")
        file_name = f"{index:03d}_{safe_hand_id}.txt"
        sanitized = sanitize_bovada_hand(record.raw_text, hero_name=record.hero_name)
        (output_dir / file_name).write_text(sanitized, encoding="utf-8")
        items.append(GtoExportItem(record.hand_id, record.hand_hash, file_name))
        manifest_hands.append(
            ManifestHand(
                hand_id=record.hand_id,
                hand_hash=record.hand_hash,
                file_name=file_name,
                sanitizer_version=sanitizer_version,
            )
        )

    manifest_path = write_manifest(
        output_dir,
        export_id,
        manifest_hands,
        export_format=export_format,
        sanitizer_version=sanitizer_version,
    )
    return GtoExportBatch(export_id, output_dir, manifest_path, items)

