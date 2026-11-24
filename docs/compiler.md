---
description: How each JSON Schema keyword becomes a set, what is opaque, and what is refused.
---

# The compiler

`valgebra_jsonschema/schema.py` compiles JSON Schema draft 2020-12, and drafts 2019-09, 07, 06
and 04 through `upgrade`, into valgebra sets. [How it works](how-it-works.md) is the same ground
in brief, with diagrams; [the conformance page](conformance.md) holds the keyword
inventory and the ledger of differences. The universe is
what `json.loads` returns for a JSON text — `None`, `bool`, `int`, a `float` that is not NaN,
`str`, `list`, and `dict` with `str` keys, nested. JSON has no NaN (RFC 8259 §6), and
`json.loads` builds one only from the token `NaN`, so no schema admits it; an infinity is
`json.loads`'s reading of a number past the float range, such as `1e400`, and stands for it. On it the translation is exact for every keyword it accepts, with
patterns read as ECMA-262 defines them; where a pattern uses a construct valgebra's engine
refuses, the schema is refused.

## Keyword semantics

An assertion keyword constrains one kind and passes every other kind: `{"minimum": 3}`
admits `"a"`. Each such keyword compiles to `complement(kind) | refined`, and a schema
object to the meet of its keywords. Where `type` already confines the instance to the
keyword's kind, the guard's other half is empty after the meet and is left out. Where `type`
names arrays alone, `items` and `prefixItems` compile to lists whose every item is a compiled
subschema, and where it names objects alone, `properties`, `required` and
`additionalProperties` to a record whose every value is one: each lies inside the JSON arrays
or objects, so the kind's own set is left out of the meet too, and a walk reads each value
once. `{"type": "array", "items": {"type": "string"}}` is `list[str]`; `patternProperties`
past four patterns is a predicate over every `dict`, and keeps the kind. An array's
kind in a guard is the bare `list`, and an object's the bare `dict`: every compiled set is
met with the JSON values, inside which the bare kind and the JSON one agree, and valgebra
decides the complement of the bare kind where it declines that of the recursive one. The
walk reads whether an array or an object lies outside the kind from its type alone, rather
than from its items.

A schema whose guard reaches past the JSON values is met with them, and only where it is
used as itself. Where `not`, `oneOf`, `if` and `contains` complement a schema, the
complement reads its keywords' meet alone (`Compiler.compile_body`): it is met with a set
inside the JSON values, where the two agree, and valgebra decides the complement of the
bare meet where it declines that of a meet holding the recursive universe.

| keyword | set |
|---|---|
| `type` | union of kinds; `integer` is an `int` that is not a `bool`, or a `float` that is a multiple of 1 |
| `enum`, `const` | union of the constants under JSON equality: `1` and `1.0` are one number, `true` is not `1`; arrays and objects compare structurally |
| `minimum`, `maximum`, `exclusive*` | bound refinements on `int` and `float` |
| `multipleOf` | an integral step up to `2**53` is valgebra's `MultipleOf`; a fractional step, and an integral one past `2**53`, which no float equals, is opaque, checked in exact rational arithmetic |
| `minLength`, `maxLength` | length refinements, in code points |
| `pattern` | `p` becomes `(?s:.*)(?:p')(?s:.*)`, where `p'` is `p` read by ECMA-262's grammar under the `u` flag and written back with every literal a code point, every class a list of code point ranges and General_Category or Script property escapes, `\d`, `\w`, `\s` and their negations the ASCII and ECMA-262 ranges they denote, `.` every code point but the four line terminators, and `\b`, `\B` boundaries of ASCII word characters: ECMA-262 searches, valgebra's `Regex` matches the whole string, and the two dialects read those constructs differently. An escape of punctuation, a lone `]` or `}` and a `{` that opens no count are the character; any other construct invalid under `u` is refused. Lookaheads opening a pattern, `^(?!A)(?=C)B`, are the strings `^B` finds a match in where no match of `A` starts the string and one of `C` does, where `B` alternates at no top level; `^((?!A).)*$` is the strings with no line terminator where `A` occurs nowhere, where `A` matches no empty string and asserts no position. Any other lookaround is outside valgebra's dialect |
| `prefixItems`, `items` | the union of the shorter fixed prefixes and the prefix followed by a repeated tail |
| `minItems`, `maxItems`, `min/maxProperties` | length refinements |
| `contains` | arrays not all of whose elements lie outside the subschema |
| `properties`, `required`, `additionalProperties` | one record: optional and required fields, and a catch-all clause for every other key; a required key outside `properties` takes the additional schema |
| `dependentRequired`, `dependentSchemas` | "key absent, or the dependency holds" |
| `allOf`, `anyOf`, `not` | meet, union, complement within the JSON values |
| `oneOf` | each branch minus every other branch valgebra does not prove disjoint from it |
| `if`, `then`, `else` | `(if & then) | (~if & else)` |
| `unevaluatedProperties`, `unevaluatedItems` | on each case of which in-place subschemas hold, the keys or items no keyword beside it nor holding subschema evaluates (draft 2020-12, section 11), read as the object group or the array of a prefix that leaves them to the subschema: an `anyOf` of more than four branches beside one, more than 64 cases, or a `$ref` reaching itself at one instance is refused |
| `$ref` | resolved against the base URI it sits under, to a resource of the document and a JSON pointer or `$anchor` in it; compiled as a `recursive` fixpoint over its target |
| `$dynamicRef`, `$dynamicAnchor` | a `$dynamicAnchor` names its schema object as an `$anchor` does; a `$dynamicRef` reads the dynamic scope only where its target sets a dynamic anchor of the fragment's name, and names the outermost schema object of the scope that sets one (draft 2020-12, sections 7.1 and 8.2.3.2). Where one schema object of every document sets that name, it is the `$ref` it resolves as; anywhere else the document compiles again keeping the scope, each schema object once per binding of the names its scope holds, and a target the scope chooses is a `recursive` fixpoint, which a reference reaching it again closes |

Annotations assert nothing and are skipped: `title`, `description`, `default`, `examples`,
`deprecated`, `readOnly`, `writeOnly`, `format` (the format-annotation vocabulary is the
default), the `content*` keywords, `$comment`, `$defs`. `$id` and `$anchor` assert nothing
either: `$id` sets the base URI of its resource, which the references inside resolve against
(draft 2020-12, section 8.2), and `$anchor` names its schema object within that resource. An
embedded resource declaring another `$schema` is refused.

## `format`, on request

`format` is an annotation, as draft 2020-12 makes it. `compile_schema(schema, assert_format=True)`
reads it as an assertion over strings, and passes every other kind as any assertion does.

| format | read as |
|---|---|
| `date`, `duration`, `ipv4`, `uuid` | a regular language, so a relation through it is decided |
| `date-time`, `time`, `email`, `hostname`, `ipv6` | a predicate, exact on membership and opaque to a relation |

Any other format is refused, since the assertion left out would admit what the schema refuses.
The results page has [the official suite's counts](results.md#format-on-request), and the
conformance ledger [the one difference](conformance.md#differences-ledger).

## Older drafts

A schema whose `$schema` names draft 2019-09, draft-07, draft-06 or draft-04 is rewritten by
`upgrade` into the draft 2020-12 schema with the same meaning before it is compiled: an
`items` array becomes
`prefixItems` and `additionalItems` becomes `items`; `dependencies` splits into
`dependentRequired` and `dependentSchemas`; a `$ref` drops its siblings, which those
drafts ignore, but for `definitions` and `$defs`; and a keyword the draft does not know is
dropped, since it reads it as an annotation: `prefixItems`, `minContains` or
`dependentRequired` written into any of them, `if`, `then` and `else` in draft-06, and
`const`, `contains` and `propertyNames` in draft-04 too. Draft-04 also writes
`exclusiveMinimum` and `exclusiveMaximum` as flags on `minimum` and `maximum`, and `$id`
as `id`; both are rewritten. An older `$id` whose fragment is a plain name, `#foo`, names its
schema object as `$anchor` does, and is rewritten to one. Only keywords that hold subschemas
are descended into, so a property named `items` stays a name.

Draft 2019-09 differs less. A `$ref` keeps its siblings, `dependencies` is no keyword, so it is
refused as in 2020-12, and an array `items` and its recursion read apart from 2020-12.
`$recursiveAnchor: true` on the root of a resource is a `$dynamicAnchor` whose name is empty,
and `$recursiveRef: "#"` the `$dynamicRef: "#"` that reads it, as the draft 2020-12 release
notes say the two pairs agree: the reference names the root of the resource holding it, or,
where that root sets the anchor, the outermost schema in the dynamic scope that sets it (draft
2019-09, section 8.2.4.2.2). The empty name is one no draft 2020-12 anchor may spell, so it meets
no anchor of a document. A `$recursiveAnchor: true` on a schema object starting no resource is
refused, since 2019-09's text reads one anywhere in the scope by its resource's root and the
release notes hold it to a root; so is a `$recursiveRef` of any other value.

## Keys

`patternProperties` and a `propertyNames` of words are clauses over keys narrowed by a pattern, so a
relation reads them: `{"patternProperties": {"^x-": {"type": "string"}}, "additionalProperties": false}`
is `subset` of an object of strings and the converse is `not_subset`. A key takes the schema of every
pattern it matches, a conjunction, and valgebra reads two clauses over one key as a disjunction, so the
keys are split where the patterns part, into up to sixteen cells, and no two clauses share a key.
`propertyNames: true` names every key, as `{}` does, and `propertyNames: false` names none, so the one
object it admits is the empty one. A `propertyNames` spelling its names out, an `enum`, a `const`, or an
`anyOf` or `oneOf` of them, is the closed record of those keys, each optional: keys as `properties` writes
them, so `{"propertyNames": {"enum": ["k", "j"]}}` over objects is `subset` of
`{"properties": {"k": {}, "j": {}}, "additionalProperties": false}` and the converse too. A name is a
string (draft 2020-12, section 10.3.2.4), so a value that is not one names no key.

`minProperties` and `maxProperties` count a record's keys. A `minProperties` counting every key the
record can hold requires each, so `{"propertyNames": {"enum": ["k", "j"]}, "minProperties": 2}` over
objects is `subset` of the object requiring `k` and `j`; a `maxProperties` counting the required keys
admits no other, so `{"required": ["k"], "maxProperties": 1}` is `subset` of the closed record of `k`.
A count of fewer keys than the record holds proves no one of them: with `"minProperties": 1` the first
is `undecided` below the object requiring `k`, which `{"j": 1}` refutes.

## What a member holds below

`Compiler.below(path)` returns the values a member of the root holds at `path`, a sequence of
keys and `ITEM`, any element of an array: the meet of what each keyword says of them, through
`properties`, `patternProperties`, `additionalProperties`, `prefixItems`, `items`, `allOf`,
`anyOf`, `oneOf`, `if` with `else`, listed values and a `$ref` resolved against the base URI it
sits under. It is an upper bound: `not`, a lone `if`, `$dynamicRef` and `unevaluatedProperties`
narrow nothing, so every value a member holds at the path lies inside, and the set may hold one
no member does. Whether the bound is tight is a relation valgebra decides against the whole
schema.

```python
from valgebra_jsonschema import ITEM, Compiler, compile_schema

page = {
    "$defs": {"run": {"properties": {"tags": {"type": "array", "items": {"enum": ["a", "b"]}}}}},
    "type": "object",
    "properties": {"runs": {"type": "array", "items": {"$ref": "#/$defs/run"}}},
}
tags = Compiler(page).below(("runs", ITEM, "tags", ITEM))
assert tags.is_equivalent(compile_schema({"enum": ["a", "b"]}))
```

## A failure in the schema's text

valgebra matches a `pattern` in its own dialect: the compiler writes it unanchored, as
ECMA-262's `test` searches, and each class atom as a code point, so a failure names that text,
`a string matching '(?s:.*)(?:^[\\x{61}-\\x{66}]{2}$)(?s:.*)'` for `^[a-f]{2}$`.
`Compiler.reworded` returns a failure with each pattern this compiler wrote named in the schema's
text, in `expected` and in `message`; `Compiler.patterns` holds the texts.

```python
from valgebra import ValidationError
from valgebra_jsonschema import Compiler

schema = {"type": "string", "pattern": "^[a-f0-9]{24}$"}
compiler = Compiler(schema)
ids = compiler.compile(schema)
assert not ids.is_valid("nope")
try:
    ids.validate("nope")
except ValidationError as error:
    named = compiler.reworded(error.errors[0])
    assert named["expected"] == "a string matching '^[a-f0-9]{24}$'"
```

A failure names a pattern this way wherever a `pattern`, a `propertyNames` pattern or a key of a
closed `patternProperties` fails. A lookahead is read as parts, none of which is the pattern, and
a failure names the part as valgebra gave it; so does a text two patterns translate to, as
`^\d$` and `^[0-9]$` do. `compile_schema` keeps its compiler, and `compile_with_fallbacks`
returns the one it read the schema with. valgebra holds no display text: a marker's fields are
its identity, so a text stored beside a `Regex` would make one pattern two markers that compare
and hash apart.

## Opaque keywords

These have no counterpart in valgebra's set language, so they compile to
predicates: membership is exact, and a relation that has to look inside one answers
"undecided", never a wrong proof. `Compiler.opaque` lists those a schema used.
`uniqueItems` is one callable in every schema, and a fractional `multipleOf` one per step,
so valgebra relates each to itself: `{"uniqueItems": true}` compiled twice is proved below
itself. The predicates of `minContains`, `maxContains` and `propertyNames` hold a set
compiled from their subschema, and each compilation holds its own.

| keyword | why |
|---|---|
| `patternProperties`, past four patterns or in a schema past valgebra's limit | a clause per cell of keys, and the cells number two to the patterns |
| `propertyNames`, but `true`, `false`, one spelling its names out, and one reading only `pattern`, `minLength`, `maxLength`, `type` | a key is narrowed by words or listed, and no other schema names them |
| `uniqueItems` | needs equality across elements |
| `minContains`, `maxContains` | need counting |
| `multipleOf` with a fractional step | `0.0075 % 0.0001` is not zero in binary floating point |
| `oneOf`, and a `$ref` to a definition that does not reach itself, in a schema past valgebra's limit with keys read by predicate too | "exactly one" of two branches is their exclusive or, which no formula writes with each branch once, and a definition inlined at each use is written once per use: the union is met with a count of the branches that hold, and the reference checks the definition's own set |

## Refused, and ignored

`Unsupported` names the keyword: references to a document neither the one compiled nor
`documents` holds, a reference to a URI two schema objects of one document claim or to an anchor
two of one resource set, a supplied document in a dialect not read where a reference names it,
an embedded `$id` whose resource declares another `$schema`, a draft other than 2020-12,
2019-09, 07, 06 and 04 or a meta-schema read [as above](#registered-keywords), a draft 2019-09 `$recursiveAnchor: true` on a schema object starting no
resource, and a property name holding a lone surrogate. A keyword outside the vocabularies is an
annotation, as draft 2020-12 says, and `Compiler.ignored` records it.

## Registered keywords

Draft 2020-12 lets anyone define a keyword, and says implementations "SHOULD treat keywords they
do not support as annotations", "save for explicit agreement" (draft 2020-12, section 6.5).
Registering one is that agreement: `compile_schema(schema, keywords={name: Keyword(kind,
holds)})` reads `name` as an assertion on `kind`, `"number"`, `"string"`, `"array"` or
`"object"`, every other kind passing as an assertion keyword's does, and `holds(instance, value)`
answering for an instance of the kind, `value` being the keyword's value in the schema. It is an
opaque predicate, recorded in `Compiler.opaque`: membership is exact, and a relation reading
inside it is `undecided`. A unit quaternion, a sum of squares no JSON Schema keyword states, is
one:

```python
import math

from valgebra_jsonschema import Keyword, compile_schema


def unit(quaternion, tolerance):
    return len(quaternion) == 4 and abs(math.fsum(x * x for x in quaternion) - 1) <= tolerance


FOUR = {"type": "array", "prefixItems": [{"type": "number"}] * 4, "minItems": 4, "maxItems": 4}
QUATERNION = {**FOUR, "x-robot-unit-quaternion": 1e-6}
reading = compile_schema(QUATERNION, keywords={"x-robot-unit-quaternion": Keyword("array", unit)})
assert reading.is_valid([0.5, 0.5, 0.5, 0.5])
assert not reading.is_valid([0, 0, 0, 5])
assert compile_schema(QUATERNION).is_valid([0, 0, 0, 5])
assert compile_schema(FOUR).relation_to(reading) == "undecided"
```

A keyword draft 2020-12 defines is not registered, and the attempt raises `ValueError` naming it.
An unregistered keyword stays an annotation.

A schema may name its own meta-schema in `$schema`, whose `$vocabulary` lists the vocabularies
of its dialect, each required or optional. Passed among `documents`, that meta-schema is read:
`compile_schema(schema, documents={uri: meta}, vocabularies={vocabulary: {name: Keyword}})` reads
each vocabulary it names outside draft 2020-12's through the keywords registered for it. An
implementation not recognizing a required vocabulary "MUST refuse to process any schemas that
declare this meta-schema" (draft 2020-12, section 8.1.2), so `UnsupportedDialect` names one no
caller registers, and an optional one's keywords stay annotations. A dialect leaving out core,
applicator, unevaluated or validation is refused too: its keywords would be annotations there,
which the compiler asserts. `dialect(schema, documents, vocabularies)` answers which keywords a
schema's meta-schema registers.

## Measured

```bash
uv run python tools/suite.py --check docs/studies/json-schema-test-suite.json
```

The official JSON-Schema-Test-Suite at commit `89e83a740146`, vendored with its MIT
license. Draft 2020-12, with the four optional files on regular expressions and large
numbers: 1393 cases run, 1393 passed, 0 failed; 5 skipped, each naming a custom meta-schema as
its dialect; 96 of the run cases go through an opaque predicate. A case's remote documents are the suite's
`remotes/`, vendored with it, and the drafts' meta-schemas from the `jsonschema-specifications`
package, passed as `documents`. Draft-07, through `upgrade`:

```bash
uv run python tools/suite.py --draft 7 --check docs/studies/json-schema-test-suite-draft7.json
```

929 cases run, 929 passed, 0 failed; 0 skipped. Draft
2019-09, through `upgrade`:

```bash
uv run python tools/suite.py --draft 2019-09 --check docs/studies/json-schema-test-suite-draft2019-09.json
```

1256 cases run, 1256 passed, 0 failed; 5 skipped, the same five. Draft-06 and draft-04,
through `upgrade`:

```bash
uv run python tools/suite.py --draft 6 --check docs/studies/json-schema-test-suite-draft6.json
uv run python tools/suite.py --draft 4 --check docs/studies/json-schema-test-suite-draft4.json
```

Draft-06, 841 cases run, 841 passed, 0 failed; 0 skipped. Draft-04, 618 cases run, 618 passed,
0 failed; 0 skipped.

```bash
uv run python tools/suite.py --reference
```

On the same optional files the `jsonschema` package 4.26.0 passes 42 of the 74
`ecmascript-regex` cases and 12 of the 12 `non-bmp-regex` cases: it reads patterns with
Python's `re`, where `\d` matches any Unicode digit and `$` matches before a final newline.
