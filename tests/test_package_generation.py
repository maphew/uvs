"""Contract tests for parsing and disposable package generation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest
try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python 3.10
    import tomli as tomllib

from uvs import __version__
from uvs.cli import install_script_quiet
from uvs.uvs import (
    derive_tool_name,
    generate_pyproject,
    parse_pep723_header,
    validate_script_has_main,
)


def write_script(path: Path, source: str) -> Path:
    path.write_text(source, encoding="utf-8", newline="")
    return path


def install_options(**overrides: object) -> dict[str, object]:
    options: dict[str, object] = {
        "name": None,
        "version": "0.1.0",
        "editable": False,
        "tempdir": None,
        "python": None,
        "dry_run": False,
        "update": False,
    }
    options.update(overrides)
    return options


def test_pep723_metadata_is_parsed_as_toml(tmp_path):
    script = write_script(
        tmp_path / "metadata.py",
        '''# /// script
# requires-python = ">=3.10"
# dependencies = ["click>=8", "quoted-name; platform_system == 'Windows'"]
# [tool.example]
# enabled = true
# ///

def main():
    pass
''',
    )

    assert parse_pep723_header(script) == {
        "requires-python": ">=3.10",
        "dependencies": ["click>=8", "quoted-name; platform_system == 'Windows'"],
        "tool": {"example": {"enabled": True}},
    }


@pytest.mark.parametrize(
    ("source", "message"),
    [
        (
            '# /// script\n# dependencies = ["unterminated"\n# ///\n',
            "toml|metadata",
        ),
        (
            "# /// script\n# dependencies = []\n# ///\n"
            "# /// script\n# dependencies = []\n# ///\n",
            "duplicate|multiple|more than one",
        ),
    ],
)
def test_pep723_malformed_and_duplicate_blocks_fail(tmp_path, source, message):
    script = write_script(tmp_path / "invalid.py", source)

    with pytest.raises(ValueError, match=f"(?i){message}"):
        parse_pep723_header(script)


@pytest.mark.parametrize(
    "source",
    [
        "def main():\n    pass\n",
        '# /// script\n# dependencies = ["click"]\n',
    ],
)
def test_absent_and_unterminated_pep723_metadata_is_ignored(tmp_path, source):
    script = write_script(tmp_path / "plain.py", source)

    assert parse_pep723_header(script) == {}


def test_generated_pyproject_round_trips_hostile_toml_strings():
    description = 'A "quoted" description with C:\\tools\\bin, a newline\nnext, and \b'
    dependency = 'demo @ file:///C:\\packages\\a"b'
    source_path = 'C:\\Users\\A "quoted" folder\\tool.py'

    rendered = generate_pyproject(
        tool_name="safe-tool",
        module_name="safe_tool",
        version="1.2.3",
        description=description,
        requires_python=">=3.10",
        dependencies=[dependency],
        source_path=source_path,
        source_hash="abc123",
    )
    parsed = tomllib.loads(rendered)

    assert parsed["project"]["description"] == description
    assert parsed["project"]["dependencies"] == [dependency]
    assert parsed["tool"]["uvs"]["source_path"] == source_path
    assert parsed["tool"]["uvs"]["generator"] == f"uvs/{__version__}"
    assert parsed["project"]["scripts"] == {"safe-tool": "safe_tool:main"}


@pytest.mark.parametrize(
    ("filename", "explicit_name", "expected"),
    [
        ("hello.py", None, ("hello", "hello")),
        ("hello_world.py", None, ("hello-world", "hello_world")),
        ("source.py", "custom-tool", ("custom-tool", "custom_tool")),
        ("source.py", "custom_tool", ("custom-tool", "custom_tool")),
    ],
)
def test_valid_derived_and_explicit_names(filename, explicit_name, expected):
    assert derive_tool_name(Path(filename), explicit_name) == expected


@pytest.mark.parametrize(
    ("filename", "explicit_name"),
    [
        ("has space.py", None),
        ("has.dot.py", None),
        ("9lives.py", None),
        ("source.py", "has space"),
        ("source.py", "has.dot"),
        ("source.py", ""),
        ("source.py", "   "),
        ("source.py", "-leading"),
        ("source.py", "trailing-"),
        ("source.py", "9lives"),
        ("source.py", "path/name"),
        ("source.py", "café"),
    ],
)
def test_invalid_derived_and_explicit_names_are_rejected(filename, explicit_name):
    with pytest.raises(ValueError, match="(?i)name|command|module"):
        derive_tool_name(Path(filename), explicit_name)


@pytest.mark.parametrize(
    ("source", "expected"),
    [
        ("def main():\n    pass\n", True),
        ("async def main():\n    pass\n", False),
        ("def outer():\n    def main():\n        pass\n", False),
        ("class App:\n    def main(self):\n        pass\n", False),
    ],
)
def test_only_synchronous_top_level_main_is_supported(source, expected):
    assert validate_script_has_main(source) is expected


def test_default_generated_package_is_removed_after_install(tmp_path):
    script = write_script(tmp_path / "ephemeral.py", "def main():\n    pass\n")
    installed_paths: list[Path] = []

    def observe_install(package: Path, **_kwargs: object) -> int:
        installed_paths.append(package)
        assert package.is_dir()
        assert (package / "pyproject.toml").is_file()
        return 0

    with (
        patch("uvs.uvs.run_uv_install", side_effect=observe_install),
        patch("uvs.cli.load_registry", return_value={"version": "1.0", "scripts": {}}),
        patch("uvs.cli.save_registry"),
    ):
        assert install_script_quiet(script, install_options()) == 0

    assert len(installed_paths) == 1
    assert not installed_paths[0].exists()
    assert not installed_paths[0].parent.exists()


def test_custom_tempdir_persists_and_copies_source_verbatim(tmp_path):
    source = '''# /// script
# dependencies = []
# ///

"""Quotes: \"hello\"; backslash: C:\\\\tools; café."""

def main():
    print("hello")

if __name__ == "__main__":
    main()
'''
    script = write_script(tmp_path / "snapshot.py", source)
    generated = tmp_path / "generated packages"

    with (
        patch("uvs.uvs.run_uv_install", return_value=0),
        patch("uvs.cli.load_registry", return_value={"version": "1.0", "scripts": {}}),
        patch("uvs.cli.save_registry"),
    ):
        assert (
            install_script_quiet(script, install_options(tempdir=generated)) == 0
        )

    package = generated / "snapshot"
    assert package.is_dir()
    assert (package / "src" / "snapshot" / "__init__.py").read_bytes() == (
        script.read_bytes()
    )


def test_editable_install_requires_persistent_tempdir(tmp_path, capsys):
    script = write_script(tmp_path / "editable.py", "def main():\n    pass\n")

    with patch("uvs.uvs.run_uv_install") as run_uv_install:
        result = install_script_quiet(script, install_options(editable=True))

    assert result == 1
    assert "Editable installs require --tempdir" in capsys.readouterr().err
    run_uv_install.assert_not_called()
