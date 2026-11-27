"""The gate `AGENTS.md` lists and the steps CI runs are one list."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).parent.parent
SETUP = ("uv lock --check", "uv sync --locked", "uv sync --locked --group docs")


def _gate() -> list[str]:
    text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    section = text.split("\n## Tooling\n", 1)[1]
    block = section.split("```bash\n", 1)[1].split("```", 1)[0]
    return [line.strip() for line in block.splitlines() if line.strip()]


def _job_text(name: str) -> str:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = re.split(r"\n  (?=[a-z][a-z-]*:\n)", text.split("\njobs:\n", 1)[1])
    return next(part for part in job if part.lstrip().startswith(f"{name}:"))


def _job(name: str) -> list[str]:
    found = re.findall(r"^\s+- run: (.+)$", _job_text(name), re.MULTILINE)
    return [step for step in found if step not in SETUP]


def test_the_gate_is_the_test_job() -> None:
    gate = _gate()
    assert len(gate) >= 5, "the scan found almost no gate commands"
    assert gate == _job("test")


def test_every_run_carries_no_sync() -> None:
    """Every `uv run` the gate and the workflows write carries `--no-sync`."""
    assert all(command.startswith("uv run --no-sync ") for command in _gate() + _job("test"))
    for workflow in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        code = "\n".join(
            line
            for line in workflow.read_text(encoding="utf-8").splitlines()
            if not line.lstrip().startswith("#")
        )
        runs = re.findall(r"\buv run\b(.*)", code)
        if workflow.name in {"ci.yml", "docs.yml"}:
            assert runs, workflow.name
        assert all(run.startswith(" --no-sync ") for run in runs), (workflow.name, runs)


def _release(version: str) -> tuple[int, ...]:
    return tuple(map(int, version.removesuffix("t").split(".")))


def _interpreters() -> tuple[set[str], str, set[str]]:
    """The releases the classifiers name, the newest, and the free-threaded builds of them.

    A free-threaded build is supported from 3.14, the first PEP 779 supports, and valgebra ships
    a wheel for each from there.
    """
    classifiers = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    named = {
        line.rsplit(" :: ", 1)[1]
        for line in classifiers["project"]["classifiers"]
        if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", line)
    }
    free = {f"{version}t" for version in named if _release(version) >= (3, 14)}
    return named, max(named, key=_release), free


def test_the_suite_runs_on_every_interpreter_and_platform() -> None:
    """Every interpreter the classifiers name runs the suite at push, and so do macOS and Windows.

    `test` runs it on Linux at the newest with the gate, `suite` at each one there, the newest
    among them, and at the free-threaded build of each from 3.14, a pair of steps an interpreter
    in one job, and `platforms` at the newest on macOS and Windows, as valgebra's push runs its
    own: a defect one interpreter or one platform alone reaches fails the push rather than the
    release smoke. Each job's name says the interpreters it runs, so the list of checks on a
    commit reads them.
    """
    named, newest, free = _interpreters()
    test = _job_text("test")
    assert re.search(rf'python-version: "{re.escape(newest)}"', test), test
    assert re.search(rf"^    name: .+, on Linux at {re.escape(newest)}$", test, re.MULTILINE), test
    suite = _job_text("suite")
    assert re.search(r"^\s+runs-on: ubuntu-26\.04$", suite, re.MULTILINE), suite
    step = r'UV_PYTHON: "([\d.]+t?)".*\n\s+run: '
    synced = re.findall(rf"{step}uv sync --locked$", suite, re.MULTILINE)
    pytest = r"uv run --no-sync python -X warn_default_encoding -m pytest"
    tested = re.findall(rf"{step}{pytest}$", suite, re.MULTILINE)
    assert synced == tested, suite
    assert set(tested) == named | free, tested
    title = re.search(r"^    name: the suite on Linux at (.+)$", suite, re.MULTILINE)
    assert title, suite
    assert re.split(r", | and ", title[1]) == tested, title[1]
    platforms = _job_text("platforms")
    systems = re.findall(r"^\s+os: \[(.+)\]$", platforms, re.MULTILINE)
    assert [s.strip() for s in systems[0].split(",")] == ["macos-26", "windows-2025-vs2026"]
    assert re.search(rf'python-version: "{re.escape(newest)}"', platforms), platforms
    assert re.search(rf"^    name: .+ at {re.escape(newest)}$", platforms, re.MULTILINE), platforms


def test_the_release_smokes_the_wheel_where_the_push_runs_the_suite() -> None:
    """The smoke installs the wheel on every interpreter the push runs the suite on.

    On Linux every release the classifiers name and its free-threaded build from 3.14; on macOS
    and Windows every release, where the push runs the newest alone.
    """
    named, _, free = _interpreters()
    text = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")
    legs = dict(re.findall(r"^\s+- name: (\w+), the wheel\n.*\n\s+legs: (.+)$", text, re.MULTILINE))
    wheels = {
        platform: {leg.removeprefix("wheel/highest/") for leg in spec.split()}
        for platform, spec in legs.items()
    }
    assert wheels == {"Linux": named | free, "macOS": named, "Windows": named}, wheels


def test_the_tested_set_is_the_lock_s() -> None:
    """`constraints.txt` pins each dependency at the lock's version: the set a release ran on.

    It is `uv export --locked --no-dev --no-emit-project --no-hashes`, its header naming the
    command; a lock that moves a version it pins fails here until it is exported again.
    """
    locked = {
        package["name"]: package["version"]
        for package in tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))["package"]
    }
    written = (ROOT / "constraints.txt").read_text(encoding="utf-8")
    pinned = dict(re.findall(r"^([A-Za-z0-9._-]+)==(\S+)$", written, re.MULTILINE))
    assert "valgebra" in pinned
    assert {name: locked.get(name) for name in pinned} == pinned
