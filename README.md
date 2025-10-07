# Quick Start Guide

How to use `uvs` to install single-file Python scripts as command-line tools.

## Prerequisites

- [uv](https://docs.astral.sh/uv/getting-started/installation/) installed and available in your PATH

## Install uvs

Install `uvs` as a command-line tool:

```bash
uv tool install https://github.com/maphew/uvs.git
```

Now you can use `uvs`:

```bash
uvs --help
```

## Your First Installation

Create a script with [PEP 723][pep723] inline metadata [using uv][uv_script] and install it as a tool:

```cmd
> uv init --script uvs-hello.py
Initialized script at `uvs-hello.py`

> uvs install uvs-hello.py
Running: uv tool install C:\...\uvs-_asjfho3\uvs-hello
⠋ Installing...⠋ Resolving dependencies...
Resolved 1 package in 3ms
      Built uvs-hello @ file:///C:/.../uvs-_asjfho3/uvs-hello
Prepared 1 package in 27ms
Installed 1 package in 16ms
 + uvs-hello==0.1.0 (from file:///C:/.../uvs-_asjfho3/uvs-hello)
Installed 1 executable: uvs-hello

╭──────── Installation Complete ───────────╮
│  ✓ Successfully installed uvs-hello      │
│                                          │
│  Source: C:\...\dev\play\uvs-hello.py    │
│  Version: 0.1.0                          │
│  Run 'uvs-hello' to use your new tool    │
╰──────────────────────────────────────────╯

> uvs-hello
Hello from uvs-hello.py!
```

[pep723]:https://peps.python.org/pep-0723/
[uv_script]:https://docs.astral.sh/uv/guides/scripts/#creating-a-python-script



## Managing Installed Tools

```bash
# List tools installed with uvs
# (note: this is different from `uv tool list`) 
> uvs list

Tool Name  Source Path             Version  Installed At       
fgmirror   C:\...\dev\fgmirror.py  0.1.0    2025-10-07T03:00:27

> uvs show fgmirror

                  Tool Details: fgmirror
Property   Value
Name       fgmirror
Source     C:\...\dev\fgmirror.py
Version    0.1.0
Installed  2025-10-07T03:00:27.171189+00:00
Hash       5192febbfb2df230...
```


### Update a Tool

1. Modify your script (e.g., change the print statement in `my-tool.py`)
2. Reinstall with the `--update` flag:

```bash
> uvs update my-tool.py
```

Uvs will detect changes and bump the version automatically.

### Uninstall a Tool

```bash
# one tool
uvs uninstall my-tool

# all uvs tools
uvs uninstall --all

# Preview without actually removing:
uvs uninstall --dry-run my-tool
```

## Usage parameters

```
uvs install --help 
Usage: uvs install [OPTIONS] [SCRIPT]

  Install a script as a CLI tool.

  SCRIPT is the path to the Python script to install. The script should:
  - Contain PEP723 metadata in a comment block
  - Have a main() function that will be called when the tool is executed

  Examples:
      uvs install my-script.py                    # Install with default name
      uvs install --name my-tool script.py        # Custom tool name
      uvs install --all ./scripts/                # Install all scripts in directory
      uvs install --dry-run script.py             # Preview without installing
      uvs install --editable --python 3.11 script.py  # Development install

  PEP723 Metadata Example:
      # /// script
      # requires-python = ">=3.8"
      # dependencies = ["requests", "click"]
      # ///

Options:
  -n, --name TEXT  Override tool name (default: derived from filename)
  --version TEXT   Initial package version (default: 0.1.0)
  -e, --editable   Install in editable mode for development
  --tempdir PATH   Directory for temporary package generation
  --python TEXT    Python version to use for installation (e.g., 3.11)
  --dry-run        Generate package but do not install
  --all            Install all .py files in directory
  --help           Show this message and exit.
```

```
uvs uninstall --help
Usage: uvs uninstall [OPTIONS] [TOOL_NAME]

  Uninstall an installed tool.

  Examples:
      uvs uninstall my-tool         # Uninstall a specific tool
      uvs uninstall --all           # Uninstall all tools
      uvs uninstall --dry-run tool  # Preview what would be uninstalled

Options:
  --all                   Uninstall all installed tools
  --dry-run               Show what would be uninstalled without actually
                          uninstalling
  --backup / --no-backup  Create a backup of the registry before uninstalling
  --force                 Force uninstall without confirmation
  --help                  Show this message and exit.
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
- **[Readme-full](Readme-full.md)** for extended docs and development notes


## Contributors

### v0.1.0

Initial idea, development, quality control, and LLM wrangling: matt wilkie @maphewyk, maphew@gmail.com.

IDE and AI orchestration: Kilo Code

LLM assistants: Claude Sonnet 4.5 (architecture), GLM 4.6 (code backbone), GPT5-Mini (docs), Grok Code Fast 1 (implementation, testing)
