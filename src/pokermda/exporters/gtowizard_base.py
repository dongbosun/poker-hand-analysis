"""Shared GTOWizard export models."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GtoExportRecord:
    hand_id: str
    hand_hash: str
    raw_text: str
    hero_name: str | None = None


@dataclass(frozen=True)
class GtoExportItem:
    export_hand_id: str
    hand_id: str
    hand_hash: str
    file_name: str
    exported_hand_no: str
    original_site_hand_no: str | None
    file_order: int
    file_offset_start: int
    file_offset_end: int
    sanitized_export_hash: str


@dataclass(frozen=True)
class GtoExportBatch:
    export_id: str
    output_dir: Path
    export_file_path: Path
    export_file_sha256: str
    manifest_csv_path: Path
    manifest_path: Path
    items: list[GtoExportItem]
