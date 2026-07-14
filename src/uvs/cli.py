#!/usr/bin/env python3
"""
uvs: Install single-file PEP723 scripts as CLI tools using uv.

This module provides the Click-based CLI interface for uvs.
"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from . import uvs
from .uvs import (
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
    load_registry,
    parse_pep723_header,
    read_script_source,
    registry_lock,
    run_uv_install,
    run_uv_uninstall,
    save_registry,
    strip_pep723_header_and_main,
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
    DEBUG = 3


class OutputManager:
    """Manages output levels and formatting."""

    def __init__(self, level: OutputLevel = OutputLevel.NORMAL, no_color: bool = False):
        self.level = level
        self.no_color = no_color
        self.console = Console(no_color=no_color, quiet=(level == OutputLevel.QUIET))
        self.error_console = Console(stderr=True, no_color=no_color)

    def print(
        self,
        message: str,
        level: OutputLevel = OutputLevel.NORMAL,
        style: Optional[str] = None,
    ):
        """Print message if current output level allows it."""
        if self.level.value >= level.value:
            if style:
                self.console.print(message, style=style)
            else:
                self.console.print(message)

    def error(self, message: str, style: str = "red"):
        """Always print error messages."""
        self.error_console.print(message, style=style)

    def warning(self, message: str):
        """Print warning if not in quiet mode."""
        if self.level.value >= OutputLevel.NORMAL.value:
            self.error_console.print(f"[yellow]Warning:[/yellow] {message}")

    def verbose(self, message: str):
        """Print verbose message in verbose or debug mode."""
        if self.level.value >= OutputLevel.VERBOSE.value:
            self.console.print(f"[dim]{message}[/dim]")

    def debug(self, message: str):
        """Print debug message in debug mode."""
        if self.level == OutputLevel.DEBUG:
            self.console.print(f"[dim]Debug: {message}[/dim]")


def show_success_message(
    output: OutputManager, tool_name: str, script_path: Path, version: str
):
    """Display success message with Rich panel."""
    success_panel = Panel(
        f"[bold green]✓ Successfully installed[/bold green] [cyan]{tool_name}[/cyan]\n\n"
        f"[dim]Source: {script_path}[/dim]\n"
        f"[dim]Version: {version}[/dim]\n\n"
        f"[yellow]Run '{tool_name}' to use your new tool[/yellow]",
        title="Installation Complete",
        border_style="green",
        padding=(1, 2),
    )

    output.console.print(success_panel)


def show_tools_table(tools: Dict[str, Any], output: OutputManager):
    """Display installed tools in a Rich table."""
    table = Table(
        show_header=True,
        header_style="bold magenta",
        box=None,
        show_edge=False,
        pad_edge=False,
        padding=(0, 1),
    )
    table.add_column("Tool Name", style="cyan", no_wrap=True)
    table.add_column("Source Path", style="green")
    table.add_column("Version", style="yellow")
    table.add_column("Installed At", style="blue")

    for name, info in tools.items():
        table.add_row(
            name,
            info["source_path"],
            info["version"],
            info["installed_at"][:19],  # Remove microseconds
        )

    output.console.print()
    output.console.print(table)
    output.console.print()

    # Show summary
    output.verbose(f"Total: {len(tools)} tools")


def show_tools_json(tools: Dict[str, Any], output: OutputManager):
    """Display stable, machine-readable JSON without Rich decoration."""
    payload = {"tools": tools, "count": len(tools)}
    click.echo(json.dumps(payload, indent=2, sort_keys=True))


def show_tools_simple(tools: Dict[str, Any], output: OutputManager):
    """Display tools in simple format."""
    for name, info in tools.items():
        output.print(f"{name} <- {info['source_path']} (v{info['version']})")


def install_with_progress(
    script_path: Path, options: Dict[str, Any], output: OutputManager
) -> int:
    """Install script with progress indicators."""
    if output.level == OutputLevel.QUIET:
        return install_script_quiet(script_path, options)

    # Show verbose info before installing
    if output.level.value >= OutputLevel.VERBOSE.value:
        try:
            header = parse_pep723_header(script_path)
        except ValueError as exc:
            output.error(f"Error: {exc}")
            return 1
        output.verbose(f"Dependencies: {header.get('dependencies', [])}")

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
    """Install script without progress indicators."""

    # Parse PEP723 header
    try:
        header = parse_pep723_header(script_path)
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    requires_python = header.get("requires-python") or header.get("requires_python")
    dependencies = header.get("dependencies") or header.get("dependencies", [])
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

    # Validate script has a main() function
    if not validate_script_has_main(source_text):
        print(
            f"Error: Script {script_path.name} does not define a main() function",
            file=sys.stderr,
        )
        return 1

    # Derive names and version
    try:
        cli_name, module_name = derive_tool_name(script_path, options.get("name"))
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    version = options.get("version", "0.1.0")

    # Check for updates if requested
    if options.get("update"):
        registry = load_registry()
        existing = registry.get("scripts", {}).get(cli_name)
        if existing:
            current_hash = compute_hash(script_path)
            if existing.get("source_hash") != current_hash:
                old_ver = existing.get("version", version)
                version = bump_patch_version(old_ver)
            else:
                # No changes, skip installation
                return 0

    description = extract_description(source_text)

    # Get source hash
    source_hash = compute_hash(script_path)

    # Setup temp directory
    tempdir = options.get("tempdir")
    if options.get("editable") and not tempdir:
        print(
            "Error: Editable installs require --tempdir to preserve package files",
            file=sys.stderr,
        )
        return 1
    managed_tempdir = None
    if tempdir:
        base_tmp = Path(tempdir)
        base_tmp.mkdir(parents=True, exist_ok=True)
    else:
        managed_tempdir = tempfile.TemporaryDirectory(prefix="uvs-")
        base_tmp = Path(managed_tempdir.name)

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
            script_path,
            source_hash,
            script_body,
        )

        # Dry run mode
        if options.get("dry_run"):
            if not options.get("quiet"):
                print(
                    f"Dry run: Would install '{cli_name}' "
                    f"(version {version}) from {script_path}"
                )
                print(f"  Package would be generated at: {pkg_dir}")
                if dependencies:
                    print(f"  Dependencies: {', '.join(dependencies)}")
                else:
                    print("  Dependencies: none")
            return 0

        # Install with uv
        result = uvs.run_uv_install(
            pkg_dir,
            editable=options.get("editable", False),
            python=options.get("python"),
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
                        "source_path": str(script_path.resolve()),
                        "source_hash": source_hash,
                        "installed_at": datetime.now(timezone.utc).isoformat(),
                        "version": version,
                    }
                    save_registry(registry)
            except Exception as e:
                print(
                    "Error: uv installed the tool but the uvs registry was not "
                    f"updated: {e}",
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


@click.group(invoke_without_command=True)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose output")
@click.option("--quiet", "-q", is_flag=True, help="Suppress non-error output")
@click.option("--debug", is_flag=True, help="Enable debug output")
@click.option("--no-color", is_flag=True, help="Disable colored output")
@click.pass_context
def cli(ctx, verbose, quiet, debug, no_color):
    """Install single-file PEP723 scripts as CLI tools using uv.

    \b
    Examples:
        uvs install script.py           # Install a script
        uvs install --name tool script.py  # Install with custom name
        uvs list                        # List installed tools
        uvs show my-tool               # Show tool details
        uvs update script.py           # Update a tool
        uvs uninstall my-tool         # Uninstall a tool
        uvs uninstall --all           # Uninstall all tools

    \b
    For detailed help on any command:
        uvs COMMAND --help
    """
    ctx.ensure_object(dict)

    # Handle conflicting options
    if quiet and verbose:
        raise click.BadParameter("Cannot specify both --quiet and --verbose")
    if quiet and debug:
        raise click.BadParameter("Cannot specify both --quiet and --debug")

    # Determine output level
    if quiet:
        level = OutputLevel.QUIET
    elif verbose:
        level = OutputLevel.VERBOSE
    elif debug:
        level = OutputLevel.DEBUG
    else:
        level = OutputLevel.NORMAL

    # Create output manager
    output = OutputManager(level=level, no_color=no_color)
    ctx.obj["output"] = output

    # Show help if no command provided
    if ctx.invoked_subcommand is None:
        console = Console(no_color=no_color)
        console.print(ctx.get_help())


@cli.command()
@click.argument("script", type=click.Path(exists=True), required=False)
@click.option(
    "--name", "-n", help="Override tool name (default: derived from filename)"
)
@click.option(
    "--version", default="0.1.0", help="Initial package version (default: 0.1.0)"
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
    "--all", "install_all", is_flag=True, help="Install all .py files in directory"
)
@click.pass_context
def install(
    ctx, script, name, version, editable, tempdir, python, dry_run, install_all
):
    """Install a script as a CLI tool.

    \b
    SCRIPT is the path to the Python script to install. The script should:
    - Contain PEP723 metadata in a comment block
    - Have a main() function that will be called when the tool is executed

    \b
    Examples:
        uvs install my-script.py                    # Install with default name
        uvs install --name my-tool script.py        # Custom tool name
        uvs install --all ./scripts/                # Install all scripts in directory
        uvs install --dry-run script.py             # Preview without installing
        uvs install --editable --python 3.11 script.py  # Development install

    \b
    PEP723 Metadata Example:
        # /// script
        # requires-python = ">=3.8"
        # dependencies = ["requests", "click"]
        # ///
    """
    output = ctx.obj["output"]

    if install_all:
        # Handle batch installation
        target_dir = Path(script) if script else Path(".")
        if not target_dir.exists() or not target_dir.is_dir():
            output.error("Target for --all must be an existing directory")
            ctx.exit(1)

        py_files = sorted(
            [p for p in target_dir.iterdir() if p.is_file() and p.suffix == ".py"]
        )
        if not py_files:
            output.print(f"No .py files found in {target_dir}")
            return 0

        success_count = 0
        failure_count = 0

        for script_path in py_files:
            output.print(f"Processing {script_path.name}...")
            options_dict = {
                "name": name,
                "version": version,
                "editable": editable,
                "tempdir": tempdir,
                "python": python,
                "dry_run": dry_run,
                "update": False,
                "quiet": output.level == OutputLevel.QUIET,
            }

            result = install_script_quiet(script_path, options_dict)
            if result == 0:
                success_count += 1
            else:
                failure_count += 1
                output.error(f"Failed to install {script_path.name}")

        if failure_count > 0:
            output.print(f"Completed with {failure_count} failures")
            ctx.exit(1)

        output.print(f"Successfully installed {success_count} scripts")
        return 0

    else:
        # Handle single script installation
        if not script:
            output.error("Script path is required")
            ctx.exit(1)

        script_path = Path(script)
        options_dict = {
            "name": name,
            "version": version,
            "editable": editable,
            "tempdir": tempdir,
            "python": python,
            "dry_run": dry_run,
            "update": False,
            "quiet": output.level == OutputLevel.QUIET,
        }

        result = install_with_progress(script_path, options_dict, output)

        if result == 0 and not dry_run:
            cli_name, _ = derive_tool_name(script_path, name)
            show_success_message(output, cli_name, script_path, version)

        if result != 0:
            ctx.exit(result)


@cli.command()
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "simple"]),
    default="table",
    help="Output format (default: table)",
)
@click.pass_context
def list(ctx, output_format):
    """List all installed scripts.

    \b
    Examples:
        uvs list                    # Table format (default)
        uvs list --format json      # JSON format
        uvs list --format simple    # Simple format
    """
    output = ctx.obj["output"]

    registry = load_registry()
    tools = registry.get("scripts", {})

    if not tools and output_format != "json":
        if output.level != OutputLevel.QUIET:
            output.print("No tools installed")
        return

    if output_format == "table":
        show_tools_table(tools, output)
    elif output_format == "json":
        show_tools_json(tools, output)
    else:
        show_tools_simple(tools, output)


@cli.command()
@click.argument("tool_name")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json", "simple"]),
    default="table",
    help="Output format (default: table)",
)
@click.pass_context
def show(ctx, tool_name, output_format):
    """Show details about an installed tool.

    \b
    Examples:
        uvs show my-tool             # Table format (default)
        uvs show --format json my-tool  # JSON format
    """
    output = ctx.obj["output"]

    registry = load_registry()
    tool_info = registry.get("scripts", {}).get(tool_name)

    if not tool_info:
        raise click.ClickException(f"No tool named '{tool_name}' found")

    if output_format == "json":
        show_tools_json({tool_name: tool_info}, output)
    else:
        # Show detailed information
        from rich.table import Table

        table = Table(
            title=f"Tool Details: {tool_name}",
            box=None,
            show_edge=False,
            pad_edge=False,
            padding=(0, 1),
        )
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("Name", tool_info["tool_name"])
        table.add_row("Source", tool_info["source_path"])
        table.add_row("Version", tool_info["version"])
        table.add_row("Installed", tool_info["installed_at"])
        table.add_row("Hash", tool_info["source_hash"][:16] + "...")

        output.console.print()
        output.console.print(table)
        output.console.print()


@cli.command()
@click.argument("script", type=click.Path(exists=True), required=False)
@click.option("--all", "update_all", is_flag=True, help="Update all installed tools")
@click.option("--python", help="Python version for installation")
@click.pass_context
def update(ctx, script, update_all, python):
    """Update an installed tool if the source changed.

    \b
    Examples:
        uvs update my-script.py       # Update specific tool
        uvs update --all             # Update all tools
        uvs update --python 3.11 script.py  # Update with specific Python
    """
    output = ctx.obj["output"]

    if not script and not update_all:
        output.error("SCRIPT or --all is required")
        ctx.exit(1)

    if update_all:
        # Update all installed tools
        registry = load_registry()
        tools = registry.get("scripts", {})

        if not tools:
            output.print("No tools installed to update")
            return 0

        success_count = 0
        failure_count = 0

        for tool_name, tool_info in tools.items():
            script_path = Path(tool_info["source_path"])
            if not script_path.exists():
                output.warning(f"Source file not found for {tool_name}: {script_path}")
                failure_count += 1
                continue

            output.print(f"Checking {tool_name}...")

            # Check if update is needed
            current_hash = compute_hash(script_path)
            if current_hash == tool_info["source_hash"]:
                output.verbose(f"No changes detected for {tool_name}")
                continue

            # Update the tool
            options_dict = {
                "name": tool_name,
                "version": tool_info["version"],
                "editable": False,  # Updates don't change editability
                "tempdir": None,
                "python": python,
                "dry_run": False,
                "update": True,
                "quiet": output.level == OutputLevel.QUIET,
            }

            result = install_script_quiet(script_path, options_dict)
            if result == 0:
                success_count += 1
                output.print(f"Updated {tool_name}")
            else:
                failure_count += 1
                output.error(f"Failed to update {tool_name}")

        if failure_count > 0:
            output.print(f"Updated {success_count} tools, {failure_count} failed")
            ctx.exit(1)

        output.print(f"Successfully updated {success_count} tools")
        return 0

    else:
        # Update single tool
        script_path = Path(script)
        if not script_path.exists():
            output.error(f"Script not found: {script_path}")
            return 1

        # Find the installed tool by canonical source path. The command may
        # have been installed with --name and therefore differ from the stem.
        registry = load_registry()
        resolved_source = canonical_source_path(script_path)
        matches = [
            (name, info)
            for name, info in registry.get("scripts", {}).items()
            if canonical_source_path(info["source_path"]) == resolved_source
        ]
        if len(matches) == 1:
            cli_name, existing = matches[0]
        elif len(matches) > 1:
            output.error(f"Multiple installed tools map to {script_path}")
            ctx.exit(1)
        else:
            cli_name, existing = "", None
        if not existing:
            output.error(f"No installed tool found for {script_path}")
            output.error("Use 'uvs install' to install the tool first")
            ctx.exit(1)

        # Check if update is needed
        current_hash = compute_hash(script_path)
        if current_hash == existing["source_hash"]:
            output.print(f"No changes detected for {cli_name}")
            return 0

        # Update the tool
        options_dict = {
            "name": cli_name,
            "version": existing["version"],
            "editable": False,
            "tempdir": None,
            "python": python,
            "dry_run": False,
            "update": True,
            "quiet": output.level == OutputLevel.QUIET,
        }

        result = install_with_progress(script_path, options_dict, output)

        if result == 0:
            output.print(f"Successfully updated {cli_name}")
            # Show new version
            new_version = bump_patch_version(existing["version"])
            output.verbose(f"New version: {new_version}")

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
@click.pass_context
def uninstall(ctx, tool_name, uninstall_all, dry_run, backup, force):
    """Uninstall an installed tool.

    \b
    Examples:
        uvs uninstall my-tool         # Uninstall a specific tool
        uvs uninstall --all           # Uninstall all tools
        uvs uninstall --dry-run tool  # Preview what would be uninstalled
    """
    output = ctx.obj["output"]

    # Check if either tool_name or --all is specified
    if not tool_name and not uninstall_all:
        output.error("Either TOOL_NAME or --all is required")
        ctx.exit(1)

    # Load registry
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
        # Uninstall all tools
        if not force and not dry_run:
            output.print(f"\nTools to uninstall ({len(tools)}):")
            for name, info in tools.items():
                output.print(f"  • {name}  ({info['source_path']})")
            output.print("")
            if not click.confirm(
                f"Are you sure you want to uninstall all {len(tools)} tools?"
            ):
                output.print("Uninstall cancelled")
                return 0

        success_count = 0
        failure_count = 0

        for name, info in tools.items():
            if dry_run:
                output.print(f"Would uninstall: {name} (from {info['source_path']})")
                success_count += 1
                continue

            output.print(f"Uninstalling {name}...")

            # Run uv tool uninstall
            result = run_uv_uninstall(
                name, quiet=output.level == OutputLevel.QUIET
            )

            if result == 0:
                # Verify it's uninstalled
                if verify_tool_uninstalled(name):
                    # Remove from registry
                    if cleanup_registry_entry(name):
                        output.verbose(f"Removed {name} from registry")
                        success_count += 1
                    else:
                        output.error(
                            f"Uninstalled {name} but failed to remove from registry"
                        )
                        failure_count += 1
                else:
                    output.error(f"Failed to verify uninstallation of {name}")
                    failure_count += 1
            else:
                # Check if the tool was already removed outside of uvs
                if verify_tool_uninstalled(name):
                    # Tool is already gone — clean up stale registry entry
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
        elif failure_count > 0:
            output.print(f"Uninstalled {success_count} tools, {failure_count} failed")
            ctx.exit(1)
        else:
            output.print(f"Successfully uninstalled all {success_count} tools")
            return 0

    else:
        # Uninstall single tool
        if tool_name not in tools:
            output.error(f"No tool named '{tool_name}' found in registry")
            ctx.exit(1)

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

        output.print(f"Uninstalling {tool_name}...")

        # Run uv tool uninstall
        result = run_uv_uninstall(
            tool_name, quiet=output.level == OutputLevel.QUIET
        )

        if result == 0:
            # Verify it's uninstalled
            if verify_tool_uninstalled(tool_name):
                # Remove from registry
                if cleanup_registry_entry(tool_name):
                    output.verbose(f"Removed {tool_name} from registry")
                    output.print(f"Successfully uninstalled {tool_name}")
                    return 0
                else:
                    output.error(
                        f"Uninstalled {tool_name} but failed to remove from registry"
                    )
                    ctx.exit(1)
            else:
                output.error(f"Failed to verify uninstallation of {tool_name}")
                ctx.exit(1)
        else:
            # Check if the tool is already uninstalled from uv but still in registry
            if verify_tool_uninstalled(tool_name):
                # Clean up the registry entry
                if cleanup_registry_entry(tool_name):
                    output.verbose(f"Removed {tool_name} from registry")
                    output.print(
                        f"Cleaned up registry entry for {tool_name} (already uninstalled)"
                    )
                    return 0
                else:
                    output.warning(f"Failed to remove {tool_name} from registry")
                    ctx.exit(1)
            else:
                output.error(f"Failed to uninstall {tool_name}")
                ctx.exit(1)


if __name__ == "__main__":
    cli()
