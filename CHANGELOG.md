# Changelog

All notable changes to valgebra-jsonschema are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- A `$ref` resolves against the base URI it sits under: an embedded `$id` starts a resource,
  and a reference names a resource of the document by its URI, then a schema in it by a JSON
  pointer or an `$anchor`. An older draft's `$id` fragment that is a plain name reads as the
  `$anchor` it names. 8 more JSONSchemaBench schemas compile, 9456 of 9558, and the suite
  studies run 1111 cases of draft 2020-12, 1022 of 2019-09, 902 of draft-07, 814 of draft-06 and
  597 of draft-04, each passing.
- `compile_schema(schema, documents={uri: document})` takes the documents a reference may name
  beside the one compiled. Each is a resource at its URI, read in its own dialect or, declaring
  none, in the compiled document's; one in a dialect not read is refused only where a reference
  names it, and no document is fetched.
  `Sampler` takes them too. The suite studies read the suite's vendored `remotes/` and the
  drafts' meta-schemas, and run every case of drafts 07, 06 and 04: 929, 841 and 618.

- A `pattern` opening with lookaheads, `^(?!A)(?=C)B`, and one tempering its dot,
  `^((?!A).)*$`, are the sets they denote, meets of patterns with complements, which a
  relation reads: 14 more JSONSchemaBench schemas compile, 9471 of 9558. Any other lookaround
  is outside valgebra's dialect.

- `unevaluatedProperties` and `unevaluatedItems` are read on each case of which in-place
  subschemas hold, as the object group or the array that leaves the keys or items nothing
  evaluates there to the subschema. The suite studies run every case of their files that
  reads no dynamic reference, 1341 of draft 2020-12 and 1239 of 2019-09, each passing, and
  the containment study proves 6564 of its 10890 questions.

- `constants(schema)` lists the values a schema spells out with `const`, `enum`, or an `anyOf`
  or `oneOf` of them, and such a schema lies inside another exactly where each value is a
  member of it, over a predicate as well. The containment study asks a finite first schema
  that way: it proves 6756 of its 10890 questions and leaves 490 undecided, and its 3 proofs
  against a label are `nonvalid/ref.json`'s tree, which the `jsonschema` package admits.

- `$dynamicRef` reads the dynamic scope across every document: where its target sets a
  `$dynamicAnchor` of its fragment's name, it names the outermost schema object of the scope
  that sets one (draft 2020-12, sections 7.1 and 8.2.3.2), and `$dynamicAnchor` names its
  schema object as `$anchor` does. Draft 2019-09's `$recursiveAnchor: true` on a resource's
  root is a dynamic anchor with no name, and its `$recursiveRef: "#"` the `$dynamicRef: "#"`
  that reads it, as the draft 2020-12 release notes say the two pairs agree, in a supplied
  document too. The suite studies run 1393 cases of draft 2020-12 and 1256 of 2019-09, each
  passing, and skip the five that name a custom meta-schema. The containment study refuses
  36 of its questions, each a reference the generator broke, and its 5 more answers against a
  label, 3 proofs in `nonvalid/dynamicRef.json` and 2 refutations in `universal/dynamicRef.json`,
  are each a wrong label the `jsonschema` package witnesses.

- A property name ending in `?` is that name. valgebra's record literal reads the suffix as
  "optional", so such a key is written with one more and, where it is required, met with its
  presence, which a `TypedDict` names whole: one more JSONSchemaBench schema compiles.

- A schema past valgebra's node limit with keys read by predicate reads each `oneOf` as its
  union met with a count of the branches that hold, and each reference to a definition that
  does not reach itself through the definition's own set: membership stays exact, and a
  relation reading inside those parts declines. The 12 JSONSchemaBench schemas past the limit
  compile, 9486 of the 9558. `compile_with_fallbacks` is the cascade `compile_schema` and
  `Sampler` share.

### Changed

- `oneOf` leaves out the complement of a branch valgebra proves disjoint from another, which
  holds none of its values: each branch is spelled once per branch it may meet rather than once
  per branch, which keeps 14 JSONSchemaBench schemas under valgebra's node bound, and 9448 of
  the 9558 compile.
- `propertyNames: true` names every key, and `propertyNames: false` none, so it admits the
  empty object alone: both are sets a relation reads rather than predicates. The containment
  study proves 6047 of its 10890 questions, and 95 of the 1071 draft 2020-12 suite cases run
  go through an opaque predicate.
- `not`, `oneOf`, `if` and `contains` complement a schema's keywords without the universe the
  schema is met with where used as itself: inside the JSON values the two agree, and valgebra
  decides the bare complement. The containment study proves 6574 of its 10890 questions and
  leaves 863 undecided, and the 3 more refutations against a label are draft-04 `const`
  pairs. `Compiler.compile_body` returns the meet, and one pass reads both, so a `oneOf`
  nested twelve deep compiles in 10 ms.
- `uniqueItems` is one predicate in every schema, and a fractional `multipleOf` one per step,
  so a schema holding either is proved below itself: the containment study proves 6634 of its
  10890 questions.
- The package requires valgebra 0.0.26 and below 0.0.27. The suite studies and the corpus
  read as on 0.0.25, and the containment study moves where 0.0.26 decides a pair 0.0.25 left
  `undecided`: it proves 200 more questions, 7048 of the 10890, refutes 13 more and leaves
  297 undecided. Each of the 11 more refutations against a label is a wrong label the
  `jsonschema` package admits a witness against: in nine the generator renames the `$ref`,
  `$id` or `$anchor` inside the value a schema labeled universal leaves out under `not`, and
  two are draft-04 `const` pairs whose witness, `2**64` or `-2**64`, lies past a bound
  beyond 64 bits.

### Fixed

- NaN is a value of no schema. JSON has none (RFC 8259 §6), and in the universe it refuted
  inclusions every JSON number satisfies: `{"type": "number"}` below `{"anyOf": [{"maximum":
  10}, {"minimum": 5}]}`. An infinity stays, as `json.loads`'s reading of a number past the
  float range. A float leaf is a bound, which valgebra 0.0.26 walks outside its scalar fast
  paths: an array of a million floats validates against `NUMBER` in 29 ms, against 22 ms for
  a bare float, and `true` over a nested document in 11.0 ms against 9.4 ms. The
  containment study refutes 809 draft-04 questions rather than 811, the two whose only witness
  valgebra found was NaN.
- A set a callback checks against, compiled again at membership time because it holds a
  fixpoint then being built, reads `format` and keys narrowed by a pattern as the compiler
  does: under `assert_format=True`, `"nope"` one level down a recursion through five
  `patternProperties` is refused as `ipv4`, as it is at the top.

## [0.0.1] - 2026-11-12

### Added

- `compile_schema` reads JSON Schema drafts 2020-12, 07, 06 and 04 into valgebra's sets over
  the values `json.loads` returns, and raises `Unsupported` naming a keyword it does not read.
- Draft 2019-09 reads through `upgrade`, and a document naming any other dialect raises
  `UnsupportedDialect`, a kind of `Unsupported`, whose message says it is not supported.
- `read_tool` reads an MCP server's tool listing into its two contracts.
- `patternProperties` up to four patterns, and a `propertyNames` of words, are clauses over keys
  narrowed by a pattern, so a relation reads them.
- `assert_format=True` reads `date`, `duration`, `ipv4`, `uuid`, `date-time`, `time`, `email`,
  `hostname` and `ipv6` as assertions, and refuses any other `format`. It is off by default.
- The package requires valgebra 0.0.25 and below 0.0.26, since a `0.0.x` minor of valgebra
  is a breaking release here: each is taken by a release of this package, with its suite run on
  it.

[Unreleased]: https://github.com/ppigazzini/valgebra-jsonschema/compare/v0.0.1...HEAD
[0.0.1]: https://github.com/ppigazzini/valgebra-jsonschema/releases/tag/v0.0.1
