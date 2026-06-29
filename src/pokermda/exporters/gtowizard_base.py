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
    hand_id: str
    hand_hash: str
    file_name: str


@dataclass(frozen=True)
class GtoExportBatch:
    export_id: str
    output_dir: Path
    manifest_path: Path
    items: list[GtoExportItem]

