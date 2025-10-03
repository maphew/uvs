# Quick Start Guide

Get up and running with `uvs` in minutes! This guide will walk you through installing single-file Python scripts as command-line tools.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed and available in your PATH

## Option 1: Quick Install (Recommended for Users)

Install `uvs` as a command-line tool:

```bash
uv tool install https://github.com/maphew/uvs.git
```

Now you can use `uvs` directly:

```bash
uvs --help
```

## Option 2: Development Setup

For contributors or those who want to modify `uvs`:

```bash
# Clone the Repository
git clone https://github.com/your-repo/uvs.git

# place in PATH in editable mode
uv tool install --editable uvs

# verify available
uvs --help

# start hacking
cd uvs
# ...etc.
```

## Your First Installation

### 1. Create a Simple Script

Create a file named `my-tool.py` with [PEP 723](https://peps.python.org/pep-0723/) inline metadata.

### 2. Install Your Script

```bash
uvs my-tool.py
```

You should see output similar to:

```
Generated package at: /tmp/uvs-abc123/my-tool
Running: uv tool install /tmp/uvs-abc123/my-tool
Installed 'my-tool' from /path/to/my-tool.py
```

### 3. Use Your New Command

```bash
my-tool
```

Output:
```
Hello from my tool!
```

## Working with Dependencies

### 1. Create a Script with Dependencies

Create a file named `api-check.py` with [PEP 723](https://peps.python.org/pep-0723/) inline metadata including `requests` as a dependency.

### 2. Install the Script

```bash
uvs api-check.py
```

### 3. Use the Tool

```bash
api-check
```

## Managing Installed Tools

### List All Installed Tools

```bash
uvs --list
```

Output:
```
my-tool      <- /path/to/my-tool.py (version: 0.1.0)
api-check    <- /path/to/api-check.py (version: 0.1.0)
```

### Find the Source of a Tool

```bash
uvs --which my-tool
```

Output:
```
/path/to/my-tool.py
```

### Update a Tool

1. Modify your script (e.g., change the print statement in `my-tool.py`)
2. Reinstall with the `--update` flag:

```bash
uvs --update my-tool.py
```

The tool will detect changes and bump the version automatically.

### Uninstall a Tool

```bash
uv tool uninstall my-tool
```

## Advanced Usage

### Custom Tool Name

Override the default tool name:

```bash
uvs --name awesome-tool my-tool.py
```

Now you can run it as:
```bash
awesome-tool
```

### Batch Installation

Install all Python scripts in a directory:

```bash
uvs --all ./scripts/
```

### Dry Run

Inspect the generated package without installing:

```bash
uvs --dry-run my-tool.py
```

## Common Workflows

### Workflow 1: Developing a Script

1. Create your script with [PEP 723](https://peps.python.org/pep-0723/) inline metadata
2. Test it directly: `uv run my-script.py`
3. Install it: `uvs my-script.py`
4. Test the installed command: `my-script`
5. Iterate: make changes, then `uvs --update my-script.py`

### Workflow 2: Sharing a Script

1. Create your script with comprehensive [PEP 723](https://peps.python.org/pep-0723/) metadata
2. Test it thoroughly
3. Share the script file with others
4. Others can install it with: `uvs path/to/script.py`

### Workflow 3: Managing a Collection

1. Organize scripts in a directory
2. Use `--all` to install all at once
3. Use `--list` to see what's installed
4. Use `--which` to find sources when needed

## Troubleshooting

### "uv: command not found"

Install uv following the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).

### "Script not found"

Check that the script path is correct:
```bash
ls -la my-script.py
```

### "uv tool install failed"

1. Check that your script has a `main()` function
2. Verify all dependencies are correctly specified in the [PEP 723](https://peps.python.org/pep-0723/) metadata
3. Use `--dry-run` to inspect the generated package

### "Permission denied"

Check write permissions for the current directory (needed for the registry file):
```bash
ls -la .uvs-registry.json
```

## Next Steps

- Explore the [examples directory](examples/) for more complex scripts
- Read the [main documentation](README.md) for advanced features
- Check the [installer documentation](scripts/README.md) for detailed options
