# Test inventory

The test suite is split by what it actually exercises:

| Location | Classification | Boundary |
| --- | --- | --- |
| `tests/test_characterization.py` | Unit and CLI/component characterization | Calls pure helpers or Click's in-process runner; subprocess and registry boundaries are isolated. |
| `tests/test_lifecycle_reliability.py` | Unit and CLI/component | Exercises registry locking, recovery, subprocess handling, and lifecycle decisions with isolated state and mocked external boundaries. |
| `tests/test_mocked_workflows.py` | Mocked workflow/component | Dispatches commands through a test helper and mocks `uv tool install`; it does not execute the installed command. |
| `tests/test_package_generation.py` | Unit/component contract | Exercises parsing, validation, package generation, and install option construction without a real tool installation. |
| `tests/test_uninstall.py` | Unit/component | Tests uninstall helpers with mocked subprocess and local registry state. |
| `tests/integration/` | Real integration | Uses the real `uv` executable in an isolated environment and executes the install/update/list/show/uninstall lifecycle. |

The fast suite excludes real integration tests. The mocked workflow marker is
useful when changing command dispatch, but it does not prove that a generated
tool can be installed or executed by `uv`:

```bash
uv run pytest -m "not integration"
uv run pytest -m mocked_workflow
```

Run the real integration suite separately and serially because it mutates its
isolated tool installation and registry state during a lifecycle:

```bash
uv run pytest -m integration -n 0
```

GitHub Actions runs the fast suite first and then the serial integration suite
on Windows and Linux with Python 3.10, 3.11, 3.12, and 3.13 after
`uv sync --dev --locked` verifies the locked development environment.
