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

### Option 1: Quick Install (Recommended for Users)

Install `uvs` as a command-line tool:

```bash
uv tool install https://github.com/your-repo/uvs.git
```

Now you can use `uvs` directly:

```bash
uvs --help
```

### Option 2: Development Setup

For contributors or those who want to modify `uvs`:

```bash
# Clone this repository
git clone https://github.com/your-repo/uvs.git
cd uvs

# Run the installer directly
uv run scripts/uvs.py --help
```

## Quick Start

1. Create a single-file script with [PEP 723](https://peps.python.org/pep-0723/) inline metadata (see [`uvs-example.py`](uvs-example.py) for an example).

2. Install it as a command-line tool:

```bash
uvs your-script.py
```

3. Use your new command:

```bash
your-script
```

4. Find the source of an installed tool:

```bash
uvs --which your-script
```

## How It Works

`uvs` converts single-file Python scripts into installable packages:

1. **Parse PEP 723 metadata** from the script header
2. **Extract script body** (removing header and `if __name__ == "__main__"` block)
3. **Generate package structure** with `pyproject.toml` and `src/<module>/__init__.py`
4. **Run `uv tool install`** on the generated package
5. **Track installations** in a local registry file

### Registry

Installations are tracked in `.uvs-registry.json` with tool names, source paths, hashes, and versions for reliable updates and management.

### PEP 723 Support

`uvs` reads [PEP 723](https://peps.python.org/pep-0723/) inline script metadata to extract dependency and Python version requirements. The tool supports the standard `requires-python` and `dependencies` fields. If no metadata is present, sensible defaults are used.

### Package Generation

Generated packages follow this structure:
```
my-tool/
├── pyproject.toml    # Project metadata and dependencies
├── README.md         # Installation info
└── src/
    └── my_tool/
        └── __init__.py  # Script body as module
```

## Usage

```bash
uvs [OPTIONS] <script-or-dir>
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
uvs --dry-run example.py

# Install with custom name
uvs --name my-tool example.py

# Update an existing installation
uvs --update example.py

# Install all scripts in a directory
uvs --all ./scripts/

# List all installed scripts
uvs --list
```

## Design Decisions

### Temporary Packages
Packages are generated in temporary directories by default to keep your original scripts as the single source of truth and avoid cluttering your project.

### Local Registry
The `.uvs-registry.json` file is stored in your current directory, making it project-specific and avoiding permission issues.

### Editable Installs Not Recommended
Editable installs have significant limitations - changes to source scripts aren't automatically reflected, and updates require manual reinstallation. Use `--update` instead for iterative development.

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

For contributors or those who want to modify `uvs`:

```bash
# Clone the Repository
git clone https://github.com/your-repo/uvs.git

# place uvs in PATH in editable mode
uv tool install --editable uvs

# verify available
uvs --help

cd uvs
# hack, hack, ...

# Run tests
uv run pytest
```


## Testing

### User-Behavior Focused Test Suite

`uvs` includes a comprehensive end-to-end test suite that focuses on user journeys and observable behavior rather than internal implementation details. This approach ensures reliability by testing complete workflows as users would experience them.

#### What is Tested

**User Journeys & Observable Behavior:**
- Complete installation workflows (single scripts, batch operations, custom names)
- Tool management (listing, showing details, finding sources)
- Update workflows (detecting changes, version bumping, registry updates)
- Error scenarios and edge cases (missing files, malformed scripts, security)
- Configuration management and persistence
- Unicode and large script handling
- Registry backup and recovery

**What is Not Tested:**
- Internal implementation details (parsing logic, package generation internals)
- Unit-level function behavior (except where it affects user experience)
- Performance micro-optimizations

#### Running the Tests

```bash
# Run all tests
uv run pytest

# Run with duration reporting (shows slowest tests)
uv run pytest --durations=10

# Run specific test categories
uv run pytest tests/test_e2e.py -v  # End-to-end tests
uv run pytest tests/test_cli.py -v  # CLI component tests
```

#### Test Execution Improvements

The test suite has been optimized for speed and reliability:

- **Fast Execution**: Uses in-memory registries and mocked subprocess calls to avoid slow I/O operations
- **Deterministic Results**: Controlled test environments prevent flaky tests from external dependencies
- **Comprehensive Coverage**: Tests simulate real user workflows end-to-end while maintaining fast execution
- **Reliable CI/CD**: Tests run consistently across different environments without external dependencies

The current test suite achieves comprehensive coverage of user-facing functionality while maintaining execution times under 30 seconds for the full suite.


## Related Projects

- [uv](https://github.com/astral-sh/uv): The Python package installer and resolver
- [PEP 723](https://peps.python.org/pep-0723/): Inline script metadata
- [pipx](https://pipx.pypa.io/): Install and run Python applications in isolated environments

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## File References

- Installer script: [`src/uvs/uvs.py`](src/uvs/uvs.py)
- Example script: [`uvs-example.py`](uvs-example.py)
- Registry file: [`.uvs-registry.json`](.uvs-registry.json)
- Detailed documentation: [`README.md`](README.md)
- Quick start guide: [`QUICKSTART.md`](QUICKSTART.md)
- Examples: [`examples/`](examples/)
