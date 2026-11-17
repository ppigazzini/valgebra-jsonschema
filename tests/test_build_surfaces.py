"""The gate `AGENTS.md` lists and the steps CI runs are one list."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
SETUP = ("uv lock --check", "uv sync --locked")


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
    commands = _gate() + _job("test") + _job("floor")
    assert all(command.startswith("uv run --no-sync ") for command in commands), commands
