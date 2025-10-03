# To do

## Structure

- install registry needs to be in a standard ~/.config or %appdata% location instead of relative to where command was run from


## Intermediate pyproject.toml

- Should show abs path instead of relative. This won't help someone find the source (pyproject.toml):

    [tool.uvs]
    source_path = "../uvs-example.py"

- Description should come from docstring of the script. If there is no docstring, generate one from analysing what the script does.
 
    [project]
    name = "uvs-single"
    version = "0.1.0"
    description = "Command-line tool from uvs-example.py"

## Features

- Editable install doesn't work. Probably because the editable location of installed exe is the intermediate packaged layout and not the source script. This might be unsurmountable without adding unreasonable amount of extra code and scaffolding. Hide the feature for now. Later we can examine fully and determine whether to pull altogether.

## Docs

- Review @/scripts/README.md with an eye to making concise. It currently contains things which are documented elsewhere, for example the structure of PEP723 metadata. Refer to authoritative upstream docs instead of repeating here.

# COMPLETE

- [x] rename the project to something more workable. Top candidates:
  
  - [x] `uvs` - uv single-file scripts as tools. Harmonizes with standard `uvx` alias for `uv tool`
  - discarded:  `uvone` - uv one-file
  - discarded: `luv` - don't know what the L is, but the name is just begging to be used. 'Local' maybe? Anyway, save for project that fits.

- [x] adjust pyproject.toml so that uvs itself is uv tool installable.
