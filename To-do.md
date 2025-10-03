# To do

## Structure

- install registry needs to be in a standard ~/.config or %appdata% location instead of relative to where command was run from


## Intermediate pyproject.toml

- Should show abs path instead of relative. This won't help someone find the source (pyproject.toml):

    [tool.uv-script-install]
    source_path = "../uv-single.py"

- Description should come from docstring of the script. If there is no docstring, generate one from analysing what the script does.
 
    [project]
    name = "uv-single"
    version = "0.1.0"
    description = "Command-line tool from uv-single.py"

## Features

- Editable install doesn't work. Probably because the editable location of installed exe is the intermediate packaged layout and not the source script. This might be unsurmountable without adding unreasonable amount of extra code and scaffolding. Hide the feature for now. Later we can examine fully and determine whether to pull altogether.

## Docs

- Review @/scripts/README.md with an eye to making concise. It currently contains things which are documented elsewhere, for example the structure of PEP723 metadata. Refer to authoritative upstream docs instead of repeating here.
