"""A schema read closed at its root: its members holding no key no keyword evaluates."""

import pytest
from valgebra import intersection, nothing

from valgebra_jsonschema import Unsupported, closed, compile_schema

DETECTION = {
    "type": "object",
    "properties": {
        "object_id": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
    },
    "required": ["object_id", "confidence"],
}
#: An argument a detection meets only through a key it does not name.
DISTANCE = {
    "type": "object",
    "properties": {
        "unit": {"type": "string", "const": "m"},
        "value": {"type": "number", "minimum": 0.2, "maximum": 0.6},
    },
    "required": ["unit", "value"],
}
#: A result whose keys a definition and the root declare between them.
INHERITED = {
    "$defs": {
        "Base": {
            "type": "object",
            "properties": {"object_id": {"type": "string"}},
            "required": ["object_id"],
        }
    },
    "allOf": [{"$ref": "#/$defs/Base"}],
    "properties": {"confidence": {"type": "number"}},
    "required": ["confidence"],
}


def test_a_closed_result_meets_no_argument_through_a_key_it_does_not_name() -> None:
    argument = compile_schema(DISTANCE)
    assert intersection(compile_schema(DETECTION), argument).relation_to(nothing) == "not_subset"
    assert intersection(compile_schema(closed(DETECTION)), argument).relation_to(nothing) == (
        "subset"
    )


def test_a_key_a_reference_declares_is_evaluated_and_another_is_not() -> None:
    reading = compile_schema(closed(INHERITED))
    result = {"object_id": "obj_1", "confidence": 0.5}
    assert reading.is_valid(result)
    assert not reading.is_valid({**result, "unit": "m"})
    assert reading.relation_to(nothing) == "not_subset"
    assert reading.relation_to(compile_schema(INHERITED)) == "subset"
    # `additionalProperties` sees its sibling `properties` alone, so it empties the same result.
    sibling = compile_schema({**INHERITED, "additionalProperties": False})
    assert sibling.relation_to(nothing) == "subset"


def test_a_record_under_a_property_stays_as_written() -> None:
    pose = {"type": "object", "properties": {"x": {"type": "number"}}, "required": ["x"]}
    schema = {"type": "object", "properties": {"pose": pose}, "required": ["pose"]}
    reading = compile_schema(closed(schema))
    assert reading.is_valid({"pose": {"x": 1, "unit": "m"}})
    assert not reading.is_valid({"pose": {"x": 1}, "unit": "m"})


def test_a_value_of_another_kind_is_held_as_the_schema_holds_it() -> None:
    reading = compile_schema(closed({"type": ["object", "string"], "properties": {"a": {}}}))
    assert reading.is_valid("text")
    assert reading.is_valid({"a": 1})
    assert not reading.is_valid({"b": 1})
    assert closed(True) == {"unevaluatedProperties": False}
    assert closed(False) is False


def test_an_unevaluated_schema_is_replaced_by_its_closing() -> None:
    schema = {"properties": {"a": {}}, "unevaluatedProperties": {"type": "integer"}}
    assert closed(schema) == {"properties": {"a": {}}, "unevaluatedProperties": False}
    assert compile_schema(schema).is_valid({"a": 1, "b": 2})
    assert not compile_schema(closed(schema)).is_valid({"a": 1, "b": 2})


def test_an_older_draft_is_upgraded_before_it_is_closed() -> None:
    draft7 = {"$schema": "http://json-schema.org/draft-07/schema#", "properties": {"a": {}}}
    reading = compile_schema(closed(draft7))
    assert reading.is_valid({"a": 1})
    assert not reading.is_valid({"b": 1})


def test_a_closing_the_compiler_cannot_read_is_refused_when_it_compiles() -> None:
    wide = {"anyOf": [{"properties": {f"k{i}": {"type": "integer"}}} for i in range(5)]}
    with pytest.raises(Unsupported, match="5 branches"):
        compile_schema(closed(wide))
    with pytest.raises(Unsupported, match="an object or a boolean"):
        closed(["not", "a", "schema"])
