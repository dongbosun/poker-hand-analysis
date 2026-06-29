"""GTOWizard export manifest writer."""

from __future__ import annotations

import json
import csv
from dataclasses import asdict, dataclass
from pathlib import Path

from pokermda.utils.time import utc_now_iso


@dataclass(frozen=True)
class ManifestHand:
    hand_id: str
    hand_hash: str
    file_name: str
    sanitizer_version: str
    exported_hand_no: str | None = None
    original_site_hand_no: str | None = None
    file_order: int | None = None
    file_offset_start: int | None = None
    file_offset_end: int | None = None
    sanitized_export_hash: str | None = None


def write_manifest(
    output_dir: Path,
    export_id: str,
    hands: list[ManifestHand],
    export_format: str,
    sanitizer_version: str,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "export_id": export_id,
        "generated_at": utc_now_iso(),
        "export_format": export_format,
        "sanitizer_version": sanitizer_version,
        "hand_count": len(hands),
        "hands": [asdict(hand) for hand in hands],
    }
    path = output_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_manifest_csv(output_dir: Path, hands: list[ManifestHand]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / "manifest.csv"
    fieldnames = [
        "file_order",
        "hand_id",
        "original_site_hand_no",
        "exported_hand_no",
        "file_name",
        "hand_hash",
        "sanitized_export_hash",
        "file_offset_start",
        "file_offset_end",
        "sanitizer_version",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for hand in hands:
            row = asdict(hand)
            writer.writerow({field: row.get(field) for field in fieldnames})
    return path
