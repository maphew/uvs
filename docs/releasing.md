# Releasing

`uvs` publishes to PyPI as the distribution **`uvs-cli`**, not `uvs`. The PyPI
project [`uvs`](https://pypi.org/project/uvs/) is an unrelated tool, and it
occupies the distribution name, the import package, and the console script. See
the README and `docs/adr/0001-uvs-product-contract.md` for the product contract.

The import package (`uvs`) and the installed command (`uvs`) are unchanged.
`uv tool install` names the tool after the distribution, so the tool itself is
`uvs-cli`.

## One-time PyPI setup (trusted publishing)

Publishing uses GitHub Actions OIDC, so no PyPI token is stored in the
repository. Before the first publish, add a *pending publisher* on PyPI under
**Account → Publishing → Add a new pending publisher**:

| Field | Value |
| --- | --- |
| PyPI project name | `uvs-cli` |
| Owner | `maphew` |
| Repository name | `uvs` |
| Workflow name | `publish.yml` |
| Environment name | `pypi` |

After the first successful publish the pending publisher becomes a normal
publisher and no longer needs to be recreated.

## Cutting a release

1. Land the release changes on `main` and let the CI matrix pass.
2. Move the `CHANGELOG.md` entries out of `## Unreleased` into a new version
   heading. Keep `pyproject.toml`, `src/uvs/__init__.py`, and that heading on the
   same version; a test guards the first two.
3. Tag and push: `git tag -a vX.Y.Z -m "..." && git push origin vX.Y.Z`.
4. Create the GitHub release: `gh release create vX.Y.Z --notes-file ...`.
   Publishing the release triggers `.github/workflows/publish.yml`.
5. If the release event was missed (for example, the workflow did not exist
   yet), run it against the tag:
   `gh workflow run publish.yml --ref vX.Y.Z`.
6. Verify the tag installs and that the version resolves from package metadata:

   ```console
   uv tool install "git+https://github.com/maphew/uvs.git@vX.Y.Z"
   uvs --version
   uv tool uninstall uvs-cli
   ```

7. Update the README install command to pin the new tag.

`uv publish --check-url https://pypi.org/simple/` makes the upload idempotent,
so re-running a partly failed publish skips files that already exist. PyPI never
allows reusing a version, so a broken release needs a new patch version and a
`CHANGELOG.md` entry rather than a re-tag.
