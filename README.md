# uvs

`uvs` installs a supported single-file Python script as a persistent command by
turning it into a small package and asking [`uv`](https://docs.astral.sh/uv/) to
install that package as a tool.

The installed command is a snapshot. Editing the original `.py` file does not
change the installed command; run `uvs update` to build and install a new
snapshot.

## Requirements and installation

- Python 3.10 or newer
- `uv` installed and available on `PATH`

Install `uvs` from this repository:

```console
uv tool install https://github.com/maphew/uvs.git
uvs --help
```

The test matrix covers Windows and Linux. macOS has not been verified.

## Supported script contract

`uvs` supports one UTF-8 Python file at a time. The file must be valid Python
and define a synchronous `main()` function directly at module scope. An
`async def main`, a method, or a function nested inside another function is not
a supported entry point. A conventional `if __name__ == "__main__": main()`
guard is fine.

PEP 723 metadata may contain `dependencies`, `requires-python`, and a `tool`
table. Dependencies and the Python constraint are copied into the generated
package. Other top-level metadata fields are rejected. The script and its
metadata are copied verbatim into the snapshot; `uvs` does not collect sibling
modules, data files, or a project directory.

For example, save this as `hello.py`:

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

Test and install it:

```console
uv run hello.py
uvs install hello.py
hello
```

The command name comes from the filename, with underscores changed to hyphens.
Use `uvs install --name another-name hello.py` to choose it explicitly.

## Lifecycle

```console
uvs install hello.py             # create and install the first snapshot
uvs list                         # list entries tracked by uvs
uvs show hello                   # show source, version, hash, and install time
uvs update hello.py              # reinstall if the source hash changed
uvs uninstall hello              # remove the uv tool and uvs registry entry
```

An update finds the registry entry by the source file's canonical path. When
the file changed, it reinstalls the tool and advances its PEP 440 version to
the next final release. Release tuples shorter than three components are padded
before their final component is incremented; epochs are preserved, while pre,
post, development, and local qualifiers are removed. For example, `1.2rc1`
updates to `1.2.1`, and `2!1.2.3.post1` updates to `2!1.2.4`. The original
source path must still exist. `list` and `show` describe the `uvs` registry,
not every tool known to `uv`; use `uv tool list` for the latter.

`uv` owns the installed tool environment and executable. `uvs` owns a small
platform-specific `registry.json` that records the source path, source hash,
version, and install time for tools it installed. Consequently, direct
`uv tool install` operations do not appear in `uvs list`, and directly removing
a tool with `uv` can leave a stale `uvs` entry. Prefer `uvs uninstall` for tools
managed by `uvs`.

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

Project records: [changelog](CHANGELOG.md),
[product contract](docs/adr/0001-uvs-product-contract.md),
[test inventory](docs/testing.md), and [MIT license](LICENSE.md).
