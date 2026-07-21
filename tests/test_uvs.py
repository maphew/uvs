"""Focused tests for core script validation and version policy."""

from __future__ import annotations

import pytest

from uvs.cli import install_script_quiet
from uvs.uvs import bump_patch_version, validate_script_has_main


@pytest.mark.parametrize(
    "signature",
    [
        "required, /",
        "required",
        "*, required",
    ],
)
def test_main_requiring_an_argument_is_rejected(signature):
    source = f"def main({signature}):\n    pass\n"

    assert validate_script_has_main(source) is False


@pytest.mark.parametrize(
    "signature",
    [
        "",
        "optional=None, /",
        "optional=None",
        "*, optional=None",
        "*args",
        "**kwargs",
        "optional=None, *args, keyword_only=None, **kwargs",
    ],
)
def test_main_callable_without_arguments_is_accepted(signature):
    source = f"def main({signature}):\n    pass\n"

    assert validate_script_has_main(source) is True


@pytest.mark.parametrize(
    "signature",
    [
        "required, /",
        "required",
        "*, required",
    ],
)
def test_install_rejects_main_requiring_an_argument(tmp_path, capsys, signature):
    script = tmp_path / "requires_argument.py"
    script.write_text(f"def main({signature}):\n    pass\n", encoding="utf-8")

    result = install_script_quiet(script, {})

    assert result == 1
    assert (
        "must define a synchronous top-level main() function callable without arguments"
        in capsys.readouterr().err
    )


@pytest.mark.parametrize(
    "rebinding",
    [
        "def main(required):\n    pass",
        "async def main():\n    pass",
        "class main:\n    pass",
        "main = object()",
        "main: object = object()",
        "main: object",
        "main += 1",
        "import os as main",
        "from os import path as main",
        "del main",
    ],
)
def test_later_incompatible_direct_binding_overrides_valid_main(rebinding):
    source = f"def main():\n    pass\n{rebinding}\n"

    assert validate_script_has_main(source) is False


@pytest.mark.parametrize(
    "earlier_binding",
    [
        "def main(required):\n    pass",
        "async def main():\n    pass",
        "class main:\n    pass",
        "main = object()",
        "import os as main",
    ],
)
def test_later_valid_function_overrides_incompatible_main_binding(earlier_binding):
    source = f"{earlier_binding}\ndef main(optional=None):\n    pass\n"

    assert validate_script_has_main(source) is True


def test_main_validation_does_not_descend_into_control_flow_bindings():
    source = "def main():\n    pass\nif False:\n    main = object()\n"

    assert validate_script_has_main(source) is True


@pytest.mark.parametrize(
    ("initial", "updated"),
    [
        ("1", "1.0.1"),
        ("1.2", "1.2.1"),
        ("1.2.3", "1.2.4"),
        ("1.2.3.4", "1.2.3.5"),
        ("2!1.2.3", "2!1.2.4"),
        ("1.2.3rc1", "1.2.4"),
        ("1.2.3.post1", "1.2.4"),
        ("1.2.3.dev1", "1.2.4"),
        ("1.2.3+build.7", "1.2.4"),
        ("3!1.2rc1.post2.dev3+local", "3!1.2.1"),
        ("v1.2.3", "1.2.4"),
    ],
)
def test_patch_bump_produces_next_final_release(initial, updated):
    assert bump_patch_version(initial) == updated


@pytest.mark.parametrize("invalid", ["", "not-a-version", "1..2"])
def test_patch_bump_rejects_invalid_versions(invalid):
    with pytest.raises(ValueError, match="Invalid package version"):
        bump_patch_version(invalid)
