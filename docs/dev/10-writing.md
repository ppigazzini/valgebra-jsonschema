# Technical writing

Three surfaces, one standard: state what is true, with the evidence, in as few words as
carry it.

## The standard

**Authoritative.** Write the fact, not the journey to it. "A fractional `multipleOf` compares in
exact rationals" — not "we tried binary floats and then realized".

**No history.** Not in pages, not in comments, not in commit messages. A text describes
what is, not what was or how it came to be known. Where a past defect is load-bearing,
state the property that prevents it: "a cell inside an `enum` is decided by checking each
listed value, so the spurious remainder valgebra cannot prove empty never reaches the
caller" — never "we saw a spurious cell and then discovered".

**No meta.** Do not describe the text, the process, or who did what. No "this section
covers", no "as mentioned above", no agent, tool or author names, no counts of how long
something went unnoticed.

**No marketing.** No "powerful", "robust", "seamless", "comprehensive", "state of the art".
A property either has a number or is not claimed.

**Lean.** Every sentence carries a fact, a number, or a consequence. Cut anything that
would survive being deleted.

**American English.** Every text here is American English: pages, comments, docstrings,
messages, names and commit messages. `-ize` and `-yze` (`serialize`, `analyze`), `-or` (`behavior`), `-er` (`center`), `-ense` (`license`,
`defense`), one `l` before a suffix (`modeled`, `labeled`), `toward` and `afterward`,
`while` and `among`, and a date month first (`Oct 29, 2026`) or as ISO 8601
(`2026-10-29`). A quotation, a published title and a third party's name keep the
spelling they were published with.

## The untracked surface

Maintainer notes — reports, analyses, plans — live in a working area `.gitignore` names, and
this standard does not govern them. **A tracked file never names that area, or a note in it**:
the area is not in the tree, so the reference dangles for every reader but its author. A page,
a comment and a commit message state the fact a note holds, with its evidence, where the fact
is needed, and a note is never the only place a fact of the tree lives.
`tools/check_markdown.py` sweeps every tracked file, prose and source alike, for the area's
name and for a report's.

## Claims

A claim needs evidence in the same sentence or the next one.

- **Measured** — give the number and the command. 1071 of 1071 suite cases pass, from
  `tools/suite.py --check docs/studies/json-schema-test-suite.json`.
- **Inferred** — say so first, not in a trailing caveat. "The mechanism is X" and "X is
  consistent with the data" are different claims.
- **Untested** — say the gap and what would close it. A gap described as a gap is
  information; a gap left implicit is a defect.

Never write a comparative result from one seed without the words "seed N, one sample" in
the same sentence as the number.

## Numbers

Every published number needs a committed command. Prose is not a study: if a number cannot
be grepped out of a command's output, it is not a result.

Quote a rate with its denominator: 1071 of 1071 cases run, 327 skipped, not "100 %".

A study records counts; a ratio is computed where it is printed, to one decimal place of a
percentage. The counts are the record, and they compare exactly.

## Pages

Structure by what the reader is doing, not by how the code is organized.

State the limit of what a page covers. A page that silently omits a case reads as though
the case does not exist.

Link with relative paths, except in `README.md`. The README is also the package's page on
PyPI, which resolves no relative link, so it links into this tree by the absolute address of
`main`, `https://github.com/ppigazzini/valgebra-jsonschema/blob/main/` and the path.
`tools/check_markdown.py` fails the build on a dead link of either kind and on a relative link
in the README.

### Markdown that GitHub renders

The renderer is strict and the failures are silent. `tools/check_markdown.py` catches these.

- Never split a token across the math boundary: write the whole symbol in one span, or
  plain text.
- No bare sub- or superscript spans.
- No spacing macros in inline `$...$`. They render literally.
- Keep a numeric range in one span. `$\sim10^4\text{ to }10^5$`, or plain text.
- Do not glue an opening `$` to a preceding `~` or `-`.
- When wrapping prose, never start a continuation line with `+ `, `- ` or `* `.
- No images, anywhere. A committed plot stops tracking the code that produced it and cannot
  be grepped against a study row.

## Code comments

**The default is no comment.** Code states what it does; a comment is for what the code
cannot state. Most lines need none.

Comment when the reason is not recoverable from the line:

- a value that looks arbitrary and is not
- an ordering that matters
- a library default being overridden
- an invariant a later edit would silently break
- a cheaper-looking alternative that is wrong

**Imperative mood.** "Keep the cell", not "This keeps the cell" or "Keeps the cell". Same
for docstring summaries, which `ruff` enforces.

Name the owner, the invariant and the failure:

```python
# Refuse the keyword. Skipping it would admit values the schema refuses, and every inclusion
# decided from the compiled set would be wrong.
```

That names the action, what breaks without it, and how far the damage reaches. `# keep it to be safe` carries none of it.

Do not restate the signature, narrate the obvious, or leave commented-out code.

Docstrings follow the numpy convention. A module docstring states what the module is
responsible for and what it must not do. A function docstring states the contract, not the
implementation.

## Commit messages

A commit states what the change does and what it measures. Same standard as everything
else: fact, no history, no meta.

```
scope: what the change does

The defect, stated as a property of the code. What the change does about it. The
measurement. What remains open.
```

- **Subject**: lowercase after the scope, no trailing period, under 72 characters. Scope is
  the module touched — `schema`, `mcp`, `study`, `suite`, `sample`, `docs`, `tools`, `build`, `ci`
  — or `repo` for the whole tree.
- **Body**: wrapped at 88. Give the numbers.
- One logical change per commit. A subject needing "and" is two commits.
- No provenance: not who found it, not how, not what was tried first, not how long it stood.
- No references to uncommitted files, external trackers, or the tooling that produced the
  change.

A defect is described in the present tense as a property:

```
The compiler's walk recurses once per level of a document, so one nested a few hundred levels
down raises `RecursionError` with no keyword to name. A document past `MAX_NESTING` is refused
before the walk; `tests/test_schema.py` pins the refusal.
```

Not: "this was introduced by the previous fix", "found while investigating X", "had been
wrong for four milestones".

If a cause is not established, state what is established and what is open. Do not narrate
the search.

## What not to write

| avoid | write |
|---|---|
| "significantly faster" | "2.68x, 917.2 ms to 342.2 ms" |
| "should work correctly" | the test that shows it does |
| "we discovered that" | the fact |
| "this was broken for months" | the property that makes it correct |
| "obviously", "simply", "just" | nothing; delete |
| "comprehensive", "robust" | the coverage, as a number |
| "note that", "it is worth mentioning" | the note |
