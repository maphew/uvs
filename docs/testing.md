# Test inventory

The test suite is split by what it actually exercises:

| Location | Classification | Boundary |
| --- | --- | --- |
| `tests/test_characterization.py` | Unit and CLI/component characterization | Calls pure helpers or Click's in-process runner; subprocess and registry boundaries are isolated. |
| `tests/test_cli.py` | Unit and CLI/component | Exercises config helpers and in-process Click commands. |
| `tests/test_mocked_workflows.py` | Mocked workflow/component | Dispatches commands through a test helper and mocks `uv tool install`; it does not execute the installed command. |
| `tests/test_uninstall.py` | Unit/component | Tests uninstall helpers with mocked subprocess and local registry state. |

There are currently **no real integration tests**. Mocked workflow tests do not
prove that a generated tool can be installed or executed by `uv`. Real isolated
lifecycle coverage is a separate hardening phase.

```bash
uv run pytest
uv run pytest -m mocked_workflow
```
