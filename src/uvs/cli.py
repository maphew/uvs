#!/usr/bin/env python3
"""
uvs: Install supported single-file PEP 723 scripts as CLI tools using uv.

This module provides the Click-based CLI interface for uvs.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import DISTRIBUTION_NAME, __version__, uvs
from .uvs import (
    RegistryError,
    backup_registry,
    bump_patch_version,
    canonical_source_path,
    cleanup_registry_entry,
    compute_hash,
    derive_tool_name,
    extract_description,
    generate_pyproject,
    generate_readme,
    get_registry_path,
    list_backups,
    load_registry,
    parse_pep723_header,
    read_script_source,
    registry_lock,
    restore_registry_backup,
    run_uv_install,
    run_uv_uninstall,
    save_registry,
    strip_pep723_header_and_main,
    uv_tool_names,
    validate_script_has_main,
    validate_script_syntax,
    verify_tool_uninstalled,
    write_package,
)


class OutputLevel(Enum):
    """Output verbosity levels."""

    QUIET = 0
    NORMAL = 1
    VERBOSE = 2


def _resolve_no_color(flag: bool) -> bool:
    """Honor --no-color, NO_COLOR, and dumb terminals."""
    if flag:
        return True
    if os.environ.get("NO_COLOR"):
        return True
    return os.environ.get("TERM", "").lower() == "dumb"


def _make_console(
    no_color: bool, *, quiet: bool = False, stderr: bool = False
) -> Console:
    if no_color:
        # color_system=None strips bold/italic emphasis as well as color.
        return Console(
            no_color=True, color_system=None, quiet=quiet, stderr=stderr
        )
    return Console(quiet=quiet, stderr=stderr)


class OutputManager:
    """Manages output levels and formatting."""

    def __init__(self, level: OutputLevel = OutputLevel.NORMAL, no_color: bool = False):
        self.level = level
        self.no_color = no_color
        self.console = _make_console(no_color, quiet=(level == OutputLevel.QUIET))
        self.error_console = _make_console(no_color, stderr=True)
        # Data output (list/show/json) is never suppressed by --quiet.
        self.data_console = _make_console(no_color)

    def print(
        self,
        message: str,
        level: OutputLevel = OutputLevel.NORMAL,
        style: Optional[str] = None,
    ):
        """Print message if current output level allows it."""
        if self.level.value >= level.value:
            if style and not self.no_color:
                self.console.print(message, style=style, soft_wrap=True)
            else:
                self.console.print(message, soft_wrap=True)

    def error(self, message: str, style: str = "red"):
        """Always print error messages, prefixed once."""
        sys.stdout.flush()
        text = message if message.startswith("Error:") else f"Error: {message}"
        if style and not self.no_color:
            self.error_console.print(text, style=style, soft_wrap=True)
        else:
            self.error_console.print(text, soft_wrap=True)

    def warning(self, message: str):
        """Print warning if not in quiet mode."""
        if self.level.value >= OutputLevel.NORMAL.value:
            sys.stdout.flush()
            prefix = (
                "Warning:" if self.no_color else "[yellow]Warning:[/yellow]"
            )
            self.error_console.print(f"{prefix} {message}", soft_wrap=True)

    def verbose(self, message: str):
        """Print a message in verbose mode."""
        if self.level.value >= OutputLevel.VERBOSE.value:
            if self.no_color:
                self.console.print(message, soft_wrap=True)
            else:
                self.console.print(f"[dim]{message}[/dim]", soft_wrap=True)


def _human_timestamp(value: Optional[str]) -> str:
    """Render a stored ISO timestamp as a compact UTC string."""
    if not value:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def _plural(count: int, singular: str, plural: Optional[str] = None) -> str:
    if count == 1:
        return singular
    return plural or f"{singular}s"


def _table_style(output: OutputManager, style: str) -> Optional[str]:
    return None if output.no_color else style


def _apply_output(
    ctx: click.Context,
    verbose: Optional[bool],
    quiet: Optional[bool],
    no_color: Optional[bool],
) -> OutputManager:
    """Merge group-level and subcommand-level output options."""
    base: OutputManager = ctx.obj["output"]
    if verbose is None and quiet is None and no_color is None:
        return base
    if quiet and verbose:
        raise click.UsageError("Cannot use --quiet and --verbose together.")
    level = base.level
    if quiet:
        level = OutputLevel.QUIET
    elif verbose:
        level = OutputLevel.VERBOSE
    output = OutputManager(level=level, no_color=base.no_color or bool(no_color))
    ctx.obj["output"] = output
    return output


def output_options(command):
    """Add the global output flags to a subcommand as well."""

    command = click.option(
        "--no-color", is_flag=True, default=None, help="Disable colored output"
    )(command)
    command = click.option(
        "--quiet", "-q", is_flag=True, default=None, help="Suppress non-error output"
    )(command)
    command = click.option(
        "--verbose", "-v", is_flag=True, default=None, help="Enable verbose output"
    )(command)
    return command


def _require_uv() -> None:
    if shutil.which("uv") is None:
        raise click.ClickException(
            "uv is not installed or not on PATH. Install uv first: "
            "https://docs.astral.sh/uv/getting-started/installation/"
        )


def _expand_user_path(value: str) -> Path:
    return Path(os.path.expanduser(value))


def _require_script(script: Optional[str]) -> Path:
    if not script:
        raise click.UsageError("Missing argument 'SCRIPT' (or use --all).")
    path = _expand_user_path(script)
    if not path.exists():
        raise click.UsageError(f"Path '{script}' does not exist.")
    if not path.is_file():
        raise click.UsageError(
            f"'{script}' is a directory. Use 'uvs install --all {script}' to "
            "install all .py files in it."
        )
    return path


def _require_directory(script: Optional[str]) -> Path:
    target = _expand_user_path(script) if script else Path(".")
    if not target.exists():
        raise click.UsageError(f"Path '{script}' does not exist.")
    if not target.is_dir():
        raise click.UsageError(
            f"Target for --all must be an existing directory (got '{script}')."
        )
    return target


def _note_name(output: OutputManager, script_path: Path, explicit_name: Optional[str]):
    """Explain command-name normalization without changing it."""
    raw_name = explicit_name if explicit_name is not None else script_path.stem
    cli_name, _ = derive_tool_name(script_path, explicit_name)
    if cli_name != raw_name:
        output.print(
            f"Note: using command name '{cli_name}' (from '{raw_name}'); "
            "command names use dashes."
        )


_STATUS_LABELS = {
    "ok": "ok",
    "outdated": "source changed",
    "source-missing": "source missing",
    "source-unreadable": "source unreadable",
    "not-installed": "not installed in uv",
    "unknown": "unknown (uv unavailable)",
}


def _tool_status(
    tool_name: str, tool_info: Dict[str, Any], uv_names: Optional[Iterable[str]]
) -> str:
    source = Path(tool_info.get("source_path", ""))
    if not source.is_file():
        return "source-missing"
    if uv_names is not None and tool_name not in set(uv_names):
        return "not-installed"
    expected = tool_info.get("source_hash")
    if expected:
        try:
            if compute_hash(source) != expected:
                return "outdated"
        except OSError:
            return "source-unreadable"
    return "ok"


def show_success_message(
    output: OutputManager,
    tool_name: str,
    script_path: Path,
    version: str,
    *,
    dependencies: Optional[list[str]] = None,
    editable: bool = False,
    python: Optional[str] = None,
):
    """Display success message with Rich panel."""
    lines = [
        f"[bold green]Successfully installed[/bold green] [cyan]{tool_name}[/cyan]",
        "",
        f"[dim]Source: {script_path.resolve()}[/dim]",
        f"[dim]Version: {version}[/dim]",
    ]
    if editable:
        lines.append("[dim]Mode: editable[/dim]")
    if python:
        lines.append(f"[dim]Python: {python}[/dim]")
    if dependencies:
        lines.append(f"[dim]Dependencies: {', '.join(dependencies)}[/dim]")

    if shutil.which(tool_name) is None:
        lines.extend(
            [
                "",
                f"[yellow]'{tool_name}' is not on PATH yet. Run "
                "`uv tool update-shell`, restart your shell, or add "
                "`uv tool dir --bin` to PATH.[/yellow]",
            ]
        )
    else:
        lines.extend(["", f"[yellow]Run '{tool_name}' to use your new tool[/yellow]"])

    success_panel = Panel(
        "\n".join(lines),
        title="Installation Complete",
        border_style="green",
        padding=(1, 2),
    )

    output.console.print(success_panel)


def show_tools_table(
    tools: Dict[str, Any],
    output: OutputManager,
    statuses: Optional[Dict[str, str]] = None,
):
    """Display installed tools in a Rich table."""
    table = Table(
        show_header=True,
        header_style=_table_style(output, "bold magenta"),
        box=None,
        show_edge=False,
        pad_edge=False,
        padding=(0, 1),
    )
    table.add_column("Tool Name", style=_table_style(output, "cyan"), no_wrap=True)
    table.add_column("Source Path", style=_table_style(output, "green"))
    table.add_column("Version", style=_table_style(output, "yellow"))
    table.add_column("Installed At", style=_table_style(output, "blue"), no_wrap=True)
    if statuses is not None:
        table.add_column("Status", style=_table_style(output, "yellow"), no_wrap=True)

    for name, info in tools.items():
        row = [
            name,
            info["source_path"],
            info["version"],
            _human_timestamp(info.get("installed_at")),
        ]
        if statuses is not None:
            status = statuses.get(name, "ok")
            row.append(_STATUS_LABELS.get(status, status))
        table.add_row(*row)

    output.data_console.print()
    output.data_console.print(table)
    output.data_console.print()

    output.verbose(f"Total: {len(tools)} tools")


def show_tools_json(
    tools: Dict[str, Any],
    output: OutputManager,
    statuses: Optional[Dict[str, str]] = None,
):
    """Display stable, machine-readable JSON without Rich decoration."""
    if statuses is None:
        payload: Dict[str, Any] = {"tools": tools, "count": len(tools)}
    else:
        annotated = {}
        for name, info in tools.items():
            status = statuses.get(name, "ok")
            annotated[name] = dict(info, status=status)
        payload = {"tools": annotated, "count": len(tools)}
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


def show_tools_simple(
    tools: Dict[str, Any],
    output: OutputManager,
    statuses: Optional[Dict[str, str]] = None,
):
    """Display tools in simple format."""
    for name, info in tools.items():
        line = f"{name} <- {info['source_path']} (v{info['version']})"
        if statuses is not None:
            status = statuses.get(name, "ok")
            line += f" [{_STATUS_LABELS.get(status, status)}]"
        click.echo(line)


def show_tool_simple(tool_name: str, tool_info: Dict[str, Any]):
    """Display one tool using the stable, undecorated simple format."""
    click.echo(f"Name: {tool_name}")
    click.echo(f"Source: {tool_info['source_path']}")
    click.echo(f"Version: {tool_info['version']}")
    click.echo(f"Installed: {tool_info['installed_at']}")
    click.echo(f"Hash: {tool_info['source_hash']}")


def _display_list(items: Iterable[str]) -> str:
    return ", ".join(items) if items else "none"


def install_with_progress(
    script_path: Path, options: Dict[str, Any], output: OutputManager
) -> int:
    """Install script with progress indicators."""
    if output.level == OutputLevel.QUIET or options.get("dry_run"):
        return install_script_quiet(script_path, options)

    # Show verbose info before installing
    if output.level.value >= OutputLevel.VERBOSE.value:
        try:
            header = parse_pep723_header(script_path)
        except ValueError as exc:
            output.error(str(exc))
            return 1
        output.verbose(f"Dependencies: {header.get('dependencies', [])}")

    if not output.console.is_terminal:
        return install_script_quiet(script_path, options)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=output.console,
        transient=True,
    ) as progress:
        task = progress.add_task("Installing...", total=None)
        result = install_script_quiet(script_path, options)
        progress.update(task, description="Complete!")
        return result


def install_script_quiet(script_path: Path, options: Dict[str, Any]) -> int:
    """Install a script without progress indicators (messages go to stdout)."""
    script_path = _expand_user_path(str(script_path))

    # Parse PEP 723 header
    try:
        header = parse_pep723_header(script_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    requires_python = header.get("requires-python") or header.get("requires_python")
    dependencies = header.get("dependencies") or []
    if isinstance(dependencies, str):
        dependencies = [dependencies]

    # Validate script syntax
    syntax_ok, syntax_error = validate_script_syntax(script_path)
    if not syntax_ok:
        print(f"Error: {syntax_error}", file=sys.stderr)
        return 1

    # Read and process script
    source_text = read_script_source(script_path)
    script_body = source_text

    # Validate the script's main entry-point contract.
    if not validate_script_has_main(source_text):
        print(
            f"Error: Script {script_path.name} must define a synchronous top-level "
            "main() function callable without arguments",
            file=sys.stderr,
        )
        return 1

    # Derive names and version
    try:
        cli_name, module_name = derive_tool_name(script_path, options.get("name"))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    existing: Optional[Dict[str, Any]] = None
    registry = load_registry()
    existing = registry.get("scripts", {}).get(cli_name)

    if options.get("update"):
        if existing:
            version = existing.get("version", options.get("version") or "0.1.0")
            current_hash = compute_hash(script_path)
            if existing.get("source_hash") != current_hash:
                version = bump_patch_version(version)
            else:
                # No changes, skip installation
                return 0
        else:
            version = options.get("version") or "0.1.0"
    else:
        version = options.get("version")
        if version is None:
            version = existing.get("version", "0.1.0") if existing else "0.1.0"

    # Reuse recorded interpreter/editable state unless explicitly overridden.
    python = options.get("python")
    if python is None and existing:
        python = existing.get("python")
    editable = bool(options.get("editable", False))
    tempdir_value = options.get("tempdir")
    if tempdir_value is None and editable and existing and existing.get("editable"):
        tempdir_value = existing.get("tempdir")

    description = extract_description(source_text)

    # Get source hash
    source_hash = compute_hash(script_path)

    # Setup temp directory
    if editable and not tempdir_value:
        print(
            "Error: Editable installs require --tempdir to preserve package "
            "files (see 'uvs install --help')",
            file=sys.stderr,
        )
        return 1

    managed_tempdir = None
    if tempdir_value:
        base_tmp = _expand_user_path(str(tempdir_value))
        base_tmp.mkdir(parents=True, exist_ok=True)
    else:
        managed_tempdir = tempfile.TemporaryDirectory(prefix="uvs-")
        base_tmp = Path(managed_tempdir.name)

    canonical_source = script_path.resolve()

    try:
        # Generate package
        pkg_dir = write_package(
            base_tmp,
            cli_name,
            module_name,
            version,
            description,
            requires_python,
            dependencies,
            canonical_source,
            source_hash,
            script_body,
        )

        # Dry run mode
        if options.get("dry_run"):
            if not options.get("quiet"):
                print(
                    f"Dry run: Would install '{cli_name}' "
                    f"(version {version}) from {canonical_source}"
                )
                if editable:
                    print("  Mode: editable")
                if python:
                    print(f"  Python: {python}")
                if tempdir_value:
                    print(f"  Package: {pkg_dir}")
                else:
                    print("  Package: temporary, discarded after this command")
                if dependencies:
                    print(f"  Dependencies: {', '.join(dependencies)}")
                else:
                    print("  Dependencies: none")
            return 0

        # Install with uv
        result = uvs.run_uv_install(
            pkg_dir,
            editable=editable,
            python=python,
            quiet=options.get("quiet", False),
        )

        if result == 0:
            # Update registry
            try:
                with registry_lock():
                    registry = load_registry()
                    registry.setdefault("scripts", {})
                    registry["scripts"][cli_name] = {
                        "tool_name": cli_name,
                        "source_path": str(canonical_source),
                        "source_hash": source_hash,
                        "installed_at": datetime.now(timezone.utc).isoformat(),
                        "version": version,
                        "editable": editable,
                        "tempdir": (
                            str(_expand_user_path(str(tempdir_value)).resolve())
                            if tempdir_value
                            else None
                        ),
                        "python": python,
                        "dependencies": list(dependencies),
                        "requires_python": requires_python,
                    }
                    save_registry(registry)
            except Exception as e:
                print(
                    "Error: uv installed the tool but the uvs registry was not "
                    f"updated: {e}",
                    file=sys.stderr,
                )
                try:
                    rollback_result = run_uv_uninstall(
                        cli_name, quiet=options.get("quiet", False)
                    )
                except Exception as rollback_error:
                    print(
                        f"Rollback failed for '{cli_name}': {rollback_error}; "
                        "the tool may remain installed but untracked",
                        file=sys.stderr,
                    )
                else:
                    if rollback_result == 0:
                        print(
                            f"Rollback succeeded: uninstalled '{cli_name}' after "
                            "the registry failure",
                            file=sys.stderr,
                        )
                    else:
                        print(
                            f"Rollback failed for '{cli_name}' (uv exit code "
                            f"{rollback_result}); the tool may remain installed but "
                            "untracked",
                            file=sys.stderr,
                        )
                return 1

        return result
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    finally:
        if managed_tempdir is not None:
            managed_tempdir.cleanup()


# Click CLI Definition


class UvsGroup(click.Group):
    """Translate registry failures into actionable CLI errors."""

    def invoke(self, ctx: click.Context):
        try:
            return super().invoke(ctx)
        except RegistryError as exc:
            raise click.ClickException(str(exc)) from exc
        except FileNotFoundError as exc:
            if exc.filename == "uv":
                raise click.ClickException(
                    "uv is not installed or not on PATH. Install uv first: "
                    "https://docs.astral.sh/uv/getting-started/installation/"
                ) from exc
            raise


@click.group(invoke_without_command=True, cls=UvsGroup)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.version_option(__version__, "-V", "--version", prog_name="uvs")
@click.pass_context
def cli(ctx, verbose, quiet, no_color):
    """Install supported single-file PEP 723 scripts as CLI tools using uv.

    \b
    Examples:
        uvs install script.py                # Install a script
        uvs install --name tool script.py    # Install with a custom name
        uvs list                             # List installed tools
        uvs show my-tool                     # Show tool details
        uvs update my-tool                   # Refresh a tool by name
        uvs update --all                     # Refresh every tool
        uvs uninstall my-tool                # Remove a tool
        uvs uninstall --all                  # Remove every tool
        uvs doctor                           # Check registry/uv health

    \b
    Global flags (--verbose, --quiet, --no-color) may also follow a command.
    For detailed help on any command:
        uvs COMMAND --help
    """
    ctx.ensure_object(dict)

    # Handle conflicting options
    if quiet and verbose:
        raise click.UsageError("Cannot use --quiet and --verbose together.")

    # Determine output level
    if quiet:
        level = OutputLevel.QUIET
    elif verbose:
        level = OutputLevel.VERBOSE
    else:
        level = OutputLevel.NORMAL

    # Create output manager
    output = OutputManager(level=level, no_color=_resolve_no_color(no_color))
    ctx.obj["output"] = output

    # Show help if no command provided
    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.command()
@click.argument("script", type=click.Path(), required=False)
@click.option(
    "--name", "-n", help="Override tool name (default: derived from filename)"
)
@click.option(
    "--version",
    default=None,
    help="Initial package version (default: preserve existing, else 0.1.0)",
)
@click.option(
    "--editable", "-e", is_flag=True, help="Install in editable mode for development"
)
@click.option(
    "--tempdir", type=click.Path(), help="Directory for temporary package generation"
)
@click.option("--python", help="Python version to use for installation (e.g., 3.11)")
@click.option("--dry-run", is_flag=True, help="Generate package but do not install")
@click.option(
    "--all", "install_all", is_flag=True, help="Install all .py files in a directory"
)
@click.option(
    "--force",
    is_flag=True,
    help="Replace a tool tracked by uvs or uv under the same name",
)
@output_options
@click.pass_context
def install(
    ctx,
    script,
    name,
    version,
    editable,
    tempdir,
    python,
    dry_run,
    install_all,
    force,
    verbose,
    quiet,
    no_color,
):
    """Install a script as a CLI tool.

    \b
    SCRIPT is the path to the Python script to install. It must define a
    synchronous top-level main() function. It may include PEP 723 metadata for
    dependencies and a Python version constraint.

    By default an existing tool with the same name is left untouched. Use
    --force to replace it; the recorded version is preserved unless --version
    is given explicitly.

    \b
    Examples:
        uvs install my-script.py                            # Install a script
        uvs install --name my-tool script.py                # Custom tool name
        uvs install --version 2.0.0 script.py               # Set initial version
        uvs install --all ./scripts/                        # Install a directory
        uvs install --dry-run script.py                     # Preview only
        uvs install -e --tempdir ./pkg --python 3.11 s.py   # Editable install

    \b
    PEP 723 Metadata Example:
        # /// script
        # requires-python = ">=3.8"
        # dependencies = ["requests", "click"]
        # ///
    """
    output = _apply_output(ctx, verbose, quiet, no_color)
    _require_uv()

    if install_all and name is not None:
        raise click.UsageError(
            "Cannot use --name with --all; batch installs derive each tool name "
            "from its filename."
        )

    q = output.level == OutputLevel.QUIET

    if install_all:
        target_dir = _require_directory(script)
        py_files = sorted(
            [p for p in target_dir.iterdir() if p.is_file() and p.suffix == ".py"]
        )
        if not py_files:
            output.print(f"No .py files found in {target_dir}")
            return 0

        registry = load_registry()
        tracked = registry.get("scripts", {})
        uv_names = uv_tool_names()

        success_count = 0
        skipped_count = 0
        failure_count = 0

        for script_path in py_files:
            cli_name, _ = derive_tool_name(script_path, None)
            _note_name(output, script_path, None)
            existing = tracked.get(cli_name)
            if existing and not force:
                same_source = canonical_source_path(
                    existing["source_path"]
                ) == canonical_source_path(script_path)
                if not same_source:
                    output.warning(
                        f"Skipping {script_path.name}: '{cli_name}' is tracked "
                        f"from a different source ({existing['source_path']}). "
                        "Use --force to replace it."
                    )
                    skipped_count += 1
                    continue
            elif not existing and uv_names and cli_name in uv_names and not force:
                output.warning(
                    f"Skipping {script_path.name}: a uv tool named '{cli_name}' "
                    "exists but is not tracked by uvs. Use --force to replace it."
                )
                skipped_count += 1
                continue

            output.print(f"Installing {script_path.name}...")
            options_dict = {
                "name": None,
                "version": version,
                "editable": editable,
                "tempdir": tempdir,
                "python": python,
                "dry_run": dry_run,
                "update": False,
                "quiet": q,
            }
            result = install_script_quiet(script_path, options_dict)
            if result == 0:
                success_count += 1
            else:
                failure_count += 1
                output.error(f"Failed to install {script_path.name}")

        total = len(py_files)
        skipped_text = (
            f", {skipped_count} skipped" if skipped_count else ""
        )
        if failure_count > 0:
            output.error(
                f"{failure_count} of {total} scripts failed "
                f"({success_count} installed{skipped_text})."
            )
            ctx.exit(1)
        if dry_run:
            output.print(
                f"Dry run: would install {success_count} of {total} scripts"
                f"{skipped_text}."
            )
        else:
            output.print(
                f"Successfully installed {success_count} "
                f"{_plural(success_count, 'script')}{skipped_text}."
            )
        return 0

    # Single script installation
    script_path = _require_script(script)
    if editable and not tempdir:
        raise click.UsageError(
            "Editable installs require --tempdir to preserve package files."
        )
    if script_path.suffix.lower() != ".py":
        output.warning(f"'{script_path.name}' does not end in .py; installing anyway.")
    _note_name(output, script_path, name)

    cli_name, _ = derive_tool_name(script_path, name)

    registry = load_registry()
    existing = registry.get("scripts", {}).get(cli_name)
    if existing and not force:
        raise click.UsageError(
            f"Tool '{cli_name}' is already tracked by uvs. Use 'uvs update "
            f"{cli_name}' to refresh it or 'uvs install --force' to replace it."
        )
    if not existing and not force:
        uv_names = uv_tool_names()
        if uv_names is not None and cli_name in uv_names:
            raise click.UsageError(
                f"A uv tool named '{cli_name}' exists but is not tracked by uvs. "
                "Re-run with --force to replace it."
            )

    options_dict = {
        "name": name,
        "version": version,
        "editable": editable,
        "tempdir": tempdir,
        "python": python,
        "dry_run": dry_run,
        "update": False,
        "quiet": q,
    }

    result = install_with_progress(script_path, options_dict, output)

    if result == 0 and not dry_run:
        entry = load_registry().get("scripts", {}).get(cli_name, {})
        show_success_message(
            output,
            cli_name,
            script_path,
            entry.get("version", version or "0.1.0"),
            dependencies=entry.get("dependencies"),
            editable=bool(entry.get("editable")),
            python=entry.get("python"),
        )

    if result != 0:
        ctx.exit(result)


@cli.command(name="list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "simple"]),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--check",
    is_flag=True,
    help="Verify each tool against uv and its source; exits 1 if any problem is found",
)
@output_options
@click.pass_context
def list_tools(ctx, output_format, check, verbose, quiet, no_color):
    """List all installed scripts.

    \b
    Examples:
        uvs list                    # Table format (default)
        uvs list --format json      # JSON format
        uvs list --format simple    # Simple format
        uvs list --check            # Include health status
    """
    output = _apply_output(ctx, verbose, quiet, no_color)

    registry = load_registry()
    tools = registry.get("scripts", {})

    statuses = None
    uv_names = None
    if check:
        uv_names = uv_tool_names()
        if uv_names is None:
            output.warning(
                "uv is unavailable; install status could not be verified"
            )
        statuses = {
            name: _tool_status(name, info, uv_names) for name, info in tools.items()
        }

    if not tools:
        if output_format == "json":
            show_tools_json(tools, output, statuses)
        else:
            click.echo("No tools installed")
        return

    if output_format == "table":
        show_tools_table(tools, output, statuses)
    elif output_format == "json":
        show_tools_json(tools, output, statuses)
    else:
        show_tools_simple(tools, output, statuses)

    if check and statuses is not None:
        problems = [name for name, status in statuses.items() if status != "ok"]
        if problems:
            output.error(
                f"{len(problems)} of {len(tools)} tools need attention: "
                + ", ".join(sorted(problems))
            )
            ctx.exit(1)


@cli.command()
@click.argument("tool_name")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "simple"]),
    default="table",
    help="Output format (default: table)",
)
@output_options
@click.pass_context
def show(ctx, tool_name, output_format, verbose, quiet, no_color):
    """Show details about an installed tool.

    \b
    Examples:
        uvs show my-tool             # Table format (default)
        uvs show --format json my-tool  # JSON format
        uvs show --format simple my-tool  # Plain-text key/value format
    """
    output = _apply_output(ctx, verbose, quiet, no_color)

    registry = load_registry()
    tool_info = registry.get("scripts", {}).get(tool_name)

    if not tool_info:
        raise click.ClickException(f"No tool named '{tool_name}' is tracked by uvs.")

    if output_format == "json":
        click.echo(json.dumps(tool_info, indent=2, sort_keys=True))
    elif output_format == "simple":
        show_tool_simple(tool_name, tool_info)
    else:
        uv_names = uv_tool_names()
        status = (
            "unknown"
            if uv_names is None
            else _tool_status(tool_name, tool_info, uv_names)
        )

        table = Table(
            title=f"Tool Details: {tool_name}",
            box=None,
            show_edge=False,
            pad_edge=False,
            padding=(0, 1),
            header_style=_table_style(output, "bold magenta"),
        )
        table.add_column("Property", style=_table_style(output, "cyan"))
        table.add_column("Value", style=_table_style(output, "white"))

        table.add_row("Name", tool_info["tool_name"])
        table.add_row("Source", tool_info["source_path"])
        table.add_row("Version", tool_info["version"])
        table.add_row("Installed", _human_timestamp(tool_info.get("installed_at")))
        table.add_row("Hash", tool_info.get("source_hash", ""))
        table.add_row(
            "Dependencies", _display_list(tool_info.get("dependencies", []))
        )
        table.add_row("Requires-Python", tool_info.get("requires_python") or "any")
        table.add_row("Python", tool_info.get("python") or "default")
        table.add_row(
            "Editable", "yes" if tool_info.get("editable") else "no"
        )
        if tool_info.get("tempdir"):
            table.add_row("Package dir", tool_info["tempdir"])
        table.add_row("Status", _STATUS_LABELS.get(status, status))

        output.data_console.print()
        output.data_console.print(table)
        output.data_console.print()


def _resolve_update_target(
    target: str, tools: Dict[str, Any]
) -> tuple[str, Optional[Dict[str, Any]]]:
    """Resolve a tool name or script path to a registry entry."""
    if target in tools:
        return target, tools[target]

    path = _expand_user_path(target)
    if path.exists() and path.is_dir():
        raise click.UsageError(
            f"'{target}' is a directory. Pass a tool name or a script path."
        )
    if path.exists():
        resolved = canonical_source_path(path)
        matches = [
            (name, info)
            for name, info in tools.items()
            if canonical_source_path(info["source_path"]) == resolved
        ]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = ", ".join(sorted(name for name, _ in matches))
            raise click.UsageError(
                f"Multiple installed tools map to {target}: {names}. "
                "Pass the tool name you want to update."
            )
        raise click.UsageError(
            f"No installed tool found for '{target}'. Use 'uvs install' first "
            "or 'uvs list' to see tracked tools."
        )
    raise click.UsageError(
        f"No installed tool or file named '{target}'. Use 'uvs list' to see "
        "tracked tools."
    )


@cli.command()
@click.argument("target", required=False)
@click.option("--all", "update_all", is_flag=True, help="Update all installed tools")
@click.option("--python", help="Python version for installation")
@click.option(
    "--dry-run", is_flag=True, help="Show what would be updated without installing"
)
@output_options
@click.pass_context
def update(ctx, target, update_all, python, dry_run, verbose, quiet, no_color):
    """Update an installed tool if its source changed.

    \b
    TARGET may be either a tracked tool name or the source script path.

    \b
    Examples:
        uvs update my-tool            # Update by tool name
        uvs update my-script.py       # Update by source path
        uvs update --all              # Update all tools
        uvs update --dry-run --all    # Preview updates
        uvs update --python 3.11 my-tool  # Reinstall on another Python
    """
    output = _apply_output(ctx, verbose, quiet, no_color)
    _require_uv()

    if not target and not update_all:
        raise click.UsageError("Provide a tool name or script path, or use --all.")
    if target and update_all:
        raise click.UsageError("Cannot combine TARGET with --all.")

    q = output.level == OutputLevel.QUIET

    if update_all:
        registry = load_registry()
        tools = registry.get("scripts", {})

        if not tools:
            output.print("No tools installed to update")
            return 0

        success_count = 0
        unchanged_count = 0
        failure_count = 0
        missing: list[str] = []

        for tool_name, tool_info in tools.items():
            script_path = Path(tool_info["source_path"])
            if not script_path.is_file():
                output.warning(
                    f"Source file not found for {tool_name}: {script_path}. "
                    f"Run 'uvs uninstall {tool_name}' to remove the stale entry."
                )
                missing.append(tool_name)
                failure_count += 1
                continue

            output.print(f"Checking {tool_name}...")

            current_hash = compute_hash(script_path)
            if current_hash == tool_info.get("source_hash"):
                output.verbose(f"No changes detected for {tool_name}")
                unchanged_count += 1
                continue

            new_version = bump_patch_version(tool_info.get("version", "0.1.0"))
            if dry_run:
                output.print(
                    f"Would update {tool_name} "
                    f"({tool_info.get('version', '?')} -> {new_version})"
                )
                success_count += 1
                continue

            options_dict = {
                "name": tool_name,
                "version": tool_info.get("version", "0.1.0"),
                "editable": bool(tool_info.get("editable")),
                "tempdir": tool_info.get("tempdir"),
                "python": python or tool_info.get("python"),
                "dry_run": False,
                "update": True,
                "quiet": q,
            }

            result = install_script_quiet(script_path, options_dict)
            if result == 0:
                success_count += 1
                output.print(
                    f"Updated {tool_name} "
                    f"({tool_info.get('version', '?')} -> {new_version})"
                )
            else:
                failure_count += 1
                output.error(f"Failed to update {tool_name}")

        if failure_count > 0:
            output.error(
                f"Updated {success_count}, {unchanged_count} already up to date, "
                f"{failure_count} failed."
            )
            ctx.exit(1)
        if dry_run:
            output.print(
                f"Dry run: {success_count} "
                f"{_plural(success_count, 'update')} available, "
                f"{unchanged_count} already up to date."
            )
            return 0
        if success_count == 0:
            output.print(f"All {len(tools)} tools are up to date.")
            return 0
        total = len(tools)
        output.print(
            f"Successfully updated {success_count} of {total} "
            f"{_plural(total, 'tool')}; {unchanged_count} already up to date."
        )
        return 0

    # Update a single tool by name or source path.
    registry = load_registry()
    cli_name, existing = _resolve_update_target(target, registry.get("scripts", {}))

    script_path = Path(existing["source_path"])
    if not script_path.is_file():
        raise click.UsageError(
            f"Source file for '{cli_name}' is missing: {script_path}. "
            f"Run 'uvs uninstall {cli_name}' to remove it or 'uvs install' to "
            "re-add it from a new path."
        )

    current_hash = compute_hash(script_path)
    if current_hash == existing.get("source_hash"):
        output.print(f"No changes detected for {cli_name}")
        return 0

    old_version = existing.get("version", "0.1.0")
    new_version = bump_patch_version(old_version)

    if dry_run:
        output.print(f"Would update {cli_name} ({old_version} -> {new_version})")
        return 0

    options_dict = {
        "name": cli_name,
        "version": old_version,
        "editable": bool(existing.get("editable")),
        "tempdir": existing.get("tempdir"),
        "python": python or existing.get("python"),
        "dry_run": False,
        "update": True,
        "quiet": q,
    }

    result = install_with_progress(script_path, options_dict, output)

    if result == 0:
        output.print(f"Successfully updated {cli_name} ({old_version} -> {new_version})")

    if result != 0:
        ctx.exit(result)


@cli.command()
@click.argument("tool_name", required=False)
@click.option(
    "--all", "uninstall_all", is_flag=True, help="Uninstall all installed tools"
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be uninstalled without actually uninstalling",
)
@click.option(
    "--backup/--no-backup",
    default=True,
    help="Create a backup of the registry before uninstalling",
)
@click.option("--force", is_flag=True, help="Force uninstall without confirmation")
@output_options
@click.pass_context
def uninstall(
    ctx, tool_name, uninstall_all, dry_run, backup, force, verbose, quiet, no_color
):
    """Uninstall an installed tool.

    \b
    Examples:
        uvs uninstall my-tool         # Uninstall a specific tool
        uvs uninstall --all           # Uninstall all tools
        uvs uninstall --dry-run tool  # Preview what would be uninstalled
        uvs backup list               # List registry backups
    """
    output = _apply_output(ctx, verbose, quiet, no_color)

    if tool_name and uninstall_all:
        raise click.UsageError(
            "Cannot combine TOOL_NAME with --all; choose one."
        )
    if not tool_name and not uninstall_all:
        raise click.UsageError("Provide TOOL_NAME or --all.")
    _require_uv()

    registry = load_registry()
    tools = registry.get("scripts", {})

    if not tools:
        output.print("No tools installed")
        return 0

    # Create backup if requested
    if backup and not dry_run:
        try:
            backup_path = backup_registry()
            output.verbose(f"Created registry backup at: {backup_path}")
        except Exception as e:
            output.warning(f"Failed to create registry backup: {e}")

    if uninstall_all:
        if not force and not dry_run:
            output.print(f"\nTools to uninstall ({len(tools)}):")
            for name, info in tools.items():
                output.print(f"  - {name}  ({info['source_path']})")
            output.print("")
            if not click.confirm(
                f"Are you sure you want to uninstall all {len(tools)} tools?"
            ):
                output.print("Uninstall cancelled")
                return 0

        uv_names = uv_tool_names()
        success_count = 0
        failure_count = 0

        for name, info in tools.items():
            if dry_run:
                output.print(f"Would uninstall: {name} (from {info['source_path']})")
                success_count += 1
                continue

            if uv_names is not None and name not in uv_names:
                if cleanup_registry_entry(name):
                    output.warning(
                        f"{name} was already uninstalled "
                        "(cleaned up stale registry entry)"
                    )
                    success_count += 1
                else:
                    output.error(f"Failed to remove stale registry entry for {name}")
                    failure_count += 1
                continue

            output.print(f"Uninstalling {name}...")
            output.verbose(f"Running: uv tool uninstall {name}")
            result = run_uv_uninstall(name, quiet=output.level == OutputLevel.QUIET)

            if result == 0 and verify_tool_uninstalled(name):
                if cleanup_registry_entry(name):
                    success_count += 1
                else:
                    output.error(
                        f"Uninstalled {name} but failed to remove it from the "
                        "uvs registry"
                    )
                    failure_count += 1
            elif verify_tool_uninstalled(name):
                if cleanup_registry_entry(name):
                    output.warning(
                        f"{name} was already uninstalled "
                        "(cleaned up stale registry entry)"
                    )
                    success_count += 1
                else:
                    output.error(f"Failed to remove stale registry entry for {name}")
                    failure_count += 1
            else:
                output.error(f"Failed to uninstall {name}")
                failure_count += 1

        if dry_run:
            output.print(f"Would uninstall {success_count} tools")
            return 0
        if failure_count > 0:
            output.error(
                f"Uninstalled {success_count} tools, {failure_count} failed."
            )
            ctx.exit(1)
        output.print(f"Successfully uninstalled all {success_count} tools")
        return 0

    # Uninstall single tool
    if tool_name not in tools:
        raise click.UsageError(f"No tool named '{tool_name}' is tracked by uvs.")

    tool_info = tools[tool_name]

    if dry_run:
        output.print(
            f"Would uninstall: {tool_name} (from {tool_info['source_path']})"
        )
        return 0

    if not force:
        if not click.confirm(f"Are you sure you want to uninstall '{tool_name}'?"):
            output.print("Uninstall cancelled")
            return 0

    # Fast path: uv already lost the tool, so only the registry needs cleanup.
    if verify_tool_uninstalled(tool_name):
        if cleanup_registry_entry(tool_name):
            output.warning(
                f"{tool_name} was already uninstalled "
                "(cleaned up stale registry entry)"
            )
            return 0
        output.error(f"Failed to remove stale registry entry for {tool_name}")
        ctx.exit(1)

    output.print(f"Uninstalling {tool_name}...")
    output.verbose(f"Running: uv tool uninstall {tool_name}")
    result = run_uv_uninstall(tool_name, quiet=output.level == OutputLevel.QUIET)

    if result == 0:
        if verify_tool_uninstalled(tool_name):
            if cleanup_registry_entry(tool_name):
                output.verbose(f"Removed {tool_name} from registry")
                output.print(f"Successfully uninstalled {tool_name}")
                return 0
            output.error(
                f"Uninstalled {tool_name} but failed to remove it from the "
                "uvs registry"
            )
            ctx.exit(1)
        output.error(f"Failed to verify uninstallation of {tool_name}")
        ctx.exit(1)

    if verify_tool_uninstalled(tool_name):
        if cleanup_registry_entry(tool_name):
            output.warning(
                f"{tool_name} was already uninstalled "
                "(cleaned up stale registry entry)"
            )
            return 0
        output.error(f"Failed to remove stale registry entry for {tool_name}")
        ctx.exit(1)

    output.error(f"Failed to uninstall {tool_name}")
    ctx.exit(1)


@cli.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
@output_options
@click.pass_context
def doctor(ctx, output_format, verbose, quiet, no_color):
    """Check the registry, uv, and every tracked tool.

    Exits 1 when a tool needs attention, so it can gate scripts and CI.
    """
    output = _apply_output(ctx, verbose, quiet, no_color)

    registry = load_registry()
    tools = registry.get("scripts", {})
    uv_names = uv_tool_names()
    uv_available = shutil.which("uv") is not None

    statuses = {
        name: _tool_status(name, info, uv_names) for name, info in tools.items()
    }
    problems = [name for name, status in statuses.items() if status != "ok"]
    orphans = (
        sorted(set(uv_names) - set(tools) - {DISTRIBUTION_NAME})
        if uv_names is not None
        else []
    )
    backups = list_backups()

    payload = {
        "registry": str(get_registry_path()),
        "registry_version": registry.get("version"),
        "uv_available": uv_available,
        "tools": {
            name: dict(info, status=statuses[name]) for name, info in tools.items()
        },
        "problems": problems,
        "untracked_uv_tools": orphans,
        "backups": len(backups),
    }

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
    else:
        table = Table(
            title="uvs doctor",
            box=None,
            show_edge=False,
            pad_edge=False,
            padding=(0, 1),
            header_style=_table_style(output, "bold magenta"),
        )
        table.add_column("Check", style=_table_style(output, "cyan"))
        table.add_column("Value")
        table.add_row("Registry", str(get_registry_path()))
        table.add_row(
            "uv",
            "available" if uv_available else "missing (install uv and add it to PATH)",
        )
        table.add_row("Backups", str(len(backups)))
        for name in sorted(tools):
            table.add_row(
                f"Tool: {name}",
                _STATUS_LABELS.get(statuses[name], statuses[name]),
            )
        for orphan in orphans:
            table.add_row(
                f"Untracked uv tool: {orphan}",
                "not managed by uvs (expected for uv itself)",
            )
        output.data_console.print()
        output.data_console.print(table)
        output.data_console.print()

    if not uv_available:
        output.error("uv is not installed or not on PATH.")
        ctx.exit(1)
    if problems:
        output.error(
            f"{len(problems)} of {len(tools)} tools need attention: "
            + ", ".join(sorted(problems))
            + ". Run 'uvs list --check' or 'uvs prune' for details."
        )
        ctx.exit(1)

    output.print("All tracked tools look healthy.")


@cli.command()
@click.option(
    "--dry-run", is_flag=True, help="Show what would be pruned without changing it"
)
@click.option("--force", is_flag=True, help="Prune without confirmation")
@output_options
@click.pass_context
def prune(ctx, dry_run, force, verbose, quiet, no_color):
    """Remove registry entries whose source or uv tool is gone."""
    output = _apply_output(ctx, verbose, quiet, no_color)

    registry = load_registry()
    tools = registry.get("scripts", {})
    if not tools:
        output.print("No tools installed")
        return 0

    uv_names = uv_tool_names()
    if uv_names is None:
        output.warning("uv is unavailable; only source files can be checked")
    stale: list[tuple[str, str]] = []
    kept: list[tuple[str, str]] = []
    for name, info in tools.items():
        source_missing = not Path(info.get("source_path", "")).is_file()
        not_installed = uv_names is not None and name not in uv_names
        if not_installed:
            reason = (
                "source file and uv tool are both missing"
                if source_missing
                else "tool is not installed in uv"
            )
            stale.append((name, reason))
        elif source_missing:
            kept.append(
                (
                    name,
                    "source file is missing but the tool is still installed; "
                    f"run 'uvs uninstall {name}' to remove it",
                )
            )

    if not stale:
        if kept:
            for name, reason in kept:
                output.warning(f"Keeping {name}: {reason}")
        output.print(f"Nothing to prune ({len(tools)} tracked tools)")
        return 0

    if dry_run:
        for name, reason in stale:
            output.print(f"Would remove {name}: {reason}")
        for name, reason in kept:
            output.warning(f"Keeping {name}: {reason}")
        output.print(f"Would prune {len(stale)} of {len(tools)} tools")
        return 0

    if not force:
        output.print(f"\nEntries to prune ({len(stale)}):")
        for name, reason in stale:
            output.print(f"  - {name}  ({reason})")
        output.print("")
        if not click.confirm(f"Remove {len(stale)} registry entries?"):
            output.print("Prune cancelled")
            return 0

    removed = 0
    for name, _reason in stale:
        if cleanup_registry_entry(name):
            removed += 1
        else:
            output.warning(f"Failed to remove {name}")
    for name, reason in kept:
        output.warning(f"Keeping {name}: {reason}")
    output.print(f"Pruned {removed} of {len(tools)} registry entries")
    return 0


@cli.group()
def backup():
    """Manage registry backups."""


@backup.command("list")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    help="Output format (default: table)",
)
@output_options
@click.pass_context
def backup_list(ctx, output_format, verbose, quiet, no_color):
    """List registry backups, newest first."""
    output = _apply_output(ctx, verbose, quiet, no_color)

    backups = list_backups()
    if output_format == "json":
        payload = [
            {"file": path.name, "path": str(path), "bytes": path.stat().st_size}
            for path in backups
        ]
        click.echo(json.dumps(payload, indent=2))
        return

    if not backups:
        click.echo("No registry backups found")
        return

    table = Table(
        show_header=True,
        box=None,
        show_edge=False,
        pad_edge=False,
        padding=(0, 1),
        header_style=_table_style(output, "bold magenta"),
    )
    table.add_column("Backup", style=_table_style(output, "cyan"))
    table.add_column("Size", style=_table_style(output, "yellow"))
    for path in backups:
        table.add_row(path.name, f"{path.stat().st_size} bytes")
    output.data_console.print()
    output.data_console.print(table)
    output.data_console.print()


@backup.command("restore")
@click.argument("target", required=False)
@click.option(
    "--dry-run", is_flag=True, help="Show what would be restored without changing it"
)
@click.option(
    "--no-backup",
    is_flag=True,
    help="Do not back up the current registry before restoring",
)
@output_options
@click.pass_context
def backup_restore(ctx, target, dry_run, no_backup, verbose, quiet, no_color):
    """Restore the registry from a backup (default: latest)."""
    output = _apply_output(ctx, verbose, quiet, no_color)

    backups = list_backups()
    if not backups:
        raise click.ClickException("No registry backups found.")

    if target in (None, "latest"):
        chosen = backups[0]
    else:
        matching = [
            path
            for path in backups
            if target in (path.name, path.stem, path.stem.removeprefix("registry_"))
        ]
        if not matching:
            raise click.UsageError(
                f"No backup matching '{target}'. Run 'uvs backup list' to see "
                "available backups."
            )
        chosen = matching[0]

    if dry_run:
        output.print(f"Would restore registry from {chosen} (dry run)")
        return 0

    if not no_backup:
        current = backup_registry()
        output.verbose(f"Backed up current registry to {current}")

    restore_registry_backup(chosen)
    output.print(f"Restored registry from {chosen}")
    return 0


if __name__ == "__main__":
    cli()
