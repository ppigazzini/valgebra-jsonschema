"""A keyword a caller registers asserts as a predicate; an unregistered one is an annotation."""

import math

import pytest

from valgebra_jsonschema import Keyword, compile_schema, compile_with_fallbacks


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
