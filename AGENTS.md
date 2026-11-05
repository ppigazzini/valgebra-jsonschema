# Agent instructions

valgebra-jsonschema reads JSON Schema into [valgebra](https://github.com/ppigazzini/valgebra)'s
sets. A keyword it reads holds as the specification states; a keyword it does not read is
refused, and never skipped. It is a frontend: what a set means is valgebra's, and what a
keyword means is here. What belongs in valgebra is a set the typing syntax spells, or a gap in
deciding one; what belongs here is reading another language's schemas.

## Git

- **Never add trailers to commit messages.** No `Co-Authored-By:`, no `Generated with` line,
  no tool attribution of any kind.
- Message style: [`docs/10-writing.md`](docs/10-writing.md#commit-messages).

## Tooling

Everything runs through `uv`, and every `uv run` carries `--no-sync`.

```bash
uv run --no-sync ruff check
uv run --no-sync ruff format --check
uv run --no-sync ty check
uv run --no-sync python tools/check_markdown.py
uv run --no-sync pytest
uv run --no-sync python tools/suite.py --check docs/studies/json-schema-test-suite.json
uv run --no-sync python tools/suite.py --draft 7 --check docs/studies/json-schema-test-suite-draft7.json
uv run --no-sync python tools/suite.py --draft 6 --check docs/studies/json-schema-test-suite-draft6.json
uv run --no-sync python tools/suite.py --draft 4 --check docs/studies/json-schema-test-suite-draft4.json
uv run --no-sync python tools/corpus.py --check docs/studies/jsonschemabench.json
uv run --no-sync python tools/containment.py --check docs/studies/containment.json
```

All of them must exit 0 before a commit. A change that moves a published count regenerates
the study with `--json` in the same commit and says why the count moved.

## Conventions

- `docs/10-writing.md` is the standard for pages, comments and commit messages.
- A proof is valgebra's or a concrete value's; nothing here turns "not proven" into "false" or
  "true". A relation valgebra cannot decide is `undecided`.
- A keyword the compiler does not translate raises `Unsupported`. `docs/03-conformance.md` holds
  the keyword inventory and the ledger of differences, and a difference outside it is a defect.
- Every leaf holds every spelling of one JSON value: `1` and `1.0` are one number, so an
  `integer` is an `int` or a `float` multiple of one, and a constant is a union of its spellings.
  valgebra's algebra does not enforce it, and its theory page states it as this package's
  obligation. `valgebra_jsonschema/_valgebra.py` is the only module that imports valgebra.
