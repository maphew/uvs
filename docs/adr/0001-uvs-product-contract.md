# ADR 0001: uvs product contract

Status: Accepted for the 0.1 hardening programme (2026-07-13)

## Context

Uvs is a thin adapter from a PEP 723 single-file script to a generated Python
package installed by `uv tool install`. Hardening needs a stable boundary so
later fixes do not grow uvs into a second package manager.

## Decision

- Installation has **snapshot semantics**. The generated tool contains a copy
  of the source. Source edits take effect only after `uvs update`.
- Supported input is one Python file with a synchronous, top-level `main()`.
  Sibling modules and data files are outside the contract. Uvs documents this
  limitation instead of attempting unreliable static detection.
- Supported source is copied verbatim into the generated module. PEP 723
  metadata consists of comments, and an `if __name__ == "__main__"` guard is
  inert when the module is imported. Textual removal can alter valid programs.
- The public CLI uses subcommands only: `uvs install`, `uvs update`, `uvs
  list`, `uvs show`, and `uvs uninstall`.
- `uv` owns environments, executable installation, replacement, and removal.
  The uvs registry owns only the mapping between an installed uvs command and
  its canonical source script, plus the metadata needed to detect an update.
- The incomplete configuration surface is not part of the 0.1 contract. CLI
  options are sufficient and the config facade will be removed in Phase 3.
- Python 3.10 and later remain supported for this cycle. Windows and Linux are
  release platforms; macOS support is desirable but not a release gate.

## Non-goals

Uvs will not package sibling files, accept arbitrary Python projects, publish
packages, or replace `uv tool` management.

## Consequences

Generated packages are disposable implementation details. Validation may be
strict where command, distribution, and import-module names have different
rules. The registry must tolerate users operating `uv tool` directly, but it
must not duplicate uv's environment state.
