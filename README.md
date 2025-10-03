# uvs: Install Single-File Python Scripts as CLI Tools

A utility that transforms single-file PEP723-style Python scripts into installable packages using `uv tool install`, making them available as command-line tools.

## Overview

`uvs` bridges the gap between single-file Python scripts and the standard Python packaging ecosystem. It allows you to:

- Convert self-contained single-file scripts into proper Python packages
- Install them as command-line tools using `uv tool install`
- Maintain a registry linking installed tools back to their source files
- Update installed tools when their source changes

This is particularly useful for developers who prefer the simplicity of single-file scripts but want the convenience of standard tool installation and management.

## Problem Statement

While `uv` provides excellent tool management for traditional Python packages, it doesn't directly support installing single-file scripts as tools. The naive approach of `uv tool install --script foobar.py` doesn't work because `uv` expects a proper package structure.

`uvs` solves this by automatically generating the necessary package structure from a single-file script and then using `uv tool install` to install it.

## Installation

### Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed and available in your PATH

### Installing the Installer

The installer itself is a PEP723 script, so you can run it directly with `uv run`:

```bash
# Clone this repository
git clone https://github.com/your-repo/uvs.git
cd uvs

# The installer is ready to use with uv run
uv run scripts/uvs.py --help
```

## Quick Start

1. Create a single-file script with [PEP 723](https://peps.python.org/pep-0723/) inline metadata (see [`uvs-example.py`](uvs-example.py) for an example).

2. Install it as a command-line tool:

```bash
uv run scripts/uvs.py your-script.py
```

3. Use your new command:

```bash
your-script
```

4. Find the source of an installed tool:

```bash
uv run scripts/uvs.py --which your-script
```

## Architecture

The tool works by:

1. Parsing the PEP723 header from the source script
2. Extracting the script body (removing the header and `if __name__ == "__main__"` block)
3. Generating a temporary package structure with:
   - `pyproject.toml` with project metadata
   - `src/<module>/__init__.py` containing the script body
   - `README.md` with installation information
4. Running `uv tool install` on the generated package
5. Recording the installation in a local registry file

### Registry

The tool maintains a registry in `.uv-scripts-registry.json` that tracks:
- Tool name and source file path
- Source file hash for change detection
- Installation timestamp and version
- Metadata for updates and uninstalls

## Usage

```bash
uv run scripts/uvs.py [OPTIONS] <script-or-dir>
```

### Options

- `--dry-run`: Generate the package but don't install it
- `--editable`: Attempt an editable install (limited functionality)
- `--all`: Install all `.py` files in a directory
- `--list`: List all registered scripts
- `--which <tool>`: Show source path for an installed tool
- `--update`: Update an installed tool if the source changed
- `--name <name>`: Override the derived tool name
- `--version <version>`: Set the initial package version
- `--tempdir <path>`: Specify where to generate the package
- `--python <specifier>`: Select Python version for installation

### Examples

```bash
# Dry run to inspect generated package
uv run scripts/uvs.py --dry-run example.py

# Install with custom name
uv run scripts/uvs.py --name my-tool example.py

# Update an existing installation
uv run scripts/uvs.py --update example.py

# Install all scripts in a directory
uv run scripts/uvs.py --all ./scripts/

# List all installed scripts
uv run scripts/uvs.py --list
```

## Design Decisions

### Temporary Package Generation

The tool generates packages in a temporary directory by default. This approach:
- Keeps the original script as the single source of truth
- Avoids polluting the project directory with generated files
- Simplifies the workflow for script authors

### Registry Location

The registry is stored in the current working directory as `.uv-scripts-registry.json`. This:
- Makes the registry project-local
- Allows different projects to maintain separate registries
- Simplifies permissions and access control

### Editable Install Limitations

Editable installs have significant limitations:
- Changes to the source script are not automatically reflected
- The installed tool points to the generated package, not the original script
- Updates require re-running the installer

For these reasons, editable installs are not recommended for most use cases.

## Troubleshooting

### Common Issues

1. **"Script not found"**
   - Check that the script path is correct
   - Use absolute paths if running from a different directory

2. **"uv tool install failed"**
   - Ensure `uv` is installed and in your PATH
   - Check that the script has a proper `main()` function
   - Verify the `requires-python` specification matches your environment

3. **"Permission denied"**
   - Check write permissions for the current directory (for the registry)
   - Use `--tempdir` to specify a writable location for package generation

4. **"Module not found" after installation**
   - Ensure all dependencies are listed in the PEP723 header
   - Check that the script exposes a `main()` function

### Getting Help

- Use `--dry-run` to inspect generated packages without installing
- Check the registry file to see what's been installed
- Use `uv tool list` to see what `uv` has installed

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Update documentation as needed
5. Submit a pull request

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-repo/uvs.git
cd uvs

# Run the installer directly
uv run scripts/uvs.py --help

# Run tests (if available)
uv run pytest tests/
```

## Related Projects

- [uv](https://github.com/astral-sh/uv): The Python package installer and resolver
- [PEP 723](https://peps.python.org/pep-0723/): Inline script metadata
- [pipx](https://pipx.pypa.io/): Install and run Python applications in isolated environments

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## File References

- Installer script: [`scripts/uvs.py`](scripts/uvs.py)
- Example script: [`uvs-example.py`](uvs-example.py)
- Registry file: [`.uvs-registry.json`](.uvs-registry.json)
- Detailed documentation: [`scripts/README.md`](scripts/README.md)
- Quick start guide: [`QUICKSTART.md`](QUICKSTART.md)
- Examples: [`examples/`](examples/)
