"""uvs: transform a single-file PEP723 script into a package and run `uv tool install` on it.

Minimal, self-contained implementation of the core single-script installation behavior.
"""

from __future__ import annotations

import ast
import hashlib
import importlib.metadata
import json
import keyword
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import platformdirs
import tomli_w
from packaging.requirements import InvalidRequirement, Requirement
from packaging.specifiers import InvalidSpecifier, SpecifierSet
from packaging.version import InvalidVersion, Version

from . import __version__

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
    import tomli as tomllib


class ScriptMetadataError(ValueError):
    """Raised when a closed PEP 723 script metadata block is invalid."""


_SCRIPT_BLOCK_START = "# /// script"
_BLOCK_END = "# ///"
_VALID_TOOL_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?$")


def parse_pep723_header(path: Path) -> dict:
    """Parse and validate the script's PEP 723 ``script`` metadata block.

    PEP 723 requires unclosed blocks to be ignored and duplicate closed blocks
    to fail. Closed blocks are TOML documents; malformed content is never
    silently degraded to a string.
    """
    lines = read_script_source(path).splitlines()
    blocks: list[str] = []
    index = 0

    while index < len(lines):
        if lines[index] != _SCRIPT_BLOCK_START:
            index += 1
            continue

        start = index
        try:
            end = lines.index(_BLOCK_END, start + 1)
        except ValueError:
            # PEP 723: unclosed metadata blocks MUST be ignored.
            break

        content: list[str] = []
        for line_number, line in enumerate(lines[start + 1 : end], start=start + 2):
            if line == _SCRIPT_BLOCK_START:
                raise ScriptMetadataError(
                    f"Invalid PEP 723 metadata in {path}: nested script block"
                )
            if line == "#":
                content.append("")
            elif line.startswith("# "):
                content.append(line[2:])
            else:
                raise ScriptMetadataError(
                    f"Invalid PEP 723 metadata in {path}: line {line_number} "
                    "must start with '# '"
                )
        blocks.append("\n".join(content))
        index = end + 1

    if not blocks:
        return {}
    if len(blocks) > 1:
        raise ScriptMetadataError(
            f"Invalid PEP 723 metadata in {path}: multiple script blocks"
        )

    try:
        metadata = tomllib.loads(blocks[0])
    except (tomllib.TOMLDecodeError, TypeError) as exc:
        raise ScriptMetadataError(
            f"Invalid PEP 723 TOML metadata in {path}: {exc}"
        ) from exc

    unexpected = set(metadata) - {"dependencies", "requires-python", "tool"}
    if unexpected:
        names = ", ".join(sorted(unexpected))
        raise ScriptMetadataError(
            f"Invalid PEP 723 metadata in {path}: unsupported field(s): {names}"
        )

    dependencies = metadata.get("dependencies", [])
    if not isinstance(dependencies, list) or not all(
        isinstance(item, str) for item in dependencies
    ):
        raise ScriptMetadataError(
            f"Invalid PEP 723 metadata in {path}: dependencies must be a list of strings"
        )
    for dependency in dependencies:
        try:
            Requirement(dependency)
        except InvalidRequirement as exc:
            raise ScriptMetadataError(
                f"Invalid PEP 723 dependency in {path}: {dependency!r}"
            ) from exc

    requires_python = metadata.get("requires-python")
    if requires_python is not None:
        if not isinstance(requires_python, str):
            raise ScriptMetadataError(
                f"Invalid PEP 723 metadata in {path}: requires-python must be a string"
            )
        try:
            SpecifierSet(requires_python)
        except InvalidSpecifier as exc:
            raise ScriptMetadataError(
                f"Invalid PEP 723 requires-python in {path}: {requires_python!r}"
            ) from exc

    if "tool" in metadata and not isinstance(metadata["tool"], dict):
        raise ScriptMetadataError(
            f"Invalid PEP 723 metadata in {path}: tool must be a table"
        )
    return metadata


def read_script_source(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def strip_pep723_header_and_main(source: str) -> str:
    """Return source unchanged; retained as a compatibility helper."""
    return source


def compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_tool_name(path: Path, explicit_name: str | None = None) -> tuple[str, str]:
    """Return (tool_name_for_cli, package_dir_name)."""
    if explicit_name is not None:
        tool = explicit_name
    else:
        tool = path.stem
    # CLI name: prefer hyphens
    cli_name = tool.replace("_", "-")
    # package / module name must be a valid identifier use underscores
    module_name = cli_name.replace("-", "_")
    if not _VALID_TOOL_NAME.fullmatch(tool):
        raise ValueError(
            f"Invalid tool name {tool!r}: use letters, numbers, hyphens, or "
            "underscores; start and end with a letter or number"
        )
    if not module_name.isidentifier() or keyword.iskeyword(module_name):
        raise ValueError(
            f"Invalid tool name {tool!r}: {module_name!r} is not a valid Python module name"
        )
    return cli_name, module_name


def get_uvs_version() -> str:
    """Return the installed generator version, with a source-tree fallback."""
    try:
        return importlib.metadata.version("uvs")
    except importlib.metadata.PackageNotFoundError:
        return __version__


def generate_pyproject(
    tool_name: str,
    module_name: str,
    version: str,
    description: str,
    requires_python: str | None,
    dependencies: list[str],
    source_path: str,
    source_hash: str,
) -> str:
    try:
        Version(version)
    except InvalidVersion as exc:
        raise ValueError(f"Invalid package version {version!r}") from exc

    project = {
        "name": tool_name,
        "version": version,
        "description": description,
        "readme": "README.md",
        "dependencies": dependencies,
    }
    if requires_python:
        project["requires-python"] = requires_python
    document = {
        "project": project,
        "tool": {
            "uvs": {
                "source_path": source_path,
                "source_hash": source_hash,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "generator": f"uvs/{get_uvs_version()}",
            }
        },
        "build-system": {
            "requires": ["uv_build>=0.8.22,<0.9.0"],
            "build-backend": "uv_build",
        },
    }
    document["project"]["scripts"] = {tool_name: f"{module_name}:main"}
    return tomli_w.dumps(document)


def generate_readme(tool_name: str, source_path: str, description: str) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    return f"""# {tool_name}

{description}

## Source
This package was generated from:
- Source: `{source_path}`
- Generated: {ts}
- Generator: uvs/{get_uvs_version()}

## Usage
```
{tool_name} [options]
```

To update:
```
uvs --update {source_path}
```
"""


def write_package(
    tempdir: Path,
    tool_name: str,
    module_name: str,
    version: str,
    description: str,
    requires_python: str | None,
    dependencies: list[str],
    source_path: Path,
    source_hash: str,
    script_body: str,
) -> Path:
    pkg_dir = tempdir / tool_name
    src_pkg_dir = pkg_dir / "src" / module_name
    src_pkg_dir.mkdir(parents=True, exist_ok=True)
    # Copy supported source verbatim. Metadata comments and a __main__ guard are
    # inert when the generated module is imported as a console entry point.
    init_py = src_pkg_dir / "__init__.py"
    init_py.write_bytes(script_body.encode("utf-8"))
    # pyproject.toml
    pyproject = pkg_dir / "pyproject.toml"
    pyproject.write_text(
        generate_pyproject(
            tool_name,
            module_name,
            version,
            description,
            requires_python,
            dependencies,
            str(source_path),
            source_hash,
        ),
        encoding="utf8",
    )
    # README
    (pkg_dir / "README.md").write_text(
        generate_readme(tool_name, str(source_path), description), encoding="utf8"
    )
    return pkg_dir


def run_uv_install(
    pkg_path: Path, editable: bool = False, python: str | None = None
) -> int:
    """Invoke `uv tool install` on the package directory. Returns subprocess exit code."""
    cmd = ["uv", "tool", "install"]
    if editable:
        cmd.append("-e")
    cmd.append(str(pkg_path))
    if python:
        cmd.extend(["--python", python])
    print("Running:", " ".join(cmd))
    return subprocess.run(cmd).returncode


def bump_patch_version(ver: str) -> str:
    """Bump the patch version of a semantic version string."""
    parts = ver.split(".")
    try:
        if len(parts) >= 3:
            parts[-1] = str(int(parts[-1]) + 1)
        elif len(parts) == 2:
            parts.append("1")
        else:
            # unknown form, fallback
            parts = [ver, "1"]
        return ".".join(parts)
    except Exception:
        return ver


def get_config_dir() -> Path:
    """Get the platform-specific configuration directory for uvs."""
    return Path(platformdirs.user_config_dir("uvs"))


def get_registry_path() -> Path:
    """Get the registry file path."""
    return get_config_dir() / "registry.json"


def load_registry() -> dict:
    """Load the registry file."""
    registry_path = get_registry_path()
    if registry_path.exists():
        try:
            return json.loads(registry_path.read_text(encoding="utf8"))
        except Exception:
            return {
                "version": "1.0",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "scripts": {},
            }
    return {
        "version": "1.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scripts": {},
    }


def save_registry(reg: dict) -> None:
    """Save the registry file."""
    registry_path = get_registry_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    registry_path.write_text(json.dumps(reg, indent=2), encoding="utf8")


def run_uv_uninstall(tool_name: str) -> int:
    """Invoke `uv tool uninstall` on the specified tool. Returns subprocess exit code."""
    cmd = ["uv", "tool", "uninstall", tool_name]
    print("Running:", " ".join(cmd))
    return subprocess.run(cmd).returncode


def verify_tool_uninstalled(tool_name: str) -> bool:
    """Verify that a tool is no longer available in the system."""
    try:
        result = subprocess.run(
            ["uv", "tool", "list"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            try:
                subprocess.run(
                    [tool_name, "--help"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                return False
            except (
                subprocess.TimeoutExpired,
                FileNotFoundError,
                subprocess.SubprocessError,
            ):
                return True

        for line in result.stdout.splitlines():
            if line.startswith(tool_name + " v") or line.startswith(tool_name + " "):
                return False

        return True
    except Exception:
        return True


def cleanup_registry_entry(tool_name: str) -> bool:
    """Remove a tool entry from the registry."""
    try:
        registry = load_registry()
        if "scripts" in registry and tool_name in registry["scripts"]:
            del registry["scripts"][tool_name]
            save_registry(registry)
            return True
        return False
    except Exception:
        return False


def backup_registry() -> Path:
    """Create a backup of the registry file."""
    registry_path = get_registry_path()
    config_dir = get_config_dir()

    # Create backups directory if it doesn't exist
    backups_dir = config_dir / "backups"
    backups_dir.mkdir(parents=True, exist_ok=True)

    # Create backup with timestamp
    from datetime import datetime

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = backups_dir / f"registry_{timestamp}.json"

    # Copy registry to backup location
    if registry_path.exists():
        import shutil

        shutil.copy2(registry_path, backup_path)

    return backup_path


def validate_script_syntax(path: Path) -> tuple[bool, str]:
    """Validate that a Python script has valid syntax.

    Returns (True, "") if valid, or (False, error_message) if invalid.
    """
    try:
        source = path.read_text(encoding="utf8")
        ast.parse(source)
        return True, ""
    except SyntaxError as e:
        return False, f"Syntax error in {path.name}: {e}"


def extract_description(source: str) -> str:
    """Extract description from script's module docstring, or return a default."""
    try:
        tree = ast.parse(source)
        docstring = ast.get_docstring(tree)
        if docstring:
            first_line = docstring.strip().split("\n")[0].strip()
            if first_line:
                return first_line
    except SyntaxError:
        pass
    return "Auto-generated package"


def validate_script_has_main(source: str) -> bool:
    """Check if the script source defines a top-level main() function."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "main"
        ):
            return True
    return False


# Core utility functions for uvs CLI
# The main CLI interface is now in cli.py using Click and Rich
