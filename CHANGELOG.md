# Changelog

This project is published on PyPI as
[`uvs-cli`](https://pypi.org/project/uvs-cli/), because the PyPI project `uvs`
is an unrelated tool. The installed command is `uvs`.

## Unreleased

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
