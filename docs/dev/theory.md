# The theory

The published results the compiler rests on, and which code each one holds up. A citation here
is a claim that a named item of `valgebra_jsonschema` exists because of a numbered result, not
a reading list. What a keyword means is the specification's, cited by its section where the
code reads it and held by the official test suite, as
[the conformance page](../conformance.md) records; what a set denotes and how valgebra decides
it is valgebra's theory page. This page holds what lies between: the formal semantics the
translation reads the specification through.

A citation is a key and a place, `(Attouche et al. 2024, §4.2)`, as
[the rule for citing a paper](writing.md#citing-a-paper) says, and the place is the number the copy in the
table below prints.

Each claim ends in a tag. **LOAD-BEARING**: code here implements the result. **DEVIATION**: the
code departs from its source on purpose, and the claim names the cost. Each is followed by an
`IMPLEMENTED-BY:` line naming the items resting on it, a module as `schema.py` or an item in it
as `schema.py::Compiler._index`, under `valgebra_jsonschema/`, and a `HELD-BY:` line naming the
tests that fail when the claim is false. `tests/test_theory_ledger.py` holds the page, the
table and the package to each other.

## Works cited

| Key | Work | Read in | Identifier |
|---|---|---|---|
| Attouche et al. 2022 | L. Attouche, M.-A. Baazizi, D. Colazzo, G. Ghelli, C. Sartiani, S. Scherzinger. Witness generation for JSON Schema. PVLDB 15(13), 4002-4014, 2022 | the published article | [doi:10.14778/3565838.3565852](https://doi.org/10.14778/3565838.3565852) |
| Attouche et al. 2024 | L. Attouche, M.-A. Baazizi, D. Colazzo, G. Ghelli, C. Sartiani, S. Scherzinger. Validation of modern JSON Schema: formalization and complexity. PACMPL 8(POPL), Article 49, 2024 | the published article | [doi:10.1145/3632891](https://doi.org/10.1145/3632891) |

## The keyword-wise semantics

**A schema object is the meet of its keywords, each guarded by its kind.** A typed terminal
assertion is trivially satisfied by an instance not of its type, and otherwise checks its
condition on it (Attouche et al. 2024, §4.2); a schema object applies its keywords in turn, and
an instance is valid where every keyword holds (Attouche et al. 2024, §4.5). So a keyword
compiles to the guarded set `complement(kind) | refined`, `{"minimum": 3}` admits `"a"`, and a
schema object compiles to the meet of its keywords and the universe of what `json.loads`
returns. On that universe the translation is exact for the keywords it accepts, which is what
lets valgebra decide inclusion, equivalence and emptiness between two compiled schemas.
**[LOAD-BEARING: keyword-wise-semantics]**

IMPLEMENTED-BY: schema.py

HELD-BY: test_an_assertion_passes_every_other_kind, test_a_type_list_keeps_the_guard_of_each_other_kind, test_the_universe_is_refuted_below_a_keyword_of_one_kind, test_membership_agrees_with_the_jsonschema_package_on_random_schemas, test_every_case_the_compiler_accepts_gets_the_specified_verdict

## References

**A URI names one schema.** Before validation every resource a document embeds moves into one
`$defs` entry named by its absolute URI, and a reference that crosses a resource's boundary is
rewritten to that URI (Attouche et al. 2024, §3.1), so a URI names one schema object. A URI two
schema objects of one document claim names neither, and a reference to it is refused, beside
draft 2020-12's own reading, which asks for an error where two schemas claim one URI.
**[LOAD-BEARING: one-uri-one-schema]**

IMPLEMENTED-BY: schema.py::Compiler._index

HELD-BY: test_a_uri_two_schema_objects_of_one_document_claim_names_neither, test_a_reference_reached_through_a_pointer_resolves_in_its_own_resource

## Witnesses

**A conjunction is drawn merged, a member per required key.** A witness of a conjunction is not
found by drawing one conjunct and hoping it meets the others: generation limits conjunctions to
assertions of one kind and merges them first, an and-elimination (Attouche et al. 2022, §4). An
object is built member by member until every requirement holds (Attouche et al. 2022, §6.3.1),
and a required key's member is drawn under the conjunction of every constraint on that key
(Attouche et al. 2022, §6.3.2). So the sampler merges an `allOf` with the schema around it, an
`anyOf` or `oneOf` branch with its siblings and a reference's target with the keywords beside it,
keyword by keyword, and draws a required key no `properties` names from `additionalProperties`.
Membership in the compiled set judges every value drawn, so a merge that keeps too much costs a
rejection and never a wrong witness. **[LOAD-BEARING: conjunctions-merged]**

IMPLEMENTED-BY: sample.py, sample.py::Sampler._object

HELD-BY: test_an_all_of_is_drawn_as_the_conjunction_of_its_members, test_a_branch_is_drawn_with_the_keywords_beside_it, test_a_reference_is_drawn_with_the_keywords_beside_it, test_a_required_key_no_property_names_takes_the_additional_schema, test_types_and_bounds_two_members_both_write_meet
