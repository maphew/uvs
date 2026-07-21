"""CLI output contract tests."""

from unittest.mock import patch

from click.testing import CliRunner

from uvs.cli import cli


def test_help_does_not_advertise_removed_debug_option():
    result = CliRunner().invoke(cli, ["--help"])

    assert result.exit_code == 0
    assert "--verbose" in result.output
    assert "--debug" not in result.output


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
