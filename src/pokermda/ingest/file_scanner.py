"""Recursive Bovada hand history file scanner."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pokermda.utils.hashing import sha256_file


@dataclass(frozen=True, slots=True)
class HandHistoryFile:
    path: Path
    realpath: Path
    file_hash: str
    file_size_bytes: int
    modified_time_ns: int
    modified_time: str


def scan_hand_history_files(root: Path, pattern: str = "*.txt") -> list[HandHistoryFile]:
    root = Path(root).expanduser()
    if not root.exists():
        return []

    records: list[HandHistoryFile] = []
    for path in sorted(root.rglob(pattern)):
        if not path.is_file():
            continue
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
        records.append(
            HandHistoryFile(
                path=path,
                realpath=path.resolve(),
                file_hash=sha256_file(path),
                file_size_bytes=stat.st_size,
                modified_time_ns=stat.st_mtime_ns,
                modified_time=modified,
            )
        )
    return records


def read_text_with_fallback(path: Path, encoding: str = "utf-8", fallback: str = "latin-1") -> str:
    try:
        return path.read_text(encoding=encoding)
    except UnicodeDecodeError:
        return path.read_text(encoding=fallback)
