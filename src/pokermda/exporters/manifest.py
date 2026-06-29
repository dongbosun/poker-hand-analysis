"""GTOWizard export manifest writer."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from pokermda.utils.time import utc_now_iso


@dataclass(frozen=True)
class ManifestHand:
    hand_id: str
    hand_hash: str
    file_name: str
    sanitizer_version: str


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

