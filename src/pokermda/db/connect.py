"""DuckDB connection management."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def require_duckdb() -> Any:
    try:
        import duckdb
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Missing dependency 'duckdb'. Install the project with: "
            "python -m pip install -e \".[dev]\""
        ) from exc
    return duckdb


def connect_database(db_path: Path):
    duckdb = require_duckdb()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(db_path))

