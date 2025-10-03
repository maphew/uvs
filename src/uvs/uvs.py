# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///

"""uvs: transform a single-file PEP723 script into a package and run `uv tool install` on it.

Minimal, self-contained implementation of the core single-script installation behavior.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
import shutil
import subprocess
import sys
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


def main() -> int:
    ap = argparse.ArgumentParser(prog="uvs", description="Install single-file PEP723 scripts via uv.")
    ap.add_argument("script", type=Path, nargs="?", help="Path to the single-file script to install or a directory when used with --all.")
    ap.add_argument("--name", "-n", help="Override tool name (CLI name).")
    ap.add_argument("--version", "-v", default="0.1.0", help="Initial package version.")
    ap.add_argument("--editable", action="store_true", help="Attempt an editable install (uv tool install -e).")
    ap.add_argument("--tempdir", type=Path, default=None, help="Directory to write generated package into (default: system tempdir).")
    ap.add_argument("--python", help="Python version to use for uv tool install (pass to uv).")
    ap.add_argument("--dry-run", action="store_true", help="Do not call uv; just generate package and print path.")
    ap.add_argument("--list", action="store_true", help="List registered installed scripts.")
    ap.add_argument("--which", help="Show source path for installed tool name.")
    ap.add_argument("--update", action="store_true", help="If installed and source changed, bump patch and reinstall.")
    ap.add_argument("--all", action="store_true", help="Install all .py scripts in the given directory (or current directory if none provided).")
    args = ap.parse_args()
    
    registry_path = Path(".uv-scripts-registry.json")
    
    def load_registry() -> dict:
        if registry_path.exists():
            try:
                return json.loads(registry_path.read_text(encoding="utf8"))
            except Exception:
                return {"version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(), "scripts": {}}
        return {"version": "1.0", "created_at": datetime.now(timezone.utc).isoformat(), "scripts": {}}
    
    def save_registry(reg: dict) -> None:
        registry_path.write_text(json.dumps(reg, indent=2), encoding="utf8")
    
    def bump_patch_version(ver: str) -> str:
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
    
    # --list: print registry and exit
    if args.list:
        reg = load_registry()
        scripts = reg.get("scripts", {})
        if not scripts:
            print("No registered scripts.")
            return 0
        for name, info in scripts.items():
            print(f"{name}\t<- {info.get('source_path')} (version: {info.get('version')})")
        return 0
    
    # --which: print source path for tool name and exit
    if args.which:
        reg = load_registry()
        info = reg.get("scripts", {}).get(args.which)
        if not info:
            print(f"No entry for tool '{args.which}' in registry.", file=sys.stderr)
            return 2
        print(info.get("source_path"))
        return 0
    
    def handle_single_install(script_path: Path) -> int:
        """Process install/update for a single script path."""
        if not script_path.exists():
            print("Script not found:", script_path, file=sys.stderr)
            return 2
    
        header = parse_pep723_header(script_path)
        requires_python = header.get("requires-python") or header.get("requires_python")  # be permissive
        dependencies = header.get("dependencies") or header.get("dependencies", []) or []
        if isinstance(dependencies, str):
            dependencies = [dependencies]
    
        source_text = read_script_source(script_path)
        script_body = strip_pep723_header_and_main(source_text)
    
        cli_name, module_name = derive_tool_name(script_path, args.name)
        version = args.version
        description = ast.get_docstring(ast.parse(script_body)) or f"Command-line tool from {script_path.name}"
        source_hash = compute_hash(script_path)
    
        # If update semantics requested, consult registry and bump version if hash changed
        if args.update:
            reg = load_registry()
            existing = reg.get("scripts", {}).get(cli_name)
            if existing:
                if existing.get("source_hash") != source_hash:
                    old_ver = existing.get("version", version)
                    version = bump_patch_version(old_ver)
                    print(f"Detected change for {cli_name}: {old_ver} -> {version}")
                else:
                    print(f"No changes detected for {cli_name}; reinstalling same version {existing.get('version')}")
                    version = existing.get("version", version)
    
        # Tempdir
        if args.tempdir:
            base_tmp = Path(args.tempdir)
            base_tmp.mkdir(parents=True, exist_ok=True)
        else:
            base_tmp = Path(tempfile.mkdtemp(prefix="uvs-"))
    
        pkg_dir = write_package(base_tmp, cli_name, module_name, version, description, requires_python, dependencies, script_path, source_hash, script_body)
    
        print("Generated package at:", pkg_dir)
        if args.dry_run:
            return 0
    
        rc = run_uv_install(pkg_dir, editable=args.editable, python=args.python)
        if rc != 0:
            print("uv tool install failed with code", rc, file=sys.stderr)
            return rc
    
        # Record local registry ~/.uv-scripts-registry.json or project-level .uv-scripts-registry.json
        try:
            reg = load_registry()
            reg.setdefault("scripts", {})
            reg["scripts"][cli_name] = {
                "tool_name": cli_name,
                "source_path": str(script_path.resolve()),
                "source_hash": source_hash,
                "installed_at": datetime.now(timezone.utc).isoformat(),
                "version": version,
            }
            save_registry(reg)
        except Exception as exc:
            print("Warning: failed to update registry:", exc, file=sys.stderr)
    
        print(f"Installed '{cli_name}' from {script_path}")
        return 0
    
    # --all: batch install
    if args.all:
        target_dir = Path(".") if not args.script else Path(args.script)
        if not target_dir.exists() or not target_dir.is_dir():
            print("Target for --all must be an existing directory (or omit to use current directory).", file=sys.stderr)
            return 2
        py_files = sorted([p for p in target_dir.iterdir() if p.is_file() and p.suffix == ".py"])
        if not py_files:
            print("No .py files found in", target_dir)
            return 0
        failures = []
        for p in py_files:
            print(f"Processing {p} ...")
            rc = handle_single_install(p)
            if rc != 0:
                failures.append((p, rc))
        if failures:
            print(f"Completed with {len(failures)} failures.", file=sys.stderr)
            for p, rc in failures:
                print(f"- {p}: rc={rc}", file=sys.stderr)
            return 1
        print(f"Successfully installed {len(py_files)} scripts from {target_dir}")
        return 0
    
    # Default single install path
    if not args.script:
        ap.error("a script path is required (or use --list/--which/--all).")
        return 2
    
    # Fall back to single install when --all not used
    return handle_single_install(args.script)