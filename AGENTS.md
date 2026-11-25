# Agent instructions

valgebra-jsonschema reads JSON Schema into [valgebra](https://github.com/ppigazzini/valgebra)'s
sets. A keyword it reads holds as the specification states; a keyword it does not read is
refused, and never skipped. It is a frontend: what a set means is valgebra's, and what a
keyword means is here. What belongs in valgebra is a set the typing syntax spells, or a gap in
deciding one; what belongs here is reading another language's schemas.

## Git

- **Never add trailers to commit messages.** No `Co-Authored-By:`, no `Generated with` line,
  no tool attribution of any kind.
- Message style: [the writing page's commit messages](docs/dev/writing.md#commit-messages).

## Tooling

Everything runs through `uv`, and every `uv run` carries `--no-sync`.

```bash
uv run --no-sync ruff check
uv run --no-sync ruff format --check
uv run --no-sync ty check
uv run --no-sync python tools/check_markdown.py
uv run --no-sync python -X warn_default_encoding -m pytest
uv run --no-sync python tools/suite.py --check docs/studies/json-schema-test-suite.json
uv run --no-sync python tools/suite.py --draft 2019-09 --check docs/studies/json-schema-test-suite-draft2019-09.json
uv run --no-sync python tools/suite.py --draft 7 --check docs/studies/json-schema-test-suite-draft7.json
uv run --no-sync python tools/suite.py --draft 6 --check docs/studies/json-schema-test-suite-draft6.json
uv run --no-sync python tools/suite.py --draft 4 --check docs/studies/json-schema-test-suite-draft4.json
uv run --no-sync python tools/suite.py --draft format --check docs/studies/json-schema-test-suite-format.json
uv run --no-sync python tools/corpus.py --check docs/studies/jsonschemabench.json
uv run --no-sync python tools/containment.py --check docs/studies/containment.json
```

All of them must exit 0 before a commit. A change that moves a published count regenerates
the study with `--json` in the same commit and says why the count moved.

The job `docs` builds the site on every push, after `uv sync --locked --group docs`, with
`uv run --no-sync zensical build --strict`: `mkdocs.yml` raises every check the builder makes on
a link and on the nav to a warning, so a dead link, a dead anchor or a page off the nav fails it.

## Conventions

- [The writing page](docs/dev/writing.md) is the standard for pages, comments and commit
  messages.
- [The theory page](docs/dev/theory.md) names the code resting on each published result, and
  an item implementing one cites it by key and place, as the writing page says.
- `docs/` is the user guide `mkdocs.yml` builds and the workflow `Docs` publishes, with
  `llms.txt`, at <https://ppigazzini.github.io/valgebra-jsonschema/>; a page added is a line of
  its `nav` and of its `llmstxt` sections, the second the page's `description:`. `docs/dev/`
  holds the developer pages, which are not published.
- [The releasing page](docs/dev/releasing.md) is the order a version reaches PyPI in, and only
  a dispatch of `.github/workflows/release.yml` uploads one. A cut follows it from
  [Before the bump](docs/dev/releasing.md#before-the-bump) on, every step in its order;
  performance is read for the code the window changed and for no other, a time on a quiet box;
  and a push, a dispatch, a tag and an advisory each wait for the maintainer's word, given for
  that one.
- A proof is valgebra's or a concrete value's; nothing here turns "not proven" into "false" or
  "true". A relation valgebra cannot decide is `undecided`.
- A keyword the compiler does not translate raises `Unsupported`.
  [The conformance page](docs/conformance.md) holds the keyword inventory and the ledger of
  differences, and a difference outside it is a defect.
- Every leaf holds every spelling of one JSON value: `1` and `1.0` are one number, so an
  `integer` is an `int` or a `float` multiple of one, and a constant is a union of its spellings.
  valgebra's algebra does not enforce it, and its theory page states it as this package's
  obligation. `valgebra_jsonschema/_valgebra.py` is the only module that imports valgebra.
