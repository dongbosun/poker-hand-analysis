"""Node export placeholder."""

from __future__ import annotations

from pathlib import Path


def export_node_summary(output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("node_id,metric,value\n", encoding="utf-8")
    return output_path

