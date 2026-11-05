"""``format`` as an assertion, on request, against the official format suite."""

from __future__ import annotations

from pathlib import Path

import pytest

from valgebra_jsonschema import Unsupported, compile_schema, read_tool
from valgebra_jsonschema.formats import LANGUAGES, PREDICATES
from valgebra_jsonschema.suite import run_formats

FORMATS = Path(__file__).parent / "data" / "json-schema-test-suite-format"


def test_format_annotates_unless_it_is_asked_to_assert():
    assert compile_schema({"format": "uuid"}).is_valid("not a uuid")
    assert compile_schema({"format": "no-such-format"}).is_valid("anything")
    assert not compile_schema({"format": "uuid"}, assert_format=True).is_valid("not a uuid")


def test_every_case_passes_but_the_labels_idna_alone_refuses():
    outcomes = run_formats(FORMATS)
    assert set(outcomes) == set(LANGUAGES) | set(PREDICATES)
    for stem, outcome in outcomes.items():
        assert outcome.skipped == 0, stem
        if stem != "hostname":
            assert outcome.failures == [], stem
    # The ledger's one row: a label is read, and what it decodes to under IDNA is not.
    assert outcomes["hostname"].failed == 23
    assert outcomes["hostname"].passed == 43


@pytest.mark.parametrize("name", sorted(set(LANGUAGES) | set(PREDICATES)))
def test_a_format_passes_every_other_kind(name):
    compiled = compile_schema({"format": name}, assert_format=True)
    for value in (None, True, 1, 1.5, [], {}):
        assert compiled.is_valid(value), value


def test_a_format_it_does_not_read_is_refused_when_it_asserts():
    with pytest.raises(Unsupported, match="format"):
        compile_schema({"format": "uri"}, assert_format=True)


@pytest.mark.parametrize("name", sorted(LANGUAGES))
def test_a_language_is_decided(name):
    a_string = {"type": "string"}
    compiled = compile_schema({"type": "string", "format": name}, assert_format=True)
    assert compiled.relation_to(compile_schema(a_string)) == "subset"
    assert compile_schema(a_string).relation_to(compiled) == "not_subset"


def test_two_languages_are_told_apart():
    uuid = compile_schema({"type": "string", "format": "uuid"}, assert_format=True)
    date = compile_schema({"type": "string", "format": "date"}, assert_format=True)
    assert uuid.relation_to(date) == "not_subset"
    assert uuid.relation_to(compile_schema({"type": "string", "maxLength": 36})) == "subset"


def test_a_predicate_is_exact_and_opaque_to_a_relation():
    time = compile_schema({"type": "string", "format": "time"}, assert_format=True)
    assert time.is_valid("12:00:00Z")
    assert not time.is_valid("noon")
    assert compile_schema({"type": "string"}).relation_to(time) == "undecided"


def test_a_tool_reads_it_too():
    spec = {
        "name": "t",
        "inputSchema": {"type": "object", "properties": {"on": {"format": "date"}}},
    }
    assert read_tool(spec).arguments.is_valid({"on": "soon"})
    assert not read_tool(spec, assert_format=True).arguments.is_valid({"on": "soon"})
    assert read_tool(spec, assert_format=True).arguments.is_valid({"on": "2024-02-29"})
    assert not read_tool(spec, assert_format=True).arguments.is_valid({"on": "2023-02-29"})
