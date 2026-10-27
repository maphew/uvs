# Changelog

This project is published on PyPI as
[`uvs-cli`](https://pypi.org/project/uvs-cli/), because the PyPI project `uvs`
is an unrelated tool. The installed command is `uvs`.

## Unreleased

- Replace tracebacks with actionable errors for directory arguments, a missing
  `uv` executable, and unsupported registry versions.
- Guard destructive actions: `uninstall --all` now rejects a tool name,
  `install` refuses to replace an existing tool without `--force`, and forced
  reinstalls preserve the recorded version unless `--version` is explicit.
- Record editable mode, package directory, requested Python, dependencies, and
  `requires-python` in the registry so `uvs update` preserves them instead of
  silently converting editable installs to snapshots.
- Accept a tracked tool name (or a source path) in `uvs update`, add
  `--dry-run`, and report up-to-date/missing-source counts accurately.
- Keep `list`/`show`/JSON output under `--quiet`, honor `NO_COLOR` and
  `TERM=dumb` (including bold text), demote internal `uv` invocations to
  `--verbose`, and use compact UTC timestamps in tables.
- Explain command-name normalization (for example `my_tool` to `my-tool`)
  instead of changing it silently.
- Add `uvs list --check`, a `Status` row in `uvs show`, `uvs doctor`,
  `uvs prune`, and `uvs backup list|restore` with backup retention.
- Show the canonical source path and a PATH warning in the install success
  panel; clear reused `--tempdir` packages before regenerating them.
- Add `-V` as a short form of `--version` and allow the global output flags
  after subcommands.

## 0.1.1 - 2026-10-27

- Publish to PyPI as `uvs-cli` through a trusted-publishing GitHub workflow.
- Document the PyPI install path. No functional changes.

## 0.1.0 - 2026-10-26

- Install supported single-file PEP 723 scripts as persistent uv tools.
- Track canonical source paths and update changed snapshots with patch versions.
- List, inspect, and uninstall tools through a deterministic subcommand CLI.
- Recover valid data from old or damaged registries with atomic, serialized writes.
- Support Python 3.10+ with real lifecycle CI on Windows and Linux.
- Reframe the public documentation around testing whether the project is useful.
- Add lightweight paths for bug reports, usefulness feedback, contributions, and
  private security reports.
- Reject ambiguous batch naming and clean up an installed tool when registry
  persistence fails.
- Add `uvs --version`.
- Name the distribution `uvs-cli` to avoid the unrelated PyPI project `uvs`;
  the import package and the installed command remain `uvs`.
