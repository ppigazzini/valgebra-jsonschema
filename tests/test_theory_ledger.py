"""The theory page, its table of works and the package, held to each other.

`docs/dev/theory.md` says which published result each item of the package rests on, so a
reader can check a step against a page of a paper rather than a recollection. That holds only
while every citation names its place, every claim names the items resting on it, and every
item citing a work is named under a claim citing that work. `docs/dev/writing.md` states the
rule; this holds it, over the comments and docstrings of `valgebra_jsonschema` and the page.

What no test can see is an item that implements a result and cites nothing: a reader decides
that a function is a theorem, and this holds the citation once written.
"""

from __future__ import annotations

import ast
import io
import re
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "valgebra_jsonschema"
THEORY = ROOT / "docs" / "dev" / "theory.md"

#: A surname, as `Attouche` or `D'Antoni`.
NAME = r"[A-Z][\w'\u2019-]*[a-z]"
#: A citation key: two surnames, or one with `et al.`, and the year.
KEY = re.compile(rf"\b{NAME}(?: et al\.| and {NAME}) (?:19|20)[0-9]{{2}}\b")
#: One place in a work: a section, or a numbered statement of a form the writing rule lists.
ONE_PLACE = r"§[0-9]+(?:\.[0-9]+)*|(?:Def|Thm|Lem|Prop|Cor|Ex|Alg|Fig)\. [0-9]+(?:\.[0-9]+)*"
#: The places after a key: a comma, then one place or more, a comma between two.
PLACES = re.compile(rf", (?:{ONE_PLACE})(?:, (?:{ONE_PLACE}))*")
#: A line break inside prose, a comment or a docstring, with what continues it.
BREAK = re.compile(r"\s*\n\s*(?:#+\s*)?")
#: A row of the table of works: its key in the first cell.
ROW = re.compile(rf"^\| ({NAME}(?: et al\.| and {NAME})? (?:19|20)[0-9]{{2}}) \|", re.MULTILINE)
#: A claim's tag.
TAG = re.compile(r"\*\*\[(LOAD-BEARING|DEVIATION): ([a-z][a-z0-9-]*)\]\*\*")
CODE = re.compile(r"`[^`\n]*`")


def _located(text: str) -> list[tuple[str, tuple[str, ...]]]:
    flat = BREAK.sub(" ", text)
    found = []
    for match in KEY.finditer(flat):
        tail = PLACES.match(flat, match.end())
        found.append((match.group(), tuple(re.findall(ONE_PLACE, tail.group()) if tail else ())))
    return found


def _keys(text: str) -> set[str]:
    return set(KEY.findall(BREAK.sub(" ", text)))


def _prose(text: str) -> str:
    """Return the comments and docstrings of a source, one after another."""
    tree = ast.parse(text)
    parts = [
        doc
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef))
        and (doc := ast.get_docstring(node)) is not None
    ]
    parts += [
        token.string
        for token in tokenize.generate_tokens(io.StringIO(text).readline)
        if token.type == tokenize.COMMENT
    ]
    return "\n\n".join(parts)


def _items(module: str, text: str) -> dict[str, set[str]]:
    """Return each item of a module the page may name, with the works its docstring cites.

    An item is the module, as `schema.py`, or a class or a function in it, as
    `schema.py::Compiler._index`; a comment inside it, and in no item nested in it, is its own.
    """
    tree = ast.parse(text)
    found = {module: _keys(ast.get_docstring(tree) or "")}
    spans: list[tuple[int, int, str]] = []

    def walk(node: ast.AST, owner: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                qualified = f"{owner}{child.name}"
                name = f"{module}::{qualified}"
                found[name] = _keys(ast.get_docstring(child) or "")
                spans.append((child.lineno, child.end_lineno or child.lineno, name))
                walk(child, f"{qualified}.")

    walk(tree, "")
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            line = token.start[0]
            owners = [name for start, end, name in spans if start <= line <= end]
            found[owners[-1] if owners else module] |= _keys(token.string)
    return found


@dataclass
class Claim:
    tag: str
    ident: str
    cites: set[str]
    implemented: list[str] = field(default_factory=list)
    held: list[str] = field(default_factory=list)


def _claims(page: str) -> list[Claim]:
    found: list[Claim] = []
    prose: list[str] = []
    for paragraph in re.split(r"\n\s*\n", page):
        text = paragraph.strip()
        label, colon, names = text.partition(": ")
        if text.startswith("#"):
            prose = []
        elif colon and label in ("IMPLEMENTED-BY", "HELD-BY") and found:
            listed = [name.strip() for name in names.split(",") if name.strip()]
            (found[-1].implemented if label == "IMPLEMENTED-BY" else found[-1].held).extend(listed)
        elif tag := TAG.search(text):
            body = CODE.sub("``", "\n".join([*prose, text]))
            found.append(Claim(tag[1], tag[2], _keys(body)))
            prose = []
        else:
            prose.append(text)
    return found


def _sources() -> dict[str, str]:
    return {path.name: path.read_text("utf-8") for path in sorted(PACKAGE.glob("*.py"))}


def _page() -> str:
    return THEORY.read_text("utf-8")


def _cited() -> dict[str, set[str]]:
    cited: dict[str, set[str]] = {}
    for module, text in _sources().items():
        cited.update(_items(module, text))
    return cited


def test_every_citation_names_its_place() -> None:
    texts = {module: _prose(text) for module, text in _sources().items()}
    # A row of the table names a work whole; a citation names a place in it.
    prose = "\n".join(line for line in _page().splitlines() if not line.startswith("|"))
    texts[THEORY.name] = CODE.sub("``", prose)
    bare = [
        f"{where}: {key}"
        for where, text in texts.items()
        for key, places in _located(text)
        if not places
    ]
    assert not bare, "a citation with no place in its work"
    assert any(_located(text) for text in texts.values()), "the ledger reads no citation"


def test_every_work_cited_is_a_row_and_every_row_is_cited() -> None:
    rows = set(ROW.findall(_page()))
    cited = set().union(*_cited().values(), *(claim.cites for claim in _claims(_page())))
    assert rows, "the table of works has no row"
    assert cited <= rows, f"cited and not in the table: {sorted(cited - rows)}"
    assert rows <= cited, f"in the table and cited nowhere: {sorted(rows - cited)}"


def test_every_claim_is_implemented_and_held_by_tests_that_exist() -> None:
    tests = {
        name
        for path in sorted((ROOT / "tests").glob("test_*.py"))
        for name in re.findall(
            r"^\s*(?:async )?def (test_\w+)", path.read_text("utf-8"), re.MULTILINE
        )
    }
    claims = _claims(_page())
    assert claims, "the page holds no claim"
    assert len({claim.ident for claim in claims}) == len(claims), "two claims share an id"
    for claim in claims:
        assert claim.implemented, f"[{claim.ident}] names no item"
        assert claim.held, f"[{claim.ident}] names no test"
        missing = [name for name in claim.held if name not in tests]
        assert not missing, f"[{claim.ident}] is held by no test named {missing}"


def test_every_item_named_cites_a_work_its_claim_cites() -> None:
    cited = _cited()
    for claim in _claims(_page()):
        for name in claim.implemented:
            assert name in cited, f"[{claim.ident}] names {name}, which is no item of the package"
            assert cited[name] & claim.cites, f"[{claim.ident}] names {name}, citing none of it"


def test_every_citing_item_is_named_under_a_claim_citing_its_works() -> None:
    claims = _claims(_page())
    for name, keys in _cited().items():
        naming = [claim for claim in claims if name in claim.implemented]
        assert not keys or naming, f"{name} cites {sorted(keys)}, and no claim names it"
        for key in keys:
            assert any(key in claim.cites for claim in naming), f"{name} cites {key} unclaimed"


def test_the_ledger_reads_a_place_a_key_and_an_item_as_written() -> None:
    text = "(Attouche et al.\n    2024, §4.2, §4.5), and (Pezoa et al. 2016)"
    assert _located(text) == [("Attouche et al. 2024", ("§4.2", "§4.5")), ("Pezoa et al. 2016", ())]
    source = (
        '"""A module (Pezoa et al. 2016, §3)."""\n\n\nclass C:\n'
        "    def f(self) -> None:\n        # a step (Attouche et al. 2024, §3.1)\n"
        "        return None\n"
    )
    items = _items("m.py", source)
    assert items["m.py"] == {"Pezoa et al. 2016"}
    assert items["m.py::C.f"] == {"Attouche et al. 2024"}
    assert items["m.py::C"] == set()
