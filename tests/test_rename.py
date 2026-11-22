"""A schema read over another record's keys: the members of a schema, their keys renamed."""

from __future__ import annotations

from typing import Any

import pytest

from valgebra_jsonschema import Unsupported, compile_schema, renamed

#: J4's pair: a result whose two keys agree, and an input whose `if` reads that agreement.
OUT = {
    "type": "object",
    "required": ["a", "b"],
    "properties": {"a": {"type": "integer"}, "b": {"type": "integer"}},
    "allOf": [
        {
            "oneOf": [
                {"properties": {"a": {"const": 1}, "b": {"const": 1}}},
                {"properties": {"a": {"const": 2}, "b": {"const": 2}}},
            ]
        }
    ],
}
PAIR = {
    "type": "object",
    "required": ["x", "y"],
    "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
    "if": {"properties": {"x": {"const": 1}}},
    "then": {"properties": {"y": {"const": 1}}},
    "else": {"properties": {"y": {"const": 2}}},
}


def test_a_result_is_below_an_input_read_over_its_keys() -> None:
    """J4: `OUT`'s records are below `PAIR` read over `OUT`'s keys, which is no proof as written."""
    over_out = renamed(PAIR, {"x": "a", "y": "b"})
    assert compile_schema(OUT).relation_to(compile_schema(over_out)) == "subset"
    assert compile_schema(OUT).relation_to(compile_schema(PAIR)) != "subset"


def test_a_name_the_schema_holds_is_given_the_old_one() -> None:
    """The renaming is a permutation: `x` taking `a` gives `a` to a key `x` the schema names."""
    schema = {"required": ["a", "x"], "properties": {"a": {"type": "string"}, "x": {}}}
    assert renamed(schema, {"a": "x"}) == {
        "required": ["x", "a"],
        "properties": {"x": {"type": "string"}, "a": {}},
    }
    chained = renamed({"required": ["a", "b", "c"]}, {"a": "b", "b": "c"})
    assert chained == {"required": ["b", "c", "a"]}


def test_the_keywords_of_the_same_instance_are_renamed_and_another_s_are_not() -> None:
    schema = {
        "properties": {"a": {"properties": {"a": {}}, "required": ["a"]}},
        "dependentRequired": {"a": ["b"]},
        "dependentSchemas": {"b": {"required": ["a"]}},
        "dependencies": {"a": ["b"], "b": {"required": ["a"]}},
        "const": {"a": {"a": 1}},
        "enum": [{"b": 2}, 3],
        "propertyNames": {"enum": ["a", "b"]},
        "anyOf": [{"required": ["a"]}],
        "not": {"required": ["b"]},
        "items": {"required": ["a"]},
        "$defs": {"d": {"required": ["a"]}},
    }
    assert renamed(schema, {"a": "x", "b": "y"}) == {
        "properties": {"x": {"properties": {"a": {}}, "required": ["a"]}},
        "dependentRequired": {"x": ["y"]},
        "dependentSchemas": {"y": {"required": ["x"]}},
        "dependencies": {"x": ["y"], "y": {"required": ["x"]}},
        "const": {"x": {"a": 1}},
        "enum": [{"y": 2}, 3],
        "propertyNames": {"enum": ["x", "y"]},
        "anyOf": [{"required": ["x"]}],
        "not": {"required": ["y"]},
        "items": {"required": ["a"]},
        "$defs": {"d": {"required": ["a"]}},
    }


@pytest.mark.parametrize(
    "schema",
    [
        {"patternProperties": {"^a": {}}},
        {"propertyNames": {"pattern": "^a"}},
        {"$ref": "#"},
        {"properties": {"child": {"$ref": "#"}}},
        {"$dynamicRef": "#node"},
        {"unknownKeyword": 1},
    ],
    ids=["pattern", "names-schema", "root-ref", "inner-ref", "dynamic-ref", "unknown"],
)
def test_a_keyword_a_renaming_cannot_follow_is_refused(schema: dict[str, Any]) -> None:
    with pytest.raises(Unsupported):
        renamed(schema, {"a": "x"})


def test_two_keys_renamed_to_one_name_are_refused() -> None:
    with pytest.raises(ValueError, match="renamed to one"):
        renamed({"required": ["a", "b"]}, {"a": "x", "b": "x"})


def test_a_reference_into_the_definitions_is_kept() -> None:
    schema = {"properties": {"a": {"$ref": "#/$defs/n"}}, "$defs": {"n": {"type": "integer"}}}
    assert renamed(schema, {"a": "x"}) == {
        "properties": {"x": {"$ref": "#/$defs/n"}},
        "$defs": {"n": {"type": "integer"}},
    }


#: Objects over the renamed keys and the names they take, and a value of each other kind.
_VALUES = [
    {"a": 1},
    {"a": 1, "b": None, "x": "a"},
    {"a": 1, "b": True},
    {"a": 1, "b": True, "x": "a"},
    {"a": 2, "y": None},
    {"a": "1"},
    {"x": "a"},
    {"a": 1, "x": "b"},
    {"a": 0, "y": {"a": 1}},
    {},
    [],
    None,
    "a",
]


@pytest.mark.parametrize("value", _VALUES)
def test_a_renamed_member_is_a_member_of_the_renamed_schema(value: object) -> None:
    """`renamed(S, n)` holds a value with its keys renamed exactly where `S` holds the value."""
    names = {"a": "x", "b": "y"}
    to = {"a": "x", "b": "y", "x": "a", "y": "b"}
    schema = {
        "type": "object",
        "required": ["a"],
        "properties": {"a": {"type": "integer"}, "x": {"const": "a"}},
        "dependentRequired": {"b": ["x"]},
        "if": {"properties": {"a": {"const": 1}}},
        "then": {"required": ["b"]},
        "additionalProperties": {"type": ["null", "boolean"]},
    }
    moved = {to.get(k, k): v for k, v in value.items()} if isinstance(value, dict) else value
    assert compile_schema(renamed(schema, names)).is_valid(moved) == compile_schema(
        schema
    ).is_valid(value)
