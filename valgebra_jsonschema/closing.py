"""A schema read closed at its root.

`closed(schema)` is the schema whose members are the members of `schema` holding no key that no
keyword of the root evaluates: every value that is not an object, as `schema` holds it, and
every object of `schema` each key of which a `properties`, `patternProperties`,
`additionalProperties` or `unevaluatedProperties` of the root, or of an in-place applicator
reaching the root's instance, evaluates. It is the root with `unevaluatedProperties: false`,
whose validation "applies only to the child values of instance names that do not appear in"
those keywords' annotation results (draft 2020-12, section 11.3), so a property an `allOf` or a
`$ref` declares is evaluated, where `additionalProperties`, which sees its own sibling
`properties` alone, would refuse it.

A published schema is open: a key it does not name may hold any value. Closing it is a reading
of the keywords that evaluate keys, so it is this package's rather than valgebra's, and what it
gives is a JSON Schema that `compile_schema` reads like any other. It is narrower than
`schema`, never wider: every member of `closed(schema)` is a member of `schema`. A record nested
under a property stays as written, open where it was.
"""

from __future__ import annotations

from valgebra_jsonschema.schema import Unsupported, older, upgrade


def closed(schema: object) -> dict[str, object] | bool:
    """Give `schema` read closed at its root: its members holding no key no keyword evaluates.

    The root gains `unevaluatedProperties: false`, which replaces an `unevaluatedProperties` it
    held, whose members are among the result's. An older draft's document, which knows no
    `unevaluatedProperties`, is first rewritten into draft 2020-12 by `upgrade`, as
    `compile_schema` rewrites it. `compile_schema` refuses the result where it refuses the
    keyword beside the root's others: an `anyOf` of more than four branches, more than 64
    cases, or a `$ref` reaching itself at one instance. `Unsupported` is raised for a schema
    that is neither an object nor a boolean.
    """
    draft = older(schema)
    if draft is not None:
        schema = upgrade(schema, draft)
    if schema is False:
        return False
    if schema is True:
        return {"unevaluatedProperties": False}
    if not isinstance(schema, dict):
        message = f"a schema is an object or a boolean, not {type(schema).__name__}"
        raise Unsupported(message)
    return {**schema, "unevaluatedProperties": False}
