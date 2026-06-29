"""Node spec model and loader."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class NodeSpec:
    node_id: str
    description: str
    street: str
    filters: dict[str, Any] = field(default_factory=dict)
    metrics: list[str] = field(default_factory=list)
    group_by: list[str] = field(default_factory=list)
    source_path: Path | None = None


def load_node_spec(path: Path) -> NodeSpec:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to load node definitions.") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return NodeSpec(
        node_id=str(data["id"]),
        description=str(data.get("description", "")),
        street=str(data.get("street", "unknown")),
        filters=dict(data.get("filters") or {}),
        metrics=list(data.get("metrics") or []),
        group_by=list(data.get("group_by") or []),
        source_path=path,
    )

