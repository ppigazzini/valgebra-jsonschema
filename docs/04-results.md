# Results

Every number below is printed by a committed command and recorded as counts in
[`studies/`](studies/); each tool's `--check` reruns it.

## The compiler

```bash
uv run python tools/suite.py --check docs/studies/json-schema-test-suite.json
uv run python tools/suite.py --draft 2019-09 --check docs/studies/json-schema-test-suite-draft2019-09.json
uv run python tools/suite.py --draft 7 --check docs/studies/json-schema-test-suite-draft7.json
uv run python tools/suite.py --draft 6 --check docs/studies/json-schema-test-suite-draft6.json
uv run python tools/suite.py --draft 4 --check docs/studies/json-schema-test-suite-draft4.json
```

Draft 2020-12, with the four optional files on regular expressions and large numbers: 1341
of the 1341 cases run pass; 57 are skipped: 52 read a dynamic reference, the meta-schema's
among them, and 5 a custom metaschema. Through `upgrade`: draft 2019-09, 1239 of the 1239
cases run pass, 22 skipped, a `$recursiveRef` where two resources set `$recursiveAnchor`
among them; draft-07, 929
of the 929 cases run pass, 0 skipped; draft-06, 841 of the 841 cases run pass, 0 skipped;
draft-04, 618 of the 618 cases run pass, 0 skipped. A case's remote documents
are the suite's `remotes/`, vendored, and the drafts' meta-schemas from the
`jsonschema-specifications` package, passed as `documents`. See
[`02-compiler.md`](02-compiler.md#measured).

## `format`, on request

```bash
uv run python tools/suite.py --draft format --check docs/studies/json-schema-test-suite-format.json
```

The nine formats `assert_format` reads, on the suite's `optional/format` files: 471 of the 494
cases pass. Each of the 23 that do not is a hostname, an `xn--` label the suite refuses for what it
decodes to, which the ledger records.

## Real-world schemas

```bash
uv run python tools/corpus.py --check docs/studies/jsonschemabench.json
```

The compiler on JSONSchemaBench (Geng et al. 2025, MIT), fetched at commit `9a94995b9279`
into `results/` and never vendored: 9558 schemas from GitHub, the JSON Schema Store,
Kubernetes, Snowplow, the Washington Post and function-calling data, in drafts 2020-12,
2019-09, 07, 06 and 04. Each compiled schema is checked on the values drawn from it and the
generic values `tools/corpus.py` lists, against the `jsonschema` package's validator for its
draft.

| subset | schemas | compiled | refused | crashed | timed out | values | disagreed |
|---|---:|---:|---:|---:|---:|---:|---:|
| Github_easy | 1943 | 1934 | 9 | 0 | 0 | 84201 | 2 |
| Github_hard | 1240 | 1222 | 18 | 0 | 0 | 48064 | 0 |
| Github_medium | 1976 | 1965 | 11 | 0 | 0 | 83613 | 0 |
| Github_trivial | 444 | 444 | 0 | 0 | 0 | 17098 | 10 |
| Github_ultra | 164 | 156 | 8 | 0 | 0 | 5470 | 0 |
| Glaiveai2K | 1707 | 1689 | 18 | 0 | 0 | 79793 | 0 |
| JsonSchemaStore | 492 | 475 | 17 | 0 | 0 | 18576 | 0 |
| Kubernetes | 1064 | 1063 | 1 | 0 | 0 | 44463 | 0 |
| Snowplow | 403 | 400 | 3 | 0 | 0 | 17745 | 0 |
| WashingtonPost | 125 | 125 | 0 | 0 | 0 | 5275 | 0 |
| all | 9558 | 9473 | 85 | 0 | 0 | 404298 | 12 |

- 9473 of the 9558 schemas compile, none crashes, none times out. Of the 85 refused, 58
  use `dependencies` or `additionalItems` in a schema declaring no older draft, 13 build
  sets valgebra refuses, 5 hold a pattern outside valgebra's regex dialect, 4 of them a
  lookahead past the pattern's start and 1 a backreference, and 7 a `$ref` to nothing in the document; the rest
  are listed by `tools/corpus.py`. A schema may name a draft's meta-schema, which both the
  compiler and the `jsonschema` package read from the `jsonschema-specifications` package.
- Membership differs from the package's on 12 of the 404298 values, each a reading the
  ledger records: 11 are an integral float, `1e300` or `-0.0`, under a draft-04
  `integer`, and 1 is `"\n"` under a pattern ending in `$`, which Python's `re` matches
  before a final newline.

## Inclusions against the containment test suite

```bash
uv run python tools/containment.py --check docs/studies/containment.json
```

The JSON Schema containment test suite (Attouche et al. 2021, MIT), fetched at commit
`446fb41c527c` into `results/` and never vendored: pairs of schemas generated from the
JSON-Schema-Test-Suite, each labeling whether the first is a subset of the second, the
converse, or both. A labeled direction is a question, asked of valgebra with
`relation_to`; the older drafts are read through `upgrade`, and the only optional files read are
the four the suite study runs.

| draft | questions | refused | proven | refuted | undecided | proven against the label | refuted against the label |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2020-12 | 3645 | 162 | 2248 | 911 | 324 | 0 | 8 |
| 7 | 2788 | 12 | 1805 | 764 | 207 | 0 | 4 |
| 6 | 2524 | 12 | 1621 | 690 | 201 | 0 | 4 |
| 4 | 1933 | 4 | 890 | 809 | 230 | 0 | 263 |

- A proof stands against a label only where the label is wrong, as a refutation does: 6564
  proofs of the 10890 questions, 0 against one. One kind of wrong label lies in a proof's
  direction: in `nonvalid/ref.json` the generator writes a `not` around the properties of the
  suite's tree of nodes and labels the tree it lists outside, where the `jsonschema` package
  admits it; valgebra 0.0.25 leaves those three questions undecided. A proof against a label
  in any other category fails `tests/test_docs.py`.
- Each of the 279 refutations against a label is a wrong label, and the `jsonschema`
  package's validator for the draft admits the witness to one side and refuses it from the
  other. In every draft the generator writes two kinds. In `universal/items.json`,
  `universal/ref.json` and, in draft 2020-12, `universal/unevaluatedItems.json` and
  `universal/unevaluatedProperties.json` it leaves keywords outside the `not` it writes,
  such as `type` and `items: false`, or `type` and `required`, so the schema it labels
  universal leaves out a value: `1`, `{}`, `1.5` or `{"prop1": 1}`. In `unsatisfiable/ref.json` and
  `unsatisfiable/id.json`, and in draft 2020-12's `unsatisfiable/anchor.json`, it renames a
  `$ref`, an `$id` or an `$anchor` inside an `enum` or `const` value as well as in the
  schema, so the two copies differ and the schema it labels empty holds the value it
  lists, such as `{"$ref": "#/allOf/0/$defs/a_string"}`. In draft-04, 259 more pairs put `const`, which draft-06 added, in a draft-04
  schema: the draft reads it as an annotation, so the first schema admits every value.
- A question is refused where the compiler refuses a schema of its pair, as the inventory
  of [`03-conformance.md`](03-conformance.md) lists; an undecided one is kept and counted.
