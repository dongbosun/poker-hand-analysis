"""Range heatmap export placeholder."""

from __future__ import annotations

from pathlib import Path


def export_heatmap_csv(matrix: dict[str, float], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    rows = ["combo,weight", *[f"{combo},{weight}" for combo, weight in matrix.items()]]
    output_path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return output_path

