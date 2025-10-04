# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "requests>=2.25.0",
#     "click>=8.0.0",
#     "rich>=10.0.0"
# ]
# ///

"""
A complex CLI tool that demonstrates advanced features of single-file scripts.

This tool provides various utilities for working with web APIs and formatting output.
"""

import json
import sys
from typing import Optional

import click
import requests
import rich
import importlib.metadata
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def fetch_json(url: str) -> dict:
    """Fetch JSON data from a URL with error handling."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        console.print(f"[red]Error fetching data: {e}[/red]")
        sys.exit(1)


def format_size(size_bytes: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


@click.group()
@click.version_option(version="1.0.0", prog_name="complex-cli")
def cli():
    """A complex CLI tool demonstrating advanced single-file script features."""
    pass


@cli.command()
@click.argument('url')
@click.option('--output', '-o', type=click.Path(), help="Save output to file")
@click.option('--indent', '-i', default=2, help="JSON indentation level")
def fetch(url: str, output: Optional[str], indent: int):
    """Fetch JSON from a URL and display it."""
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task(f"Fetching {url}...", total=None)
        data = fetch_json(url)
        progress.update(task, completed=True)

    json_str = json.dumps(data, indent=indent)
    
    if output:
        with open(output, 'w') as f:
            f.write(json_str)
        console.print(f"[green]Data saved to {output}[/green]")
    else:
        console.print(Panel(json_str, title="JSON Response", border_style="blue"))


@cli.command()
@click.argument('username')
@click.option('--limit', '-l', default=10, help="Maximum number of repositories")
def github(username: str, limit: int):
    """Show GitHub repositories for a user."""
    url = f"https://api.github.com/users/{username}/repos"
    repos = fetch_json(url)
    
    table = Table(title=f"GitHub repositories for {username}")
    table.add_column("Name", style="cyan", no_wrap=True)
    table.add_column("Stars", style="magenta")
    table.add_column("Language", style="green")
    table.add_column("Size", style="blue")
    table.add_column("Updated", style="yellow")
    
    for repo in repos[:limit]:
        table.add_row(
            repo['name'],
            str(repo['stargazers_count']),
            repo['language'] or 'N/A',
            format_size(repo['size']),
            repo['updated_at'][:10]
        )
    
    console.print(table)


@cli.command()
@click.argument('query')
@click.option('--count', '-c', default=10, help="Number of results to show")
def search(query: str, count: int):
    """Search for packages on PyPI."""
    url = f"https://pypi.org/pypi/{query}/json"
    
    try:
        data = fetch_json(url)
        releases = data.get('releases', {})
        
        table = Table(title=f"PyPI package: {query}")
        table.add_column("Version", style="cyan")
        table.add_column("Upload Date", style="green")
        table.add_column("Python Versions", style="yellow")
        
        versions = sorted(releases.keys(), reverse=True)[:count]
        for version in versions:
            release_info = releases[version][0] if releases[version] else {}
            upload_date = release_info.get('upload_time', 'N/A')[:10]
            py_versions = ', '.join(release_info.get('requires_python', 'N/A').split(','))
            
            table.add_row(version, upload_date, py_versions)
        
        console.print(table)
    except Exception:
        # Fallback to search API
        search_url = f"https://pypi.org/search/?q={query}"
        console.print(f"[yellow]Package info not found. Try searching at: {search_url}[/yellow]")


@cli.command()
@click.option('--width', '-w', default=80, help="Terminal width")
def info(width: int):
    """Display system and tool information."""
    import platform
    import sys
    
    info_data = [
        ("System", f"{platform.system()} {platform.release()}"),
        ("Python", f"{sys.version.split()[0]}"),
        ("Terminal Width", str(width)),
        ("Requests", requests.__version__),
        ("Click", importlib.metadata.version("click")),
        ("Rich", importlib.metadata.version("rich")),
    ]
    
    table = Table(title="System Information")
    table.add_column("Component", style="cyan")
    table.add_column("Version", style="green")
    
    for component, version in info_data:
        table.add_row(component, version)
    
    console.print(table)


def main():
    """Entry point for the CLI tool."""
    cli()


if __name__ == "__main__":
    main()