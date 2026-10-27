"""CLI output contract tests."""

from unittest.mock import patch

from click.testing import CliRunner

from uvs.cli import cli


def test_help_does_not_advertise_removed_debug_option():
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "--verbose" in result.output
    assert "--debug" not in result.output


def test_version_option_reports_package_version():
    from uvs import __version__

    result = CliRunner().invoke(cli, ["--version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"uvs, version {__version__}"


def test_removed_debug_option_is_rejected():
    result = CliRunner().invoke(cli, ["--debug"])

    assert result.exit_code == 2
    assert "No such option: --debug" in result.output


def test_verbose_option_still_enables_detailed_output():
    tool_info = {
        "tool_name": "example",
        "source_path": "C:/scripts/example.py",
        "version": "1.2.3",
        "installed_at": "2026-07-14T12:34:56+00:00",
        "source_hash": "0123456789abcdef0123456789abcdef",
    }
    registry = {"version": "1.0", "scripts": {"example": tool_info}}

    with patch("uvs.cli.load_registry", return_value=registry):
        result = CliRunner().invoke(cli, ["--verbose", "list"])

    assert result.exit_code == 0
    assert "Total: 1 tools" in result.output


def test_show_simple_has_stable_undecorated_output():
    tool_info = {
        "tool_name": "example",
        "source_path": "C:/scripts/example.py",
        "version": "1.2.3",
        "installed_at": "2026-07-14T12:34:56+00:00",
        "source_hash": "0123456789abcdef0123456789abcdef",
    }
    registry = {"version": "1.0", "scripts": {"example": tool_info}}

    with patch("uvs.cli.load_registry", return_value=registry):
        result = CliRunner().invoke(cli, ["show", "example", "--format", "simple"])

    assert result.exit_code == 0
    assert result.output == (
        "Name: example\n"
        "Source: C:/scripts/example.py\n"
        "Version: 1.2.3\n"
        "Installed: 2026-07-14T12:34:56+00:00\n"
        "Hash: 0123456789abcdef0123456789abcdef\n"
    )
    assert result.exception is None


def test_install_all_rejects_explicit_name_before_processing(tmp_path):
    with patch("uvs.cli.install_script_quiet") as install_script:
        result = CliRunner().invoke(
            cli, ["install", "--all", "--name", "shared-name", str(tmp_path)]
        )

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Cannot use --name with --all" in result.stderr
    install_script.assert_not_called()


def test_directory_script_argument_is_a_usage_error(tmp_path):
    result = CliRunner().invoke(cli, ["install", str(tmp_path)])

    assert result.exit_code == 2
    assert "is a directory" in result.stderr
    assert "--all" in result.stderr
    assert not isinstance(result.exception, OSError)


def test_missing_uv_is_reported_without_a_traceback(tmp_path, monkeypatch):
    script = tmp_path / "source.py"
    script.write_text("def main():\n    pass\n", encoding="utf-8")
    monkeypatch.setattr("uvs.cli.shutil.which", lambda _name: None)

    result = CliRunner().invoke(cli, ["install", str(script)])

    assert result.exit_code == 1
    assert "uv is not installed or not on PATH" in result.stderr
    assert not isinstance(result.exception, FileNotFoundError)


def test_unsupported_registry_version_is_a_clean_error(tmp_path):
    from uvs.uvs import get_registry_path

    registry_path = get_registry_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text('{"version": "9.9", "scripts": {}}', encoding="utf-8")

    result = CliRunner().invoke(cli, ["list"])

    assert result.exit_code == 1
    assert "unsupported registry version" in result.stderr
    assert not isinstance(result.exception, RuntimeError)


def test_uninstall_all_and_tool_name_conflict_is_rejected():
    result = CliRunner().invoke(cli, ["uninstall", "--all", "some-tool"])

    assert result.exit_code == 2
    assert "Cannot combine TOOL_NAME with --all" in result.stderr


def test_install_refuses_to_replace_a_tracked_tool_without_force(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main():\n    pass\n", encoding="utf-8")
    registry = {
        "version": "1.0",
        "scripts": {
            "source": {
                "tool_name": "source",
                "source_path": str(script.resolve()),
                "source_hash": "old",
                "installed_at": "2026-01-01T00:00:00+00:00",
                "version": "3.0.0",
            }
        },
    }
    with patch("uvs.cli.load_registry", return_value=registry):
        result = CliRunner().invoke(cli, ["install", str(script)])

    assert result.exit_code == 2
    assert "already tracked" in result.stderr
    assert "--force" in result.stderr


def test_install_force_preserves_existing_version(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main():\n    pass\n", encoding="utf-8")
    registry = {
        "version": "1.0",
        "scripts": {
            "source": {
                "tool_name": "source",
                "source_path": str(script.resolve()),
                "source_hash": "old",
                "installed_at": "2026-01-01T00:00:00+00:00",
                "version": "3.0.0",
            }
        },
    }
    with (
        patch("uvs.cli.load_registry", return_value=registry),
        patch("uvs.cli.save_registry"),
        patch("uvs.uvs.run_uv_install", return_value=0),
        patch("uvs.cli.uv_tool_names", return_value=None),
    ):
        result = CliRunner().invoke(cli, ["install", "--force", str(script)])

    assert result.exit_code == 0
    assert registry["scripts"]["source"]["version"] == "3.0.0"


def test_install_reports_name_normalization(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main():\n    pass\n", encoding="utf-8")
    with (
        patch("uvs.cli.load_registry", return_value={"version": "1.0", "scripts": {}}),
        patch("uvs.cli.save_registry"),
        patch("uvs.uvs.run_uv_install", return_value=0),
        patch("uvs.cli.uv_tool_names", return_value=set()),
    ):
        result = CliRunner().invoke(
            cli, ["install", "--name", "my_tool", str(script)]
        )

    assert result.exit_code == 0
    assert "using command name 'my-tool' (from 'my_tool')" in result.stdout


def test_update_accepts_a_tool_name(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main():\n    pass\n# changed\n", encoding="utf-8")
    registry = {
        "version": "1.0",
        "scripts": {
            "custom-command": {
                "tool_name": "custom-command",
                "source_path": str(script.resolve()),
                "source_hash": "old",
                "installed_at": "2026-01-01T00:00:00+00:00",
                "version": "0.1.0",
            }
        },
    }
    with (
        patch("uvs.cli.load_registry", return_value=registry),
        patch("uvs.cli.save_registry"),
        patch("uvs.uvs.run_uv_install", return_value=0),
    ):
        result = CliRunner().invoke(cli, ["update", "custom-command"])

    assert result.exit_code == 0
    assert "Successfully updated custom-command" in result.stdout


def test_update_dry_run_does_not_install(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main():\n    pass\n# changed\n", encoding="utf-8")
    registry = {
        "version": "1.0",
        "scripts": {
            "custom-command": {
                "tool_name": "custom-command",
                "source_path": str(script.resolve()),
                "source_hash": "old",
                "installed_at": "2026-01-01T00:00:00+00:00",
                "version": "0.1.0",
            }
        },
    }
    with (
        patch("uvs.cli.load_registry", return_value=registry),
        patch("uvs.uvs.run_uv_install") as install,
    ):
        result = CliRunner().invoke(cli, ["update", "--dry-run", "custom-command"])

    assert result.exit_code == 0
    assert "Would update custom-command (0.1.0 -> 0.1.1)" in result.stdout
    install.assert_not_called()


def test_quiet_list_still_prints_data():
    tools = {
        "example": {
            "tool_name": "example",
            "source_path": "/tmp/example.py",
            "version": "1.0.0",
            "installed_at": "2026-01-01T00:00:00+00:00",
            "source_hash": "",
        }
    }
    with patch("uvs.cli.load_registry", return_value={"version": "1.0", "scripts": tools}):
        result = CliRunner().invoke(cli, ["--quiet", "list", "--format", "simple"])

    assert result.exit_code == 0
    assert "example <- /tmp/example.py (v1.0.0)" in result.stdout


def test_quiet_show_still_prints_data():
    tools = {
        "example": {
            "tool_name": "example",
            "source_path": "/tmp/example.py",
            "version": "1.0.0",
            "installed_at": "2026-01-01T00:00:00+00:00",
            "source_hash": "abc",
        }
    }
    with patch("uvs.cli.load_registry", return_value={"version": "1.0", "scripts": tools}):
        result = CliRunner().invoke(
            cli, ["--quiet", "show", "example", "--format", "simple"]
        )

    assert result.exit_code == 0
    assert result.stdout.startswith("Name: example\n")


def test_no_color_flag_and_environment_are_honored(monkeypatch):
    from uvs.cli import _resolve_no_color

    assert _resolve_no_color(True) is True
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("TERM", "xterm-256color")
    assert _resolve_no_color(False) is False
    monkeypatch.setenv("NO_COLOR", "1")
    assert _resolve_no_color(False) is True


def test_human_timestamp_is_compact_and_utc():
    from uvs.cli import _human_timestamp

    assert _human_timestamp("2026-07-14T12:34:56.123456+00:00") == (
        "2026-07-14 12:34:56 UTC"
    )
    assert _human_timestamp("") == "unknown"


def test_list_check_reports_status_and_exit_code(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main():\n    pass\n", encoding="utf-8")
    tools = {
        "example": {
            "tool_name": "example",
            "source_path": str(script.resolve()),
            "version": "1.0.0",
            "installed_at": "2026-01-01T00:00:00+00:00",
            "source_hash": "stale",
        }
    }
    with (
        patch("uvs.cli.load_registry", return_value={"version": "1.0", "scripts": tools}),
        patch("uvs.cli.uv_tool_names", return_value={"example"}),
    ):
        result = CliRunner().invoke(cli, ["list", "--check", "--format", "simple"])

    assert result.exit_code == 1
    assert "source changed" in result.stdout
    assert "need attention" in result.stderr


def test_backup_list_and_restore(tmp_path):
    from uvs.uvs import save_registry

    save_registry(
        {
            "version": "1.0",
            "scripts": {
                "example": {
                    "tool_name": "example",
                    "source_path": str(tmp_path / "source.py"),
                    "source_hash": "abc",
                    "installed_at": "2026-01-01T00:00:00+00:00",
                    "version": "1.0.0",
                }
            },
        }
    )
    runner = CliRunner()
    uninstall = runner.invoke(cli, ["uninstall", "--force", "example"])
    assert uninstall.exit_code == 0

    listed = runner.invoke(cli, ["backup", "list", "--format", "json"])
    assert listed.exit_code == 0
    assert "registry_" in listed.stdout

    restored = runner.invoke(cli, ["backup", "restore", "latest"])
    assert restored.exit_code == 0
    assert "Restored registry" in restored.stdout
