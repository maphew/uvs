# To do

- `uvs uninstall --all` yields "Are you sure you want to uninstall all 3 tools? [y/N]:". It should list the tools.

- stale registry: if tool is removed outside of uvs, uvs won't know. Running `uvs uninstall {tool}` will be told by uv the tool doesn't exist, and uvs automatically clean the registry. --> however `uvs uninstall --all` will not clean, only report the uv tool error.


# COMPLETE

- [x] rename the project to something more workable. Top candidates:
  
  - [x] `uvs` - uv single-file scripts as tools. Harmonizes with standard `uvx` alias for `uv tool`
  - discarded:  `uvone` - uv one-file
  - discarded: `luv` - don't know what the L is, but the name is just begging to be used. 'Local' maybe? Anyway, save for project that fits.

- [x] adjust pyproject.toml so that uvs itself is uv tool installable.

- [x] Review @/scripts/README.md with an eye to making concise. It currently contains things which are documented elsewhere, for example the structure of PEP723 metadata. Refer to authoritative upstream docs instead of repeating here.

- [x] uvs should use same syntax style as uv. For example `uvs list` instead of `uv --list`. Let's enrich cli experience too while we're at it.

- [x] install registry needs to be in a standard ~/.config or %appdata% location instead of relative to where command was run from

- [x] add tests for user-facing behaviour

- [x] verify configs are stored properly in home dirs, following standard convention -- using [platformdirs](https://platformdirs.readthedocs.io/en/latest/) instead of building our own.

- [x] Should show abs path instead of relative. This won't help someone find the source

- [x] Description should come from docstring of the script. If there is no docstring, generate one from analysing what the script does.

- [x] verify all examples work

- [x] Add uninstall command - while `uv tool uninstall` works already, only uvs has the mapping of what it installed (`uvs list`). Also `uninstall --all`.
