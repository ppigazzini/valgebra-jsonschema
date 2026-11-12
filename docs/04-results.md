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

Draft 2020-12, with the four optional files on regular expressions and large numbers: 1071
of the 1071 cases run pass; 327 are skipped: the `unevaluatedItems` and
`unevaluatedProperties` files (200 cases), dynamic, anchor and remote references, and a
custom metaschema. Through `upgrade`: draft 2019-09, 961 of the 961 cases run pass, 300
skipped; draft-07, 870 of the 870 cases run pass, 59 skipped; draft-06, 790 of the 790 cases run
pass, 51 skipped; draft-04, 587 of the 587 cases run pass, 31 skipped. See
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
| Github_easy | 1943 | 1932 | 11 | 0 | 0 | 84129 | 2 |
| Github_hard | 1240 | 1218 | 22 | 0 | 0 | 47920 | 0 |
| Github_medium | 1976 | 1964 | 12 | 0 | 0 | 83585 | 0 |
| Github_trivial | 444 | 444 | 0 | 0 | 0 | 17098 | 10 |
| Github_ultra | 164 | 156 | 8 | 0 | 0 | 5470 | 0 |
| Glaiveai2K | 1707 | 1689 | 18 | 0 | 0 | 79793 | 0 |
| JsonSchemaStore | 492 | 457 | 35 | 0 | 0 | 17946 | 0 |
| Kubernetes | 1064 | 1063 | 1 | 0 | 0 | 44463 | 0 |
| Snowplow | 403 | 400 | 3 | 0 | 0 | 17745 | 0 |
| WashingtonPost | 125 | 125 | 0 | 0 | 0 | 5275 | 0 |
| all | 9558 | 9448 | 110 | 0 | 0 | 403424 | 12 |

- 9448 of the 9558 schemas compile, none crashes, none times out. Of the 110 refused, 58
  use `dependencies` or `additionalItems` in a schema declaring no older draft, 13 build
  sets valgebra refuses, 19 hold a pattern outside valgebra's regex dialect, 18 of them a
  lookaround and 1 a backreference, and 11 an embedded `$id` over a reference or another
  dialect; the rest are listed by `tools/corpus.py`.
- Membership differs from the package's on 12 of the 403424 values, each a reading the
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
| 2020-12 | 3645 | 738 | 1847 | 786 | 274 | 0 | 2 |
| 7 | 2788 | 96 | 1759 | 740 | 193 | 0 | 2 |
| 6 | 2524 | 96 | 1575 | 666 | 187 | 0 | 2 |
| 4 | 1933 | 66 | 866 | 785 | 216 | 0 | 252 |

- No proof contradicts a label: 6047 proofs of the 10890 questions, 0 against one.
- Each of the 258 refutations against a label is a wrong label. In every draft
  two: in `universal/items.json` the generator leaves `type` and `items: false` outside the
  `not` it writes, so the schema it labels universal leaves out the value `1`; in
  `unsatisfiable/ref.json` it rewrites a `$ref` inside an `enum` value, so the two `enum`s
  differ and the schema it labels empty holds `{"$ref": "#/allOf/0/$defs/a_string"}`.
  In draft-04, 250 more pairs put `const`, which draft-06 added, in a draft-04 schema: the
  draft reads it as an annotation, so the first schema admits every value.
- A question is refused where the compiler refuses a schema of its pair, as the inventory
  of [`03-conformance.md`](03-conformance.md) lists; an undecided one is kept and counted.
