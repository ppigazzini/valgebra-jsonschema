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


def test_the_suite_runs_on_every_interpreter_and_platform() -> None:
    """Every interpreter the classifiers name runs the suite at push, and so do macOS and Windows.

    `test` runs it on Linux at the newest, `suite` at each one below it there, a pair of steps
    an interpreter in one job, and `platforms` at the newest on macOS and Windows, as valgebra's
    push runs its own: a defect one interpreter or one platform alone reaches fails the push
    rather than the release smoke.
    """
    classifiers = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    named = {
        line.rsplit(" :: ", 1)[1]
        for line in classifiers["project"]["classifiers"]
        if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", line)
    }
    newest = max(named, key=lambda version: tuple(map(int, version.split("."))))
    test = _job_text("test")
    assert re.search(rf'python-version: "{re.escape(newest)}"', test), test
    suite = _job_text("suite")
    assert re.search(r"^\s+runs-on: ubuntu-26\.04$", suite, re.MULTILINE), suite
    synced = re.findall(r'UV_PYTHON: "([\d.]+)".*\n\s+run: uv sync --locked$', suite, re.MULTILINE)
    pytest = r"uv run --no-sync python -X warn_default_encoding -m pytest"
    tested = re.findall(rf'UV_PYTHON: "([\d.]+)".*\n\s+run: {pytest}$', suite, re.MULTILINE)
    assert synced == tested, suite
    assert set(tested) == named - {newest}, tested
    platforms = _job_text("platforms")
    systems = re.findall(r"^\s+os: \[(.+)\]$", platforms, re.MULTILINE)
    assert [s.strip() for s in systems[0].split(",")] == ["macos-26", "windows-2025-vs2026"]
    assert re.search(rf'python-version: "{re.escape(newest)}"', platforms), platforms


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
