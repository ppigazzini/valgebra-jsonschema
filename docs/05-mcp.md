# Reading an MCP tool

A [Model Context Protocol](https://modelcontextprotocol.io) server lists each tool with an
`inputSchema` and, optionally, an `outputSchema`. `read_tool` reads one entry into its two
contracts, so a call and its result can be checked, and two versions of a tool compared:

```python
from valgebra_jsonschema import read_tool


def listing(units):
    return {
        "name": "get_weather",
        "inputSchema": {
            "type": "object",
            "properties": {"location": {"type": "string"}, "units": {"enum": units}},
            "required": ["location"],
        },
        "outputSchema": {
            "type": "object",
            "properties": {"reading": {"type": "number"}},
            "required": ["reading"],
        },
    }


old = read_tool(listing(["celsius"]))
new = read_tool(listing(["celsius", "kelvin"]))

assert old.arguments.is_valid({"location": "Paris"})
assert not old.arguments.is_valid({"location": "Paris", "units": "kelvin"})
assert old.result.is_valid({"reading": 21.5})

# A new version replaces an old one where it takes every call the old one took,
# and returns only what the old one promised.
assert old.arguments.relation_to(new.arguments) == "subset"
assert new.result.relation_to(old.result) == "subset"
```

## Dialects

The protocol states a schema's dialect, and each reads here as:

| a document's `$schema` | read as |
|---|---|
| absent | draft 2020-12, as the protocol states |
| draft 2020-12 | draft 2020-12 |
| draft 2019-09 | rewritten by `upgrade`: an array `items`, and `$recursiveRef` |
| draft-07, draft-06, draft-04 | rewritten by `upgrade`, as [`02-compiler.md`](02-compiler.md#older-drafts) says |
| anything else | `UnsupportedDialect`, whose message says the dialect is not supported |

`UnsupportedDialect` is an `Unsupported`, so a caller refusing a schema it cannot read catches
both, and one answering the protocol's error can tell them apart. A document in another
dialect with no `$schema` is read as 2020-12: name its dialect with `{"$schema": uri, **schema}`.

## What a tool's schema may hold

- **Any 2020-12 keyword.** [`03-conformance.md`](03-conformance.md#the-inventory) lists what each
  does here. A keyword that is refused raises `Unsupported` naming it, and is never skipped.
- **`format` is an annotation**, as 2020-12 makes it, so it admits every value.
- **No reference is fetched.** A `$ref` outside the document is refused, which is how the protocol's
  rule against dereferencing a network reference reads here.
- **Bounds hold what a document may cost.** A document past `MAX_NESTING` is refused before it is
  walked, and valgebra refuses a set past the bounds it holds.
- **`inputSchema` names an object**: `type: "object"`, or a root that is a bare `$ref` to one, as
  zod's named schemas are. `outputSchema` may be any schema.

## What a model vendor enforces

A tool author emits a subset of 2020-12 for a model to generate from, and which subset is the
vendor's. OpenAI's strict structured outputs ask `additionalProperties: false` and every property
required, and leave out `allOf`, `not` and `if`. Anthropic's strict tools leave out numeric and
length constraints and recursion. Gemini's `responseSchema` is an OpenAPI 3.0 subset, whose
`nullable` is outside the vocabularies, so here it is an annotation that asserts nothing. These
are the vendors' to change, so no test here holds them. Whichever subset a tool emits, a contract
checks the membership of the value returned.
