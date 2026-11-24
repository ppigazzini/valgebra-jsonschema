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
    commands = _gate() + _job("test") + _job("suite") + _job("docs")
    assert all(command.startswith("uv run --no-sync ") for command in commands), commands


def test_the_suite_runs_on_every_interpreter_and_platform() -> None:
    """Every interpreter the classifiers name runs the suite at push, and so do macOS and Windows.

    `test` runs it on Linux at the newest, and `suite` at each one below it there and at the
    newest on macOS and Windows, as valgebra's push runs its own: a defect one interpreter or
    one platform alone reaches fails the push rather than the release smoke.
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
    systems = re.findall(r"^\s+os: \[(.+)\]$", suite, re.MULTILINE)
    versions = re.findall(r"^\s+python: \[(.+)\]$", suite, re.MULTILINE)
    assert len(systems) == len(versions) == 1, suite
    linux = {
        (os.strip(), version.strip().strip('"'))
        for os in systems[0].split(",")
        for version in versions[0].split(",")
    }
    included = set(re.findall(r'- \{ os: ([\w.-]+), python: "([\d.]+)" \}', suite))
    assert linux | included == {("ubuntu-26.04", version) for version in named - {newest}} | {
        ("macos-26", newest),
        ("windows-2025-vs2026", newest),
    }


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
