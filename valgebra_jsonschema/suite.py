"""Run the official JSON-Schema-Test-Suite against the compiler and count the outcomes.

Each test case is a schema, an instance and the verdict the specification requires. A
schema the compiler refuses is skipped and counted with the reason; every other instance
is checked by membership in the compiled set. The counts are the record: a pass rate is
computed where it is printed.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from valgebra_jsonschema.schema import Compiler, Unsupported, in_dialect, older, upgrade

#: Where the suite serves its ``remotes/`` from, by path below this URI.
REMOTE = "http://localhost:1234/"
#: The ``$schema`` each older draft's files are read in where a group declares none.
DIALECTS = {
    2019: "https://json-schema.org/draft/2019-09/schema",
    7: "http://json-schema.org/draft-07/schema#",
    6: "http://json-schema.org/draft-06/schema#",
    4: "http://json-schema.org/draft-04/schema#",
}


@dataclass(slots=True)
class Outcome:
    """Counts for one suite file, and the failures by name."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    opaque: int = 0
    failures: list[str] = field(default_factory=list)
    reasons: Counter[str] = field(default_factory=Counter)


def remotes(directory: Path) -> dict[str, object]:
    """Return the suite's remote documents in ``directory``, by the URI its cases name each by."""
    return {
        REMOTE + p.relative_to(directory).as_posix(): json.loads(p.read_text(encoding="utf-8"))
        for p in sorted(directory.rglob("*.json"))
    }


def run_file(
    path: Path,
    *,
    draft: int | None = None,
    assert_format: bool = False,
    documents: Mapping[str, object] | None = None,
) -> Outcome:
    """Run every case of one suite file; an older draft's schemas are upgraded first.

    ``documents`` are the remote documents a reference may name, each read in its own
    dialect, or in the file's draft where it declares none.
    """
    out = Outcome()
    for group in json.loads(path.read_text(encoding="utf-8")):
        schema = group["schema"]
        # A group naming a dialect of its own is that dialect's, so it reaches the refusal.
        declared = schema.get("$schema") if isinstance(schema, dict) else None
        try:
            given = documents
            if draft is not None and (declared is None or older(schema) == draft):
                given = in_dialect(documents or {}, DIALECTS[draft])
                schema = upgrade(schema, draft)
            compiler = Compiler(schema, assert_format=assert_format, documents=given)
            compiled = compiler.compile(schema)
        except Unsupported as exc:
            out.skipped += len(group["tests"])
            out.reasons[str(exc).split(":")[0]] += len(group["tests"])
            continue
        for test in group["tests"]:
            if compiler.opaque:
                out.opaque += 1
            if compiled.is_valid(test["data"]) == test["valid"]:
                out.passed += 1
            else:
                out.failed += 1
                out.failures.append(f"{path.stem}: {group['description']} / {test['description']}")
    return out


def run_formats(directory: Path) -> dict[str, Outcome]:
    """Run the vendored ``optional/format`` files, with ``format`` read as an assertion."""
    return {p.stem: run_file(p, assert_format=True) for p in sorted(directory.glob("*.json"))}


def run_older(
    directory: Path, draft: int, documents: Mapping[str, object] | None = None
) -> dict[str, Outcome]:
    """Run every suite file of an older draft in ``directory`` through `upgrade`, by stem."""
    return {
        p.stem: run_file(p, draft=draft, documents=documents)
        for p in sorted(directory.glob("*.json"))
    }


def run(directory: Path, documents: Mapping[str, object] | None = None) -> dict[str, Outcome]:
    """Run every suite file in ``directory`` and its ``optional/``, by relative stem.

    Of the optional files, the vendored ones are the four on regular expressions and on
    large numbers: draft 2020-12 says a pattern is ECMA-262 and a number a JSON number, and
    those files test what that means.
    """
    files = sorted(directory.glob("*.json")) + sorted(directory.glob("optional/*.json"))
    return {
        p.relative_to(directory).with_suffix("").as_posix(): run_file(p, documents=documents)
        for p in files
    }
