"""A keyword a caller registers asserts as a predicate; an unregistered one is an annotation."""

import math
import re

import pytest

from valgebra_jsonschema import (
    Keyword,
    UnsupportedDialect,
    compile_schema,
    compile_with_fallbacks,
)


def _unit(quaternion: list[float], tolerance: float) -> bool:
    return len(quaternion) == 4 and abs(math.fsum(x * x for x in quaternion) - 1) <= tolerance


UNIT = {"x-robot-unit-quaternion": Keyword("array", _unit)}
FOUR = {"type": "array", "prefixItems": [{"type": "number"}] * 4, "minItems": 4, "maxItems": 4}
QUATERNION = {**FOUR, "x-robot-unit-quaternion": 1e-6}


def test_a_registered_keyword_asserts_on_its_kind_and_is_recorded_as_opaque() -> None:
    compiler, reading = compile_with_fallbacks(QUATERNION, QUATERNION, keywords=UNIT)
    assert reading.is_valid([0, 0, 0, 1])
    assert reading.is_valid([0.5, 0.5, 0.5, 0.5])
    assert not reading.is_valid([0, 0, 0, 5])
    assert "x-robot-unit-quaternion" in compiler.opaque
    assert "x-robot-unit-quaternion" not in compiler.ignored


def test_an_unregistered_keyword_is_an_annotation_recorded_as_ignored() -> None:
    compiler, reading = compile_with_fallbacks(QUATERNION, QUATERNION)
    assert reading.is_valid([0, 0, 0, 5])
    assert "x-robot-unit-quaternion" in compiler.ignored


def test_a_relation_reading_inside_a_registered_keyword_is_undecided() -> None:
    four = compile_schema(FOUR)
    unit = compile_schema(QUATERNION, keywords=UNIT)
    assert four.relation_to(unit) == "undecided"
    assert unit.relation_to(four) != "not_subset"


def test_a_registered_keyword_passes_every_other_kind() -> None:
    reading = compile_schema({"x-robot-unit-quaternion": 1e-6}, keywords=UNIT)
    assert reading.is_valid("not an array")
    assert reading.is_valid({"w": 1})
    assert not reading.is_valid([1, 1, 1, 1])


def test_a_number_keyword_reads_no_boolean_as_a_number() -> None:
    positive = {"x-positive": Keyword("number", lambda number, _: number > 0)}
    reading = compile_schema({"x-positive": True}, keywords=positive)
    assert reading.is_valid(2)
    assert not reading.is_valid(-2)
    assert reading.is_valid(True)  # a boolean is another kind, which the keyword passes


def test_a_keyword_draft_2020_12_defines_is_not_registered() -> None:
    with pytest.raises(ValueError, match="'minimum': a keyword draft 2020-12 defines"):
        compile_schema({}, keywords={"minimum": Keyword("number", lambda *_: True)})


ROBOT = "https://example.com/vocab/robot"
META = "https://example.com/robot-meta"
STANDARD = {
    f"https://json-schema.org/draft/2020-12/vocab/{name}": True
    for name in ("core", "applicator", "unevaluated", "validation", "meta-data")
}


def _meta(vocabularies: dict[str, bool]) -> dict[str, object]:
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": META,
        "$vocabulary": vocabularies,
    }


def test_a_meta_schema_naming_a_registered_vocabulary_reads_its_keywords() -> None:
    documents = {META: _meta({**STANDARD, ROBOT: True})}
    schema = {"$schema": META, **QUATERNION}
    reading = compile_schema(schema, documents=documents, vocabularies={ROBOT: UNIT})
    assert reading.is_valid([0, 0, 0, 1])
    assert not reading.is_valid([0, 0, 0, 5])
    assert not reading.is_valid([0, 0, 1])


def test_a_required_vocabulary_no_caller_registers_is_refused() -> None:
    documents = {META: _meta({**STANDARD, ROBOT: True})}
    with pytest.raises(UnsupportedDialect, match=re.escape(f"requires the vocabulary {ROBOT!r}")):
        compile_schema({"$schema": META, **QUATERNION}, documents=documents)


def test_an_optional_vocabulary_no_caller_registers_is_read_as_annotations() -> None:
    documents = {META: _meta({**STANDARD, ROBOT: False})}
    reading = compile_schema({"$schema": META, **QUATERNION}, documents=documents)
    assert reading.is_valid([0, 0, 0, 5])


def test_a_dialect_leaving_out_an_asserting_vocabulary_is_refused() -> None:
    validation = "https://json-schema.org/draft/2020-12/vocab/validation"
    without = {uri: on for uri, on in STANDARD.items() if uri != validation}
    documents = {META: _meta({**without, ROBOT: True})}
    with pytest.raises(UnsupportedDialect, match="leaves out"):
        compile_schema({"$schema": META}, documents=documents, vocabularies={ROBOT: UNIT})


def test_a_meta_schema_no_document_holds_is_refused_as_before() -> None:
    with pytest.raises(UnsupportedDialect, match="this dialect is not supported"):
        compile_schema({"$schema": META, **QUATERNION}, vocabularies={ROBOT: UNIT})
