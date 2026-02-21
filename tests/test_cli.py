import json
import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from click.testing import CliRunner

from uvs.cli import (
    ConfigManager,
    cli,
    parse_config_value,
)


@pytest.fixture
def isolated_temp_dir(tmp_path):
    """Provide an isolated temporary directory for each test."""
    original_cwd = os.getcwd()
    try:
        os.chdir(tmp_path)
        yield tmp_path
    finally:
        os.chdir(original_cwd)


@pytest.fixture
def mock_registry_reset():
    """Reset registry state between tests."""
    # Clean up any existing registry
    registry_path = Path(".uvs-registry.json")
    if registry_path.exists():
        registry_path.unlink()

    yield

    # Clean up after test
    if registry_path.exists():
        registry_path.unlink()


@pytest.fixture
def mock_subprocess():
    """Mock subprocess calls with deterministic behavior."""
    with patch('subprocess.run') as mock_run:
        # Default successful return
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        yield mock_run


class TestConfigManager:
    """Test ConfigManager functionality."""

    def test_init(self, isolated_temp_dir):
        """Test initialization."""
        config = ConfigManager()
        assert "default" in config.config
        assert "install" in config.config
        assert "registry" in config.config

    @patch('pathlib.Path.home')
    def test_get_config_dirs(self, mock_home, isolated_temp_dir):
        """Test config directory resolution."""
        mock_home.return_value = Path("/home/user")
        config = ConfigManager()
        dirs = config._get_config_dirs()
        assert dirs["global"] == Path("/home/user/.config/uvs")
        assert dirs["project"] == Path.cwd()

    def test_get_config_files(self, isolated_temp_dir):
        """Test config file path resolution."""
        with patch('pathlib.Path.home', return_value=Path("/home/user")), \
              patch('pathlib.Path.cwd', return_value=Path("/project")):
            config = ConfigManager()
            files = config._get_config_files()
            assert files["global"] == Path("/home/user/.config/uvs/config.toml")
            assert files["project"] == Path("/project/uvs.toml")
            assert "env" not in files

    def test_get_config_files_with_env_override(self, isolated_temp_dir, monkeypatch):
        """Test config file path resolution with UVS_CONFIG_DIR override."""
        monkeypatch.setenv("UVS_CONFIG_DIR", "/env/config")
        with patch('pathlib.Path.home', return_value=Path("/home/user")), \
              patch('pathlib.Path.cwd', return_value=Path("/project")), \
              patch('pathlib.Path.exists', return_value=True):
            config = ConfigManager()
            files = config._get_config_files()
            assert files["env"] == Path("/env/config/config.toml")

    def test_merge_config(self, isolated_temp_dir):
        """Test config merging."""
        config = ConfigManager()
        config._merge_config({"new_section": {"key": "value"}})
        assert config.config["new_section"]["key"] == "value"

    def test_get_value(self, isolated_temp_dir):
        """Test getting config values."""
        config = ConfigManager()
        config.config.setdefault("test", {})["key"] = "value"
        assert config.get("test.key") == "value"
        assert config.get("nonexistent") is None
        assert config.get("nonexistent", "default") == "default"

    def test_set_value(self, isolated_temp_dir):
        """Test setting config values."""
        config = ConfigManager()
        config.set("test.key", "value")
        assert config.config["test"]["key"] == "value"

    @patch('pathlib.Path.mkdir')
    @patch('pathlib.Path.open', new_callable=MagicMock)
    def test_save_config(self, mock_open, mock_mkdir, isolated_temp_dir):
        """Test saving config."""
        config = ConfigManager()
        config.set("test.key", "value")
        config._save_config("project")
        # The open method should have been called to write the config
        assert mock_open.call_count >= 1

    def test_create_default_config(self, isolated_temp_dir):
        """Test creating default config."""
        config = ConfigManager()
        with patch('pathlib.Path.mkdir'), \
              patch('builtins.open', MagicMock()):
            path = config.create_default_config("project")
            assert "default" in config.config
            assert "install" in config.config


class TestParseConfigValue:
    """Test config value parsing."""

    def test_parse_boolean_true(self, isolated_temp_dir):
        """Test parsing boolean true."""
        assert parse_config_value("true") is True
        assert parse_config_value("True") is True

    def test_parse_boolean_false(self, isolated_temp_dir):
        """Test parsing boolean false."""
        assert parse_config_value("false") is False
        assert parse_config_value("False") is False

    def test_parse_integer(self, isolated_temp_dir):
        """Test parsing integers."""
        assert parse_config_value("42") == 42
        assert parse_config_value("0") == 0

    def test_parse_float(self, isolated_temp_dir):
        """Test parsing floats."""
        assert parse_config_value("3.14") == 3.14
        assert parse_config_value("1.0") == 1.0

    def test_parse_string(self, isolated_temp_dir):
        """Test parsing strings."""
        assert parse_config_value("hello") == "hello"
        assert parse_config_value("hello world") == "hello world"


class TestConfigSecurity:
    """Test config-related security considerations."""

    def test_config_value_no_code_execution(self, isolated_temp_dir):
        """Test config parsing doesn't execute code."""
        # This should not execute code
        result = parse_config_value("__import__('os').system('echo pwned')")
        assert result == "__import__('os').system('echo pwned')"


class TestConfigCommands:
    """Test config command behavior."""

    def test_config_get_global_scope(self, isolated_temp_dir, monkeypatch):
        """config get --global reads global scope, not merged/project."""
        home = isolated_temp_dir / "home"
        global_dir = home / ".config" / "uvs"
        global_dir.mkdir(parents=True)
        (global_dir / "config.toml").write_text(
            '[default]\npython = "3.12"\n', encoding="utf-8"
        )
        (isolated_temp_dir / "uvs.toml").write_text(
            '[default]\npython = "3.11"\n', encoding="utf-8"
        )
        monkeypatch.setenv("HOME", str(home))

        runner = CliRunner()
        result = runner.invoke(cli, ["config", "get", "--global", "default.python"])

        assert result.exit_code == 0
        assert "default.python = 3.12" in result.output

    def test_config_list_global_scope(self, isolated_temp_dir, monkeypatch):
        """config list --global shows global values."""
        home = isolated_temp_dir / "home"
        global_dir = home / ".config" / "uvs"
        global_dir.mkdir(parents=True)
        (global_dir / "config.toml").write_text(
            '[default]\npython = "3.12"\n', encoding="utf-8"
        )
        (isolated_temp_dir / "uvs.toml").write_text(
            '[default]\npython = "3.11"\n', encoding="utf-8"
        )
        monkeypatch.setenv("HOME", str(home))

        runner = CliRunner()
        result = runner.invoke(cli, ["--no-color", "config", "list", "--global"])

        assert result.exit_code == 0
        assert "3.12" in result.output
        assert "3.11" not in result.output
