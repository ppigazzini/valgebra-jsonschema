# valgebra-jsonschema

JSON Schema read into [valgebra](https://github.com/ppigazzini/valgebra)'s sets, so a schema
answers two questions: whether a value belongs, as the specification states it, and whether
everything one schema admits another admits too.

```python
from valgebra_jsonschema import compile_schema

# What an MCP server lists for a tool: its arguments, as JSON Schema.
tool = {
    "name": "get_weather",
    "inputSchema": {
        "type": "object",
        "properties": {
            "location": {"type": "string", "minLength": 1},
            "days": {"type": "number", "minimum": 1, "maximum": 7},
            "units": {"enum": ["celsius", "fahrenheit"]},
        },
        "required": ["location"],
    },
}
arguments = compile_schema(tool["inputSchema"])

assert arguments.is_valid({"location": "Paris", "days": 3})
assert not arguments.is_valid({"days": 3})
assert not arguments.is_valid({"location": "Paris", "days": 8})

# `1` and `1.0` are one JSON number, and `true` is none.
assert compile_schema({"type": "integer"}).is_valid(1.0)
assert not compile_schema({"type": "integer"}).is_valid(True)

# The next release of the tool takes another unit. Every call that was valid still is,
# and the converse fails: that is a compatible change, decided without running either.
wider = compile_schema(
    {
        "type": "object",
        "properties": {
            "location": {"type": "string", "minLength": 1},
            "days": {"type": "number", "minimum": 1, "maximum": 7},
            "units": {"enum": ["celsius", "fahrenheit", "kelvin"]},
        },
        "required": ["location"],
    }
)
assert arguments.relation_to(wider) == "subset"
assert wider.relation_to(arguments) == "not_subset"
```

`relation_to` answers `subset`, `not_subset` or `undecided`. It is `undecided` where valgebra
can prove neither, which is never a wrong proof, and a keyword this package does not read raises
`Unsupported` naming it, since skipping one would admit values the schema refuses.

## What it reads

Drafts 2020-12, 2019-09, 07, 06 and 04, all but the first through `upgrade`, and a document
naming any other dialect fails saying so, as the Model Context Protocol asks
([`docs/05-mcp.md`](https://github.com/ppigazzini/valgebra-jsonschema/blob/main/docs/05-mcp.md)).
Patterns follow ECMA-262, as the specification requires, and numbers compare by value: `1` and
`1.0` are one number, and `true` is none. `format` is an annotation, as 2020-12 makes it, and
`assert_format=True` reads nine of them as assertions. A `$ref` resolves against the base URI it
sits under, within the document or to one passed in `documents={uri: document}`; nothing is
fetched.
[`docs/02-compiler.md`](https://github.com/ppigazzini/valgebra-jsonschema/blob/main/docs/02-compiler.md)
says how each keyword becomes a set, and
[`docs/03-conformance.md`](https://github.com/ppigazzini/valgebra-jsonschema/blob/main/docs/03-conformance.md)
holds the inventory and the ledger of differences.

## Measured

```bash
uv run python tools/suite.py --check docs/studies/json-schema-test-suite.json
uv run python tools/corpus.py --check docs/studies/jsonschemabench.json
uv run python tools/containment.py --check docs/studies/containment.json
```

- **Against the official JSON-Schema-Test-Suite**: draft 2020-12 with the four optional files on
  regular expressions and large numbers, 1341 of the 1341 cases it runs; draft 2019-09, 1239 of
  1239; draft-07, 929 of 929; draft-06, 841 of 841; draft-04, 618 of 618. Skipped: dynamic
  references.
- **Real-world schemas** (JSONSchemaBench, 9558 schemas from GitHub, the JSON Schema Store,
  Kubernetes and function-calling data): 9473 compile, none crashes; membership differs from the
  `jsonschema` package's on 12 of 404298 values, each a reading the ledger records.
- **Inclusions** (the JSON Schema containment test suite, 10890 labeled questions): 6564 proven,
  none against a label; each of the 279 refutations against a label is a wrong label, which
  [`docs/04-results.md`](https://github.com/ppigazzini/valgebra-jsonschema/blob/main/docs/04-results.md)
  names.

## Install

On Python 3.11 or later, from PyPI, with valgebra, a Rust extension published as wheels:

```bash
pip install valgebra-jsonschema
```

## License

MIT or Apache-2.0, at your option.
