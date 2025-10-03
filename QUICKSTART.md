# Quick Start Guide

Get up and running with `uvs` in minutes! This guide will walk you through installing single-file Python scripts as command-line tools.

## Prerequisites

- Python 3.8 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed and available in your PATH

## Installation Steps

### 1. Clone or Download the Project

```bash
git clone https://github.com/your-repo/uvs.git
cd uvs
```

### 2. Verify the Installer Works

```bash
uv run scripts/uvs.py --help
```

You should see the help output showing all available options.

## Your First Installation

### 1. Create a Simple Script

Create a file named `my-tool.py` with the following content:

```python
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///

def main():
    print("Hello from my tool!")

if __name__ == "__main__":
    main()
```

### 2. Install Your Script

```bash
uv run scripts/uvs.py my-tool.py
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

Create a file named `api-check.py` with the following content:

```python
# /// script
# requires-python = ">=3.8"
# dependencies = ["requests"]
# ///

import requests
import sys

def main():
    try:
        response = requests.get("https://httpbin.org/json", timeout=5)
        print(f"Status: {response.status_code}")
        print(f"Response: {response.json()}")
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
```

### 2. Install the Script

```bash
uv run scripts/uvs.py api-check.py
```

### 3. Use the Tool

```bash
api-check
```

## Managing Installed Tools

### List All Installed Tools

```bash
uv run scripts/uvs.py --list
```

Output:
```
my-tool      <- /path/to/my-tool.py (version: 0.1.0)
api-check    <- /path/to/api-check.py (version: 0.1.0)
```

### Find the Source of a Tool

```bash
uv run scripts/uvs.py --which my-tool
```

Output:
```
/path/to/my-tool.py
```

### Update a Tool

1. Modify your script (e.g., change the print statement in `my-tool.py`)
2. Reinstall with the `--update` flag:

```bash
uv run scripts/uvs.py --update my-tool.py
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
uv run scripts/uvs.py --name awesome-tool my-tool.py
```

Now you can run it as:
```bash
awesome-tool
```

### Batch Installation

Install all Python scripts in a directory:

```bash
uv run scripts/uvs.py --all ./scripts/
```

### Dry Run

Inspect the generated package without installing:

```bash
uv run scripts/uvs.py --dry-run my-tool.py
```

## Common Workflows

### Workflow 1: Developing a Script

1. Create your script with PEP723 header
2. Test it directly: `uv run my-script.py`
3. Install it: `uv run scripts/uvs.py my-script.py`
4. Test the installed command: `my-script`
5. Iterate: make changes, then `uv run scripts/uvs.py --update my-script.py`

### Workflow 2: Sharing a Script

1. Create your script with comprehensive PEP723 metadata
2. Test it thoroughly
3. Share the script file with others
4. Others can install it with: `uv run scripts/uvs.py path/to/script.py`

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
2. Verify all dependencies are correctly specified in the PEP723 header
3. Use `--dry-run` to inspect the generated package

### "Permission denied"

Check write permissions for the current directory (needed for the registry file):
```bash
ls -la .uv-scripts-registry.json
```

## Next Steps

- Explore the [examples directory](examples/) for more complex scripts
- Read the [main documentation](README.md) for advanced features
- Check the [installer documentation](scripts/README.md) for detailed options

## Copy-Paste Ready Commands

```bash
# Install the installer (clone the repo first)
git clone https://github.com/your-repo/uvs.git
cd uvs

# Create and install a simple script
cat > hello.py << 'EOF'
# /// script
# requires-python = ">=3.8"
# dependencies = []
# ///

def main():
    print("Hello from uvs!")

if __name__ == "__main__":
    main()
EOF

uv run scripts/uvs.py hello.py
hello

# List installed tools
uv run scripts/uvs.py --list

# Find source of a tool
uv run scripts/uvs.py --which hello

# Update the tool
uv run scripts/uvs.py --update hello.py

# Uninstall the tool
uv tool uninstall hello