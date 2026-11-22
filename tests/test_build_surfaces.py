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


def _job(name: str) -> list[str]:
    text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    job = re.split(r"\n  (?=[a-z][a-z-]*:\n)", text.split("\njobs:\n", 1)[1])
    steps = next(part for part in job if part.lstrip().startswith(f"{name}:"))
    found = re.findall(r"^\s+- run: (.+)$", steps, re.MULTILINE)
    return [step for step in found if step not in SETUP]


def test_the_gate_is_the_test_job() -> None:
    gate = _gate()
    assert len(gate) >= 5, "the scan found almost no gate commands"
    assert gate == _job("test")


def test_every_run_carries_no_sync() -> None:
    commands = _gate() + _job("test") + _job("floor") + _job("docs")
    assert all(command.startswith("uv run --no-sync ") for command in commands), commands


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
