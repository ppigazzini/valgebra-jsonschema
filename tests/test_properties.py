"""Properties checked over many random cases rather than a few chosen ones."""

import itertools
import random

import jsonschema
import pytest
from valgebra import ValidationError, intersection

from valgebra_jsonschema import closed
from valgebra_jsonschema.schema import ITEM, Compiler, Unsupported, compile_schema

SCALARS = [None, True, False, 0, 1, -1, 1.0, 2.5, -7, 10**6, "", "a", "ab", "abc", "Z9"]


def _value(rng, depth=2):
    kind = rng.randrange(7 if depth > 0 else 5)
    if kind < 5:
        return rng.choice(SCALARS)
    if kind == 5:
        return [_value(rng, depth - 1) for _ in range(rng.randrange(4))]
    keys = rng.sample(["a", "b", "c", "d"], rng.randrange(4))
    return {k: _value(rng, depth - 1) for k in keys}


def _schema(rng, depth=2):
    """Draw a schema over the keywords whose meaning `jsonschema` shares exactly.

    Patterns are left out (`jsonschema` reads them with Python's `re`, not ECMA-262) and
    so is a fractional `multipleOf` (it divides binary floats).
    """
    leaf = [
        lambda: {
            "type": rng.choice(
                ["null", "boolean", "integer", "number", "string", "array", "object"]
            )
        },
        lambda: {"type": rng.sample(["null", "integer", "string", "array"], 2)},
        lambda: {"enum": rng.sample(SCALARS, 3)},
        lambda: {"const": rng.choice(SCALARS)},
        lambda: {"minimum": rng.randrange(-3, 4)},
        lambda: {"exclusiveMaximum": rng.randrange(-3, 4)},
        lambda: {"multipleOf": rng.choice([1, 2, 3])},
        lambda: {"minLength": rng.randrange(3)},
        lambda: {"maxLength": rng.randrange(3)},
        lambda: {"minItems": rng.randrange(3)},
        lambda: {"maxProperties": rng.randrange(3)},
        lambda: {"required": rng.sample(["a", "b", "c"], rng.randrange(1, 3))},
        lambda: {"propertyNames": {"enum": rng.sample(["a", "b", "c", "d", 1], 2)}},
        lambda: {"propertyNames": {"const": rng.choice(["a", "b", 1])}},
    ]
    if depth == 0:
        return rng.choice(leaf)()
    nested = [
        lambda: {"items": _schema(rng, depth - 1)},
        lambda: {"prefixItems": [_schema(rng, depth - 1)], "items": _schema(rng, depth - 1)},
        lambda: {"contains": _schema(rng, depth - 1)},
        lambda: {
            "properties": {"a": _schema(rng, depth - 1), "b": _schema(rng, depth - 1)},
            "additionalProperties": rng.choice([True, False, _schema(rng, depth - 1)]),
        },
        lambda: {"anyOf": [_schema(rng, depth - 1), _schema(rng, depth - 1)]},
        lambda: {"allOf": [_schema(rng, depth - 1), _schema(rng, depth - 1)]},
        lambda: {"oneOf": [_schema(rng, depth - 1), _schema(rng, depth - 1)]},
        lambda: {"not": _schema(rng, depth - 1)},
        lambda: {"if": _schema(rng, depth - 1), "then": _schema(rng, depth - 1)},
        lambda: {"dependentRequired": {"a": ["b"]}},
    ]
    return rng.choice(leaf + nested)()


@pytest.mark.parametrize("seed", range(10))
def test_membership_agrees_with_the_jsonschema_package_on_random_schemas(seed):
    rng = random.Random(f"diff:{seed}")
    for _ in range(40):
        schema = _schema(rng)
        compiled = compile_schema(schema)
        reference = jsonschema.Draft202012Validator(schema)
        for _ in range(25):
            value = _value(rng)
            assert compiled.is_valid(value) == reference.is_valid(value), (schema, value)


@pytest.mark.parametrize("seed", range(10))
def test_every_inclusion_and_emptiness_valgebra_proves_holds_on_every_drawn_value(seed):
    rng = random.Random(f"proof:{seed}")
    schemas = [compile_schema(_schema(rng)) for _ in range(24)]
    values = [_value(rng) for _ in range(200)]
    for a, b in itertools.combinations(schemas, 2):
        if a.is_subtype_of(b):
            assert not [v for v in values if a.is_valid(v) and not b.is_valid(v)]
        if intersection(a, b).is_empty():
            assert not [v for v in values if a.is_valid(v) and b.is_valid(v)]


def _held(value, depth=2):
    """Yield each path below ``value`` to ``depth`` steps, with the value there."""
    if depth == 0:
        return
    if isinstance(value, dict):
        steps = value.items()
    elif isinstance(value, list):
        steps = [(ITEM, item) for item in value]
    else:
        return
    for step, below in steps:
        yield (step,), below
        for path, deeper in _held(below, depth - 1):
            yield (step, *path), deeper


@pytest.mark.parametrize("seed", range(10))
def test_every_value_a_member_holds_below_lies_in_what_below_reads(seed):
    # An upper bound: no keyword's reading may leave out a value a member holds there.
    rng = random.Random(f"below:{seed}")
    for _ in range(30):
        schema = _schema(rng)
        compiled, compiler, read = compile_schema(schema), Compiler(schema), {}
        for member in (v for v in (_value(rng) for _ in range(60)) if compiled.is_valid(v)):
            for path, held in _held(member):
                if path not in read:
                    read[path] = compiler.below(path)
                assert read[path].is_valid(held), (schema, member, path)


@pytest.mark.parametrize("seed", range(10))
def test_a_closed_schema_is_below_its_schema_and_held_as_jsonschema_holds_it(seed):
    """`closed(s)` is below `s`, and its members are those `jsonschema` reads it to hold."""
    rng = random.Random(f"closed:{seed}")
    for _ in range(30):
        schema = _schema(rng)
        try:
            reading = compile_schema(closed(schema))
        except Unsupported:
            continue
        written = compile_schema(schema)
        assert reading.relation_to(written) == "subset", schema
        reference = jsonschema.Draft202012Validator(closed(schema))
        for _ in range(25):
            value = _value(rng)
            assert reading.is_valid(value) == reference.is_valid(value), (schema, value)
            assert not reading.is_valid(value) or written.is_valid(value), (schema, value)


#: The keywords a failure below is reported under by its subschema's own.
READING_DOWN = {
    *("properties", "patternProperties", "additionalProperties", "unevaluatedProperties"),
    *("prefixItems", "items", "unevaluatedItems", "contains", "propertyNames"),
}


def _many_keywords(rng):
    """Draw a schema object of several keywords, the applicators `_schema` leaves out among them."""

    def sub():
        return _schema(rng, 1)

    more = [
        lambda: {"patternProperties": {"^[ab]$": sub()}},
        lambda: {"dependentSchemas": {"a": sub()}},
        lambda: {"$ref": "#/$defs/A"},
        lambda: {"unevaluatedProperties": rng.choice([False, sub()])},
        lambda: {"properties": {"a": False}},
        lambda: {"items": False},
        lambda: {"if": sub(), "then": sub(), "else": sub()},
        lambda: {"contains": sub(), "minContains": 2},
        lambda: {"minimum": rng.randrange(-3, 4), "maximum": rng.randrange(-3, 4)},
    ]
    schema = {}
    for _ in range(rng.randrange(1, 4)):
        schema |= _schema(rng) if rng.random() < 0.5 else rng.choice(more)()
    return schema | {"$defs": {"A": sub()}}


def _reported(schema, value):
    """Return the location of every error `jsonschema` reports, the ones inside a union too."""
    where = set()
    errors = list(jsonschema.Draft202012Validator(schema).iter_errors(value))
    while errors:
        error = errors.pop()
        where.add("".join(f"/{step}" for step in error.absolute_schema_path))
        errors += error.context
    return where


@pytest.mark.parametrize("seed", range(10))
def test_every_keyword_named_is_one_the_jsonschema_package_reports(seed):
    rng = random.Random(f"located:{seed}")
    failures = unnamed = 0
    for _ in range(60):
        schema = _many_keywords(rng)
        compiler = Compiler(schema)
        compiled = compiler.compile(schema)
        for _ in range(12):
            value = _value(rng)
            try:
                compiled.validate(value)
            except ValidationError as refused:
                where = _reported(schema, value)
                for failure in refused.errors:
                    path = failure["path"]
                    assert isinstance(path, tuple)
                    named = compiler.keywords_failed(value, path)
                    failures += 1
                    # valgebra reports the nearest branch of a union, so a failure may be of the
                    # `else` its `if` does not pick, which no keyword made; and a key left
                    # unevaluated beside a sibling that fails is not told from one left by it.
                    unnamed += not named and not schema.keys() & {"else", "unevaluatedProperties"}
                    for keyword, location in named:
                        # `jsonschema` leaves a reference, and the name of a field whose schema
                        # is `false`, out of a location, where Core's section 12.3.1 writes both.
                        at = location.removeprefix("#").replace("/$ref", "")
                        below = any(other.startswith(f"{at}/") for other in where)
                        assert (
                            at in where
                            or (keyword in READING_DOWN and below)
                            or (
                                keyword == "properties"
                                and "/properties" in at
                                and at.rpartition("/")[0] in where
                            )
                        ), (schema, value, path, location, where)
    assert failures > 200
    assert unnamed == 0
