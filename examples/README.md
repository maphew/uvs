# Examples for uvs

This directory contains example scripts that demonstrate various features and use cases for `uvs`.

## Examples

### 1. complex-cli.py

A sophisticated command-line tool that demonstrates how to create a full-featured CLI application as a single file.

**Features:**
- Multiple subcommands with Click
- API integration with requests
- Rich terminal output with tables and progress bars
- Error handling and user feedback
- JSON processing and formatting

**Dependencies:**
- `requests>=2.25.0` - HTTP client library
- `click>=8.0.0` - Command-line interface framework
- `rich>=10.0.0` - Rich text and beautiful formatting

**Installation:**
```bash
uv run ../scripts/uvs.py examples/complex-cli.py
```

**Usage:**
```bash
# Fetch JSON from an API
complex-cli fetch https://api.github.com/users/python

# Show GitHub repositories for a user
complex-cli github python --limit 5

# Search PyPI packages
complex-cli search requests

# Display system information
complex-cli info
```

### 2. advanced-pep723.py

Demonstrates comprehensive PEP723 metadata usage and advanced features in a single-file script.

**Features:**
- Comprehensive PEP723 metadata (authors, classifiers, extras, etc.)
- Pydantic models for data validation
- HTTP client with httpx
- Modern CLI with Typer
- Rich terminal output
- Metadata introspection

**Dependencies:**
- `pydantic>=2.0.0` - Data validation using Python type annotations
- `httpx>=0.24.0` - Modern HTTP client
- `typer>=0.9.0` - Modern CLI framework

**Recommended Dependencies:**
- `rich>=13.0.0` - Rich text and beautiful formatting
- `ipython>=8.0.0` - Enhanced interactive Python shell

**Development Extras:**
- `pytest>=7.0.0` - Testing framework
- `black>=23.0.0` - Code formatter
- `mypy>=1.0.0` - Static type checker

**Installation:**
```bash
uv run ../scripts/uvs.py examples/advanced-pep723.py
```

**Usage:**
```bash
# Display script information and metadata
advanced-pep723 info

# Fetch data from a URL
advanced-pep723 fetch https://api.github.com/users/python

# Demonstrate Pydantic validation
advanced-pep723 demo

# Display all PEP723 metadata
advanced-pep723 metadata
```

## Installing Examples

To install any of these examples:

1. Navigate to the project root directory
2. Run the installer with the example script path:
   ```bash
   uv run scripts/uvs.py examples/complex-cli.py
   ```
3. The tool will be available in your PATH with the same name as the script (with underscores converted to hyphens)

## Uninstalling Examples

To remove an installed example using uvs:
```bash
uvs uninstall complex-cli
uvs uninstall advanced-pep723
```

You can also uninstall all examples at once:
```bash
uvs uninstall --all
```

For a preview of what would be uninstalled:
```bash
uvs uninstall --dry-run complex-cli
```

## Finding Installed Tools

To see which tools you've installed from examples:
```bash
uv run scripts/uvs.py --list
```

To find the source of a specific tool:
```bash
uv run scripts/uvs.py --which complex-cli
```

## Creating Your Own Scripts

When creating your own scripts based on these examples:

1. Start with the PEP723 header to specify dependencies
2. Include a `main()` function as the entry point
3. Use appropriate CLI frameworks (Click, Typer, argparse) for command-line interfaces
4. Add proper error handling and user feedback
5. Include docstrings and comments for maintainability

### Basic Script Template

```python
# /// script
# requires-python = ">=3.8"
# dependencies = ["click"]
# ///

"""Your script description here."""

import click

@click.command()
def main():
    """Main entry point for your script."""
    click.echo("Hello from your script!")

if __name__ == "__main__":
    main()
```

See [PEP 723](https://peps.python.org/pep-0723/) for complete inline metadata specification.

## Best Practices

1. **Dependency Management**: Specify exact or minimum versions for dependencies
2. **Error Handling**: Provide clear error messages and appropriate exit codes
3. **Documentation**: Include docstrings and comments
4. **Testing**: Test your script before installing it
5. **Versioning**: Use semantic versioning for your scripts
6. **Metadata**: Include comprehensive PEP723 metadata for better discoverability

## Troubleshooting

If you encounter issues with the examples:

1. Check that you have the latest version of `uv` installed
2. Ensure all dependencies in the PEP723 header are available
3. Use `--dry-run` to inspect the generated package before installation
4. Check the `.uvs-registry.json` file for installation records
5. Use `uv tool list` to see what tools are currently installed

## Contributing

To contribute new examples:

1. Create a new script in this directory
2. Add comprehensive documentation to this README
3. Include a PEP723 header with all necessary dependencies
4. Test the script thoroughly
5. Submit a pull request with your example