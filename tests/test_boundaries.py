"""The package's boundaries, held by tests rather than by convention."""

import ast
import json
import re
from pathlib import Path

import pytest

from valgebra_jsonschema.schema import ANNOTATIONS, REFUSED, SUPPORTED, Compiler

PACKAGE = Path(__file__).parent.parent / "valgebra_jsonschema"

#: Every keyword of the draft 2020-12 vocabularies, from the meta-schemas.
DRAFT_2020_12 = {
    "core": [
        "$id",
        "$schema",
        "$ref",
        "$anchor",
        "$dynamicRef",
        "$dynamicAnchor",
        "$vocabulary",
        "$comment",
        "$defs",
    ],
    "applicator": [
        "prefixItems",
        "items",
        "contains",
        "additionalProperties",
        "properties",
        "patternProperties",
        "dependentSchemas",
        "propertyNames",
        "if",
        "then",
        "else",
        "allOf",
        "anyOf",
        "oneOf",
        "not",
    ],
    "unevaluated": ["unevaluatedItems", "unevaluatedProperties"],
    "validation": [
        "type",
        "const",
        "enum",
        "multipleOf",
        "maximum",
        "exclusiveMaximum",
        "minimum",
        "exclusiveMinimum",
        "maxLength",
        "minLength",
        "pattern",
        "maxItems",
        "minItems",
        "uniqueItems",
        "maxContains",
        "minContains",
        "maxProperties",
        "minProperties",
        "required",
        "dependentRequired",
    ],
    "meta-data": [
        "title",
        "description",
        "default",
        "deprecated",
        "readOnly",
        "writeOnly",
        "examples",
    ],
    "format-annotation": ["format"],
    "content": ["contentEncoding", "contentMediaType", "contentSchema"],
}


def test_only_the_boundary_module_imports_valgebra():
    for path in PACKAGE.glob("*.py"):
        if path.name == "_valgebra.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        imported = {
            node.module.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        } | {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        assert "valgebra" not in imported, path.name


def test_every_draft_2020_12_keyword_is_classified_once():
    every = [k for words in DRAFT_2020_12.values() for k in words]
    classes = {"supported": SUPPORTED, "annotation": ANNOTATIONS, "refused": REFUSED}
    for keyword in every:
        homes = [name for name, words in classes.items() if keyword in words]
        assert len(homes) == 1, (keyword, homes)


def test_the_inventory_names_no_keyword_outside_the_vocabularies():
    every = {k for words in DRAFT_2020_12.values() for k in words}
    extra = (
        (SUPPORTED | REFUSED)
        - every
        - {"additionalItems", "dependencies", "$recursiveRef", "$recursiveAnchor", "definitions"}
    )
    assert extra == set()
    assert json.dumps(sorted(SUPPORTED))


def _inventory():
    """Read the page's table: each class, and the keywords its row names."""
    page = (Path(__file__).parent.parent / "docs" / "03-conformance.md").read_text(encoding="utf-8")
    table = page[page.index("| class | keywords |") :]
    rows = {}
    for line in table.splitlines()[2:]:
        if not line.startswith("|"):
            break
        name, words = line.strip("|").split("|", 1)
        rows[name.strip()] = set(re.findall(r"`([^`]+)`", words))
    return rows


def test_the_page_lists_each_class_as_the_code_does():
    rows = _inventory()
    exact, opaque = rows["translated exactly"], rows["translated as an opaque predicate"]
    assert exact | opaque == set(SUPPORTED)
    assert exact & opaque == {"multipleOf"}, "a step is exact where it is whole"
    assert rows["annotations"] == set(ANNOTATIONS)
    assert rows["refused"] == set(REFUSED)


@pytest.mark.parametrize(
    "schema",
    [
        {"patternProperties": {"a": {"type": "integer"}}},
        {"propertyNames": {"maxLength": 1}},
        {"uniqueItems": True},
        {"contains": {"type": "integer"}, "minContains": 2},
        {"contains": {"type": "integer"}, "maxContains": 2},
        {"multipleOf": 0.5},
    ],
)
def test_what_the_page_calls_opaque_is_opaque(schema):
    compiler = Compiler(schema)
    compiler.compile(schema)
    assert compiler.opaque, schema


@pytest.mark.parametrize(
    "schema",
    [
        {"multipleOf": 2},
        {"type": "integer", "minimum": 1},
        {"pattern": "a"},
        {"properties": {"a": {"type": "string"}}, "required": ["a"]},
        {"if": {"type": "string"}, "then": {"minLength": 1}},
    ],
)
def test_what_the_page_calls_exact_is_not_opaque(schema):
    compiler = Compiler(schema)
    compiler.compile(schema)
    assert not compiler.opaque, schema
