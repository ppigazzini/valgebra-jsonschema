r"""Check Markdown against the rendering rules of `docs/10-writing.md`, and for dead links.

GitHub's inline math renderer is strict and its failures are silent: the page
renders, wrongly. `$^{238}$U` becomes a dangling superscript, `\\!`
inside inline `$...$` prints as a literal `!`, and a range split across two spans
(`$10^4$`-`$10^5$`) renders the second span as source text.

Every tracked file, prose and source alike, is swept for a name of the untracked
working area or of a report in it: `.gitignore` names the area, so such a name
points every reader but its author at nothing. `.gitignore`, which declares the
area, and this file, which names it to refuse it, are exempt.

    uv run python tools/check_markdown.py            # every tracked file
    uv run python tools/check_markdown.py README.md  # specific files

Exit status is 1 if anything is found, so it works as a pre-commit hook.

Inline code spans are stripped before the rendering rules match: a page that
documents these rules quotes the broken forms deliberately.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Each rule is (pattern, description). Applied outside fenced blocks and outside
# inline code spans.
RULES: tuple[tuple[str, str], ...] = (
    (r"\$\{?\^", "bare superscript span -- write the whole symbol in one span"),
    (r"\$\{?_", "bare subscript span -- write the whole symbol in one span"),
    (r"\}\$[A-Za-z]", "math span glued to a following letter (split token)"),
    (r"[A-Za-z]\$\{?[A-Za-z^_]", "letter glued to an opening math span"),
    (r"\\text\{[^}]*\\[_^]", r"escaped \_ or \^ inside \text{} -- use n_{\mathrm{in}}"),
    (r"[~\-\u2013]\$", "opening $ glued to a preceding ~, - or en dash"),
    (r"\$[^$\n]*\\[!,;][^$\n]*\$", r"spacing macro (\! \, \;) in inline math"),
)

FENCE = re.compile(r"^\s*(```|~~~)")
LINK = re.compile(r"\[[^\]]*\]\(([^)#\s]+)(?:#[^)\s]*)?\)")
ROOT = Path(__file__).resolve().parent.parent
# The README is also the package's page on PyPI, which resolves no relative link: it links
# into this tree by the address of `main`, and that address names a path the tree must hold.
README = ROOT / "README.md"
TREE = re.compile(r"https://github\.com/ppigazzini/valgebra-jsonschema/(?:blob|tree)/main/(.+)")
# The untracked working area, and a report in it. A report is named in prose, with no path to
# match, so its name is held directly.
INTERNAL = re.compile(r"__DEV|REPORT-[0-9]+")
# The files that name the area to declare it or to refuse it.
DECLARES_INTERNAL = frozenset({ROOT / ".gitignore", ROOT / "tools" / "check_markdown.py"})


def strip_code_spans(line: str) -> str:
    """Blank out inline code spans, by the CommonMark backtick-run rule.

    A run of N backticks opens a span and the next run of *exactly* N closes it.
    A regex cannot express that, and a greedy match splits an inline
    ``` ```math ``` span in the middle, exposing an unrelated ``$`` further along
    the line as unbalanced.
    """
    out: list[str] = []
    i = 0
    while i < len(line):
        if line[i] != "`":
            out.append(line[i])
            i += 1
            continue
        n = 0
        while i + n < len(line) and line[i + n] == "`":
            n += 1
        j = i + n
        while j < len(line):
            if line[j] != "`":
                j += 1
                continue
            m = 0
            while j + m < len(line) and line[j + m] == "`":
                m += 1
            if m == n:
                break
            j += m
        if j >= len(line):  # unclosed run: leave the rest as prose
            out.append(line[i:])
            break
        out.append("``")
        i = j + n
    return "".join(out)


def tracked() -> list[Path]:
    """Return every file git knows about."""
    out = subprocess.run(
        ["git", "ls-files"],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    )
    return [Path(line) for line in out.stdout.splitlines() if line]


def internal_references(path: Path) -> list[str]:
    """Return one message per name of the untracked working area, or of a report in it."""
    if path.resolve() in DECLARES_INTERNAL:
        return []
    text = path.read_bytes().decode("utf-8", errors="replace")
    return [
        f"{path}:{n}: names {match[0]}, which is untracked: the reference dangles for every "
        "reader but its author, so the sentence states the fact itself"
        for n, line in enumerate(text.splitlines(), 1)
        for match in INTERNAL.finditer(line)
    ]


def link_problems(path: Path, line: str) -> list[str]:
    """Return one message per dead link on ``line``, and per relative one in the README."""
    problems: list[str] = []
    for target in LINK.findall(line):
        if target.startswith(("http://", "https://", "mailto:")):
            own = TREE.match(target)
            if own and not (ROOT / own[1]).exists():
                problems.append(f"dead link -> {target}")
        elif path.resolve() == README:
            problems.append(f"relative link in the README, which PyPI cannot follow -> {target}")
        elif not (path.parent / target).exists():
            problems.append(f"dead link -> {target}")
    return problems


def check(path: Path) -> list[str]:
    """Return one message per problem found in ``path``."""
    problems: list[str] = []
    in_fence = False
    for n, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if FENCE.match(raw):
            in_fence = not in_fence
            continue

        problems.extend(f"{path}:{n}: {why}" for why in link_problems(path, raw))

        if in_fence:
            continue
        line = strip_code_spans(raw)
        if line.count("$") % 2:
            problems.append(f"{path}:{n}: odd number of $ -- the whole line stops rendering")
        for pattern, why in RULES:
            if re.search(pattern, line):
                problems.append(f"{path}:{n}: {why}\n    {raw.strip()[:100]}")
    return problems


def main(argv: list[str]) -> int:
    """Scan the named files, or every tracked file: the rendering rules read its pages."""
    files = [Path(a) for a in argv] if argv else tracked()
    files = [p for p in files if p.exists()]
    pages = [p for p in files if p.suffix == ".md"]
    problems = [msg for p in pages for msg in check(p)]
    problems += [msg for p in files for msg in internal_references(p)]
    for msg in problems:
        print(msg)
    print(f"\n{len(problems)} problem(s) in {len(files)} file(s), {len(pages)} of them pages")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
