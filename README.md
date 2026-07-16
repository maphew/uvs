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
current 0.1 code from this repository:

```console
uv tool install https://github.com/maphew/uvs.git
uvs --help
```

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
uv tool uninstall uvs
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
change it. `uvs update` finds the registry entry by the source file's canonical
path and reinstalls the tool only when the source hash changed. The original
source path must still exist.

```console
uvs install hello.py             # create and install the first snapshot
uvs list                         # list entries tracked by uvs
uvs show hello                   # show source, version, hash, and install time
uvs update hello.py              # reinstall if the source hash changed
uvs uninstall hello              # remove the uv tool and uvs registry entry
```

Each changed update advances the generated package's PEP 440 version to the
next final release. Release tuples shorter than three components are padded
before their final component is incremented; epochs are preserved, while pre,
post, development, and local qualifiers are removed. For example, `1.2rc1`
updates to `1.2.1`, and `2!1.2.3.post1` updates to `2!1.2.4`.

`uv` owns the installed tool environment and executable. `uvs` owns a small,
platform-specific `registry.json` containing the source path, source hash,
version, and install time for tools it installed. `uvs list` and `uvs show`
describe that registry, not every tool known to `uv`; use `uv tool list` for
the latter. Direct `uv tool install` operations do not appear in `uvs list`,
and removing a managed tool directly with `uv` can leave a stale `uvs` entry.
Prefer `uvs uninstall` for tools managed by `uvs`.

`uvs show NAME --format simple` emits five undecorated `Label: value` lines in
this fixed order: `Name`, `Source`, `Version`, `Installed`, and `Hash`. Unlike
the default Rich table, the simple format includes the complete source hash and
is stable for plain-text consumers.

The CLI exposes additional flags on some commands. They are not part of the
narrow contract documented here; consult `uvs COMMAND --help` for the current
interface.

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
- **`uvs update` cannot find the tool:** pass the same source file used for
  installation. If it moved, uninstall by command name and install it again
  from the new path.
- **`uvs list` and `uv tool list` disagree:** the former is `uvs` bookkeeping;
  the latter reports environments owned by `uv`. Reinstall with `uvs` or use
  `uvs uninstall` to reconcile a tracked tool.

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
