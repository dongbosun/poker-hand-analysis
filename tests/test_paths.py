from pathlib import Path

from pokermda.config.settings import DATASET_SUBDIRS, load_settings


def test_default_settings_are_pathlib_paths():
    settings = load_settings()

    assert isinstance(settings.project_root, Path)
    assert settings.dataset_dir == settings.project_root / "dataset"
    assert "lake/bronze/raw_hand_blocks" in DATASET_SUBDIRS

