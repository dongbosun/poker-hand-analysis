"""Load node specs from config directories."""

from __future__ import annotations

from pathlib import Path

from pokermda.nodes.node_spec import NodeSpec, load_node_spec


def load_node_registry(directory: Path) -> list[NodeSpec]:
    if not directory.exists():
        return []
    return [load_node_spec(path) for path in sorted(directory.glob("*.yaml"))]

