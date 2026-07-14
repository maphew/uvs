"""Shared test isolation fixtures."""

from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_uvs_registry(tmp_path, monkeypatch):
    """Keep tests out of the user's registry and CLI config directories."""
    config_dir = tmp_path / "uvs-config"
    home_dir = tmp_path / "home"
    monkeypatch.setattr("uvs.uvs.get_config_dir", lambda: config_dir)
    monkeypatch.setattr(Path, "home", lambda: home_dir)
