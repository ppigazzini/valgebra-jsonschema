# Releasing

How a version reaches PyPI: where it is declared, how it is built, what stands between a
dispatch and an upload, what the repository and the indexes hold for it, what is made ready
before the bump, the order of the steps, the checks on what an index serves, and the advisory.
`.github/workflows/release.yml` owns the build, the tests of the built artifacts and the upload;
this page owns the order and the checks outside it.

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
- **The smoke passes.** Each artifact is installed in a fresh environment, its dependencies
  resolved from PyPI as a user's are. The wheel installs on every CPython the classifiers name,
  3.11 through 3.15, on x86_64 Linux, Apple silicon macOS and x64 Windows: an install pulls the
  valgebra wheel of its interpreter and platform, and each of those is a build of its own. The
  sdist installs on 3.11 and 3.15 on Linux, and the wheel installs on 3.11 and 3.15 once more
  with each dependency at the floor `pyproject.toml` names (`--resolution lowest-direct`), where
  every other leg installs the newest release each admits. Each imports with every warning an
  error, from `site-packages`, and the suite the sdist carries runs on it with the group `test`
  at the lock's versions, so a file the suite reads and the sdist leaves out fails there. A
  version cannot be replaced on an index once uploaded, only yanked, so a broken artifact has to
  fail before the upload.
- **`confirm_version` equals the built version**, and an empty input aborts.
- **The ref is `main`**, and each environment admits `main` alone
  ([below](#what-the-repository-and-the-indexes-hold)).
- **`ci.yml` passed on the commit.** A push run of it on `main`, at this very commit,
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

## Before the bump

Everything the version carries is committed before the bump, one concern to a commit, so the
bump holds the version and the changelog alone. `LAST` is the version PyPI serves, and the
window is `git log --oneline "v$LAST"..HEAD`.

**A push, a dispatch, a tag and an advisory each wait for the maintainer's word.** A word given
for one is not given for the next, and a request to run the tests is none for `main`: a push
there deploys the site and puts the changelog's `Security` entries in public. A push to
`github_ci` or a dispatch of `ci.yml` runs the same jobs on a branch.

**Dependencies, tools and actions**, in one `build` commit. Each moves to its latest tagged
release; the commit names each one held back, and why.

| What moves | By | Read after |
|---|---|---|
| `uv.lock`, a floor in `pyproject.toml`, `constraints.txt` | `uv lock --upgrade`, then the export `constraints.txt` names in its header | the `pip-audit` job's two commands |
| an action | its tag in each `uses:`, then `gh actions-lock` | `gh actions-lock --verify`, and the `zizmor` job's command |
| a tool a job runs: uv, zizmor, pip-audit, griffe, twine | its pin in `.github/workflows/` | that job's own command |
| the pre-commit hooks | `uv run --no-sync pre-commit autoupdate` | `uv run --no-sync pre-commit run --all-files` |

**Performance, of the code that changed and of no other.** The window's diff names it:

```bash
git diff --stat "v$LAST" -- valgebra_jsonschema
```

Where the diff moves no code nothing is timed, and the bump's message says so. Elsewhere each
function it changes is timed on the input the change is about, in two environments of the last
release and in the tree, on one interpreter and with every dependency at one version:

```bash
uv sync --locked
for env in /tmp/last1 /tmp/last2; do
  uv venv --python .venv/bin/python "$env"
  VIRTUAL_ENV="$env" uv pip install "valgebra-jsonschema==$LAST" -c constraints.txt
done
uptime
tree="$PWD"; cd /
for round in 1 2 3 4 5; do
  for env in /tmp/last1 /tmp/last2 "$tree/.venv"; do
    echo "$env $(taskset -c 2 "$env/bin/python" -m timeit -s "$SETUP" "$CALL")"
  done
done
cd "$tree"
```

The three run from `/`, since `python -m` puts the working directory first on the path. A figure
is the median of its rounds, and the last release's second environment is the control: a
difference inside the spread of the two is none.

**A time is read on a quiet box.** No build, suite, sweep or second reading runs beside it, no
one else uses the machine, and `uptime` reads a one-minute load under 0.5 before the first
round. `taskset` keeps each run on one core, and the environments take turns, so a drift of the
machine falls on each alike. A driver written for a reading runs in a shell that bounds it,
`ulimit -u` the processes and `ulimit -v` the memory of each, and its file takes no standard
library module's name: `python bisect.py` puts its folder first on the path, where `random`
imports it as `bisect`.

A rise is restored in the commit of the window that made it, or is named in the version's
section with what it buys; one read after the tag is named in the published version's section,
and is restored, or kept for what it buys, in a commit of the next window. The wheel holds the
tree's Python files and nothing compiled, so the reading before the bump is of what the index
serves, and none follows the upload. A count is no time, and reads the same on any box: the
gate's `--check` holds each study's, and one that moves is regenerated in the commit that moves
it.

**Documentation.** Each page that states what the diff changes states the tree as it stands: the
guide, the README, `SECURITY.md`, `llms.txt`'s sections, the docstrings.
`tools/check_markdown.py` passes, and so does the site's strict build, `uv run --no-sync
zensical build --strict` after `uv sync --locked --group docs`.

**Papers and theorems.** Every item the diff adds or changes that implements a numbered result
cites it by key and place, and [the theory page](theory.md) names the item under the claim, as
[citing a paper](writing.md#citing-a-paper) says. No check sees a citation that is missing, so
the diff is read for one. `tests/test_theory_ledger.py` holds the citations to the page.

**Security.** Each defect of `LAST` that is one
[the security policy](../../SECURITY.md#what-is-a-security-issue) names stands under `Security`
in `Unreleased`, and [its advisory](#an-advisory) is drafted before the dispatch to PyPI.

**The changelog.** Each change a user meets has its entry under `Unreleased`, and each public
name removed or changed is one under Changed or Removed: the `api` job's command lists them.

## The order

1. **Move valgebra's floor where the release needs it.** `pyproject.toml` names valgebra's floor
   and no ceiling, so a valgebra release installs beside this package the day it is published
   and asks no release here. A release that needs what a valgebra release adds moves the floor
   to it, with the lock and every study, in a commit of its own with
   [the gate](../../AGENTS.md#tooling) green, before the bump. The `Upstream` workflow runs
   the suite and the studies on valgebra's `main` each Monday, so a change that moves a count
   shows before valgebra's cut. `constraints.txt` moves with the lock, exported again by the
   command its header names, and `test_the_tested_set_is_the_lock_s` holds its pins to the
   lock's: at a release's tag it is the set the release was tested with, which the README tells
   a deployment to pin. This package is the second of
   [the release order](https://github.com/ppigazzini/valgebra-planning/blob/main/docs/dev/releasing.md#the-release-order).
2. **Bump, in one commit, the tip of the window.** `version` in `pyproject.toml`, `uv lock`, the
   README's install pin, and the changelog: the `Unreleased` entries roll into a section for the
   version, dated the day of the commit and opened by a paragraph saying what a user gets, with
   its compare and tag links. The message says which checks ran, what they read, and what was not
   measured. A job a commit of the window broke is repaired by amending that commit, and the bump
   stays the tip. It lands on `main`, and the push runs `ci.yml` on the tree about to
   be published; the dispatches wait until it passes. The run's `api` job lists each public name
   removed or changed since the last tag, and each is an entry under Changed or Removed: one it
   lists and the changelog does not is fixed in the bump commit before any dispatch.
3. **Dispatch to TestPyPI**, with the version confirmed:

   ```bash
   gh workflow run release.yml -f publish_target=testpypi -f confirm_version=X.Y.Z
   ```

4. **Check what TestPyPI serves** ([the fast test](#checking-an-index)).
5. **Dispatch to PyPI**, `-f publish_target=pypi`, the same version.
6. **Check what PyPI serves**, and publish [the advisory](#an-advisory) of a section with
   `Security` entries.
7. **Tag the published commit**, annotated:

   ```bash
   git tag -a vX.Y.Z -m "valgebra-jsonschema X.Y.Z" <commit>
   git push origin vX.Y.Z
   ```

## Checking an index

The smoke proves each artifact. It cannot prove what the index serves: the resolution, the file an
installer picks and the metadata it reads all come after the upload, and steps 4 and 6 are the only
ones that read them.

**The fast test**, in minutes and from outside the tree:

1. The release run is green on the commit that will be tagged, and the index lists the version,
   its wheel and its sdist.
2. Each file has the sha256 the index states, and a provenance naming this repository,
   `release.yml` and the index's environment
   (`https://pypi.org/integrity/valgebra-jsonschema/X.Y.Z/<file>/provenance`). Two builds of one
   commit give the same bytes, so PyPI's hashes are TestPyPI's.
3. Every file of the wheel and the sdist that is in the tree equals the commit's.
4. The wheel installs on the floor and on the newest CPython, the sdist on the newest, and the
   wheel on the floor with `--resolution lowest-direct`; `uv pip check` passes on each.
5. The package imports with every warning an error, from `site-packages`, and one recipe the
   release touched prints what its page shows.
6. One behavior for each `Security` and `Fixed` entry, asked of the last release and of this
   one. The two answer differently, and a control both answer alike shows that the question
   reaches the code: one they answer alike tests nothing.

The suite is not part of it: the release's smoke ran it on the files it uploaded. Where the fast
test leaves an artifact in doubt, the install and the suite below are run on it.

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

## An advisory

A section with `Security` entries has one advisory, published when PyPI serves the fix, as
`SECURITY.md` says: a fix and its advisory go out together. It is a row for each way through,
with what went through and the releases affected.

**A range is what the published releases answer.** Each one is installed from PyPI and asked the
case, beside a control that release handles, so a release without the feature does not read as
one unaffected. A case an earlier advisory covers names that advisory.

**Each sentence is probed before it is published.** The draft is made, read back and corrected,
then published:

```bash
gh api -X POST repos/ppigazzini/valgebra-jsonschema/security-advisories --input advisory.json
gh api repos/ppigazzini/valgebra-jsonschema/security-advisories/$GHSA --jq .description
gh api -X PATCH repos/ppigazzini/valgebra-jsonschema/security-advisories/$GHSA -f state=published
```

`advisory.json` holds `summary`, `description`, `cvss_vector_string`, `cwe_ids` and one of
`vulnerabilities`, the `pip` package with `vulnerable_version_range` and `patched_versions`. It
names no person and no address.

## What this does not cover

- **The push lanes on macOS and Windows past 3.15.** A push runs the suite on every CPython the
  classifiers name on Linux and on 3.15 on macOS and Windows: 3.11 to 3.14 there are read by the
  smoke alone, when a release is dispatched.
- **Free-threaded CPython and PyPy.** No job runs them and no classifier claims them.
- **valgebra's other wheels.** Linux on aarch64 and musl, macOS on x86_64 and Windows on arm64
  run no leg here: valgebra's own release smoke installs each of those wheels on its platform and
  runs valgebra's suite on it.
- **The floors between releases.** The smoke's floor legs install them when a release is
  dispatched; the push lanes run the lock's versions, which a lock update can move past them.
- **A published version that is wrong.** It cannot be replaced, only yanked, and the workflow
  refuses a version the index serves. The remedy is the next version, which is why step 4 comes
  before step 5.
