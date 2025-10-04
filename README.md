# Quick Start Guide

How to use `uvs` to install single-file Python scripts as command-line tools.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed and available in your PATH

## Install

Install `uvs` as a command-line tool:

```bash
uv tool install https://github.com/maphew/uvs.git
```

Now you can use `uvs` directly:

```bash
uvs --help
```

## Your First Installation

### 1. Create a Simple Script

Create a file named `my-tool.py` with [PEP 723](https://peps.python.org/pep-0723/) inline metadata (see https://docs.astral.sh/uv/guides/scripts/#creating-a-python-script)

### 2. Install Your Script

```bash
uvs install my-tool.py
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
uvs uninstall my-tool
```

You can also uninstall all tools at once:

```bash
uvs uninstall --all
```

For a preview of what would be uninstalled without actually removing it:

```bash
uvs uninstall --dry-run my-tool
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

### Developing a Script

1. Create your script with inline script metadata
2. Test it directly: `uv run my-script.py`
3. Install it: `uvs my-script.py`
4. Test the installed command: `my-script`
5. Iterate: make changes, then `uvs --update my-script.py`

### Managing a Collection

1. Organize scripts in a directory
2. Use `--all` to install all at once
3. Use `--list` to see what's installed
4. Use `--which` to find sources when needed


## Troubleshooting

### "uv: command not found"

Install uv following the [official installation guide](https://docs.astral.sh/uv/getting-started/installation/).


### "uv tool install failed"

1. Check that your script has a `main()` function
2. Verify all dependencies are correctly specified in the [PEP 723](https://peps.python.org/pep-0723/) metadata
3. Verify script executes properly with `uv run myscript.py`
4. Use `uvs --dry-run` to inspect the generated package


### "Tool not found" during uninstall

1. Check the tool name with `uvs --list`
2. Verify the tool was installed with uvs (not directly with uv)
3. Use `uv tool list` to see all tools installed with uv


### "Failed to uninstall tool"

1. Check if the tool is still in use by another process
2. Try running with `--force` flag to skip confirmation
3. Use `uv tool list` to verify the tool exists in uv's registry
4. Use `uvs uninstall --dry-run tool-name` to preview what would be removed


## Next Steps

- Explore the [examples directory](examples/) for more complex scripts
- [Readme-full](Readme-full.md) for extended docs and development notes


## Contributors

### v0.1.0

Initial idea, development, quality control, and LLM wrangling: matt wilkie @maphewyk, maphew@gmail.com.

IDE and AI orchestration: Kilo Code

LLM assistants: Claude Sonnet 4.5 (architecture), GLM 4.6 (code backbone), GPT5-Mini (docs), Grok Code Fast 1 (implementation, testing)
