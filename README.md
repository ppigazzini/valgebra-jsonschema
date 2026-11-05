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

Drafts 2020-12, 07, 06 and 04, the last three through `upgrade`. Patterns follow ECMA-262, as the
specification requires, and numbers compare by value: `1` and `1.0` are one number, and `true` is
none. [`docs/02-compiler.md`](docs/02-compiler.md) says how each keyword becomes a set, and
[`docs/03-conformance.md`](docs/03-conformance.md) holds the inventory and the ledger of differences.

## Measured

```bash
uv run python tools/suite.py --check docs/studies/json-schema-test-suite.json
uv run python tools/corpus.py --check docs/studies/jsonschemabench.json
uv run python tools/containment.py --check docs/studies/containment.json
```

- **Against the official JSON-Schema-Test-Suite**: draft 2020-12 with the four optional files on
  regular expressions and large numbers, 1071 of the 1071 cases it runs; draft-07, 870 of 870;
  draft-06, 790 of 790; draft-04, 587 of 587. Skipped: `unevaluated*`, dynamic, anchor and
  remote references.
- **Real-world schemas** (JSONSchemaBench, 9558 schemas from GitHub, the JSON Schema Store,
  Kubernetes and function-calling data): 9429 compile, none crashes; membership differs from the
  `jsonschema` package's on 12 of 402633 values, each a reading the ledger records.
- **Inclusions** (the JSON Schema containment test suite, 10890 labeled questions): 5746 proven,
  none against a label; each of the 234 refutations against a label is a wrong label, which
  [`docs/04-results.md`](docs/04-results.md) names.

## Install

The package is not on PyPI. It installs from this repository, on Python 3.11 or later, and takes
valgebra from PyPI, a Rust extension published as wheels:

```bash
pip install git+https://github.com/ppigazzini/valgebra-jsonschema
```

## License

MIT or Apache-2.0, at your option.
