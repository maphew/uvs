"""Contract tests for deterministic lifecycle and registry behavior."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from uvs.cli import cli
from uvs.uvs import (
    get_registry_path,
    load_registry,
    registry_lock,
    run_uv_install,
    run_uv_uninstall,
    save_registry,
)


def registry_entry(source: Path, *, source_hash: str = "old") -> dict[str, str]:
    return {
        "tool_name": "custom-command",
        "source_path": str(source),
        "source_hash": source_hash,
        "installed_at": "2026-01-01T00:00:00Z",
        "version": "0.1.0",
    }


def test_registry_write_is_atomic_when_replace_fails(tmp_path):
    registry_path = get_registry_path()
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text('{"sentinel": true}\n', encoding="utf8")
    source = tmp_path / "source.py"
    source.write_text("def main(): pass\n", encoding="utf8")

    with patch("uvs.uvs.os.replace", side_effect=OSError("replace failed")):
        with pytest.raises(OSError, match="replace failed"):
            save_registry({"version": "1.0", "scripts": {"tool": registry_entry(source)}})

    assert registry_path.read_text(encoding="utf8") == '{"sentinel": true}\n'
    assert list(registry_path.parent.glob(".registry.json.*.tmp")) == []


def test_corrupt_registry_is_archived_and_recovered(capsys):
    registry_path = get_registry_path()
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text("not json", encoding="utf8")

    recovered = load_registry()

    assert recovered["version"] == "1.0"
    assert recovered["scripts"] == {}
    assert not registry_path.exists()
    archives = list(registry_path.parent.glob("registry.invalid-*.json"))
    assert len(archives) == 1
    assert archives[0].read_text(encoding="utf8") == "not json"
    assert "archived invalid registry" in capsys.readouterr().err


def test_pre_versioned_registry_is_normalized(tmp_path):
    source = tmp_path / "source.py"
    registry_path = get_registry_path()
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps({"scripts": {"custom-command": registry_entry(source)}}),
        encoding="utf8",
    )

    registry = load_registry()

    assert registry["version"] == "1.0"
    assert registry["scripts"]["custom-command"]["tool_name"] == "custom-command"
    assert Path(registry["scripts"]["custom-command"]["source_path"]).is_absolute()


def test_future_registry_version_is_left_untouched():
    registry_path = get_registry_path()
    registry_path.parent.mkdir(parents=True)
    contents = '{"version": "2.0", "scripts": {}}\n'
    registry_path.write_text(contents, encoding="utf8")

    with pytest.raises(RuntimeError, match="unsupported registry version"):
        load_registry()

    assert registry_path.read_text(encoding="utf8") == contents
    assert list(registry_path.parent.glob("registry.invalid-*.json")) == []


def test_invalid_entry_is_archived_without_losing_valid_entries(tmp_path):
    source = tmp_path / "source.py"
    registry_path = get_registry_path()
    registry_path.parent.mkdir(parents=True)
    registry_path.write_text(
        json.dumps(
            {
                "version": "1.0",
                "scripts": {
                    "valid": registry_entry(source),
                    "broken": {"source_path": ""},
                },
            }
        ),
        encoding="utf8",
    )

    recovered = load_registry()

    assert set(recovered["scripts"]) == {"valid"}
    assert set(load_registry()["scripts"]) == {"valid"}
    assert registry_path.exists()
    assert len(list(registry_path.parent.glob("registry.invalid-*.json"))) == 1


def test_registry_lock_prevents_overlapping_mutations():
    with registry_lock():
        with pytest.raises(TimeoutError, match="registry lock"):
            with registry_lock(timeout=0.01):
                pass


@pytest.mark.parametrize(
    ("operation", "argument"),
    [
        (run_uv_install, Path("package")),
        (run_uv_uninstall, "tool"),
    ],
)
def test_quiet_subprocess_helpers_suppress_normal_output(operation, argument, capsys):
    completed = type(
        "Completed", (), {"returncode": 0, "stdout": "uv chatter", "stderr": ""}
    )()
    with patch("uvs.uvs.subprocess.run", return_value=completed) as run:
        assert operation(argument, quiet=True) == 0

    assert capsys.readouterr() == ("", "")
    assert run.call_args.kwargs == {"capture_output": True, "text": True}


def test_quiet_install_dry_run_has_no_output(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main(): pass\n", encoding="utf8")

    result = CliRunner().invoke(cli, ["--quiet", "install", "--dry-run", str(script)])

    assert result.exit_code == 0
    assert result.stdout == ""
    assert result.stderr == ""


def test_empty_list_json_is_plain_parseable_json():
    with patch("uvs.cli.load_registry", return_value={"version": "1.0", "scripts": {}}):
        result = CliRunner().invoke(cli, ["list", "--format", "json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"tools": {}, "count": 0}
    assert result.stderr == ""


def test_list_json_has_no_rich_decoration(tmp_path):
    tools = {"custom-command": registry_entry(tmp_path / "source.py")}
    with patch("uvs.cli.load_registry", return_value={"version": "1.0", "scripts": tools}):
        result = CliRunner().invoke(cli, ["--no-color", "list", "--format", "json"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == {"tools": tools, "count": 1}
    assert "Installed Tools" not in result.stdout


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["install"], "Script path is required"),
        (["update"], "SCRIPT or --all is required"),
        (["uninstall"], "Either TOOL_NAME or --all is required"),
    ],
)
def test_missing_lifecycle_arguments_fail_on_stderr(arguments, message):
    result = CliRunner().invoke(cli, arguments)

    assert result.exit_code != 0
    assert result.stdout == ""
    assert message in result.stderr


def test_removed_config_surface_is_rejected():
    result = CliRunner().invoke(cli, ["config", "list"])

    assert result.exit_code == 2
    assert "No such command 'config'" in result.stderr


def test_update_noop_is_successful(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main(): pass\n", encoding="utf8")
    from uvs.uvs import compute_hash

    entry = registry_entry(script, source_hash=compute_hash(script))
    registry = {"version": "1.0", "scripts": {"custom-command": entry}}
    with patch("uvs.cli.load_registry", return_value=registry):
        result = CliRunner().invoke(cli, ["update", str(script)])

    assert result.exit_code == 0
    assert result.stderr == ""
    assert "No changes detected for custom-command" in result.stdout


def test_update_rejects_ambiguous_canonical_source(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main(): pass\n", encoding="utf8")
    registry = {
        "version": "1.0",
        "scripts": {
            "first": registry_entry(script),
            "second": registry_entry(script),
        },
    }
    with patch("uvs.cli.load_registry", return_value=registry):
        result = CliRunner().invoke(cli, ["update", str(script)])

    assert result.exit_code != 0
    assert result.stdout == ""
    assert "Multiple installed tools map to" in result.stderr


def test_registry_save_failure_rolls_back_installed_tool(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main(): pass\n", encoding="utf8")
    with (
        patch("uvs.uvs.run_uv_install", return_value=0),
        patch("uvs.cli.save_registry", side_effect=OSError("disk full")),
        patch("uvs.cli.run_uv_uninstall", return_value=0) as rollback,
    ):
        result = CliRunner().invoke(cli, ["--no-color", "install", str(script)])

    assert result.exit_code != 0
    assert "uv installed the tool but the uvs registry was not updated" in result.stderr
    assert "disk full" in result.stderr
    assert "Rollback succeeded: uninstalled 'source'" in result.stderr
    assert "Successfully installed" not in result.stdout
    rollback.assert_called_once_with("source", quiet=False)


def test_registry_save_failure_reports_failed_rollback(tmp_path):
    script = tmp_path / "source.py"
    script.write_text("def main(): pass\n", encoding="utf8")
    with (
        patch("uvs.uvs.run_uv_install", return_value=0),
        patch("uvs.cli.save_registry", side_effect=OSError("disk full")),
        patch("uvs.cli.run_uv_uninstall", return_value=7) as rollback,
    ):
        result = CliRunner().invoke(cli, ["--no-color", "install", str(script)])

    assert result.exit_code != 0
    assert "uv installed the tool but the uvs registry was not updated" in result.stderr
    assert "disk full" in result.stderr
    assert "Rollback failed for 'source' (uv exit code 7)" in result.stderr
    assert "may remain installed but untracked" in result.stderr
    assert "Successfully installed" not in result.stdout
    rollback.assert_called_once_with("source", quiet=False)
