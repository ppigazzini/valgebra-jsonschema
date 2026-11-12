# Releasing

How a version reaches PyPI: where it is declared, how it is built, what stands between a
dispatch and an upload, what the repository and the indexes hold for it, the order of the steps,
and the checks on what an index serves. `.github/workflows/release.yml` owns the build, the tests
of the built artifacts and the upload; this page owns the order and the checks outside it.

## The version is declared once

`version` in `pyproject.toml` is the only declaration, and `uv.lock` records it for the project,
so a bump runs `uv lock`. The wheel's file name and its metadata carry what `pyproject.toml`
says.

## The build runs locked code

The build job makes the files the publish job uploads, so every Python package it runs comes
from `uv.lock`, each hash required: the backend `[build-system]` names is the group `build`, and
the job passes that group's export to `uv build` as build constraints, with `--require-hashes`.
A backend release reaches the artifacts only through a lock update, which pip-audit reads as it
reads every group. twine, which resolves fresh, checks the metadata in a job of its own, on
copies of the artifacts. hatchling fixes every timestamp, and two builds of one commit
give the same bytes.

## Publishing is a dispatch, and a tag publishes nothing

`release.yml` runs on `workflow_dispatch` alone. Its `publish_target` input selects the index,
`none`, `testpypi` or `pypi`, and `none` builds and tests the artifacts without uploading them:
the dry run, which a dispatch from any branch can make. No workflow listens for a tag; the tag
records a release that happened.

Six conditions stand between a dispatch and an upload, each a job, a step or a job condition in
`release.yml`:

- **The metadata reads as the index reads it.** `twine check --strict` passes on both artifacts.
- **The smoke passes.** The wheel and the sdist are each installed in a fresh environment on
  CPython 3.11 and 3.15, their dependencies resolved from PyPI as a user's are; each imports with
  every warning an error, from `site-packages`, and the suite the sdist carries runs on it with
  the group `test` at the lock's versions, so a file the suite reads and the sdist leaves out
  fails there. A version cannot be replaced on an index once uploaded, only yanked, so a broken
  artifact has to fail before the upload.
- **`confirm_version` equals the built version**, and an empty input aborts.
- **The ref is `main`**, and each environment admits `main` alone
  ([below](#what-the-repository-and-the-indexes-hold)).
- **`test.yml` passed on the commit.** A push run of it on `main`, at this very commit,
  concluded in success; a failed, canceled or unfinished run, none at all, or an API that does
  not answer refuses.
- **The version is absent from the index.** Only a definitive 404 for it proceeds: a 200 is a
  re-publish, and any other answer leaves the question open. A version the index names as its
  latest is refused as well.

The upload is trusted publishing: PyPI and TestPyPI each hold a publisher naming this repository,
`release.yml` and the deployment environment named after the index, and the publish job runs in
that environment, so no token is stored anywhere. Each upload carries PEP 740 attestations,
signed with the same token.

## What the repository and the indexes hold

The condition on the ref is a line of `release.yml`, and a dispatch from a branch runs that
branch's copy of the file, which can drop it. Each environment therefore admits a deployment from
`main` alone, a rule of the repository's settings that no branch edits, and the publisher on the
index names the environment, so the rule holds for every copy of the workflow:

```bash
for env in testpypi pypi; do
  gh api -X PUT repos/ppigazzini/valgebra-jsonschema/environments/$env \
    -F 'deployment_branch_policy[protected_branches]=false' \
    -F 'deployment_branch_policy[custom_branch_policies]=true'
  gh api -X POST repos/ppigazzini/valgebra-jsonschema/environments/$env/deployment-branch-policies \
    -f name=main -f type=branch
done
```

The first upload of the name creates the project from a pending publisher, entered on each index
under the account's publishing settings, with the same four fields: the project name, the owner
and repository, `release.yml` and the environment.

## The order

1. **Move to the newest valgebra first.** A `0.0.x` minor of valgebra is a breaking release here,
   so its floor in `pyproject.toml`, the lock and every study move in a commit of their own, with
   the gate of [`AGENTS.md`](../AGENTS.md) green, before the bump.
2. **Bump, in one commit.** `version` in `pyproject.toml`, `uv lock`, and the changelog: the
   `Unreleased` entries roll into a section for the version, dated the day of the commit, with its
   compare and tag links. It lands on `main`, and the push runs `test.yml` on the tree about to
   be published; the dispatches wait until it passes.
3. **Dispatch to TestPyPI**, with the version confirmed:

   ```bash
   gh workflow run release.yml -f publish_target=testpypi -f confirm_version=X.Y.Z
   ```

4. **Check what TestPyPI serves** ([below](#checking-an-index)).
5. **Dispatch to PyPI**, `-f publish_target=pypi`, the same version.
6. **Check what PyPI serves.**
7. **Tag the published commit**, annotated:

   ```bash
   git tag -a vX.Y.Z -m "valgebra-jsonschema X.Y.Z" <commit>
   git push origin vX.Y.Z
   ```

## Checking an index

The smoke proves each artifact. It cannot prove what the index serves: the resolution, the file an
installer picks and the metadata it reads all come after the upload, and steps 4 and 6 are the only
ones that read them.

TestPyPI serves whatever anyone uploaded under a name, so only this package comes from it, without
its dependencies, and those come from PyPI at the lock's versions, in an install of their own. From
the repository root:

```bash
uv venv /tmp/vj
uv export --locked --no-dev --no-emit-project -o /tmp/vj-deps.txt
VIRTUAL_ENV=/tmp/vj uv pip install -r /tmp/vj-deps.txt
VIRTUAL_ENV=/tmp/vj uv pip install --no-deps --index-url https://test.pypi.org/simple/ "valgebra-jsonschema==X.Y.Z"
VIRTUAL_ENV=/tmp/vj uv pip check
```

`uv pip check` holds what was installed to the uploaded metadata's requirements. From PyPI the
install is the user's, `VIRTUAL_ENV=/tmp/vj uv pip install "valgebra-jsonschema==X.Y.Z"`, in a
fresh environment. Then the import and the suite, with the test group at the lock's versions,
both from outside the tree:

```bash
uv export --locked --only-group test --no-emit-project -o /tmp/vj-test.txt
VIRTUAL_ENV=/tmp/vj uv pip install -r /tmp/vj-test.txt
tree="$PWD"; cd /tmp
/tmp/vj/bin/python -W error -c 'import valgebra_jsonschema as m; assert "site-packages" in m.__file__, m.__file__; s = m.compile_schema({"type": "integer"}); assert s.is_valid(1.0) and not s.is_valid(True)'
/tmp/vj/bin/pytest -p no:cacheprovider "$tree/tests"
cd "$tree"
```

`python -c` and `python -m pytest` put the working directory first on the path, and from the
repository root either imports the checkout's package in place of the installed one. The import
asserts where it read the package from, and the suite runs through the environment's `pytest`
script, which puts no directory of the tree on the path.

**The simple index lags the JSON API, and the simple index is what an installer reads.** A
same-day check passes `--refresh-package valgebra-jsonschema`, since uv caches an index's
answers, and "no such version" is read against the index itself before it is believed:

```bash
curl -sS https://test.pypi.org/simple/valgebra-jsonschema/ \
  -H "Accept: application/vnd.pypi.simple.v1+json" \
  | python3 -c "import json, sys; print(json.load(sys.stdin)['versions'])"
```

## What this does not cover

- **CPython 3.12, 3.13 and 3.14.** They are classifiers in `pyproject.toml`; the smoke and the
  push lanes run 3.11 and 3.15, and no job runs the releases between.
- **Free-threaded CPython and PyPy.** No job runs them and no classifier claims them.
- **The floors.** The smoke resolves each dependency to its newest release, and no job installs
  the floors `pyproject.toml` names. Each floor is the lock's version, which a lock update can
  move past.
- **A published version that is wrong.** It cannot be replaced, only yanked, and the workflow
  refuses a version the index serves. The remedy is the next version, which is why step 4 comes
  before step 5.
