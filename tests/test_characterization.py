"""Characterize pre-hardening behavior without endorsing it as the contract."""

from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from uvs.cli import ConfigManager, cli, install_script_quiet
from uvs.uvs import (
    derive_tool_name,
    parse_pep723_header,
    strip_pep723_header_and_main,
    validate_script_has_main,
)


def write_script(path: Path, body: str) -> Path:
    path.write_text(body, encoding="utf-8")
    return path


def test_current_pep723_parser_reads_scalar_and_multiline_list(tmp_path):
    script = write_script(
        tmp_path / "sample.py",
        '''# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "click>=8",
#   "rich",
# ]
# ///
''',
    )
    assert parse_pep723_header(script) == {
        "requires-python": ">=3.10",
        "dependencies": ["click>=8", "rich"],
    }


def test_current_pep723_parser_returns_empty_for_unterminated_block(tmp_path):
    script = write_script(
        tmp_path / "unterminated.py",
        '# /// script\n# dependencies = ["click"]\n',
    )
    assert parse_pep723_header(script) == {}


def test_current_pep723_parser_degrades_malformed_value_to_string(tmp_path):
    script = write_script(
        tmp_path / "malformed.py",
        '# /// script\n# dependencies = [not valid]\n# ///\n',
    )
    assert parse_pep723_header(script) == {"dependencies": "[not valid]"}


def test_current_source_transformation_removes_metadata_and_main_guard():
    source = '''# /// script
# dependencies = []
# ///

def main():
    print("hello")

if __name__ == "__main__":
    main()
'''
    transformed = strip_pep723_header_and_main(source)
    assert "# /// script" not in transformed
    assert 'if __name__ == "__main__"' not in transformed
    assert "def main():" in transformed
    assert transformed.endswith("\n")


@pytest.mark.parametrize(
    ("filename", "explicit", "expected"),
    [
        ("hello.py", None, ("hello", "hello")),
        ("hello_world.py", None, ("hello-world", "hello_world")),
        ("ignored.py", "custom_name", ("custom-name", "custom_name")),
        ("odd name.py", None, ("odd name", "odd name")),
        ("ignored.py", "a.b", ("a.b", "a.b")),
    ],
)
def test_current_filename_and_tool_name_derivation(filename, explicit, expected):
    assert derive_tool_name(Path(filename), explicit) == expected


def test_custom_name_install_is_stored_under_custom_command(tmp_path):
    script = write_script(
        tmp_path / "source_name.py", "def main():\n    print('hello')\n"
    )
    registry = {"version": "1.0", "scripts": {}}
    with (
        patch("uvs.cli.load_registry", return_value=registry),
        patch("uvs.cli.save_registry") as save_registry,
        patch("uvs.uvs.run_uv_install", return_value=0),
    ):
        result = install_script_quiet(
            script,
            {
                "name": "custom-command",
                "version": "0.1.0",
                "tempdir": tmp_path / "generated",
            },
        )
    assert result == 0
    saved = save_registry.call_args.args[0]
    assert set(saved["scripts"]) == {"custom-command"}
    assert saved["scripts"]["custom-command"]["source_path"] == str(script.resolve())


def test_current_update_lookup_does_not_find_custom_name_by_source(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = write_script(tmp_path / "source_name.py", "def main():\n    pass\n")
    registry = {
        "version": "1.0",
        "scripts": {
            "custom-command": {
                "tool_name": "custom-command",
                "source_path": str(script.resolve()),
                "source_hash": "old",
                "version": "0.1.0",
            }
        },
    }
    with patch("uvs.cli.load_registry", return_value=registry):
        result = CliRunner().invoke(cli, ["update", str(script)])
    assert result.exit_code == 0
    assert "No installed tool found for" in result.output
    assert script.name in result.output


@pytest.mark.parametrize(
    ("command", "exit_code", "message", "exception_type"),
    [
        ("install", 0, "Script path is required", None),
        ("update", 1, "", TypeError),
        ("list", 0, "No tools installed", None),
        ("show", 2, "Missing argument 'TOOL_NAME'", SystemExit),
        ("uninstall", 0, "Either TOOL_NAME or --all is required", None),
    ],
)
def test_current_no_argument_command_behavior(
    tmp_path, monkeypatch, command, exit_code, message, exception_type
):
    monkeypatch.chdir(tmp_path)
    empty_registry = {"version": "1.0", "scripts": {}}
    with patch("uvs.cli.load_registry", return_value=empty_registry):
        result = CliRunner().invoke(cli, [command])
    assert result.exit_code == exit_code
    assert message in result.output
    if exception_type is None:
        assert result.exception is None
    else:
        assert isinstance(result.exception, exception_type)


def test_current_main_detection_accepts_sync_and_async_but_not_nested():
    assert validate_script_has_main("def main():\n    pass\n") is True
    assert validate_script_has_main("async def main():\n    pass\n") is True
    assert (
        validate_script_has_main(
            "def outer():\n    def main():\n        pass\n    return main\n"
        )
        is False
    )


def test_current_config_creation_writes_an_empty_project_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    with patch("pathlib.Path.home", return_value=tmp_path / "home"):
        path = ConfigManager().create_default_config("project")
    assert path == tmp_path / "uvs.toml"
    assert path.read_text(encoding="utf-8") == ""


def test_current_global_config_option_is_accepted_but_ignored(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    supplied = tmp_path / "supplied.toml"
    supplied.write_text('[default]\npython = "3.13"\n', encoding="utf-8")
    (tmp_path / "uvs.toml").write_text(
        '[default]\npython = "3.11"\n', encoding="utf-8"
    )
    with patch("pathlib.Path.home", return_value=tmp_path / "home"):
        result = CliRunner().invoke(
            cli,
            ["--config", str(supplied), "config", "get", "default.python"],
        )
    assert result.exit_code == 0
    assert "default.python = 3.11" in result.output
    assert "3.13" not in result.output
