# Changelog

This project is not yet published on PyPI. The repository can be installed
directly as described in the README.

## Unreleased

- Reframe the public documentation around testing whether the project is useful.
- Add lightweight paths for bug reports, usefulness feedback, contributions, and
  private security reports.
- Reject ambiguous batch naming and clean up an installed tool when registry
  persistence fails.

## 0.1.0 - 2026-07-14

- Install supported single-file PEP 723 scripts as persistent uv tools.
- Track canonical source paths and update changed snapshots with patch versions.
- List, inspect, and uninstall tools through a deterministic subcommand CLI.
- Recover valid data from old or damaged registries with atomic, serialized writes.
- Support Python 3.10+ with real lifecycle CI on Windows and Linux.
