---
description: Tasks done end to end with a JSON Schema in hand -- a model's tool call, a schema change checked before release, a result read closed, a schema split across documents, files checked against a schema, and what a schema asserts.
---

# Recipes

Each recipe is one task done end to end with a JSON Schema already in hand, and each says what
it cannot do. Each block runs as written. What a keyword compiles to is
[the compiler page](compiler.md)'s, and where a reading differs from another validator's is
[the ledger of differences](conformance.md#differences-ledger)'s.

## A model's tool call, against the schema it was shown

A model calling a tool writes the arguments as JSON against the `inputSchema` it was shown, and
nothing about the model makes them belong. Compiling that same schema checks them, so the schema
is written once: what the model reads and what the call is held to are one document. `load`
parses the arguments and checks them in one call, and its error names each wrong argument, which
the server returns to the model as a tool error:

```python
from valgebra import ValidationError
from valgebra_jsonschema import read_tool

GET_WEATHER = {
    "name": "get_weather",
    "description": "The forecast for a city.",
    "inputSchema": {
        "type": "object",
        "properties": {
            "city": {"type": "string", "minLength": 1},
            "unit": {"enum": ["celsius", "fahrenheit"]},
            "days": {"type": "integer", "minimum": 1, "maximum": 7},
        },
        "required": ["city", "unit"],
        "additionalProperties": False,
    },
}
ARGUMENTS = read_tool(GET_WEATHER).arguments


def call(arguments: str) -> dict[str, object]:
    """Answer a `tools/call` of `get_weather`: the forecast, or an error the model reads."""
    try:
        parsed = ARGUMENTS.load(arguments)
    except ValidationError as error:
        return {"content": [{"type": "text", "text": str(error)}], "isError": True}
    return {"content": [{"type": "text", "text": f"{parsed['city']}: sunny"}], "isError": False}


refused = call('{"city": "Turin", "unit": "kelvin", "country": "IT"}')
assert refused["isError"]
assert refused["content"][0]["text"].splitlines() == [
    "2 validation errors:",
    (
        "at unit: expected one of: the literal 'celsius', the literal 'fahrenheit', "
        "got 'kelvin' [union_error]"
    ),
    "at country: expected no unexpected key, got 'country' [extra_forbidden]",
]
assert not call('{"city": "Turin", "unit": "celsius", "days": 3.0}')["isError"]
```

`"days": 3.0` meets `"type": "integer"`: JSON Schema reads a number by its value, and `3.0` is
the integer 3, where valgebra's own `int` refuses it
([valgebra's recipe for a tool call](https://ppigazzini.github.io/valgebra/get-started/recipes/#a-models-tool-call)
writes the schema a second time, as a `TypedDict`). An argument the tool does not take is
refused by `additionalProperties: false`; a schema without it admits any other key with any
value.

**It checks, and does not convert.** `"days": "3"` is a string, and the model is told so rather
than the value read as a number. `format` asserts nothing unless asked:
`read_tool(spec, assert_format=True)` reads nine formats as assertions and refuses a schema
naming any other ([what a tool's schema may hold](mcp.md#what-a-tools-schema-may-hold)).

## A schema change, checked before release

Whether a new version of a schema breaks its users is a question about two sets, and which one
must hold the other turns on who writes the value
([Habib et al. 2021](https://arxiv.org/abs/1911.12651)). A **request** is written by an old
client and read by the new server, so every old value must be a new one: the old schema lies
inside the new. A **response** is written by the new server and read by an old client, so the
new schema must lie inside the old. Two documents can differ where their sets do not, so the
check compares the sets, not the text:

```python
from valgebra_jsonschema import compile_schema

ORDER_V1 = {
    "type": "object",
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "status": {"enum": ["open", "paid"]},
    },
    "required": ["id", "status"],
}
# The same set, its fields written once under `$defs`.
ORDER_V1_DEFS = {
    "$defs": {"id": {"type": "integer", "minimum": 1}, "status": {"enum": ["open", "paid"]}},
    "type": "object",
    "properties": {"id": {"$ref": "#/$defs/id"}, "status": {"$ref": "#/$defs/status"}},
    "required": ["id", "status"],
}
# A status added.
ORDER_V2 = {
    **ORDER_V1,
    "properties": {**ORDER_V1["properties"], "status": {"enum": ["open", "paid", "refunded"]}},
}
# A field required.
ORDER_V3 = {
    **ORDER_V1,
    "properties": {**ORDER_V1["properties"], "currency": {"type": "string"}},
    "required": ["id", "status", "currency"],
}


def check(old: object, new: object, role: str) -> int:
    """Return a CI step's exit status for a change: 0 compatible, 1 a break, 2 undecided."""
    before, after = compile_schema(old), compile_schema(new)
    inner, outer = (before, after) if role == "request" else (after, before)
    return {"subset": 0, "not_subset": 1, "undecided": 2}[inner.relation_to(outer)]


for role in ("request", "response"):
    assert check(ORDER_V1, ORDER_V1_DEFS, role) == 0
assert check(ORDER_V1, ORDER_V2, "request") == 0
assert check(ORDER_V1, ORDER_V2, "response") == 1  # an old client refuses "refunded"
assert check(ORDER_V1, ORDER_V3, "request") == 1  # an old client sends no currency
assert check(ORDER_V1, ORDER_V3, "response") == 0
assert check({"type": "array"}, {"type": "array", "uniqueItems": True}, "request") == 2
```

`ORDER_V3` holds as a response because the first version is open: it admits a `currency` of any
value already, so every new response is one an old client reads.

**Undecided is not compatible.** `uniqueItems` is an
[opaque keyword](compiler.md#opaque-keywords), exact on membership, and a relation that
looks inside one answers `undecided`: `[1, 1]` is an array outside the second schema, and the
relation does not refute the request. The exit status keeps the two apart, so a gate passing on
0 alone passes no change it could not decide; a test asserting a compatibility compares with
`"subset"`, never with `!= "not_subset"`. A proof is about the schemas, not about data stored
under the old one, which
[valgebra's recipe for stored data](https://ppigazzini.github.io/valgebra/get-started/recipes/#stored-data-against-a-new-schema)
reads row by row.

## A result read as another step's input

A step's result feeds a later step whose input schema names the same values under other keys:
the result's `a` and `b` are the input's `x` and `y`. Whether every result is an input is one
inclusion once the input is read over the result's keys, and `renamed` reads it so, renaming
the keys each keyword names rather than the text. The result's two keys agree, and the input's
`if` reads exactly that agreement, so neither field alone would answer it:

```python
from valgebra_jsonschema import compile_schema, renamed

RESULT = {
    "type": "object",
    "required": ["a", "b"],
    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    "oneOf": [
        {"properties": {"a": {"const": 1}, "b": {"const": 1}}},
        {"properties": {"a": {"const": 2}, "b": {"const": 2}}},
    ],
}
INPUT = {
    "type": "object",
    "required": ["x", "y"],
    "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
    "if": {"properties": {"x": {"const": 1}}},
    "then": {"properties": {"y": {"const": 1}}},
    "else": {"properties": {"y": {"const": 2}}},
}
over_result = renamed(INPUT, {"x": "a", "y": "b"})
assert compile_schema(RESULT).relation_to(compile_schema(over_result)) == "subset"
```

The renaming is a permutation of the key strings, so a key the input names under a new name is
given the old one, and no two keys of a member become one. A keyword naming keys a renaming
cannot follow is refused: `patternProperties`, a `propertyNames` other than a list of names, and
a reference anywhere but into the definitions.

## A result read closed, as an assumption

A published result is open: a key it does not name may hold any value, so a detection meets a
distance argument through a `unit` and a `value` it never names. A server that sends no key its
schema does not name is described by the schema read closed, and `closed` reads it so: the root
with `unevaluatedProperties: false`, which counts a key a `$ref` or an `allOf` declares as named,
where `additionalProperties: false` sees its sibling `properties` alone and here empties the
result:

```python
from valgebra import intersection, nothing

from valgebra_jsonschema import closed, compile_schema

DETECTION = {
    "$defs": {
        "Found": {
            "type": "object",
            "properties": {"object_id": {"type": "string"}},
            "required": ["object_id"],
        }
    },
    "allOf": [{"$ref": "#/$defs/Found"}],
    "properties": {"confidence": {"type": "number", "minimum": 0, "maximum": 1}},
    "required": ["confidence"],
}
DISTANCE = {
    "type": "object",
    "properties": {
        "unit": {"type": "string", "const": "m"},
        "value": {"type": "number", "minimum": 0.2, "maximum": 0.6},
    },
    "required": ["unit", "value"],
}
argument = compile_schema(DISTANCE)
assert intersection(compile_schema(DETECTION), argument).relation_to(nothing) == "not_subset"
reading = compile_schema(closed(DETECTION))
assert intersection(reading, argument).relation_to(nothing) == "subset"
assert reading.is_valid({"object_id": "obj_1", "confidence": 0.9})
assert not reading.is_valid({"object_id": "obj_1", "confidence": 0.9, "unit": "m"})
sibling = compile_schema({**DETECTION, "additionalProperties": False})
assert sibling.relation_to(nothing) == "subset"
```

The closed reading is narrower than the published one, never wider, so a proof over it is a
proof under the assumption that the server sends no other key, and a result carrying one breaks
the assumption rather than the schema. Only the root is closed: a record under a property stays
as written. An older draft's document is upgraded first, and the compiler refuses the closing
where it refuses `unevaluatedProperties` beside the root's other keywords, an `anyOf` of more
than four branches among them.

## A schema split across documents

A `$ref` may name another document by its URI. Nothing is fetched: each document a reference
may name is passed in `documents`, keyed by the URI the reference resolves to, and a reference
to any other is refused when the schema compiles, never when a value is checked:

```python
from valgebra_jsonschema import Unsupported, compile_schema

ADDRESS = {
    "$id": "https://example.com/schemas/address.json",
    "type": "object",
    "properties": {
        "street": {"type": "string"},
        "country": {"type": "string", "pattern": "^[A-Z]{2}$"},
    },
    "required": ["street", "country"],
}
CUSTOMER = {
    "$id": "https://example.com/schemas/customer.json",
    "type": "object",
    "properties": {"name": {"type": "string"}, "shipping": {"$ref": "address.json"}},
    "required": ["name"],
}

customers = compile_schema(CUSTOMER, documents={ADDRESS["$id"]: ADDRESS})
assert customers.is_valid({"name": "Ada", "shipping": {"street": "Via Roma 1", "country": "IT"}})
assert not customers.is_valid(
    {"name": "Ada", "shipping": {"street": "Via Roma 1", "country": "Italy"}}
)

refused = False
try:
    compile_schema(CUSTOMER)
except Unsupported as error:
    refused = True
    assert str(error) == "$ref 'address.json' names a document this one does not hold"
assert refused
```

`address.json` resolves against the customer schema's `$id` to the address schema's. Documents
kept as files are read the same way: each file parsed, keyed by its `$id`, or, where it declares
none, by the URI the references name it by. A supplied document declaring no `$schema` is read
in the compiled document's dialect.

**A document on the network is the caller's to fetch.** A schema naming one by an `https` URI
compiles only once the caller has fetched the document and passed it, so which hosts to trust is
the caller's decision; a tool's schema reads the protocol's rule against dereferencing a network
reference the same way ([what a tool's schema may hold](mcp.md#what-a-tools-schema-may-hold)). A URI two schema
objects of one document claim is refused where a reference names it
([the inventory](conformance.md#the-inventory)).

## Files checked against a schema

A directory of JSON files, configurations or fixtures, is checked against one schema file by
file. `validate_json` parses each file's bytes and checks the value in one call, building no
error for a file that belongs, and each failure carries the path to the wrong value and a code:

```python
from valgebra import ValidationError
from valgebra_jsonschema import compile_schema

SERVICE = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "release": {"type": "string", "format": "date"},
        "port": {"type": "integer", "minimum": 1, "maximum": 65535},
    },
    "required": ["name", "release"],
    "additionalProperties": False,
}
SERVICES = compile_schema(SERVICE, assert_format=True)


def problems(text: bytes) -> list[tuple[tuple[object, ...], str]]:
    """Return the path and the code of each reason the schema refuses a file's bytes."""
    try:
        SERVICES.validate_json(text)
    except ValidationError as error:
        return [(item["path"], item["code"]) for item in error.errors]
    return []


# Each file's bytes, as `path.read_bytes()` returns them.
files = {
    "web.json": b'{"name": "web", "release": "2026-11-18", "port": 8080}',
    "jobs.json": b'{"name": "", "release": "18/11/2026", "port": 0, "debug": true}',
    "admin.json": b'{"name": "admin"',
}
assert {name: problems(text) for name, text in files.items()} == {
    "web.json": [],
    "jobs.json": [
        (("name",), "too_short"),
        (("port",), "union_error"),
        (("release",), "union_error"),
        (("debug",), "extra_forbidden"),
    ],
    "admin.json": [((), "json_invalid")],
}
```

**Report the path and the code, not the message.** A message renders the set the schema
compiled to, not the keyword it was written as: a `format` reads as its predicate or its
regular expression, a `pattern` as its translation into valgebra's dialect, and an `integer`
with a bound as `int and >= 1, float and >= 1`. The path names the value and the code the
failed check, and both are stable. A file in TOML or YAML is parsed by the library that owns the
format, and the value it returns checked with `validate`, which reads only what `json.loads`
could return: a TOML date is no JSON value, and no schema admits it. `assert_format=True`
refuses a schema whose `format` is one of the many it does not read, `uri` among them, so a
schema from elsewhere compiles with formats as annotations or not at all.

## What a schema asserts

A keyword outside the vocabularies is an annotation, as draft 2020-12 says, so a misspelled one
asserts nothing and admits every value. `compile_with_fallbacks` returns the compiler beside the
set, and the compiler records each keyword it read as an annotation in `ignored` and each it
read as an opaque predicate in `opaque`; `compile_schema` refuses a keyword it does not read:

```python
from valgebra_jsonschema import Unsupported, compile_schema, compile_with_fallbacks

PROFILE = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "maxLenght": 20},
        "tags": {"type": "array", "uniqueItems": True},
    },
}
compiler, profiles = compile_with_fallbacks(PROFILE, PROFILE)
assert compiler.ignored == {"maxLenght"}
assert compiler.opaque == {"uniqueItems"}
assert profiles.is_valid({"name": "a" * 50})  # the misspelled bound bounds nothing

refused = False
try:
    compile_schema({"type": "object", "dependencies": {"card": ["billing"]}})
except Unsupported as error:
    refused = True
    assert str(error) == "keyword 'dependencies' is not supported"
assert refused
```

A schema's author reads `ignored` for a keyword meant to assert, and `opaque` for the keywords a
relation through the schema answers `undecided` across. `dependencies`, a draft-07 keyword draft
2020-12 removed, is refused in a 2020-12 schema rather than read as an annotation, since its
author wrote it to a draft where it asserts; a schema declaring draft-07 compiles it.

**`compile_with_fallbacks` reads draft 2020-12.** It compiles the document as given, so an older
one goes through `upgrade(document, older(document))` first, which `compile_schema` does itself.
A `$defs` entry no reference names is never compiled, so a keyword in it is neither recorded nor
checked.
