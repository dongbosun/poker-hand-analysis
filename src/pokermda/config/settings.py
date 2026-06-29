"""Local settings for the poker hand analyzer."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pokermda.utils.paths import project_root


@dataclass(frozen=True)
class IngestSettings:
    file_glob: str = "*.txt"
    encoding: str = "utf-8"
    fallback_encoding: str = "latin-1"
    stop_on_parse_error: bool = False


@dataclass(frozen=True)
class GtoWizardSettings:
    export_format: str = "bovada_sanitized"
    sanitizer_version: str = "hero-perspective-v1"
    default_batch_size: int = 20


@dataclass(frozen=True)
class AppSettings:
    project_root: Path
    dataset_dir: Path
    bovada_raw_hand_history_dir: Path
    duckdb_path: Path
    create_raw_symlink: bool = True
    raw_symlink_name: str = "bovada_hand_history"
    timezone: str = "America/Los_Angeles"
    hero_aliases: tuple[str, ...] = ("Hero",)
    ingest: IngestSettings = field(default_factory=IngestSettings)
    gtowizard: GtoWizardSettings = field(default_factory=GtoWizardSettings)

    @property
    def raw_symlink_path(self) -> Path:
        return self.dataset_dir / "raw" / self.raw_symlink_name


DATASET_SUBDIRS = (
    "raw",
    "db",
    "lake/bronze/raw_hand_blocks",
    "lake/silver/hands",
    "lake/silver/participants",
    "lake/silver/actions",
    "lake/silver/results",
    "lake/silver/player_hand_facts",
    "lake/gold/decision_instances",
    "lake/gold/node_instances",
    "lake/gold/stat_aggregates",
    "lake/gold/range_aggregates",
    "lake/gold/review_candidates",
    "exports/gtowizard",
    "exports/review_queue",
    "exports/ranges",
    "review/notes",
    "review/screenshots",
    "review/gtowizard_manual_results",
    "logs",
    "tmp/duckdb",
    "ledger",
)


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise RuntimeError("PyYAML is required to read YAML config files.") from exc

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file must contain a YAML mapping: {path}")
    return data


def _path_from_config(value: str | None, fallback: Path) -> Path:
    if not value:
        return fallback
    return Path(value).expanduser()


def load_settings(config_path: str | Path | None = None) -> AppSettings:
    root = project_root()
    env_path = os.environ.get("POKERMDA_CONFIG")
    default_local = root / "config" / "local.yaml"

    chosen_path: Path | None
    if config_path:
        chosen_path = Path(config_path).expanduser()
    elif env_path:
        chosen_path = Path(env_path).expanduser()
    elif default_local.exists():
        chosen_path = default_local
    else:
        chosen_path = None

    data: dict[str, Any] = _load_yaml(chosen_path) if chosen_path and chosen_path.exists() else {}

    project = _path_from_config(data.get("project_root"), root)
    dataset = _path_from_config(data.get("dataset_dir"), project / "dataset")
    raw_dir = _path_from_config(
        data.get("bovada_raw_hand_history_dir"),
        Path("/Users/dongbosun/Bovada.lv Poker/Hand History"),
    )
    duckdb_path = _path_from_config(data.get("duckdb_path"), dataset / "db" / "poker.duckdb")

    ingest_data = data.get("ingest") or {}
    gto_data = data.get("gtowizard") or {}

    return AppSettings(
        project_root=project,
        dataset_dir=dataset,
        bovada_raw_hand_history_dir=raw_dir,
        duckdb_path=duckdb_path,
        create_raw_symlink=bool(data.get("create_raw_symlink", True)),
        raw_symlink_name=str(data.get("raw_symlink_name", "bovada_hand_history")),
        timezone=str(data.get("timezone", "America/Los_Angeles")),
        hero_aliases=tuple(data.get("hero_aliases") or ("Hero",)),
        ingest=IngestSettings(
            file_glob=str(ingest_data.get("file_glob", "*.txt")),
            encoding=str(ingest_data.get("encoding", "utf-8")),
            fallback_encoding=str(ingest_data.get("fallback_encoding", "latin-1")),
            stop_on_parse_error=bool(ingest_data.get("stop_on_parse_error", False)),
        ),
        gtowizard=GtoWizardSettings(
            export_format=str(gto_data.get("export_format", "bovada_sanitized")),
            sanitizer_version=str(gto_data.get("sanitizer_version", "hero-perspective-v1")),
            default_batch_size=int(gto_data.get("default_batch_size", 20)),
        ),
    )


def ensure_dataset_layout(settings: AppSettings) -> list[str]:
    messages: list[str] = []
    for relative in DATASET_SUBDIRS:
        (settings.dataset_dir / relative).mkdir(parents=True, exist_ok=True)

    if settings.create_raw_symlink:
        link_path = settings.raw_symlink_path
        target = settings.bovada_raw_hand_history_dir
        if not link_path.exists() and not link_path.is_symlink() and target.exists():
            try:
                link_path.symlink_to(target, target_is_directory=True)
                messages.append(f"Created symlink: {link_path} -> {target}")
            except OSError as exc:
                messages.append(f"Could not create raw symlink: {exc}")
        elif link_path.exists() or link_path.is_symlink():
            messages.append(f"Raw symlink already exists: {link_path}")
        else:
            messages.append(f"Bovada raw directory does not exist yet: {target}")

    return messages

