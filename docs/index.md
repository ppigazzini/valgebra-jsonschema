---
description: What valgebra-jsonschema is, how it reads JSON Schema into valgebra's sets, and the index to this guide.
---

# valgebra-jsonschema

**JSON Schema read into valgebra's sets.**

A schema answers two questions: whether a value belongs, as the specification states it, and
whether everything one schema admits another admits too. `compile_schema` reads draft 2020-12,
and drafts 2019-09, 07, 06 and 04 through `upgrade`, into
[valgebra](https://ppigazzini.github.io/valgebra/)'s sets over the values `json.loads` returns,
and raises `Unsupported` naming a keyword it does not read; valgebra then decides membership and
inclusion.

```python
from valgebra_jsonschema import compile_schema

tags = compile_schema({"type": "array", "items": {"type": "string", "minLength": 1}})
assert tags.is_valid(["io", "net"])
assert not tags.is_valid(["io", ""])

# Every array of nonempty strings is an array of strings, and not the converse.
strings = compile_schema({"type": "array", "items": {"type": "string"}})
assert tags.relation_to(strings) == "subset"
assert strings.relation_to(tags) == "not_subset"
```

```bash
pip install valgebra-jsonschema          # Python 3.11 or later
```

| page | what it holds |
|---|---|
| [mcp.md](mcp.md) | reading an MCP tool, its dialects, and what its schema may hold |
| [recipes.md](recipes.md) | tasks done end to end: a model's tool call, a schema change before release, a schema across documents, files against a schema, what a schema asserts |
| [changelog.md](changelog.md) | every released version and what it changed |
| [compiler.md](compiler.md) | how each JSON Schema keyword becomes a set, what is opaque, what is refused |
| [conformance.md](conformance.md) | the contract, its oracles, the keyword inventory and the ledger of differences |
| [results.md](results.md) | every measured count, with the command that prints it |
| [api.md](api.md) | the public names, read from the package's docstrings |

The site serves [`llms.txt`](https://ppigazzini.github.io/valgebra-jsonschema/llms.txt), a
manifest of these pages, and
[`llms-full.txt`](https://ppigazzini.github.io/valgebra-jsonschema/llms-full.txt), their full
text, for a reader that is not a browser. The developer pages under `docs/dev/` are not
published: how a version reaches PyPI, `docs/dev/releasing.md`, and the standard for every
text, `docs/dev/writing.md`. The study files each tool's `--check` reruns are under
`docs/studies/`.
