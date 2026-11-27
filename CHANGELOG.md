# Changelog

All notable changes to valgebra-jsonschema are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- `keywordLocation` is a JSON Pointer, as draft 2020-12 asks (section 12.3.1) and prints
  (section 12.4.2): `/properties/pos/$ref/maximum` where it was `#/properties/pos/$ref/maximum`.
  The `#` made it a URI fragment, which percent-encodes a key as a pointer does not, so a key
  holding `%41` read back as one named `A`; a pointer walk reads each location back to the
  keyword it names.

## [0.0.8] - 2026-11-26

A release on valgebra 0.0.36, with no change to the compiler. An excluded middle,
`{"anyOf": [{"not": C}, C]}`, leaves no array out under emptiness as under the relation, with
`C` a list `const` or an `enum` of lists, and a meet no reading decides is declined at a cost
bounded a complement. Every case of the suite gets the verdict it got, and the corpus and
containment studies read no difference on 0.0.36.

### Changed

- valgebra is required from 0.0.36, which reads a meet below an excluded middle empty as its
  relation proves it. `{"anyOf": [{"not": C}, C]}` holds every JSON value, and with `C` a list
  `const` or an `enum` of lists the arrays' meet with its complement was not read empty, though
  the arrays were `subset` of it; it is now, for `{"const": [1]}` and `{"enum": [[1], [2]]}`. A
  meet no reading decides is declined at a cost bounded a complement.

## [0.0.7] - 2026-11-25

A release of three readings made exact and two answers to ask for, on valgebra 0.0.35. An asserted
`format` alone, a constant past the float range and an integral step past `2**53` each admitted a
value the schema refuses or proved an inclusion that does not hold, and no longer do. A failure
names the keyword that made it, held to the locations `jsonschema` reports, and a sized schema
reads as its length range. valgebra's newer floor decides a relation between two bounds past
`2**120`. Every case of the suite gets the verdict it got, and the corpus and containment studies
read no difference on 0.0.35.

### Security

- An integral `multipleOf` is decided exactly. A step past `2**53` has no float equal to it, and
  valgebra's `MultipleOf` read a float instance against the float nearest the step, so `1e16`
  passed `multipleOf: 10000000000000001`. And `typing.Annotated` caches a subscript by its
  arguments' equality, where `MultipleOf(2) == MultipleOf(2.0)`, so in a process that had built
  `Annotated[int, MultipleOf(2.0)]` first, `multipleOf: 2` held the float step and admitted
  `2**53 + 1`. A step up to `2**53` is a class of its own that no float step stands for, and one
  past it is checked in exact rational arithmetic, as a fractional step is. The exact check costs
  more: under `{"type": "integer", "multipleOf": 10000000000000001}`, `is_valid` of the step
  itself takes 0.72 µs where 0.0.6 took 0.09, on CPython 3.15, and 14 under `multipleOf: 7` takes
  60 ns in both.

- A constant past the float range is its infinity. `json.loads` reads `1e400` as `inf`, in a
  schema and in an instance alike, and `type` and `maximum` read it so, but a `const` or an `enum`
  of it compiled to the empty set: `{"const": 1e400}` refused the instance written the same way,
  and was `subset` of every schema, `false` among them. An infinity compiles to its literal, so
  the constant holds the infinity of its sign and nothing else, and is `not_subset` of
  `{"const": 0}` and of `false`; a constant of `nan`, which JSON holds none of, stays empty.

- An asserted `format` alone admits only JSON values. Its set was the strings of the format beside
  every value that is no string, met with nothing, so `{"format": "date"}` read with
  `assert_format=True` admitted `nan`, a tuple, bytes and a set, on the root and under a tool's
  arguments, and `{"format": "uuid"}` was `not_subset` of `true`. A format is guarded as every other
  keyword is, so a schema holding it is met with the JSON values: the four are refused under each
  format, and a format alone is `subset` of `true`. Beside `"type": "string"`, a string the format
  refuses fails with the format's own code, `string_pattern_mismatch` for a regular one, as a
  `minLength` fails with its own, where it failed with `union_error`.

### Added

- `length(schema)` reads a length range beside `interval`'s numeric one: a schema that is `type`
  and its two length keywords alone, a string's `minLength` and `maxLength`, an array's
  `minItems` and `maxItems` or an object's `minProperties` and `maxProperties`, is a `Length` of
  its kind and its bounds, `2.0` read as 2, and anything else is `None`.

- A failure names the keyword that made it. valgebra reports a failure's instance path and the set
  the schema compiled to, so `{"type": "integer", "minimum": 1}` refused `0` as `union_error` over
  `int and >= 1, float and >= 1`, with no keyword. `Compiler.located(failure, value)` adds
  `keyword` and `keywordLocation`, the keyword's location along the evaluation path through each
  `$ref` (draft 2020-12, section 12.3.1): `minimum` at `#/minimum` there, `type` where a value of
  the wrong kind, `nan` among them, is refused, and `enum` where a listed value is missed.
  `Compiler.keywords_failed(value, path)` lists every keyword refusing the value at a path, the
  ones pinning a kind first. Each is asked of the value again beside the keywords it depends on,
  and named where it refuses what they admit: a branch of an `anyOf` that holds, an `if`, the
  branch it does not pick and a dependent schema of a key the object lacks name nothing, and a
  missing key is named by the `required` or `dependentRequired` asking for it. Over 600 drawn
  schemas of several keywords, every keyword named is one `jsonschema` reports.

### Changed

- A schema object's order bounds compile to one interval a kind. `{"type": "number", "minimum": 0,
  "maximum": 100}` was the meet of the kind and a guarded set per bound, each a union of an `int`
  and a `float` refinement, so a value walked the two kinds once per bound. The bounds of one
  object compile together, the integers and the floats each under all of them, with the same
  members: `is_valid` on it takes 76 ns where it took 101 on `50.5`, and 4,559 instructions for
  three calls where it took 5,174, on CPython 3.15. The kind stays in the meet, where a relation
  finds its refutation: without it, `{"type": "number"}` is `undecided` below the numbers under a
  bound of more than 1,024 bits, which `inf` refutes.

- valgebra is required from 0.0.35, which holds an integer bound to 1,024 bits where one past
  `2**120` declined. `{"type": "integer", "minimum": 2**121}` is `not_subset` of the integers from
  `2**121 + 1` and `{"maximum": 1e101}` of `{"maximum": 1e100}`, each `undecided` before, and the
  integers up to `1e100` are `subset` of the numbers up to it. No study's count moves.

- The ledger of differences names valgebra's walk depth. A value nested past valgebra's walk is
  refused by every schema, `is_valid` answering `False` and `validate` raising `recursion_limit`:
  under `true` and `{}`, 127 lists around a number are admitted and 128 refused, and a `not` takes
  a level, where the specification admits a JSON value at any depth.

### Fixed

- A tool's `inputSchema` naming `type: "object"` beside a `$ref` is read. `read_tool` followed a
  root's `$ref` first and refused one with any sibling but an annotation, so `{"type": "object",
  "$ref": "#/$defs/Q"}` was refused as naming no object while the same set through `allOf` was
  read. A `$ref` is an applicator its siblings meet (draft 2020-12, section 8.2.3.1), so a root
  naming `type: "object"` is an object schema whatever stands beside it.

## [0.0.6] - 2026-11-22

A release of three readings and the tested set, on valgebra 0.0.32: a schema read closed at its
root, the assumption that a server sends no key its schema does not name; a keyword a caller
registers, which asserts where draft 2020-12 makes an unknown one an annotation; a meta-schema's
vocabularies read through the registered ones; and a constraints file naming the versions a
release ran on. Every case of the suite gets the verdict it got, and the corpus and containment
studies read no difference on 0.0.32.

### Added

- `closed(schema)` reads a schema closed at its root: its members holding no key that no
  keyword of the root evaluates, the root with `unevaluatedProperties: false` (draft 2020-12,
  section 11.3). A key a `$ref` or an `allOf` declares counts as evaluated, where
  `additionalProperties: false` sees its sibling `properties` alone and empties a result whose
  keys a definition declares. The reading is narrower than the schema, never wider, so it states
  an assumption about a server that sends no other key; a record under a property stays as
  written, an older draft's document is upgraded first, and the compiler refuses the closing
  where it refuses `unevaluatedProperties` beside the root's other keywords. Over 300 drawn
  schemas, the closing is below each and holds what `jsonschema` reads it to hold, and narrows
  205.

- A caller may register a keyword outside the vocabularies: `compile_schema(schema,
  keywords={name: Keyword(kind, holds)})`, and `Compiler` and `compile_with_fallbacks` alike, read
  it as an assertion on its kind, `holds(instance, value)` answering for an instance, every other
  kind passing. Draft 2020-12 makes such a keyword an annotation "save for explicit agreement"
  (section 6.5), and registering it is that agreement. It is an opaque predicate, recorded in
  `Compiler.opaque`: a unit quaternion is exact on membership, and a relation through it is
  `undecided`. An unregistered keyword stays in `Compiler.ignored`, and a keyword draft 2020-12
  defines is not registered.

- A schema whose `$schema` names its own meta-schema, passed among `documents`, is read through
  the meta-schema's `$vocabulary`: `compile_schema(..., vocabularies={uri: {name: Keyword}})`
  reads each vocabulary outside draft 2020-12's through the keywords registered for it. A
  required vocabulary no caller registers is refused with `UnsupportedDialect` naming it, as
  draft 2020-12 has an implementation refuse it (section 8.1.2); an optional one's keywords stay
  annotations; and a dialect leaving out core, applicator, unevaluated or validation is refused,
  since the compiler would assert keywords it makes annotations. `dialect` answers which keywords
  a schema's meta-schema registers. The suite reads no difference.

- The recipes hold "a number that is finite": `{"type": "number"}` admits `1e400`, which
  `json.loads` reads as infinity, and the float range as bounds is the decided "finite", a bounded
  number `subset` of it and a plain one `not_subset`.

- The README names the schemas pydantic's `model_json_schema()` emits, as the MCP Python SDK and
  FastMCP publish a tool's, as compiling as written, which the suite holds, and counts the
  recipes, eight.

- `constraints.txt` holds the tested set, every dependency at the lock's version, as
  `uv export --locked --no-dev --no-emit-project --no-hashes` writes it, and a test holds its pins
  to the lock's. The README says to pin the file at a release's tag, and carries the license
  under its title.

## [0.0.5] - 2026-11-22

A release of one reading and one wording, on valgebra 0.0.32: a schema read over another
record's keys, so a step's result is asked against a later step's input in one inclusion, and a
failure naming each pattern in the schema's own text. Every case of the suite gets the verdict
it got, and the corpus and containment studies read no difference on 0.0.32.

### Added

- `renamed(schema, names)` reads a schema over another record's keys: its members, each key `k`
  written as `names[k]`, so a step's result is asked against a later step's input written over
  other names in one inclusion. It renames what `properties`, `required`, `dependentRequired`,
  `dependentSchemas`, `dependencies`, an object `const` or `enum` and a `propertyNames` list
  name, through `allOf`, `anyOf`, `oneOf`, `not` and `if`, and leaves a property's value, an
  item and a definition as written; a keyword naming keys by a pattern or a reference reaching
  the renamed schema is refused. With valgebra 0.0.32 a result whose two keys agree reads
  `subset` below an input whose `if` reads that agreement.
- `Compiler.reworded(failure)` names each pattern a failure names in the schema's text,
  `a string matching '^[a-f0-9]{24}$'` where valgebra names the text it was given, the pattern
  unanchored and its classes written out; `Compiler.patterns` holds the texts. A part a
  lookahead is read as, and a text two patterns translate to, are named as valgebra gave them.

### Changed

- valgebra is required from 0.0.32, which asks a meet holding a union as its clauses once every
  other reading declines: a result whose `oneOf` pairs two keys is `subset` of an input whose
  `if` reads the pair, read over the result's keys. The suite, corpus and containment studies
  read no difference on it.

## [0.0.4] - 2026-11-21

A release of three readings, on valgebra 0.0.31: what a member holds at a path inside a schema, a
`propertyNames` spelling its names out as the record of those keys, and a conjunction drawn
merged. Every case of the suite gets the verdict it got, and the corpus disagrees with the
`jsonschema` package on the same 13 values; the containment study decides 65 questions more, 29
as the suite labels them and 36 against labels the `jsonschema` package's validator for the
draft shows wrong.

### Added

- A page follows a schema from its document to its two answers, membership and inclusion, with a
  diagram for each step: what the compiler reads, what valgebra decides, and where a keyword
  read as a predicate leaves a relation `undecided`.

- `Compiler.below(path)` returns the values a member of the root holds at a path of keys and
  `ITEM`, any element of an array, read through every keyword that narrows them and a `$ref`
  resolved against the base URI it sits under: an upper bound, holding every value a member holds
  there. A consumer reading one field's schema itself, as through `properties` alone or a `$ref`
  from the document's root, reads less, or another resource's schema.

### Fixed

- `Sampler` draws a conjunction merged keyword by keyword: an `allOf` with the schema around it,
  an `anyOf` or `oneOf` branch with its siblings, and a reference's target with the keywords
  beside it, `properties` met key by key, `required` united, `type` keeping the kinds both name
  and each bound the tighter. A member's `properties` replaced the outer schema's, so a record an
  `allOf` narrows drew no member. A required key `properties` does not name is drawn from
  `additionalProperties`, a pattern holding a group, an alternation or `.` is drawn inside it,
  and a schema naming no `type` draws the container kind its keywords read beside the scalars.
  On fishtest's six output schemas, 215 of 240 draws are members, against 88.

### Changed

- The documentation site is built by Zensical, Material for MkDocs' maintained successor, from
  `mkdocs.yml` as written under `zensical build --strict`: its own search, the redirects from
  each page's former address, `llms.txt` and `llms-full.txt`, the Mermaid diagrams and the API
  reference through the mkdocstrings Python handler. No page moves.

- A `propertyNames` spelling its names out, an `enum`, a `const`, or an `anyOf` or `oneOf` of
  them, compiles to the closed record of those keys, each optional, rather than to an opaque
  predicate: `{"propertyNames": {"enum": ["k", "j"]}}` is `subset` of the object whose
  `properties` are `k` and `j` with `additionalProperties: false`, and the converse too, where
  both read `undecided`. Membership is unchanged; the suite's `propertyNames` cases going
  through an opaque predicate fall from 7 to 0 in drafts 2020-12, 2019-09, 07 and 06.

- The package requires valgebra 0.0.31 or later, which counts a record's keys under
  `minProperties` and `maxProperties`: `{"propertyNames": {"enum": ["k", "j"]}, "minProperties":
  2}` is `subset` of the object requiring `k` and `j`, and `{"required": ["k"], "maxProperties":
  1}` of the closed record of `k`, where both read `undecided`. The suite and corpus studies
  read no difference. The containment study decides 65 questions more, a proof and 64
  refutations, 36 of them against the suite's labels: 35 in draft 4 stand on a `const`, which
  draft 4 does not have, and one in draft 2020-12's `unsatisfiable/dynamicRef.json` on
  `{"bar": {"baz": {}}}`, which the meet it labels empty holds.

## [0.0.3] - 2026-11-19

A release of the dependency range: the compiler is 0.0.2's, and every published count is the one
0.0.2 recorded, read again on valgebra 0.0.30.

### Changed

- The package requires valgebra 0.0.30 or later, with no upper bound: a valgebra release
  installs beside this package the day it is published, with no release of this package.

## [0.0.2] - 2026-11-18

A release of the user guide, with no change to the compiler: every schema compiles to the set
0.0.1 compiled it to, and every published count is the one 0.0.1 recorded.

### Added

- The user guide is published at <https://ppigazzini.github.io/valgebra-jsonschema/>, with
  `llms.txt` and `llms-full.txt` for a reader that is not a browser, and the API reference read
  from the package's docstrings.
- A recipes page does five tasks end to end: a model's tool call checked against the schema it
  was shown, a schema change checked before release, a schema split across documents, files
  checked against a schema, and what a schema asserts, keyword by keyword.

### Changed

- The package's `Documentation` link and the README's links go to the published guide. Each
  page's address is its topic, `/mcp/` and `/compiler/`, and an address the site has served
  before answers with a page that sends the reader on.
- The package requires valgebra 0.0.29 and below 0.0.30, whose release changes no answer of
  0.0.28.

## [0.0.1] - 2026-11-17

### Added

- `compile_schema` reads JSON Schema drafts 2020-12, 07, 06 and 04 into valgebra's sets over
  the values `json.loads` returns, and raises `Unsupported` naming a keyword it does not read.
- Draft 2019-09 reads through `upgrade`, and a document naming any other dialect raises
  `UnsupportedDialect`, a kind of `Unsupported`, whose message says it is not supported.
- A `$ref` resolves against the base URI it sits under: an embedded `$id` starts a resource,
  and a reference names a resource of the document by its URI, then a schema in it by a JSON
  pointer or an `$anchor`. An older draft's `$id` fragment that is a plain name reads as the
  `$anchor` it names. A URI two schema objects of one document claim, and an anchor two of one
  resource set, name neither, and a `$ref` or `$dynamicRef` naming one is refused, as draft
  2020-12 asks for an error (sections 8.2.2 and 9.1.2).
- `compile_schema(schema, documents={uri: document})` takes the documents a reference may name
  beside the one compiled, and `Sampler` takes them too. Each is a resource at its URI, read
  in its own dialect or, declaring none, in the compiled document's; one in a dialect not read
  is refused only where a reference names it, and no document is fetched. The compiled
  document names its own URI throughout a compile, as draft 2020-12 makes the root's `$id` its
  canonical URI (section 9.1.1), so a document supplied at that URI is not read.
- `$dynamicRef` reads the dynamic scope across every document: where its target sets a
  `$dynamicAnchor` of its fragment's name, it names the outermost schema object of the scope
  that sets one (draft 2020-12, sections 7.1 and 8.2.3.2), and `$dynamicAnchor` names its
  schema object as `$anchor` does. Draft 2019-09's `$recursiveAnchor: true` on a resource's
  root is a dynamic anchor with no name, and its `$recursiveRef: "#"` the `$dynamicRef: "#"`
  that reads it, as the draft 2020-12 release notes say the two pairs agree.
- `unevaluatedProperties` and `unevaluatedItems` are read on each case of which in-place
  subschemas hold, as the object group or the array that leaves the keys or items nothing
  evaluates there to the subschema.
- `patternProperties` up to four patterns, and a `propertyNames` of words, are clauses over keys
  narrowed by a pattern, so a relation reads them. `propertyNames: true` names every key, and
  `propertyNames: false` none, so it admits the empty object alone.
- A `pattern` opening with lookaheads, `^(?!A)(?=C)B`, and one tempering its dot,
  `^((?!A).)*$`, are the sets they denote, meets of patterns with complements, which a
  relation reads. Any other lookaround is outside valgebra's dialect.
- A property name ending in `?` is that name. valgebra's record literal reads the suffix as
  "optional", so such a key is written with one more and, where it is required, met with its
  presence, which a `TypedDict` names whole.
- `uniqueItems` is one predicate in every schema, and a fractional `multipleOf` one per step,
  so a schema holding either is proved below itself.
- `oneOf` leaves out the complement of a branch valgebra proves disjoint from another, which
  holds none of its values: each branch is spelled once per branch it may meet.
- A schema past valgebra's node limit with keys read by predicate reads each `oneOf` as its
  union met with a count of the branches that hold, and each reference to a definition that
  does not reach itself through the definition's own set: membership stays exact, and a
  relation reading inside those parts declines. `compile_with_fallbacks` is the cascade
  `compile_schema` and `Sampler` share.
- `constants(schema)` lists the values a schema spells out with `const`, `enum`, or an `anyOf`
  or `oneOf` of them, and such a schema lies inside another exactly where each value is a
  member of it, over a predicate as well.
- NaN is a value of no schema, since JSON has none (RFC 8259 §6). An infinity is a number,
  as `json.loads` reads one past the float range.
- `read_tool` reads an MCP server's tool listing into its two contracts.
- `assert_format=True` reads `date`, `duration`, `ipv4`, `uuid`, `date-time`, `time`, `email`,
  `hostname` and `ipv6` as assertions, and refuses any other `format`. It is off by default.
- The package requires valgebra 0.0.28 and below 0.0.29, since a `0.0.x` minor of valgebra
  is a breaking release here: each is taken by a release of this package, with its suite run on
  it.
- Measured on this release, each figure in [the results page](https://ppigazzini.github.io/valgebra-jsonschema/results/): the
  official JSON-Schema-Test-Suite passes the 1393 draft 2020-12 cases it runs and the 1256 of
  2019-09, each skipping the five that name a custom meta-schema, and every case of drafts 07,
  06 and 04, 929, 841 and 618. 9486 of JSONSchemaBench's 9558 schemas compile, and membership
  differs from the `jsonschema` package's on 13 of 404720 values, each a reading the ledger
  records. Of the containment test suite's 10890 questions, 7048 are proven, 3560 refuted,
  246 undecided and 36 refused.

[Unreleased]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.8...HEAD
[0.0.8]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.7...v0.0.8
[0.0.7]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.6...v0.0.7
[0.0.6]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.5...v0.0.6
[0.0.5]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.4...v0.0.5
[0.0.4]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.3...v0.0.4
[0.0.3]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.2...v0.0.3
[0.0.2]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.1...v0.0.2
[0.0.1]: https://github.com/ppigazzini/valgebra-jsonschema/releases/tag/v0.0.1
