"""The values drawn from a schema: each one the compiled set admits, and enough of them."""

import random
from typing import Any

import pytest

from valgebra_jsonschema import compile_schema
from valgebra_jsonschema.sample import Sampler

TAG = {"enum": ["a", "b"]}


def _drawn(schema: object, tries: int = 40) -> list[Any]:
    return Sampler(schema, random.Random(0)).draw(schema, tries)


def test_an_all_of_is_drawn_as_the_conjunction_of_its_members():
    # The member narrows the items of a property the outer schema declares, beside a required
    # one it does not mention: both survive the merge.
    schema = {
        "type": "object",
        "required": ["n", "rs"],
        "properties": {"n": {"enum": [1, 2]}, "rs": {"type": "array", "items": {"type": "string"}}},
        "allOf": [{"properties": {"rs": {"items": TAG}}}],
    }
    drawn = _drawn(schema, 200)
    assert len(drawn) >= 20
    assert all(set(value) == {"n", "rs"} for value in drawn)


def test_a_branch_is_drawn_with_the_keywords_beside_it():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "integer"}, "b": {"type": "string"}},
        "anyOf": [{"required": ["a"]}, {"required": ["b"]}],
    }
    assert len(_drawn(schema)) >= 10


def test_a_reference_is_drawn_with_the_keywords_beside_it():
    schema = {"$defs": {"L": {"type": "array", "items": TAG}}, "$ref": "#/$defs/L", "minItems": 4}
    drawn = _drawn(schema)
    assert len(drawn) >= 5
    assert all(len(value) >= 4 for value in drawn)


def test_a_required_key_no_property_names_takes_the_additional_schema():
    schema = {"type": "object", "required": ["x"], "additionalProperties": {"type": "integer"}}
    assert len(_drawn(schema)) >= 10


@pytest.mark.parametrize(
    "pattern", [r"^([A-Z]{2}|\?)$", r"^(?:ab|cd)+x?$", r"^v[0-9]+(\.[0-9]+){2}$", r"^a.c$"]
)
def test_a_pattern_with_groups_and_alternatives_is_drawn_inside_it(pattern):
    drawn = _drawn({"type": "string", "pattern": pattern})
    assert len(drawn) >= 4
    assert all(compile_schema({"pattern": pattern}).is_valid(value) for value in drawn)


def test_a_pattern_the_generator_does_not_read_is_still_judged_by_membership():
    # A lookahead is left to the fallback text; whatever is drawn, the set admits it.
    schema = {"type": "string", "pattern": "^(?=a)a+$"}
    assert all(compile_schema(schema).is_valid(value) for value in _drawn(schema))


def test_types_and_bounds_two_members_both_write_meet():
    # The kinds both admit, an integer being a number, and the tighter of each bound.
    schema = {
        "allOf": [
            {"type": ["integer", "string"], "minimum": 100},
            {"type": "number", "minimum": 0, "maximum": 105},
        ]
    }
    drawn = _drawn(schema)
    assert len(drawn) >= 5
    assert all(isinstance(value, int) and 100 <= value <= 105 for value in drawn)
