"""The pages quote the counts the study files hold, and their examples run as written."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _page(name):
    """Return a page with every run of whitespace one space: wrapping is not content."""
    return " ".join((ROOT / name).read_text(encoding="utf-8").split())


def _study(name):
    return json.loads((ROOT / "docs" / "studies" / name).read_text(encoding="utf-8"))


def _suite(name):
    files = _study(name)["files"]
    return {k: sum(f[k] for f in files) for k in ("passed", "failed", "skipped", "opaque")}


def test_the_pages_quote_the_draft_2020_12_totals():
    t = _suite("json-schema-test-suite.json")
    run = t["passed"] + t["failed"]
    assert f"{t['passed']} of the {run} cases it runs" in _page("README.md")
    assert f"{t['passed']} of the {run} cases run pass" in _page("docs/04-results.md")
    assert (
        f"{run} cases run, {t['passed']} passed, {t['failed']} failed; {t['skipped']} skipped"
    ) in _page("docs/02-compiler.md")
    assert f"{t['opaque']} of the run cases" in _page("docs/02-compiler.md")


@pytest.mark.parametrize("draft", ["2019-09", "7", "6", "4"])
def test_the_pages_quote_the_older_drafts_totals(draft):
    t = _suite(f"json-schema-test-suite-draft{draft}.json")
    run = t["passed"] + t["failed"]
    name = "draft 2019-09" if draft == "2019-09" else f"draft-0{draft}"
    assert f"{name}, {t['passed']} of {run}" in _page("README.md")
    assert f"{t['passed']} of the {run} cases run pass" in _page("docs/04-results.md")
    assert (
        f"{run} cases run, {t['passed']} passed, {t['failed']} failed; {t['skipped']} skipped"
    ) in _page("docs/02-compiler.md")


def test_the_pages_quote_the_corpus_totals():
    rows = _study("jsonschemabench.json")["subsets"]
    total = {k: sum(r[k] for r in rows) for k in ("schemas", "compiled", "values", "disagreed")}
    assert sum(r["crashed"] + r["timed_out"] for r in rows) == 0
    readme, page = _page("README.md"), _page("docs/04-results.md")
    assert f"{total['schemas']} schemas" in readme
    assert f"{total['compiled']} compile, none crashes" in readme
    assert f"{total['disagreed']} of {total['values']} values" in readme
    assert f"{total['compiled']} of the {total['schemas']} schemas compile, none crashes" in page
    assert f"on {total['disagreed']} of the {total['values']} values" in page


def test_the_pages_quote_the_containment_totals():
    rows = _study("containment.json")["rows"]
    keys = ("questions", "refused", "proven", "refuted", "undecided")
    keys += ("proven_against", "refuted_against")
    page, readme = _page("docs/04-results.md"), _page("README.md")
    for draft in ("2020-12", "7", "6", "4"):
        total = [sum(r[k] for r in rows if r["draft"] == draft) for k in keys]
        assert f"| {draft} | " + " | ".join(map(str, total)) + " |" in page
    grand = {k: sum(r[k] for r in rows) for k in keys}
    assert grand["proven_against"] == 0
    assert f"{grand['proven']} proofs of the {grand['questions']} questions, 0 against one" in page
    assert f"{grand['questions']} labeled questions" in readme
    assert f"{grand['proven']} proven, none against a label" in readme
    assert f"each of the {grand['refuted_against']} refutations against a label" in readme


@pytest.mark.parametrize("page", ["README.md", "docs/05-mcp.md"])
def test_the_examples_run_as_written(page):
    text = (ROOT / page).read_text(encoding="utf-8")
    blocks = re.findall(r"^```python\n(.*?)^```$", text, re.MULTILINE | re.DOTALL)
    assert blocks, f"{page} holds no example"
    for block in blocks:
        exec(compile(block, page, "exec"), {})  # noqa: S102 - the page's own examples
