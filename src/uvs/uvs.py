"""Transform a supported single-file PEP 723 script for ``uv tool install``.

Minimal, self-contained implementation of the core single-script installation behavior.
"""

from __future__ import annotations

import ast
from contextlib import contextmanager
import hashlib
import importlib.metadata
import json
import keyword
import os
import re
import subprocess
import sys
import tempfile
import time
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


class UnsupportedRegistryVersionError(ValueError):
    """Raised when a registry was written by an unknown schema version."""


_SCRIPT_BLOCK_START = "# /// script"
_BLOCK_END = "# ///"
_VALID_TOOL_NAME = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_-]*[A-Za-z0-9])?$")
_REGISTRY_VERSION = "1.0"


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
uvs update {source_path}
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
    pkg_path: Path,
    editable: bool = False,
    python: str | None = None,
    quiet: bool = False,
) -> int:
    """Invoke `uv tool install` on the package directory. Returns subprocess exit code."""
    cmd = ["uv", "tool", "install"]
    if editable:
        cmd.append("-e")
    cmd.append(str(pkg_path))
    if python:
        cmd.extend(["--python", python])
    if not quiet:
        print("Running:", " ".join(cmd))
        return subprocess.run(cmd).returncode
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.returncode


def bump_patch_version(ver: str) -> str:
    """Return the next final PEP 440 release for an installed version.

    The final release component is incremented after padding short releases to
    three components. Epochs are preserved, while pre, post, dev, and local
    qualifiers are intentionally discarded.

    Raises:
        ValueError: If *ver* is not a valid PEP 440 version.
    """
    try:
        version = Version(ver)
    except InvalidVersion as exc:
        raise ValueError(f"Invalid package version {ver!r}") from exc

    release = list(version.release)
    release.extend([0] * (3 - len(release)))
    release[-1] += 1

    epoch = f"{version.epoch}!" if version.epoch else ""
    return epoch + ".".join(str(component) for component in release)


def get_config_dir() -> Path:
    """Get the platform-specific configuration directory for uvs."""
    return Path(platformdirs.user_config_dir("uvs"))


def get_registry_path() -> Path:
    """Get the registry file path."""
    return get_config_dir() / "registry.json"


def _new_registry() -> dict:
    return {
        "version": _REGISTRY_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scripts": {},
    }


def canonical_source_path(path: str | Path) -> str:
    """Return a stable path key for registry source comparisons."""
    if not str(path):
        raise ValueError("source path cannot be empty")
    return os.path.normcase(str(Path(path).expanduser().resolve(strict=False)))


def _normalize_registry(
    data: object, *, tolerate_invalid_entries: bool = False
) -> tuple[dict, list[str]]:
    """Validate the registry and migrate the pre-versioned schema."""
    if not isinstance(data, dict):
        raise ValueError("registry root must be an object")
    version = data.get("version", _REGISTRY_VERSION)
    if version != _REGISTRY_VERSION:
        raise UnsupportedRegistryVersionError(
            f"unsupported registry version {version!r}"
        )
    scripts = data.get("scripts", {})
    if not isinstance(scripts, dict):
        raise ValueError("registry 'scripts' must be an object")

    normalized = dict(data)
    normalized["version"] = _REGISTRY_VERSION
    normalized.setdefault("created_at", datetime.now(timezone.utc).isoformat())
    normalized_scripts: dict[str, dict] = {}
    invalid_entries: list[str] = []
    for name, entry in scripts.items():
        try:
            if not isinstance(name, str) or not isinstance(entry, dict):
                raise ValueError("registry script entries must be named objects")
            normalized_entry = dict(entry)
            normalized_entry["tool_name"] = name
            source_path = normalized_entry.get("source_path")
            if not isinstance(source_path, str) or not source_path:
                raise ValueError(f"registry entry {name!r} has no source path")
            normalized_entry["source_path"] = canonical_source_path(source_path)
            for field, default in (
                ("source_hash", ""),
                ("installed_at", ""),
                ("version", "0.1.0"),
            ):
                value = normalized_entry.get(field, default)
                if not isinstance(value, str):
                    raise ValueError(f"registry entry {name!r} has invalid {field}")
                normalized_entry[field] = value
            normalized_scripts[name] = normalized_entry
        except ValueError:
            if not tolerate_invalid_entries:
                raise
            invalid_entries.append(str(name))
    normalized["scripts"] = normalized_scripts
    return normalized, invalid_entries


def _archive_invalid_registry(registry_path: Path) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    archive_path = registry_path.with_name(
        f"{registry_path.stem}.invalid-{timestamp}{registry_path.suffix}"
    )
    os.replace(registry_path, archive_path)
    return archive_path


@contextmanager
def registry_lock(timeout: float = 10.0):
    """Serialize registry read-modify-write operations across processes."""
    lock_path = get_registry_path().with_suffix(".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout
    while True:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(descriptor)
            break
        except FileExistsError:
            try:
                stale = time.time() - lock_path.stat().st_mtime > 60
            except FileNotFoundError:
                continue
            if stale:
                try:
                    lock_path.unlink()
                except FileNotFoundError:
                    pass
                continue
            if time.monotonic() >= deadline:
                raise TimeoutError(f"Timed out waiting for registry lock at {lock_path}")
            time.sleep(0.05)
    try:
        yield
    finally:
        try:
            lock_path.unlink()
        except FileNotFoundError:
            pass


def load_registry() -> dict:
    """Load and normalize the registry, archiving data that cannot be trusted."""
    registry_path = get_registry_path()
    recovered_registry: dict | None = None
    if not registry_path.exists():
        return _new_registry()
    try:
        contents = registry_path.read_text(encoding="utf8")
    except OSError as exc:
        raise RuntimeError(f"Cannot read registry at {registry_path}: {exc}") from exc
    except UnicodeError as exc:
        invalid_error: Exception | None = exc
    else:
        try:
            normalized, invalid_entries = _normalize_registry(
                json.loads(contents), tolerate_invalid_entries=True
            )
            if not invalid_entries:
                return normalized
            recovered_registry = normalized
            invalid_error = ValueError(
                "invalid registry entries: " + ", ".join(invalid_entries)
            )
        except UnsupportedRegistryVersionError as exc:
            raise RuntimeError(
                f"Cannot use registry at {registry_path}: {exc}"
            ) from exc
        except (json.JSONDecodeError, ValueError) as exc:
            invalid_error = exc

    try:
        archive_path = _archive_invalid_registry(registry_path)
    except OSError as archive_exc:
        raise RuntimeError(
            f"Cannot read or archive invalid registry at {registry_path}: {archive_exc}"
        ) from archive_exc
    print(
        f"Warning: archived invalid registry at {archive_path}: {invalid_error}",
        file=sys.stderr,
    )
    if recovered_registry is not None:
        save_registry(recovered_registry)
        return recovered_registry
    return _new_registry()


def save_registry(reg: dict) -> None:
    """Validate and atomically replace the registry file."""
    normalized, invalid_entries = _normalize_registry(reg)
    if invalid_entries:  # pragma: no cover - strict normalization raises first
        raise ValueError("registry contains invalid entries")
    registry_path = get_registry_path()
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf8",
            dir=registry_path.parent,
            prefix=f".{registry_path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temp_path = Path(handle.name)
            json.dump(normalized, handle, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, registry_path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def run_uv_uninstall(tool_name: str, quiet: bool = False) -> int:
    """Invoke `uv tool uninstall` on the specified tool. Returns subprocess exit code."""
    cmd = ["uv", "tool", "uninstall", tool_name]
    if not quiet:
        print("Running:", " ".join(cmd))
        return subprocess.run(cmd).returncode
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0 and result.stderr:
        print(result.stderr, file=sys.stderr, end="")
    return result.returncode


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
                # A failed fallback cannot prove absence. Preserve registry
                # metadata rather than turning an infrastructure error into
                # destructive stale-entry cleanup.
                return False

        for line in result.stdout.splitlines():
            if line.startswith(tool_name + " v") or line.startswith(tool_name + " "):
                return False

        return True
    except Exception:
        return False


def cleanup_registry_entry(tool_name: str) -> bool:
    """Remove a tool entry from the registry."""
    try:
        with registry_lock():
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


def _function_is_callable_without_arguments(node: ast.FunctionDef) -> bool:
    arguments = node.args
    positional_count = len(arguments.posonlyargs) + len(arguments.args)
    required_positional_count = positional_count - len(arguments.defaults)
    has_required_keyword_only = any(
        default is None for default in arguments.kw_defaults
    )
    return required_positional_count == 0 and not has_required_keyword_only


def _target_binds_main(target: ast.expr) -> bool:
    if isinstance(target, ast.Name):
        return target.id == "main"
    if isinstance(target, (ast.List, ast.Tuple)):
        return any(_target_binds_main(element) for element in target.elts)
    if isinstance(target, ast.Starred):
        return _target_binds_main(target.value)
    return False


def _direct_main_binding(node: ast.stmt) -> bool | None:
    """Describe a direct module-body binding of ``main``, if present."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        if node.name != "main":
            return None
        return (
            _function_is_callable_without_arguments(node)
            if isinstance(node, ast.FunctionDef)
            else False
        )

    if isinstance(node, ast.Assign):
        return (
            False
            if any(_target_binds_main(target) for target in node.targets)
            else None
        )
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        return False if _target_binds_main(node.target) else None
    if isinstance(node, ast.Delete):
        return (
            False
            if any(_target_binds_main(target) for target in node.targets)
            else None
        )
    if isinstance(node, ast.Import):
        for alias in node.names:
            bound_name = alias.asname or alias.name.split(".", 1)[0]
            if bound_name == "main":
                return False
    if isinstance(node, ast.ImportFrom):
        for alias in node.names:
            if alias.name == "*" or (alias.asname or alias.name) == "main":
                return False
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.NamedExpr):
        return False if _target_binds_main(node.value.target) else None
    return None


def validate_script_has_main(source: str) -> bool:
    """Check the final direct top-level ``main`` binding against the contract.

    This intentionally models source-ordered bindings directly in the module
    body. Bindings nested in conditional and other control-flow statements are
    outside this static validation contract.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False

    main_is_valid = False
    for node in tree.body:
        binding = _direct_main_binding(node)
        if binding is not None:
            main_is_valid = binding
    return main_is_valid


# Core utility functions for uvs CLI
# The main CLI interface is now in cli.py using Click and Rich
