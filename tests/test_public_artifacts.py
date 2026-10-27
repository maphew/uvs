"""Keep shipped examples aligned with the supported script contract."""

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10 CI
    import tomli as tomllib

from uvs.uvs import parse_pep723_header, read_script_source, validate_script_has_main

PROJECT_ROOT = Path(__file__).parents[1]


def test_all_examples_are_supported_scripts():
    examples = sorted((PROJECT_ROOT / "examples").glob("*.py"))
    assert examples, "at least one public example is required"

    for example in examples:
        metadata = parse_pep723_header(example)
        assert set(metadata) <= {"dependencies", "requires-python", "tool"}
        assert validate_script_has_main(read_script_source(example))


def test_package_metadata_marks_the_project_as_experimental():
    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text("utf-8"))
    classifiers = metadata["project"]["classifiers"]

    assert "Development Status :: 3 - Alpha" in classifiers
    assert "Development Status :: 4 - Beta" not in classifiers


def test_distribution_name_matches_pyproject():
    from uvs import DISTRIBUTION_NAME

    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text("utf-8"))

    assert metadata["project"]["name"] == DISTRIBUTION_NAME
    # The unrelated PyPI project `uvs` already occupies this name.
    assert DISTRIBUTION_NAME != "uvs"


def test_package_version_matches_pyproject():
    from uvs import __version__

    metadata = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text("utf-8"))

    assert metadata["project"]["version"] == __version__


def test_public_feedback_files_are_shipped_in_the_repository():
    expected_paths = [
        "CONTRIBUTING.md",
        "SECURITY.md",
        ".github/ISSUE_TEMPLATE/bug-report.yml",
        ".github/ISSUE_TEMPLATE/usefulness-feedback.yml",
        ".github/ISSUE_TEMPLATE/config.yml",
        ".github/workflows/publish.yml",
        "docs/releasing.md",
    ]

    assert all((PROJECT_ROOT / path).is_file() for path in expected_paths)


def test_changelog_distinguishes_unreleased_work():
    from uvs import __version__

    changelog = (PROJECT_ROOT / "CHANGELOG.md").read_text("utf-8")

    assert "## Unreleased" in changelog
    # Every shipped version needs its own dated section, and the current
    # package version must not still be sitting under Unreleased.
    assert re.search(
        rf"^## {re.escape(__version__)} - \d{{4}}-\d{{2}}-\d{{2}}$",
        changelog,
        re.MULTILINE,
    )
    assert "pypi.org/project/uvs-cli" in changelog
