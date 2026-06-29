"""Path helpers.

All filesystem paths in the project should flow through pathlib.
"""

from __future__ import annotations

from pathlib import Path


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def ensure_directory(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def expand_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()

