# UV tool install single-file scripts

How can I do the equivalent of `uv tool install foobar.py` on single file self-contained PEP723 scripts and then have foobar available as a general command?

The naive `uv tool install --script foobar.py` doesn't work. 
Reading through UV docs and asking on Discord determines that installing single-file scripts is not a feature at present.
So can we build a single-to-src tool that we can feed to uv and get the appearance as if uv supports it?

## Context

I have a dev folder where I keep and work on my single-file scripts, under source code control. Once I'm happy enough with the work I want to 'publish' the script to PATH, the same way I can with a  script using traditional source layout of `src/module/script.py`. Sure I can do this with a Makefile or similar, but that's a pain to manage and `uv tool install` is just so much nicer!


## What works

`uv init --package uv-tool-pkg` - Creates `uv-tool-pkg/` hello world python project with a pyproject.toml and src layout.

Running `uv tool install .` in that folder will install a script to path called `uv-tool-pkg`:

    > uv tool install -e uv-tool-pkg/
    Resolved 1 package in 1ms
        Built uv-tool-pkg @ file:///var/home/matt/OneDrive/dev/uvs/uv-tool-pkg
    Prepared 1 package in 13ms
    Installed 1 package in 6ms
    + uv-tool-pkg==0.1.0 (from file:///var/home/matt/OneDrive/dev/uvs/uv-tool-pkg)
    Installed 1 executable: uv-tool-pkg

    > uv-tool-pkg 
    Hello from uv-tool-pkg!


We want this same convenience, but applied to a self-contained single-file script:

    uv init --script uv-single.py


##  The Idea

Write a tool that will transform a single-file script into a package layout automatically and then uv tool install it.


## Questions

How to maintain the link back to the source single-file.py? Some weeks or months later we will want to work on this script and might not remember where this python tool in path came from.

Will standard `uv tool uninstall` still work?

Can we make editable installs feasible? Likely not, but would be cool if could.

Assuming success on above, is this something we can contribute to uv?

How do we structure our collection of single-file scripts to make both developing them and installing them easily managed?

Do we use a single pyproject.toml, and each script has it's own [project.scripts] entry? Or do we need to have per-script toml? (ugh, unless it's all behind the scenes and automatic)


## Reference material

LLM Agents: Use context7 mcp

https://docs.astral.sh/uv/guides/scripts/
https://docs.astral.sh/uv/guides/tools/
