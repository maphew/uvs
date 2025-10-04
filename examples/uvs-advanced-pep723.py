# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "pydantic>=2.0.0",
#     "httpx>=0.24.0",
#     "typer>=0.9.0"
# ]
# extras = {
#     "dev": [
#         "pytest>=7.0.0",
#         "black>=23.0.0",
#         "mypy>=1.0.0"
#     ]
# }
# license = {text = "MIT"}
# authors = [
#     {name = "Example Author", email = "author@example.com"}
# ]
# keywords = ["example", "pep723", "advanced"]
# classifiers = [
#     "Development Status :: 4 - Beta",
#     "Intended Audience :: Developers",
#     "License :: OSI Approved :: MIT License",
#     "Programming Language :: Python :: 3",
#     "Programming Language :: Python :: 3.9",
#     "Programming Language :: Python :: 3.10",
#     "Programming Language :: Python :: 3.11",
#     "Programming Language :: Python :: 3.12"
# ]
# readme = {file = "README.md", content-type = "text/markdown"}
# ///

"""
Advanced PEP723 script demonstrating comprehensive metadata usage.

This script showcases various PEP723 metadata fields and advanced features
that can be used in single-file scripts.
"""

import sys
from typing import Optional
from datetime import datetime

import httpx
import pydantic
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

# Create Typer app
app = typer.Typer(
    name="advanced-pep723",
    help="Advanced PEP723 script with comprehensive metadata",
    add_completion=False
)

# Rich console for pretty output
console = Console()


class UserModel(pydantic.BaseModel):
    """User model using Pydantic for validation."""
    id: int
    name: str
    email: str
    created_at: datetime
    is_active: bool = True


class APIResponse(pydantic.BaseModel):
    """API response model."""
    success: bool
    data: dict
    message: Optional[str] = None


@app.command()
def info():
    """Display script metadata and environment information."""
    # Create a table with script information
    table = Table(title="Script Information")
    table.add_column("Property", style="cyan")
    table.add_column("Value", style="green")
    
    # Add script metadata
    table.add_row("Name", "Advanced PEP723 Example")
    table.add_row("Description", "Demonstrates comprehensive PEP723 metadata")
    table.add_row("License", "MIT")
    table.add_row("Python Version", sys.version.split()[0])
    table.add_row("Pydantic Version", pydantic.VERSION)
    
    console.print(table)
    
    # Display additional information in a panel
    metadata_info = """
    This script demonstrates advanced PEP723 features including:
    - Multiple dependencies with version constraints
    - Recommended dependencies for enhanced features
    - Optional extras for development
    - Comprehensive project metadata
    - Author and classifier information
    - URLs for repository, docs, etc.
    """
    console.print(Panel(metadata_info, title="PEP723 Features", border_style="blue"))


@app.command()
def fetch(
    url: str = typer.Argument(..., help="URL to fetch data from"),
    timeout: int = typer.Option(10, help="Request timeout in seconds"),
    validate: bool = typer.Option(True, help="Validate response as JSON")
):
    """Fetch data from a URL and display it."""
    console.print(f"Fetching data from: {url}")
    
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.get(url)
            response.raise_for_status()
            
            if validate:
                try:
                    data = response.json()
                    console.print(Panel(
                        f"Response type: {type(data).__name__}\nKeys: {list(data.keys()) if isinstance(data, dict) else 'N/A'}",
                        title="Response Validation",
                        border_style="green"
                    ))
                except Exception:
                    console.print("[yellow]Warning: Response is not valid JSON[/yellow]")
                    console.print(f"Response length: {len(response.text)} characters")
            else:
                console.print(f"Response length: {len(response.text)} characters")
                
    except httpx.HTTPError as e:
        console.print(f"[red]HTTP Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)


@app.command()
def demo():
    """Demonstrate Pydantic model validation."""
    # Create valid user
    user_data = {
        "id": 1,
        "name": "John Doe",
        "email": "john@example.com",
        "created_at": datetime.now(),
        "is_active": True
    }
    
    try:
        user = UserModel(**user_data)
        console.print(Panel(
            f"Created valid user:\n{user.model_dump_json(indent=2)}",
            title="Pydantic Validation",
            border_style="green"
        ))
    except pydantic.ValidationError as e:
        console.print(f"[red]Validation error: {e}[/red]")
    
    # Try to create invalid user
    invalid_data = {
        "id": "invalid",  # Should be int
        "name": "Jane Doe",
        "email": "jane@example.com",
        "created_at": "2023-01-01",  # Should be datetime
    }
    
    try:
        user = UserModel(**invalid_data)
    except pydantic.ValidationError as e:
        console.print(Panel(
            f"Expected validation error:\n{str(e)}",
            title="Validation Error (Expected)",
            border_style="yellow"
        ))


@app.command()
def metadata():
    """Display all PEP723 metadata from this script."""
    import ast
    import re
    
    # Read the script file
    script_path = __file__
    with open(script_path, 'r') as f:
        content = f.read()
    
    # Extract PEP723 metadata
    header_match = re.search(r'# /// script\n(.*?)\n# ///', content, re.DOTALL)
    if not header_match:
        console.print("[red]No PEP723 header found[/red]")
        return
    
    header_content = header_match.group(1)
    
    # Parse the header
    metadata = {}
    for line in header_content.split('\n'):
        line = line.strip().lstrip('# ')
        if not line or not line.startswith('#'):
            continue
        
        # Remove the leading #
        line = line[1:].strip()
        
        # Parse key-value pairs
        if '=' in line:
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip()
            
            try:
                # Try to evaluate as Python literal
                metadata[key] = ast.literal_eval(value)
            except Exception:
                # If that fails, keep as string
                metadata[key] = value
    
    # Display metadata in a table
    table = Table(title="PEP723 Metadata")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")
    
    for key, value in metadata.items():
        if isinstance(value, (list, dict)):
            value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
        else:
            value_str = str(value)
        table.add_row(key, value_str)
    
    console.print(table)


def main():
    """Entry point for the script."""
    app()


if __name__ == "__main__":
    main()