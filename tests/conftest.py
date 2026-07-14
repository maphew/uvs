"""Shared test isolation fixtures."""

import pytest


@pytest.fixture(autouse=True)
def isolate_uvs_registry(tmp_path, monkeypatch):
    """Keep every unit/component test out of the user's real config directory."""
    config_dir = tmp_path / "uvs-config"
    monkeypatch.setattr("uvs.uvs.get_config_dir", lambda: config_dir)
