# uvs

You have a useful, self-contained Python script under source control. You want
to run it as a normal command from anywhere, without maintaining a package
project just to put it on `PATH`.

`uvs` fills that narrow gap. It turns one supported Python file into a small,
disposable package and asks [`uv`](https://docs.astral.sh/uv/) to install it as
a persistent tool. It also remembers the source file so that a later
`uvs update` can install a new snapshot.

> **Project status:** `uvs` 0.1 is experimental and seeking public validation.
> It works for the deliberately small contract below, but its usefulness beyond
> one person's workflow is still an open question. If you try it, please share
> [whether it fits your work](https://github.com/maphew/uvs/issues/new?template=usefulness-feedback.yml),
> including why it does not.

## Is uvs a fit?

Choose `uvs` when:

- your tool is one self-contained, UTF-8 Python file with a synchronous,
  top-level `main()`;
- you want an explicit installed snapshot, not a command that changes whenever
  its source file changes; and
- you already use `uv` and want it to keep owning the tool environment and
  executable.

Do not choose `uvs` when:

- your code needs sibling modules, data files, or a project directory: package
  it as a normal Python project instead;
- you want to run directly from changing source: `uv run path/to/script.py` or
  a shell alias is a better fit;
- you need an asynchronous, nested, or method-based entry point; or
- you want a replacement for `uv tool` or a way to publish packages.

## Try it, then remove the installed state

Requirements are Python 3.10 or newer and `uv` available on `PATH`. Install the
[current release](https://pypi.org/project/uvs-cli/) from PyPI:

```console
uv tool install uvs-cli
uvs --help
```

The distribution is named `uvs-cli`: the PyPI project
[`uvs`](https://pypi.org/project/uvs/) is an unrelated tool. The installed
command is still `uvs`, and `uv tool uninstall uvs-cli` removes it. Because
`uv` gives each tool its own isolated environment, the shared name inside the
packages does not interfere with the install above. Do not `pip install` both
distributions into one environment.

To track `main` instead of the released version, install
`"git+https://github.com/maphew/uvs.git"`.

If the shell cannot find `uvs` (or a tool installed later), run
`uv tool update-shell` and restart the shell. `uv tool dir --bin` prints the
executable directory if you prefer to add it to `PATH` yourself.

Save this as `hello.py`:

```python
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///

def main() -> None:
    print("Hello from uvs")


if __name__ == "__main__":
    main()
```

Test the source, install it, and run the installed command:

```console
uv run hello.py
uvs install hello.py
hello
```

Now edit `hello.py` so that its function prints different text:

```python
def main() -> None:
    print("Hello from a new snapshot")
```

Install and run the new snapshot:

```console
uvs update hello.py
hello
```

The first command removes both the installed `hello` tool and its `uvs`
registry entry; the second removes `uvs` itself. Your source file remains
untouched:

```console
uvs uninstall hello
uv tool uninstall uvs-cli
```

The test matrix covers Windows and Linux. macOS has not been verified.

## Supported script contract

`uvs` supports one UTF-8 Python file at a time. The file must be valid Python
and define a synchronous `main()` function directly at module scope. An
`async def main`, a method, or a function nested inside another function is not
a supported entry point. A conventional `if __name__ == "__main__": main()`
guard is fine.

PEP 723 metadata is optional. When present, it may contain `dependencies`,
`requires-python`, and a `tool` table. Dependencies and the Python constraint
are copied into the generated package. Other top-level metadata fields are
rejected. The script, including its metadata comments, is copied verbatim into
the snapshot; `uvs` does not collect sibling modules, data files, or a project
directory.

The command name comes from the filename, with underscores changed to hyphens.
Use `uvs install --name another-name hello.py` to choose it explicitly.

## Snapshots, updates, and ownership

The installed command is a snapshot. Editing the original `.py` file does not
change it. `uvs update` accepts either the tracked tool name or the source
path, finds the registry entry, and reinstalls the tool only when the source
hash changed. The original source path must still exist.

```console
uvs install hello.py             # create and install the first snapshot
uvs list                         # list entries tracked by uvs
uvs show hello                   # show source, version, hash, and install time
uvs update hello                 # reinstall if the source hash changed
uvs update hello.py              # same, addressed by source path
uvs update --all --dry-run       # preview every pending update
uvs uninstall hello              # remove the uv tool and uvs registry entry
```

`uvs install` is idempotent-safe: it refuses to replace a tool that is already
tracked (or a uv tool with the same name) unless you pass `--force`. Forcing a
reinstall preserves the recorded version unless `--version` is given
explicitly. Batches (`--all`) skip colliding names from other sources and
report how many were skipped.

Each changed update advances the generated package's PEP 440 version to the
next final release. Release tuples shorter than three components are padded
before their final component is incremented; epochs are preserved, while pre,
post, development, and local qualifiers are removed. For example, `1.2rc1`
updates to `1.2.1`, and `2!1.2.3.post1` updates to `2!1.2.4`.

`uv` owns the installed tool environment and executable. `uvs` owns a small,
platform-specific `registry.json` containing the source path, source hash,
version, install time, and the install inputs needed to refresh a snapshot
(dependencies, `requires-python`, requested Python, editable mode, and package
directory). `uvs list` and `uvs show` describe that registry, not every tool
known to `uv`; use `uv tool list` for the latter. Direct `uv tool install`
operations do not appear in `uvs list`, and removing a managed tool directly
with `uv` can leave a stale `uvs` entry. Prefer `uvs uninstall` for tools
managed by `uvs`.

`uvs list --check` compares each entry with `uv` and its source file and exits
non-zero when anything needs attention. `uvs doctor` prints the registry path,
`uv` availability, every tool's status, untracked uv tools, and the backup
count. `uvs prune` removes entries whose uv tool is gone; entries that still
have a working install but a missing source are reported and left alone so a
successful command is not silently orphaned. Use `uvs uninstall NAME` for
those.

`uvs show NAME --format simple` emits five undecorated `Label: value` lines in
this fixed order: `Name`, `Source`, `Version`, `Installed`, and `Hash`. Unlike
the default Rich table, the simple format includes the complete source hash and
is stable for plain-text consumers. Table output uses compact UTC timestamps
(`2026-07-14 12:34:56 UTC`); `simple` and `json` keep the stored ISO value.

`uvs backup list` shows registry backups, and `uvs backup restore [TARGET]`
restores one (default: the latest). Uninstall and restore create a backup
unless `--no-backup` is given; the newest 20 are retained.

## Output, exit codes, and shell integration

- `--verbose`/`-v`, `--quiet`/`-q`, and `--no-color` work before or after the
  subcommand. `--quiet` suppresses progress and success chrome but never
  `list`, `show`, or machine-readable output.
- Usage errors (missing arguments, conflicting flags, nonexistent paths) exit
  `2` and include Click's usage hint. Operational failures (invalid PEP 723
  metadata, a rejected entry point, `uv` failures, unusable registries) exit
  `1`.
- `NO_COLOR` and `TERM=dumb` are honored; `--no-color` strips emphasis as well
  as color.
- The simple list format appends `[status]` with `--check`:

  ```console
  uvs list --format simple --check
  hello <- /home/me/hello.py (v0.1.1) [ok]
  ```

- Click shell completion works without extra packages:

  ```console
  eval "$(_UVS_COMPLETE=bash_source uvs)"
  ```

  Use `zsh_source` or `fish_source` for those shells.

The CLI exposes additional flags on some commands. Consult
`uvs COMMAND --help` for the current interface.

## Troubleshooting

- **`uv` is not found:** install it using the
  [official uv instructions](https://docs.astral.sh/uv/getting-started/installation/)
  and ensure it is on `PATH`.
- **An installed command is not found:** run `uv tool update-shell`, restart the
  shell, or use `uv tool dir --bin` to find the directory to add to `PATH`.
- **The script is rejected:** run `uv run path/to/script.py`, check that it is
  UTF-8 and syntactically valid, and verify that it has a synchronous,
  top-level `def main(...):`.
- **PEP 723 metadata is rejected:** use one closed `# /// script` block with
  valid TOML and only the supported top-level fields above.
- **`uvs update` cannot find the tool:** pass the tracked tool name or the
  same source file used for installation. If the source moved, uninstall by
  command name and install it again from the new path.
- **`uvs update` reports "source file not found":** the snapshot still works,
  but it can no longer be refreshed. Run `uvs uninstall NAME` (or
  `uvs prune --dry-run`) to reconcile the registry.
- **`uvs list` and `uv tool list` disagree:** the former is `uvs` bookkeeping;
  the latter reports environments owned by `uv`. Run `uvs list --check`,
  `uvs doctor`, or `uvs prune` to see and reconcile drift.

## Feedback and project policy

Success here means learning whether this small workflow is useful, and where
it fails. Please use the focused form to share
[usefulness feedback](https://github.com/maphew/uvs/issues/new?template=usefulness-feedback.yml)
or [report a bug](https://github.com/maphew/uvs/issues/new?template=bug-report.yml).
Contributions are welcome; read [CONTRIBUTING.md](CONTRIBUTING.md) before
starting. Report security concerns through [SECURITY.md](SECURITY.md), not a
public issue.

Project records: [changelog](CHANGELOG.md),
[product contract](docs/adr/0001-uvs-product-contract.md),
[test inventory](docs/testing.md), and [MIT license](LICENSE.md).

## Development and tests

Create the locked development environment:

```console
uv sync --dev --locked
```

Run the fast suite (the repository configuration excludes integration tests):

```console
uv run pytest
```

Run only mocked subprocess workflow tests (these are component tests, not
end-to-end tests):

```console
uv run pytest -m mocked_workflow
```

Run the isolated lifecycle test against the real `uv` executable, serially:

```console
uv run pytest -m integration -n 0
```

See [`examples/`](examples/) for the minimal supported example.
