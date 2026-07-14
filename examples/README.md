# Example

[`uvs-simple-example.py`](uvs-simple-example.py) is intentionally small. It is
a UTF-8, single-file script with valid PEP 723 metadata and a synchronous
top-level `main()` function—the public contract exercised by the repository's
example validation test.

From the repository root:

```console
uv run examples/uvs-simple-example.py
uvs install examples/uvs-simple-example.py
uvs-simple-example
uvs show uvs-simple-example
uvs uninstall uvs-simple-example
```

The fast test suite parses every `examples/*.py` metadata block and checks its
entry point. The separate real-`uv` integration test exercises install,
execution, dependency installation, update, list, show, and uninstall with an
isolated generated script; it does not install this example itself.
