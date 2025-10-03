# Migration Guide: From uv-experiments/uv-script-install to uvs

This document explains the rebranding and migration from the previous project names (`uv-experiments` and `uv-script-install`) to the new unified name `uvs`.

## What Changed

### Project Name
- **Old**: `uv-experiments` and `uv-script-install`
- **New**: `uvs`

### Tool Name
- **Old**: `uv-script-install`
- **New**: `uvs`

### File Names
- **Old**: `uv-script-install.py` (installer script)
- **New**: `uvs.py` (installer script)

### Command Names
- **Old**: `uv-script-install <script.py>`
- **New**: `uvs <script.py>`

### Package Names
- **Old**: Generated packages used `uv-script-install` metadata
- **New**: Generated packages use `uvs` metadata in `[tool.uvs]` section

### Registry File
- **Old**: `.uv-scripts-registry.json` (same filename)
- **New**: Same filename, but updated metadata structure with `uvs` generator information

## Migration Steps for Users

### Step 1: Uninstall Old Tools
If you have any tools installed with the old `uv-script-install` tool, uninstall them first:

```bash
# List currently installed tools
uv tool list

# Uninstall any tools that were installed with uv-script-install
uv tool uninstall <old-tool-name>
```

### Step 2: Remove Old Registry (Optional)
The old registry file (if it exists) can be safely removed or renamed:

```bash
# Check if old registry exists
ls -la .uv-scripts-registry.json

# Remove or backup the old registry
rm .uv-scripts-registry.json  # or mv .uv-scripts-registry.json .uv-scripts-registry.json.backup
```

### Step 3: Install the New Tool
Install scripts using the new `uvs` tool:

```bash
# For a single script
python3 scripts/uvs.py your-script.py

# For all scripts in a directory
python3 scripts/uvs.py --all ./scripts/
```

### Step 4: Update Any Automation/Scripts
Update any scripts, Makefiles, or automation that referenced the old tool:

```bash
# Old command
uv-script-install script.py

# New command
uvs script.py
```

### Step 5: Verify Installation
Check that your tools are working with the new system:

```bash
# List installed scripts
python3 scripts/uvs.py --list

# Find source of installed tool
python3 scripts/uvs.py --which <tool-name>

# Test the tool works
<tool-name> --help
```

## Backward Compatibility Notes

### No Automatic Migration
- **No aliases**: The old command names (`uv-script-install`) are not available
- **No automatic registry migration**: Old registry files are not automatically converted
- **No backward compatibility**: Old installations must be manually reinstalled

### Registry Compatibility
- The registry file format has been updated with new metadata fields
- Old registry files will not be read by the new tool
- You can safely delete old registry files without data loss

### Package Metadata
- Previously installed packages will continue to work normally
- `uv tool uninstall` works the same for both old and new packages
- No changes needed for already installed tools

## Breaking Changes

### Command Line Interface
- **Breaking**: `uv-script-install` command no longer exists
- **Breaking**: All command-line flags and options have been renamed to use `uvs`
- **Breaking**: Registry query commands (`--list`, `--which`) now use `uvs` prefix

### Registry File
- **Breaking**: Old registry files are not compatible with the new tool
- **Breaking**: Registry metadata structure has changed (new generator field, updated timestamps)

### Package Generation
- **Breaking**: Generated packages now include `[tool.uvs]` metadata section instead of `[tool.uv-script-install]`
- **Breaking**: Package names and metadata reflect the new `uvs` branding

### Installation Process
- **Breaking**: The installer script filename changed from `uv-script-install.py` to `uvs.py`
- **Non-breaking**: The core functionality (PEP723 parsing, package generation, uv tool installation) works identically

## Troubleshooting Migration Issues

### "Command not found" Errors
If you get "uv-script-install: command not found":
1. Use the new command: `uvs`
2. Update any scripts or aliases that reference the old command

### Registry Issues
If you encounter registry-related errors:
1. Delete the old registry file: `rm .uv-scripts-registry.json`
2. Reinstall your scripts with the new tool
3. The new registry will be created automatically

### Tool Not Working After Migration
If a tool doesn't work after migration:
1. Check if it was installed with the old tool: `uv tool list`
2. Uninstall the old version: `uv tool uninstall <tool-name>`
3. Reinstall with the new tool: `uvs <script.py>`

### Permission Issues
If you encounter permission errors during migration:
1. Ensure you have write permissions in the current directory (for registry)
2. Use `sudo` if installing system-wide tools (though this is not recommended)
3. Check that `uv` is properly installed and accessible

## Timeline

- **Previous versions**: Used `uv-experiments` and `uv-script-install` names
- **Current version**: Unified under `uvs` branding
- **Migration required**: Yes, manual migration needed for existing users
- **Support**: Old versions are no longer maintained

## Need Help?

If you encounter issues during migration:

1. Check the troubleshooting section above
2. Review the main documentation: [`README.md`](README.md:1)
3. See the quick start guide: [`QUICKSTART.md`](QUICKSTART.md:1)
4. Check the detailed installer docs: [`scripts/README.md`](scripts/README.md:1)

The new `uvs` tool provides the same functionality as the previous tools, with improved documentation and a cleaner, more maintainable codebase.