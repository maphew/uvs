# Plan: Fix Issues for Wider Use

## Context
Assessment identified several issues preventing `uvs` from being ready for wider use. This plan addresses all of them.

## Changes

### 1. Move test dependencies to dev group
**File:** `pyproject.toml`
**Problem:** `pytest` and `pytest-xdist` are in runtime `[project.dependencies]`. Users installing `uvs` as a tool pull in test frameworks unnecessarily.
**Fix:** Move to `[dependency-groups] dev`.

### 2. Remove vestigial PEP 723 header from `uvs.py`
**File:** `src/uvs/uvs.py`
**Problem:** `uvs.py` has a `# /// script` block declaring `requires-python = ">=3.13"` while `pyproject.toml` says `>=3.8`. The header is a leftover from when this was a standalone script — it's a module now.
**Fix:** Delete the `# /// script` / `# ///` block from `uvs.py`.

### 3. Clean up unused/redundant imports
**Files:** `src/uvs/cli.py`
**Problem:** `import ast` at top of `cli.py` is unused. Two inline `import ast` statements inside `install_with_progress()` and `install_script_quiet()` are redundant (ast is already imported in `uvs.py` where it's actually needed).
**Fix:** Remove the unused `import ast` from `cli.py` top-level. Remove the inline `import ast` statements from the two functions.

### 4. Fix `verify_tool_uninstalled()` — broken `--format=json`
**File:** `src/uvs/uvs.py`, `tests/test_uninstall.py`
**Problem:** `uv tool list` has no `--format=json` flag. The function calls a nonexistent option and relies on a fragile fallback (running `tool_name --help`).
**Fix:** Parse the plain text output of `uv tool list`. Tool names appear as `<name> v<version>` lines. Check if the tool name appears. Update all tests in `TestVerifyToolUninstalled` to match the new text-based interface.

### 5. Validate `main()` exists in script before packaging
**File:** `src/uvs/uvs.py` (new function), `src/uvs/cli.py` (call sites)
**Problem:** If a script lacks a `main()` function, `uv tool install` will succeed but the resulting command will crash at runtime. No early feedback.
**Fix:** Add `validate_script_has_main(source: str) -> bool` in `uvs.py` that uses `ast.parse` + AST walk to check for a `main` function definition. Call it in `install_script_quiet()` and `install_with_progress()` before generating the package. Return error code 1 with a clear message if missing. Add tests for this validation.

### 6. Add syntax validation before packaging
**File:** `src/uvs/uvs.py` (new function), `src/uvs/cli.py` (call sites)
**Problem:** Scripts with syntax errors are silently packaged and installed, producing broken tools. The existing `test_batch_install_partial_failure` test expects this to fail but the code doesn't check.
**Fix:** Add `validate_script_syntax(path: Path) -> tuple[bool, str]` that runs `ast.parse()` and returns (ok, error_message). Call before packaging. This also fixes the pre-existing test failure.

### 7. `uvs uninstall --all` — list tools before confirmation
**File:** `src/uvs/cli.py`
**Problem:** The `--all` flag asks "Are you sure you want to uninstall all N tools?" without listing which tools.
**Fix:** Before `click.confirm()`, print each tool name and source path.

### 8. `uvs uninstall --all` — stale registry self-heal
**File:** `src/uvs/cli.py`
**Problem:** During `--all` uninstall, if `run_uv_uninstall` fails (because the tool was already removed outside uvs), the code just reports failure and leaves the stale registry entry.
**Fix:** When `run_uv_uninstall` returns non-zero, call `verify_tool_uninstalled()`. If the tool is actually gone, clean the registry entry with a warning and count as success. (This logic already exists for single-tool uninstall — extend it to the `--all` loop.)

### 9. Remove pytest `addopts` hard-filter
**File:** `pyproject.toml`
**Problem:** `addopts = "-k '...'"` silently excludes all tests not in the allowlist. Running `pytest` gives a false sense of completeness.
**Fix:** Remove the `-k` filter from `addopts` entirely.

## Verification
- `uv run pytest` — all tests pass (including the previously-failing `test_batch_install_partial_failure`)
- No import errors when running `uvs --help`
