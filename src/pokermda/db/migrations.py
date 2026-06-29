"""Schema application helpers."""

from __future__ import annotations

from pathlib import Path


def schema_path() -> Path:
    return Path(__file__).with_name("schema.sql")


def apply_schema(connection) -> None:
    sql = schema_path().read_text(encoding="utf-8")
    for statement in sql.split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)
