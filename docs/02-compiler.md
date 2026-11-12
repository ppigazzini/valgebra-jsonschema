# The compiler

`valgebra_jsonschema/schema.py` compiles JSON Schema draft 2020-12, and drafts 2019-09, 07, 06
and 04 through `upgrade`, into valgebra sets. [`03-conformance.md`](03-conformance.md) holds the keyword inventory
and the ledger of differences. The universe is
what `json.loads` returns — `None`, `bool`, `int`, `float`, `str`, `list`, and `dict` with
`str` keys, nested. On it the translation is exact for every keyword it accepts, with
patterns read as ECMA-262 defines them; where a pattern uses a construct valgebra's engine
refuses, the schema is refused.

## Keyword semantics

An assertion keyword constrains one kind and passes every other kind: `{"minimum": 3}`
admits `"a"`. Each such keyword compiles to `complement(kind) | refined`, and a schema
object to the meet of its keywords. Where `type` already confines the instance to the
keyword's kind, the guard's other half is empty after the meet and is left out.

| keyword | set |
|---|---|
| `type` | union of kinds; `integer` is an `int` that is not a `bool`, or a `float` that is a multiple of 1 |
| `enum`, `const` | union of the constants under JSON equality: `1` and `1.0` are one number, `true` is not `1`; arrays and objects compare structurally |
| `minimum`, `maximum`, `exclusive*` | bound refinements on `int` and `float` |
| `multipleOf` | an integral step is valgebra's `MultipleOf`; a fractional step is opaque, checked in exact rational arithmetic |
| `minLength`, `maxLength` | length refinements, in code points |
| `pattern` | `p` becomes `(?s:.*)(?:p')(?s:.*)`, where `p'` is `p` read by ECMA-262's grammar under the `u` flag and written back with every literal a code point, every class a list of code point ranges and General_Category or Script property escapes, `\d`, `\w`, `\s` and their negations the ASCII and ECMA-262 ranges they denote, `.` every code point but the four line terminators, and `\b`, `\B` boundaries of ASCII word characters: ECMA-262 searches, valgebra's `Regex` matches the whole string, and the two dialects read those constructs differently. An escape of punctuation, a lone `]` or `}` and a `{` that opens no count are the character; any other construct invalid under `u` is refused |
| `prefixItems`, `items` | the union of the shorter fixed prefixes and the prefix followed by a repeated tail |
| `minItems`, `maxItems`, `min/maxProperties` | length refinements |
| `contains` | arrays not all of whose elements lie outside the subschema |
| `properties`, `required`, `additionalProperties` | one record: optional and required fields, and a catch-all clause for every other key; a required key outside `properties` takes the additional schema |
| `dependentRequired`, `dependentSchemas` | "key absent, or the dependency holds" |
| `allOf`, `anyOf`, `not` | meet, union, complement within the JSON values |
| `oneOf` | each branch minus every other branch valgebra does not prove disjoint from it |
| `if`, `then`, `else` | `(if & then) | (~if & else)` |
| `$ref` | a local JSON pointer, compiled as a `recursive` fixpoint over its target |

Annotations assert nothing and are skipped: `title`, `description`, `default`, `examples`,
`deprecated`, `readOnly`, `writeOnly`, `format` (the format-annotation vocabulary is the
default), the `content*` keywords, `$comment`, `$defs`. A root `$id` is skipped, and so is
an embedded one whose resource holds no reference or anchor and declares no other `$schema`:
the base URI it sets is one nothing inside resolves against.

## `format`, on request

`format` is an annotation, as draft 2020-12 makes it. `compile_schema(schema, assert_format=True)`
reads it as an assertion over strings, and passes every other kind as any assertion does.

| format | read as |
|---|---|
| `date`, `duration`, `ipv4`, `uuid` | a regular language, so a relation through it is decided |
| `date-time`, `time`, `email`, `hostname`, `ipv6` | a predicate, exact on membership and opaque to a relation |

Any other format is refused, since the assertion left out would admit what the schema refuses.
[`04-results.md`](04-results.md#format-on-request) has the official suite's counts, and
[`03-conformance.md`](03-conformance.md#differences-ledger) the one difference.

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
as `id`; both are rewritten. Only keywords that hold subschemas are descended into, so a
property named `items` stays a name.

Draft 2019-09 differs less. A `$ref` keeps its siblings, `dependencies` is no keyword, so it is
refused as in 2020-12, and two keywords read apart from 2020-12: an array `items`, and
`$recursiveRef`. `$recursiveRef: "#"` is `$ref: "#"` wherever one resource holds it, which is
every document compiled here, since a reference inside an embedded `$id` is refused. Any other
value is refused.

## Keys

`patternProperties` and a `propertyNames` of words are clauses over keys narrowed by a pattern, so a
relation reads them: `{"patternProperties": {"^x-": {"type": "string"}}, "additionalProperties": false}`
is `subset` of an object of strings and the converse is `not_subset`. A key takes the schema of every
pattern it matches, a conjunction, and valgebra reads two clauses over one key as a disjunction, so the
keys are split where the patterns part, into up to sixteen cells, and no two clauses share a key.

## Opaque keywords

These have no counterpart in valgebra's set language, so they compile to
predicates: membership is exact, and a relation that has to look inside one answers
"undecided", never a wrong proof. `Compiler.opaque` lists those a schema used.

| keyword | why |
|---|---|
| `patternProperties`, past four patterns or in a schema past valgebra's limit | a clause per cell of keys, and the cells number two to the patterns |
| `propertyNames`, reading more than `pattern`, `minLength`, `maxLength`, `type` | a key is narrowed by words, and no other schema names them |
| `uniqueItems` | needs equality across elements |
| `minContains`, `maxContains` | need counting |
| `multipleOf` with a fractional step | `0.0075 % 0.0001` is not zero in binary floating point |

## Refused, and ignored

`Unsupported` names the keyword: `unevaluatedProperties`, `unevaluatedItems`,
`$dynamicRef`, `$dynamicAnchor`, `$anchor` references, references outside the document, an
embedded `$id` whose resource holds a reference or an anchor or declares another `$schema`,
a pointer through any embedded `$id`, a draft other than 2020-12, 2019-09, 07, 06 and 04, and a
property name ending in `?` (valgebra reads that suffix as "optional"). A keyword outside the
vocabularies is an annotation, as draft 2020-12 says, and `Compiler.ignored` records it.

## Measured

```bash
uv run python tools/suite.py --check docs/studies/json-schema-test-suite.json
```

The official JSON-Schema-Test-Suite at commit `89e83a740146`, vendored with its MIT
license. Draft 2020-12, with the four optional files on regular expressions and large
numbers: 1071 cases run, 1071 passed, 0 failed; 327 skipped by the refusals above; 99 of
the run cases go through an opaque predicate. Draft-07, through `upgrade`:

```bash
uv run python tools/suite.py --draft 7 --check docs/studies/json-schema-test-suite-draft7.json
```

870 cases run, 870 passed, 0 failed; 59 skipped (remote references and `$id` scopes). Draft
2019-09, through `upgrade`:

```bash
uv run python tools/suite.py --draft 2019-09 --check docs/studies/json-schema-test-suite-draft2019-09.json
```

961 cases run, 961 passed, 0 failed; 300 skipped, by the same refusals. Draft-06 and draft-04,
through `upgrade`:

```bash
uv run python tools/suite.py --draft 6 --check docs/studies/json-schema-test-suite-draft6.json
uv run python tools/suite.py --draft 4 --check docs/studies/json-schema-test-suite-draft4.json
```

Draft-06, 790 cases run, 790 passed, 0 failed; 51 skipped. Draft-04, 587 cases run, 587
passed, 0 failed; 31 skipped. Both skip remote references, `$id` scopes and anchors.

```bash
uv run python tools/suite.py --reference
```

On the same optional files the `jsonschema` package 4.26.0 passes 42 of the 74
`ecmascript-regex` cases and 12 of the 12 `non-bmp-regex` cases: it reads patterns with
Python's `re`, where `\d` matches any Unicode digit and `$` matches before a final newline.
