"""A schema read over another record's keys.

`renamed(schema, names)` is the schema whose members are the members of `schema` with their
keys renamed: an object holding `names[k]` where a member of `schema` holds `k`, and every
value that is not an object as it is. Renaming is a reading of the keywords that name keys, so
it is this package's rather than valgebra's, and what it gives is a JSON Schema that
`compile_schema` reads like any other. Asking whether a result whose keys are `a` and `b` is
below an input schema written over `x` and `y` is then one inclusion:
`compile_schema(result).relation_to(compile_schema(renamed(input, {"x": "a", "y": "b"})))`.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from valgebra_jsonschema.schema import Unsupported

#: The keywords applying to the instance their schema applies to, each holding one schema.
_SAME_INSTANCE = frozenset({"not", "if", "then", "else"})

#: The keywords applying to the instance their schema applies to, each holding a list of them.
_SAME_INSTANCE_LISTS = frozenset({"allOf", "anyOf", "oneOf"})

#: The keywords that name no key of the instance and hold no schema of it: a member's other
#: kinds, its counts, the values under keys no keyword names, an array's items, a string's or a
#: number's own constraints, the definitions `$ref` reads, and the annotations.
_NAME_FREE = frozenset(
    {
        "$anchor",
        "$comment",
        "$defs",
        "$dynamicAnchor",
        "$id",
        "$schema",
        "$vocabulary",
        "additionalItems",
        "additionalProperties",
        "contains",
        "contentEncoding",
        "contentMediaType",
        "contentSchema",
        "default",
        "definitions",
        "deprecated",
        "description",
        "examples",
        "exclusiveMaximum",
        "exclusiveMinimum",
        "format",
        "id",
        "items",
        "maxContains",
        "maxItems",
        "maxLength",
        "maxProperties",
        "maximum",
        "minContains",
        "minItems",
        "minLength",
        "minProperties",
        "minimum",
        "multipleOf",
        "pattern",
        "prefixItems",
        "readOnly",
        "title",
        "type",
        "unevaluatedItems",
        "unevaluatedProperties",
        "uniqueItems",
        "writeOnly",
    }
)

#: The references a renamed schema keeps: into its definitions, which hold the schemas of other
#: instances and are not renamed. Any other reaches the renamed schema itself or a part of it.
_KEPT_REFERENCES = ("#/$defs/", "#/definitions/")

#: The keywords of a `propertyNames` a renaming reads: the names listed, and their kind.
_NAMES_LISTED = frozenset({"const", "enum", "type", "$comment", "title", "description"})


def renamed(schema: object, names: Mapping[str, str]) -> object:
    """Give `schema` read over the keys `names` renames, `{old: new}`.

    A member of the result is an object of `schema` with each key `k` written as `names[k]`, and
    a value that is not an object as `schema` holds it. The renaming is a permutation of the
    key strings: a new name `schema` does not rename is written as the old name that took it, so
    `{"a": "x"}` reads a key `x` of `schema` as `a`, and no two keys of a member become one.

    Renamed where the instance is the one the schema reads: `properties`, `required`,
    `dependentRequired`, `dependentSchemas` and `dependencies` name keys, an object `const` or
    `enum` holds them, a `propertyNames` of `const` or `enum` lists them, and `allOf`, `anyOf`,
    `oneOf`, `not`, `if`, `then` and `else` read the same instance. A property's value, an item
    and a definition belong to other instances and stay as written.

    `Unsupported` is raised where a keyword names keys in a way a renaming cannot follow:
    `patternProperties`, a `propertyNames` schema other than a list of names, a reference
    anywhere but into the definitions, and a keyword this does not know. `ValueError` is raised
    where two names are renamed to one.
    """
    if len(set(names.values())) != len(names):
        message = "two keys are renamed to one name, so a member holding both has no renaming"
        raise ValueError(message)
    # A chain `a -> b -> c` closes as `c -> a`; a cycle closes itself.
    permutation = dict(names)
    for start in names:
        if start in names.values():
            continue
        end = names[start]
        while end in names:
            end = names[end]
        permutation[end] = start
    _refuse_references(schema)
    return _rename(schema, permutation)


def _refuse_references(schema: object) -> None:
    """Refuse a reference a renamed schema would read renamed where it was written whole."""
    if isinstance(schema, list):
        for item in schema:
            _refuse_references(item)
        return
    if not isinstance(schema, dict):
        return
    for keyword in ("$ref", "$dynamicRef", "$recursiveRef"):
        target = schema.get(keyword)
        if target is not None and not (
            keyword == "$ref" and isinstance(target, str) and target.startswith(_KEPT_REFERENCES)
        ):
            message = (
                f"`{keyword}: {target!r}` may read the schema being renamed, whose keys a "
                "renaming changes; a reference into `$defs` or `definitions` is read as written"
            )
            raise Unsupported(message)
    for value in schema.values():
        _refuse_references(value)


def _rename(schema: object, to: dict[str, str]) -> object:
    """Rename the keys `schema` names of the instance it reads, by the permutation `to`."""
    if isinstance(schema, bool) or not to:
        return schema
    if not isinstance(schema, dict):
        message = f"a schema is an object or a boolean, not {type(schema).__name__}"
        raise Unsupported(message)
    out: dict[str, Any] = {}
    for keyword, value in schema.items():
        out[keyword] = _keyword(keyword, value, to)
    return out


def _keyword(keyword: str, value: Any, to: dict[str, str]) -> Any:  # noqa: PLR0911 - one arm a keyword
    """Rename what `keyword` names of the instance its schema reads."""
    name = lambda key: to.get(key, key)  # noqa: E731 - one reading, named for its arms
    if keyword in _NAME_FREE:
        return value
    if keyword in _SAME_INSTANCE:
        return _rename(value, to)
    if keyword in _SAME_INSTANCE_LISTS:
        return [_rename(branch, to) for branch in value]
    if keyword == "properties":
        return {name(key): sub for key, sub in value.items()}
    if keyword == "required":
        return [name(key) for key in value]
    if keyword == "dependentRequired":
        return {name(key): [name(other) for other in keys] for key, keys in value.items()}
    if keyword == "dependentSchemas":
        return {name(key): _rename(sub, to) for key, sub in value.items()}
    if keyword == "dependencies":
        return {
            name(key): [name(other) for other in sub] if isinstance(sub, list) else _rename(sub, to)
            for key, sub in value.items()
        }
    if keyword == "const":
        return _renamed_object(value, to)
    if keyword == "enum":
        return [_renamed_object(member, to) for member in value]
    if keyword == "propertyNames":
        return _renamed_names(value, to)
    if keyword == "patternProperties" and not value:
        return value
    reason = (
        "names keys by a pattern, which a renaming does not read"
        if keyword == "patternProperties"
        else "is a keyword a renaming does not read"
    )
    message = f"`{keyword}` {reason}"
    raise Unsupported(message)


def _renamed_object(value: object, to: dict[str, str]) -> object:
    """Rename a constant's keys where it is an object, and keep it as it is where it is not."""
    if isinstance(value, dict):
        return {to.get(key, key): member for key, member in value.items()}
    return value


def _renamed_names(value: object, to: dict[str, str]) -> object:
    """Rename the names a `propertyNames` lists, refusing one that lists none."""
    if isinstance(value, bool):
        return value
    if not isinstance(value, dict) or not set(value) <= _NAMES_LISTED:
        message = "`propertyNames` other than a `const` or an `enum` of names is not renamed"
        raise Unsupported(message)
    out = dict(value)
    if isinstance(out.get("const"), str):
        out["const"] = to.get(out["const"], out["const"])
    if "enum" in out:
        out["enum"] = [to.get(n, n) if isinstance(n, str) else n for n in out["enum"]]
    return out
