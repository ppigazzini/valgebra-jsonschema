---
description: What valgebra-jsonschema is, how it reads JSON Schema into valgebra's sets, and the index to this guide.
---

# valgebra-jsonschema

**JSON Schema read into valgebra's sets.**

A schema answers two questions: whether a value belongs, as the specification states it, and
whether everything one schema admits another admits too. `compile_schema` reads drafts 2020-12,
07, 06 and 04, and 2019-09 through `upgrade`, into [valgebra](https://ppigazzini.github.io/valgebra/)'s sets over the
values `json.loads` returns, and raises `Unsupported` naming a keyword it does not read; valgebra
then decides membership and inclusion.

```bash
pip install valgebra-jsonschema          # Python 3.11 or later
```

| page | what it holds |
|---|---|
| [05-mcp.md](05-mcp.md) | reading an MCP tool, its dialects, and what its schema may hold |
| [19-recipes.md](19-recipes.md) | tasks done end to end: a model's tool call, a schema change before release, a schema across documents, files against a schema, what a schema asserts |
| [12-changelog.md](12-changelog.md) | every released version and what it changed |
| [02-compiler.md](02-compiler.md) | how each JSON Schema keyword becomes a set, what is opaque, what is refused |
| [03-conformance.md](03-conformance.md) | the contract, its oracles, the keyword inventory and the ledger of differences |
| [04-results.md](04-results.md) | every measured count, with the command that prints it |
| [16-api.md](16-api.md) | the public names, read from the package's docstrings |

The site serves [`llms.txt`](https://ppigazzini.github.io/valgebra-jsonschema/llms.txt), a
manifest of these pages, and
[`llms-full.txt`](https://ppigazzini.github.io/valgebra-jsonschema/llms-full.txt), their full
text, for a reader that is not a browser. The developer pages under `docs/dev/` are not
published: how a version reaches PyPI, `docs/dev/06-releasing.md`, and the standard for every
text, `docs/dev/10-writing.md`. The study files each tool's `--check` reruns are under
`docs/studies/`.
