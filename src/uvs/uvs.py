# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

"""uvs: transform a single-file PEP723 script into a package and run `uv tool install` on it.

Minimal, self-contained implementation of the core single-script installation behavior.
"""

from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path


def parse_pep723_header(path: Path) -> dict:
    """Parse a minimal PEP723-like header in the script.

    Looks for lines between '# /// script' and '# ///' and evaluates simple assignments.
    Returns dict with keys like 'requires-python' and 'dependencies'.
    """
    header = {}
    start = None
    end = None
    with path.open("r", encoding="utf8") as fh:
        lines = fh.readlines()

    for i, line in enumerate(lines):
        if line.strip().startswith("# /// script"):
            start = i
            break

    if start is None:
        return header

    for j in range(start + 1, len(lines)):
        if lines[j].strip().startswith("# ///"):
            end = j
            break

    if end is None:
        return header

    block = lines[start + 1 : end]
    for ln in block:
        stripped = ln.lstrip("# ").rstrip()
        if not stripped:
            continue
        # Expect lines like 'requires-python = ">=3.13"' or 'dependencies = []'
        if "=" not in stripped:
            continue
        key, val = stripped.split("=", 1)
        key = key.strip()
        val = val.strip()
        try:
            # Use ast.literal_eval for safety for lists/strings
            header[key] = ast.literal_eval(val)
        except Exception:
            header[key] = val.strip('"').strip("'")

    return header


def read_script_source(path: Path) -> str:
    return path.read_text(encoding="utf8")


def strip_pep723_header_and_main(source: str) -> str:
    """Remove the PEP723 header block and the __main__ invocation if present."""
    lines = source.splitlines()
    # Remove header between '# /// script' and next '# ///'
    out: list[str] = []
    i = 0
    while i < len(lines):
        if lines[i].strip().startswith("# /// script"):
            # skip until next '# ///'
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("# ///"):
                i += 1
            # skip the closing marker line as well
            i += 1
            continue
        out.append(lines[i])
        i += 1

    # Remove "if __name__ == '__main__':" block by detecting the line and skipping following indented lines
    filtered: list[str] = []
    skip_block = False
    for idx, ln in enumerate(out):
        if skip_block:
            if ln.startswith((" ", "\t")) or ln.strip() == "":
                # still in block; skip
                continue
            else:
                skip_block = False
        stripped = ln.strip()
        if stripped.startswith("if __name__") and "__main__" in stripped:
            skip_block = True
            continue
        filtered.append(ln)

    return "\n".join(filtered) + "\n"


def compute_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_tool_name(path: Path, explicit_name: str | None = None) -> tuple[str, str]:
    """Return (tool_name_for_cli, package_dir_name)."""
    if explicit_name:
        tool = explicit_name
    else:
        tool = path.stem
    # CLI name: prefer hyphens
    cli_name = tool.replace("_", "-")
    # package / module name must be a valid identifier use underscores
    module_name = cli_name.replace("-", "_")
    return cli_name, module_name


def generate_pyproject(tool_name: str, module_name: str, version: str, description: str, requires_python: str | None, dependencies: list[str], source_path: str, source_hash: str) -> str:
    deps_repr = ",\n    ".join(f'"{d}"' for d in dependencies) if dependencies else ""
    requires_line = f'requires-python = "{requires_python}"' if requires_python else ''
    proj_section = f"""[project]
name = "{tool_name}"
version = "{version}"
description = {json.dumps(description)}
readme = "README.md"
{requires_line}
dependencies = [
    {deps_repr}
]

[project.scripts]
{tool_name} = "{module_name}:main"

[tool.uvs]
source_path = "{source_path}"
source_hash = "{source_hash}"
generated_at = "{datetime.now(timezone.utc).isoformat()}"
generator = "uvs/0.1.0"

[build-system]
requires = ["uv_build>=0.8.22,<0.9.0"]
build-backend = "uv_build"
"""
    return proj_section


def generate_readme(tool_name: str, source_path: str, description: str) -> str:
    ts = datetime.now(timezone.utc).isoformat()
    return f"""# {tool_name}

{description}

## Source
This package was generated from:
- Source: `{source_path}`
- Generated: {ts}
- Generator: uvs/0.1.0

## Usage
```
{tool_name} [options]
```

To update:
```
uvs --update {source_path}
```
"""


def write_package(tempdir: Path, tool_name: str, module_name: str, version: str, description: str, requires_python: str | None, dependencies: list[str], source_path: Path, source_hash: str, script_body: str) -> Path:
    pkg_dir = tempdir / tool_name
    src_pkg_dir = pkg_dir / "src" / module_name
    src_pkg_dir.mkdir(parents=True, exist_ok=True)
    # Write __init__.py
    init_py = src_pkg_dir / "__init__.py"
    content = f"""# Auto-generated package for {tool_name}
# Source: {source_path}
# Generated at: {datetime.now(timezone.utc).isoformat()}

{script_body}
"""
    init_py.write_text(content, encoding="utf8")
    # pyproject.toml
    pyproject = pkg_dir / "pyproject.toml"
    pyproject.write_text(generate_pyproject(tool_name, module_name, version, description, requires_python, dependencies, str(source_path), source_hash), encoding="utf8")
    # README
    (pkg_dir / "README.md").write_text(generate_readme(tool_name, str(source_path), description), encoding="utf8")
    return pkg_dir


def run_uv_install(pkg_path: Path, editable: bool = False, python: str | None = None) -> int:
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


def get_registry_path() -> Path:
    """Get the registry file path."""
    return Path(".uvs-registry.json")


def load_registry() -> dict:
    """Load the registry file."""
    registry_path = get_registry_path()
    if registry_path.exists():
        try:
            return json.loads(registry_path.read_text(encoding="utf8"))
        except Exception:
            return {"version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(), "scripts": {}}
    return {"version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(), "scripts": {}}


def save_registry(reg: dict) -> None:
    """Save the registry file."""
    registry_path = get_registry_path()
    registry_path.write_text(json.dumps(reg, indent=2), encoding="utf8")


# Core utility functions for uvs CLI
# The main CLI interface is now in cli.py using Click and Rich