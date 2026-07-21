# Contributing to uvs

`uvs` is an experimental, one-maintainer project. Reports from real use,
criticism of the underlying idea, documentation fixes, tests, and small focused
code changes are all welcome. Feedback that the tool is not useful is valuable
too, especially when it describes the job you were trying to do.

## Scope

The supported contract is intentionally narrow: `uvs` turns one Python file
with a synchronous, top-level `main()` into a snapshot installed through
`uv tool`. See the [README](README.md#supported-script-contract) and the
[product contract](docs/adr/0001-uvs-product-contract.md) for details.

Packaging sibling modules or data files, accepting arbitrary Python projects,
publishing packages, and replacing `uv tool` management are non-goals.
Proposals may be declined when they fall outside that scope, add more ongoing
maintenance than their benefit supports, or lack enough evidence to justify a
larger interface. That is a product trade-off, not a judgment on the
contribution.

Use the GitHub issue forms for bugs and usefulness or design feedback. Small,
focused pull requests are easier to evaluate; consider opening an issue before
investing in a broad change. The project has no promised roadmap or response
schedule.

## Quality gates

Create the locked development environment and run the fast suite:

```console
uv sync --dev --locked
uv run pytest
```

Changes that affect installation or lifecycle behavior should also pass the
real integration suite, run serially:

```console
uv run pytest -m integration -n 0
```

See the [test inventory](docs/testing.md) for what each suite proves.
