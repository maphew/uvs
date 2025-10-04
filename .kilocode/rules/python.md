# python.md

Instructions for using python

## Guidelines

- In general use `uv run ...` instead of `python ...`
- preface self-contained single-file scripts with `#!/usr/bin/env -S uv run --script`
- add and remove dependencies with `uv add|remove ...`
  - for single file scripts `uv add|remove --script ...`
- `pytest` is probably in PATH
