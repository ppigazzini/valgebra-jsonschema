import contextlib
import itertools
import json
import math
import operator
import random
import re
import subprocess
import sys
from collections.abc import Callable
from fractions import Fraction
from typing import Annotated, Any, ClassVar

import pytest
from annotated_types import MinLen
from valgebra import ValidationError, Validator, complement, intersection, nothing

from valgebra_jsonschema import Length, admitted, length
from valgebra_jsonschema import schema as schema_module
from valgebra_jsonschema.schema import (
    ANNOTATIONS,
    ARRAY,
    ITEM,
    JSON,
    OBJECT,
    REFUSED,
    SUPPORTED,
    Compiler,
    Unsupported,
    compile_schema,
    constants,
    json_key,
    upgrade,
)


class TestSemantics:
    def test_an_assertion_passes_every_other_kind(self):
        assert compile_schema({"minimum": 3}).is_valid("a")
        assert not compile_schema({"minimum": 3}).is_valid(2)

    def test_integer_admits_an_integral_float_and_refuses_a_boolean(self):
        integer = compile_schema({"type": "integer"})
        assert integer.is_valid(1.0)
        assert not integer.is_valid(1.5)
        assert not integer.is_valid(True)

    def test_enum_compares_numbers_by_value_and_never_equals_a_boolean(self):
        one = compile_schema({"enum": [1]})
        assert one.is_valid(1.0)
        assert not one.is_valid(True)

    def test_pattern_searches_rather_than_matching_the_whole_string(self):
        assert compile_schema({"pattern": "b+"}).is_valid("abbbc")
        assert not compile_schema({"pattern": "^b+$"}).is_valid("abbbc")

    def test_a_required_key_outside_properties_takes_the_additional_schema(self):
        s = compile_schema({"required": ["x"], "additionalProperties": {"type": "integer"}})
        assert s.is_valid({"x": 1})
        assert not s.is_valid({"x": "1"})

    def test_a_fractional_step_is_checked_in_exact_rational_arithmetic(self):
        compiler = Compiler({"multipleOf": 0.0001})
        assert compiler.compile({"multipleOf": 0.0001}).is_valid(0.0075)
        assert compiler.opaque == {"multipleOf"}

    def test_an_integral_step_is_decided_exactly(self):
        # Past `EXACT_STEP` a step has no float equal to it, and `1e16`, a multiple of the
        # float nearest `10000000000000001`, is no multiple of the step.
        step = 10000000000000001
        past = Compiler({"multipleOf": step})
        compiled = past.compile({"multipleOf": step})
        assert not compiled.is_valid(1e16)
        assert compiled.is_valid(2 * step)
        assert past.opaque == {"multipleOf"}
        assert Compiler({"multipleOf": 2}).opaque == set()

    def test_an_integral_step_agrees_with_exact_arithmetic(self):
        # Steps on both sides of `EXACT_STEP`, against integers, integral floats past 2**53
        # and any floats, each answered as `Fraction` arithmetic answers it; seed 0.
        rng = random.Random(0)
        edge = schema_module.EXACT_STEP
        for _ in range(200):
            step = rng.choice(
                [rng.randrange(1, edge + 1), edge, edge - 1, edge + 1, rng.randrange(edge, 2**70)]
            )
            compiled = compile_schema({"multipleOf": step})
            for _ in range(25):
                value = rng.choice(
                    [
                        float(step * rng.randrange(1, 2**20)),
                        step * rng.randrange(-(2**20), 2**20),
                        float(rng.randrange(1, 2**80)),
                        rng.randrange(1, 2**90),
                        rng.uniform(1, 2**60),
                    ]
                )
                exact = Fraction(value) % step == 0
                assert compiled.is_valid(value) == exact, (step, value)

    def test_an_integral_step_is_no_float_step_typing_cached(self):
        # `typing.Annotated` caches a subscript by its arguments' equality, and
        # `MultipleOf(2) == MultipleOf(2.0)`: a process that built the float step first held
        # it where an integral step was asked, and admitted `2**53 + 1`.
        program = (
            "from typing import Annotated\n"
            "from annotated_types import MultipleOf\n"
            "Annotated[int, MultipleOf(2.0)], Annotated[float, MultipleOf(2.0)]\n"
            "from valgebra_jsonschema import compile_schema\n"
            "print(compile_schema({'multipleOf': 2}).is_valid(2**53 + 1))\n"
        )
        ran = subprocess.run(  # noqa: S603 - this interpreter, a fixed program
            [sys.executable, "-c", program],
            capture_output=True,
            text=True,
            encoding="locale",
            check=True,
        )
        assert ran.stdout.split() == ["False"]

    def test_a_recursive_reference_compiles_to_its_fixpoint(self):
        tree = {
            "$defs": {
                "node": {
                    "type": "object",
                    "properties": {"kids": {"type": "array", "items": {"$ref": "#/$defs/node"}}},
                }
            },
            "$ref": "#/$defs/node",
        }
        s = compile_schema(tree)
        assert s.is_valid({"kids": [{"kids": []}, {}]})
        assert not s.is_valid({"kids": [1]})


_INT = {"type": "integer"}
_STR = {"type": "string"}


class TestEmbeddedResources:
    def test_an_embedded_id_with_nothing_resolving_inside_is_an_annotation(self):
        # A base URI matters to the references inside its resource; with none, the resource
        # means what its keywords mean.
        schema = {"properties": {"a": {"$id": "#/properties/a", "type": "string", "minLength": 2}}}
        compiled = compile_schema(schema)
        assert compiled.is_valid({"a": "ab"})
        assert not compiled.is_valid({"a": "a"})

    def test_an_embedded_id_declaring_another_dialect_is_refused(self):
        draft7 = "http://json-schema.org/draft-07/schema#"
        resource = {"$id": "http://example.com/a", "$schema": draft7}
        with pytest.raises(Unsupported, match="declares another dialect"):
            compile_schema({"properties": {"a": resource}})

    def test_a_reference_resolves_against_the_resource_it_sits_in(self):
        resource = {"$id": "http://example.com/a", "$ref": "#/$defs/b", "$defs": {"b": _INT}}
        s = compile_schema({"$defs": {"b": _STR}, "properties": {"a": resource}})
        assert s.is_valid({"a": 1})
        assert not s.is_valid({"a": "1"})

    def test_an_anchor_names_its_schema_within_its_resource(self):
        schema = {
            "$defs": {
                "a": {"$id": "http://example.com/a", "$defs": {"n": {"$anchor": "n", **_INT}}}
            },
            "$ref": "http://example.com/a#n",
        }
        assert compile_schema(schema).is_valid(1)
        assert not compile_schema(schema).is_valid("1")
        with pytest.raises(Unsupported, match="no anchor"):
            compile_schema({**schema, "$ref": "http://example.com/a#m"})
        with pytest.raises(Unsupported, match="no anchor"):
            compile_schema({**schema, "$ref": "#n"})

    def test_an_anchored_schema_reads_its_references_in_its_resource(self):
        anchored = {"$anchor": "n", "$ref": "#/$defs/z"}
        resource = {"$id": "http://example.com/e", "$defs": {"z": _INT, "n": anchored}}
        schema = {"$defs": {"z": _STR, "e": resource}, "$ref": "http://example.com/e#n"}
        assert compile_schema(schema).is_valid(1)
        assert not compile_schema(schema).is_valid("1")

    def test_a_predicate_inside_a_resource_reads_its_references_there(self):
        # Five patterns are a predicate, whose subschemas compile again at membership time
        # when they hold the placeholder of the fixpoint `t`: in `e`, `#/$defs/t` is `e`'s.
        patterns = {f"^{c}": {"$ref": "#/$defs/t"} for c in "abcde"}
        t = {"type": "object", "patternProperties": patterns}
        resource = {"$id": "http://example.com/e", "$defs": {"t": t}, "$ref": "#/$defs/t"}
        schema = {"$defs": {"t": _STR, "e": resource}, "$ref": "#/$defs/e"}
        compiled = compile_schema(schema)
        assert compiled.is_valid({"a": {"b": {}}})
        assert not compiled.is_valid({"a": "x"})

    def test_a_fragment_alone_keeps_a_base_urljoin_does_not_join(self):
        schema = {"$id": "urn:example:root", "$defs": {"n": {"$anchor": "n", **_INT}}, "$ref": "#n"}
        assert compile_schema(schema).is_valid(1)
        assert not compile_schema(schema).is_valid("1")

    def test_a_pointer_through_an_embedded_id_reaches_its_schema(self):
        schema = {
            "$defs": {"s": {"$id": "http://example.com/s", "properties": {"n": _INT}}},
            "$ref": "#/$defs/s/properties/n",
        }
        assert compile_schema(schema).is_valid(1)
        assert not compile_schema(schema).is_valid("1")

    def test_a_reference_to_another_document_is_refused(self):
        with pytest.raises(Unsupported, match="does not hold"):
            compile_schema({"$ref": "http://example.com/other.json"})

    def test_an_older_drafts_id_fragment_is_an_anchor(self):
        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "definitions": {"n": {"$id": "#n", **_INT}},
            "$ref": "#n",
        }
        assert compile_schema(schema).is_valid(1)
        assert not compile_schema(schema).is_valid("1")


def _keyed(key, value):
    return {"properties": {key: {"const": value}}, "required": [key]}


class TestUnevaluated:
    @pytest.mark.parametrize(
        ("schema", "admitted", "refused"),
        [
            ({"properties": {"a": {}}}, [{"a": 1}, {}], [{"b": 1}]),
            (
                {
                    "$defs": {"x": {"properties": {"b": {}}}},
                    "allOf": [{"properties": {"a": {}}}],
                    "$ref": "#/$defs/x",
                },
                [{"a": 1, "b": 1}],
                [{"c": 1}],
            ),
            ({"anyOf": [_keyed("a", 1), _keyed("b", 1)]}, [{"a": 1, "b": 1}], [{"a": 1, "b": 2}]),
            ({"oneOf": [_keyed("a", 1), _keyed("b", 1)]}, [{"a": 1}], [{"a": 1, "c": 1}]),
            (
                # The first branch names `b` and `c`, and evaluates them only where it holds.
                {
                    "oneOf": [
                        {**_keyed("a", 1), "properties": {"a": {"const": 1}, "b": {}, "c": {}}},
                        {"properties": {"c": {}}, "required": ["c"]},
                    ]
                },
                [{"c": 1}, {"a": 1, "b": 1}],
                [{"c": 1, "b": 1}],
            ),
            ({"patternProperties": {"^x": {}}}, [{"x1": 1}], [{"y": 1}]),
            (
                {
                    "if": _keyed("k", "x"),
                    "then": {"properties": {"t": {}}},
                    "else": {"properties": {"e": {}}},
                },
                [{"k": "x", "t": 1}, {"e": 1}],
                [{"k": "x", "e": 1}, {"k": "y", "e": 1}],
            ),
            (
                # `else` names `k`, which it evaluates only where `if` fails.
                {
                    "if": _keyed("k", "x"),
                    "then": {"properties": {"t": {}}},
                    "else": {"properties": {"e": {}, "k": {}}},
                },
                [{"k": "y", "e": 1}],
                [{"k": "x", "e": 1}, {"k": "y", "t": 1}],
            ),
            ({"not": _keyed("a", 2)}, [{}], [{"a": 1}]),
            (
                {"properties": {"a": {}}, "dependentSchemas": {"a": {"properties": {"b": {}}}}},
                [{"a": 1, "b": 1}],
                [{"b": 1}],
            ),
            ({"allOf": [{"unevaluatedProperties": True}]}, [{"x": 1}], []),
        ],
    )
    def test_a_key_is_evaluated_where_a_holding_subschema_names_it(self, schema, admitted, refused):
        s = compile_schema({**schema, "unevaluatedProperties": False})
        assert [s.is_valid(v) for v in admitted] == [True] * len(admitted)
        assert [s.is_valid(v) for v in refused] == [False] * len(refused)

    def test_an_item_is_evaluated_by_a_prefix_or_a_contains(self):
        s = compile_schema(
            {"prefixItems": [_STR], "contains": {"const": 9}, "unevaluatedItems": False}
        )
        assert s.is_valid(["a", 9])
        assert s.is_valid(["a", 9, 9])
        assert not s.is_valid(["a", 9, 1])

    @pytest.mark.parametrize(
        "schema",
        [
            {"anyOf": [{}] * 5, "unevaluatedProperties": False},
            # The keyword first, so its walk meets the cycle before valgebra's build does.
            {"unevaluatedItems": False, "$defs": {"x": {"$ref": "#/$defs/x"}}, "$ref": "#/$defs/x"},
        ],
    )
    def test_too_many_cases_or_a_reference_to_itself_is_refused(self, schema):
        with pytest.raises(Unsupported, match="unevaluated"):
            compile_schema(schema)

    def test_a_relation_reads_the_unevaluated_keys(self):
        named = {"properties": {"a": {}}}
        s = compile_schema({**named, "unevaluatedProperties": False})
        assert s.is_equivalent(compile_schema({**named, "additionalProperties": False}))


class TestDynamicReferences:
    def test_a_dynamic_reference_one_schema_object_anchors_is_a_reference(self):
        schema = {
            "$dynamicAnchor": "node",
            "type": "object",
            "properties": {"next": {"$dynamicRef": "#node"}, "v": _INT},
        }
        s = compile_schema(schema)
        assert s.is_valid({"next": {"next": {"v": 1}}})
        assert not s.is_valid({"next": {"v": "1"}})

    # A fragment names an anchor percent-decoded, as a `$ref` reads it.
    @pytest.mark.parametrize("fragment", ["node", "n%6Fde"])
    def test_a_dynamic_reference_reaches_the_outermost_anchor_in_scope(self, fragment):
        # The draft 2020-12 release notes' tree, and the strict tree extending it.
        tree = {
            "$id": "http://example.com/tree",
            "$dynamicAnchor": "node",
            "type": "object",
            "properties": {"data": True, "children": {"items": {"$dynamicRef": f"#{fragment}"}}},
        }
        strict = {
            "$id": "http://example.com/strict",
            "$dynamicAnchor": "node",
            "$ref": "tree",
            "unevaluatedProperties": False,
        }
        s = compile_schema(strict, documents={"http://example.com/tree": tree})
        assert s.is_valid({"children": [{"data": 1}]})
        assert not s.is_valid({"children": [{"daat": 1}]})
        # Compiled as itself, the tree has the strict one in no scope.
        loose = compile_schema(tree, documents={"http://example.com/strict": strict})
        assert loose.is_valid({"children": [{"daat": 1}]})

    def test_an_embedded_resource_is_kept_for_the_scope_entering_it(self):
        # `t` and the resource around it set one anchor: reached directly, `t` binds it;
        # reached through `p`, `p` does, and the two sets are not one.
        p = {
            "$id": "http://example.com/p",
            "$dynamicAnchor": "z",
            "type": "object",
            "properties": {"viaP": {"$ref": "t"}},
            "$defs": {
                "t": {"$id": "t", "$dynamicAnchor": "z", "properties": {"n": {"$dynamicRef": "#z"}}}
            },
        }
        root = {
            "properties": {
                "direct": {"$ref": "http://example.com/t"},
                "viaP": {"$ref": "http://example.com/p"},
            }
        }
        s = compile_schema(root, documents={"http://example.com/p": p})
        assert s.is_valid({"direct": {"n": 1}})
        assert s.is_valid({"viaP": {"viaP": {"n": {}}}})
        assert not s.is_valid({"viaP": {"viaP": {"n": 1}}})

    def test_unevaluated_cases_enter_the_resources_on_the_way_to_a_dynamic_reference(self):
        a = {
            "$id": "http://example.com/a",
            "$defs": {"x": {"$dynamicAnchor": "x", "properties": {"fromA": True}}},
            "$ref": "b",
        }
        b = {
            "$id": "http://example.com/b",
            "$defs": {"x": {"$dynamicAnchor": "x", "properties": {"fromB": True}}},
            "$dynamicRef": "#x",
        }
        root = {"$ref": "http://example.com/a", "unevaluatedProperties": False}
        documents = {"http://example.com/a": a, "http://example.com/b": b}
        s = compile_schema(root, documents=documents)
        assert s.is_valid({"fromA": 1})
        assert not s.is_valid({"fromB": 1})

    def test_a_cycle_only_the_scope_closes_is_a_fixpoint(self):
        # No `$ref` reaches `r` again; the `$dynamicRef` in `b` does, under r's binding.
        b = {
            "$id": "http://example.com/b",
            "$defs": {"leaf": {"$dynamicAnchor": "x", **_STR}},
            "properties": {"next": {"$dynamicRef": "#x"}},
        }
        r = {"$id": "http://example.com/r", "$dynamicAnchor": "x", "$ref": "b", "type": "object"}
        documents = {"http://example.com/b": b}
        for by_predicate in (False, True):
            s = Compiler(r, by_predicate=by_predicate, documents=documents).compile(r)
            assert s.is_valid({"next": {"next": {}}})
            assert not s.is_valid({"next": {"next": "a"}})

    def test_a_dynamic_anchor_names_its_schema_as_a_plain_one(self):
        schema = {"$defs": {"n": {"$dynamicAnchor": "n", **_INT}}, "$ref": "#n"}
        assert compile_schema(schema).is_valid(1)
        assert not compile_schema(schema).is_valid("1")

    def test_a_dynamic_reference_through_a_pointer_is_a_reference(self):
        schema = {"$defs": {"n": _INT}, "$dynamicRef": "#/$defs/n"}
        assert compile_schema(schema).is_valid(1)
        assert not compile_schema(schema).is_valid("1")

    def test_unevaluated_properties_read_what_a_dynamic_reference_evaluates(self):
        target = {"$dynamicAnchor": "n", "properties": {"a": {}}}
        schema = {"$defs": {"n": target}, "$dynamicRef": "#n", "unevaluatedProperties": False}
        s = compile_schema(schema)
        assert s.is_valid({"a": 1})
        assert not s.is_valid({"b": 1})


class TestDocuments:
    def test_a_reference_reaches_a_supplied_document(self):
        documents = {"http://example.com/s.json": {"$defs": {"n": _INT}}}
        s = compile_schema({"$ref": "http://example.com/s.json#/$defs/n"}, documents=documents)
        assert s.is_valid(1)
        assert not s.is_valid("1")

    def test_an_anchor_in_a_supplied_document_names_its_schema(self):
        documents = {"http://example.com/s.json": {"$defs": {"n": {"$anchor": "n", **_INT}}}}
        s = compile_schema({"$ref": "http://example.com/s.json#n"}, documents=documents)
        assert s.is_valid(1)
        assert not s.is_valid("1")

    def test_a_predicate_compiled_again_reaches_the_supplied_documents(self):
        # Five patterns are a predicate, compiled again at membership time around `t`.
        value = {"anyOf": [{"$ref": "#/$defs/t"}, {"$ref": "http://example.com/n.json"}]}
        t = {"type": "object", "patternProperties": {f"^{c}": value for c in "abcde"}}
        documents = {"http://example.com/n.json": _INT}
        s = compile_schema({"$defs": {"t": t}, "$ref": "#/$defs/t"}, documents=documents)
        assert s.is_valid({"a": {"b": 1}})
        assert not s.is_valid({"a": "x"})

    def test_a_supplied_documents_references_resolve_against_its_uri(self):
        documents = {
            "http://example.com/a/s.json": {"$ref": "t.json"},
            "http://example.com/a/t.json": _INT,
            "http://example.com/t.json": _STR,
        }
        s = compile_schema({"$ref": "http://example.com/a/s.json"}, documents=documents)
        assert s.is_valid(1)
        assert not s.is_valid("1")

    def test_two_documents_naming_each_other_are_a_fixpoint(self):
        documents = {
            "http://example.com/a.json": {
                "type": "object",
                "properties": {"b": {"$ref": "b.json"}},
            },
            "http://example.com/b.json": {
                "type": "object",
                "properties": {"a": {"$ref": "a.json"}},
            },
        }
        s = compile_schema({"$ref": "http://example.com/a.json"}, documents=documents)
        assert s.is_valid({"b": {"a": {"b": {}}}})
        assert not s.is_valid({"b": {"a": 1}})

    def test_a_document_declaring_no_dialect_is_read_in_the_compiled_ones(self):
        draft4 = "http://json-schema.org/draft-04/schema#"
        documents = {"http://example.com/m.json": {"maximum": 3, "exclusiveMaximum": True}}
        schema = {"$schema": draft4, "$ref": "http://example.com/m.json"}
        s = compile_schema(schema, documents=documents)
        assert s.is_valid(2)
        assert not s.is_valid(3)

    def test_a_document_supplied_at_the_compiled_ones_uri_is_not_read(self):
        # The second `#/$defs/a` follows an anchor reference, which builds the index of
        # resources; the compiled document names its URI on both sides of it.
        uri = "http://example.com/root"
        root = {
            "$id": uri,
            "$defs": {"a": _STR, "b": {"$anchor": "b", "type": "null"}},
            "properties": {
                "p": {"$ref": "#/$defs/a"},
                "q": {"$ref": "#b"},
                "r": {"$ref": "#/$defs/a"},
            },
        }
        other = {"$defs": {"a": _INT, "b": {"$anchor": "b", "type": "boolean"}}}
        s = compile_schema(root, documents={uri: other})
        assert [s.is_valid({key: "x"}) for key in ("p", "r")] == [True, True]
        assert [s.is_valid({key: 1}) for key in ("p", "r")] == [False, False]
        assert s.is_valid({"q": None})
        assert not s.is_valid({"q": True})
        other["$defs"]["c"] = {"$anchor": "c"}
        with pytest.raises(Unsupported, match="names no anchor"):
            compile_schema({**root, "properties": {"c": {"$ref": "#c"}}}, documents={uri: other})
        # Nor is an embedded resource of another supplied document that claims the URI.
        nested = {"$defs": {"e": {"$id": uri, "$defs": {"a": _INT}}}}
        properties = {"w": {"$ref": "http://example.com/n"}, "r": {"$ref": "#/$defs/a"}}
        s = compile_schema(
            {**root, "properties": properties}, documents={"http://example.com/n": nested}
        )
        assert s.is_valid({"r": "x"})
        assert not s.is_valid({"r": 1})

    def test_a_uri_two_schema_objects_of_one_document_claim_names_neither(self):
        # Draft 2020-12 asks for an error where two schemas claim one URI (section 9.1.2),
        # and `jsonschema` reads either, by the order Python's string hashing gives its
        # keywords. A pointer to either names a location, and compiles.
        base = "http://example.com/"
        defs = {"one": {"$id": base + "a", **_STR}, "two": {"$id": base + "a", **_INT}}
        root = {"$id": base + "root", "$defs": defs}
        with pytest.raises(Unsupported, match="two schema objects of one document claim"):
            compile_schema({**root, "properties": {"x": {"$ref": base + "a"}}})
        s = compile_schema({**root, "properties": {"x": {"$ref": "#/$defs/one"}}})
        assert s.is_valid({"x": "s"})
        assert not s.is_valid({"x": 1})
        # Of two documents, the first read names the URI: the supplied one.
        one = {"$id": base + "root", "$defs": {"one": defs["one"]}}
        x = {"properties": {"x": {"$ref": base + "a"}}}
        s = compile_schema({**one, **x}, documents={base + "a": _INT})
        assert s.is_valid({"x": 1})
        assert not s.is_valid({"x": "s"})
        # A supplied document claims the URI it is supplied by.
        claims = {"$defs": {"e": {"$id": base + "a", **_STR}}, **_INT}
        with pytest.raises(Unsupported, match="two schema objects of one document claim"):
            compile_schema({"$id": base + "root", **x}, documents={base + "a": claims})
        # The compiled document names its own URI against an embedded claim of it, on both
        # sides of the index the anchor reference builds.
        own = {
            "$id": base + "root",
            "$defs": {"a": _STR, "e": {"$id": base + "root", "$defs": {"a": _INT}}},
            "properties": {
                "p": {"$ref": "#/$defs/a"},
                "q": {"$ref": "#b"},
                "r": {"$ref": "#/$defs/a"},
            },
        }
        own["$defs"]["b"] = {"$anchor": "b"}
        s = compile_schema(own)
        assert [s.is_valid({key: "x"}) for key in ("p", "r")] == [True, True]
        assert [s.is_valid({key: 1}) for key in ("p", "r")] == [False, False]

    def test_an_anchor_two_schema_objects_of_one_resource_set_names_neither(self):
        defs = {"s": {"$anchor": "s", **_STR}, "t": {"$anchor": "s", **_INT}}
        with pytest.raises(Unsupported, match="two schema objects of its resource set"):
            compile_schema({"$defs": defs, "properties": {"x": {"$ref": "#s"}}})
        assert compile_schema({"$defs": defs}).is_valid({"x": 1})

    def test_a_dynamic_reference_reaching_an_anchor_set_twice_is_refused(self):
        inner = {
            "$id": "http://example.com/inner",
            "$defs": {"n": {"$dynamicAnchor": "n", "type": "null"}},
            "properties": {"v": {"$dynamicRef": "#n"}},
        }
        defs: dict[str, object] = {"a": {"$dynamicAnchor": "n", **_STR}, "inner": inner}
        outer = {
            "$id": "http://example.com/outer",
            "$defs": defs,
            "$ref": "http://example.com/inner",
        }
        s = compile_schema(outer)
        assert s.is_valid({"v": "s"})
        assert not s.is_valid({"v": None})
        defs["b"] = {"$dynamicAnchor": "n", **_INT}
        with pytest.raises(Unsupported, match="reaches an anchor two schema objects"):
            compile_schema(outer)

    def test_a_property_named_schema_in_a_resource_is_a_name(self):
        # A meta-schema declares the property `$schema`, which declares no dialect.
        resource = {"$id": "http://example.com/m", "properties": {"$schema": _STR}}
        s = compile_schema(
            {"$ref": "http://example.com/m"}, documents={"http://example.com/m": resource}
        )
        assert s.is_valid({"$schema": "x"})
        assert not s.is_valid({"$schema": 1})

    def test_a_document_in_a_dialect_not_read_is_refused_only_where_named(self):
        documents = {
            "http://example.com/old.json": {"$schema": "http://json-schema.org/draft-03/schema#"},
            "http://example.com/n.json": _INT,
        }
        assert compile_schema({"$ref": "http://example.com/n.json"}, documents=documents).is_valid(
            1
        )
        with pytest.raises(Unsupported, match="refused"):
            compile_schema({"$ref": "http://example.com/old.json"}, documents=documents)


class TestContainmentLabels:
    # Pairs of the containment test suite carry a label the specification refutes, in the
    # kinds the results page names; each value here is the witness of one kind.
    def test_the_array_labeled_outside_a_dynamic_reference_is_inside_it(self):
        # The official suite holds `["foo", "bar"]` valid here, where the generator labels
        # it outside: a `$dynamicRef` to a `$dynamicAnchor` of its own resource is the
        # `$ref` it resolves as.
        root = "https://test.json-schema.org/dynamicRef-dynamicAnchor-same-schema/root"
        schema = {
            "$id": root,
            "type": "array",
            "items": {"$dynamicRef": "#items"},
            "$defs": {"foo": {"$dynamicAnchor": "items", "type": "string"}},
        }
        compiled = compile_schema(schema)
        assert compiled.is_valid(["foo", "bar"])
        assert not compiled.is_valid(["foo", 42])
        assert compile_schema({"const": ["foo", "bar"]}).relation_to(compiled) == "subset"

    def test_the_object_labeled_outside_a_not_the_dynamic_scope_reaches_is_inside_it(self):
        # The generator puts the `$ref` of the suite's relative dynamic reference under a
        # `not`, which the reference reaches again: the object the suite holds valid is in.
        root = "https://test.json-schema.org/relative-dynamic-reference/root"
        extended = {"$id": "extended", "$dynamicAnchor": "meta", "type": "object"}
        extended["properties"] = {"bar": {"$ref": "bar"}}
        bar = {"$id": "bar", "type": "object"}
        bar["properties"] = {"baz": {"$dynamicRef": "extended#meta"}}
        schema = {
            "$id": root,
            "$dynamicAnchor": "meta",
            "type": "object",
            "properties": {"foo": {"const": "pass"}},
            "$defs": {"extended": extended, "bar": bar},
            "not": {"$ref": "extended"},
        }
        listed = {"foo": "pass", "bar": {"baz": {"foo": "pass"}}}
        compiled = compile_schema(schema)
        assert compiled.is_valid(listed)
        assert not compiled.is_valid({"bar": {}})
        # The study proves a schema that spells its values out by each value's membership.
        assert constants({"const": listed}) == [listed]

    def test_the_meet_labeled_empty_with_no_not_holds_the_empty_array(self):
        # The generator renames the copy and leaves out the `not` it writes elsewhere.
        def copy(n):
            return {
                "$id": f"https://test{n}.json-schema.org/root",
                "type": "array",
                "items": {"$dynamicRef": f"#items{n}"},
                "$defs": {"foo": {"$dynamicAnchor": f"items{n}", "type": "string"}},
            }

        compiled = compile_schema({"allOf": [copy(""), copy(1)]})
        assert compiled.is_valid([])
        assert compiled.relation_to(nothing) == "not_subset"

    def test_the_meet_labeled_empty_holds_what_a_not_the_dynamic_scope_reaches_refuses(self):
        # The generator meets the suite's relative dynamic reference with a renamed copy whose
        # `not` wraps the copy's `extended`, which the copy's own `$dynamicAnchor` reaches
        # again: `{"bar": {"baz": {}}}` fails `extended1`, its `baz` failing the copy's root.
        def copy(n):
            extended = {"$id": f"extended{n}", "$dynamicAnchor": f"meta{n}", "type": "object"}
            extended["properties"] = {"bar": {"$ref": f"bar{n}"}}
            bar = {"$id": f"bar{n}", "type": "object"}
            bar["properties"] = {"baz": {"$dynamicRef": f"extended{n}#meta{n}"}}
            return {
                "$id": f"https://test{n}.json-schema.org/relative-dynamic-reference/root",
                "$dynamicAnchor": f"meta{n}",
                "type": "object",
                "properties": {"foo": {"const": "pass"}},
                "$defs": {"extended": extended, "bar": bar},
            }

        root, renamed = copy(""), copy(1)
        root["$ref"] = "extended"
        renamed["not"] = {"$ref": "extended1"}
        compiled = compile_schema({"allOf": [root, renamed]})
        assert compiled.is_valid({"bar": {"baz": {}}})
        assert not compiled.is_valid({"bar": {}})
        assert compiled.relation_to(nothing) == "not_subset"

    def test_the_tree_labeled_outside_a_tree_under_not_is_inside_it(self):
        # The `not` around the properties holds of a tree whose nodes hold subtrees that are
        # not trees: each child's own nodes satisfy the properties, so the child fails it.
        node = {
            "$id": "http://localhost:1234/node",
            "type": "object",
            "properties": {"value": {"type": "number"}, "subtree": {"$ref": "tree"}},
            "required": ["value"],
        }
        nodes = {"type": "array", "items": {"$ref": "node"}}
        schema = {
            "$id": "http://localhost:1234/tree",
            "type": "object",
            "required": ["meta", "nodes"],
            "$defs": {"node": node},
            "not": {"properties": {"meta": {"type": "string"}, "nodes": nodes}},
        }
        child = {"meta": "child", "nodes": [{"value": 1.1}, {"value": 1.2}]}
        tree = {"meta": "root", "nodes": [{"value": 1, "subtree": child}]}
        compiled = compile_schema(schema)
        assert compiled.is_valid(tree)
        assert not compiled.is_valid(child)
        assert compile_schema({"const": tree}).relation_to(compiled) != "not_subset"

    def test_the_schema_labeled_universal_leaves_out_a_number(self):
        def tree(n):
            sub = f"#/anyOf/{n}/$defs/sub-item"
            item = {"type": "array", "items": False, "prefixItems": [{"$ref": sub}] * 2}
            defs = {"item": item, "sub-item": {"type": "object", "required": ["foo"]}}
            return {"$defs": defs, "type": "array", "items": False}

        top = [{"$ref": "#/anyOf/0/$defs/item"}] * 3
        neither = [{"$ref": "#/anyOf/1/$defs/item"}] * 3
        schema = {
            "anyOf": [{**tree(0), "prefixItems": top}, {**tree(1), "not": {"prefixItems": neither}}]
        }
        compiled = compile_schema(schema)
        assert not compiled.is_valid(1)
        assert JSON.relation_to(compiled) == "not_subset"

    def test_the_schema_labeled_empty_holds_an_object_named_like_a_reference(self):
        def branch(n, key):
            defs = {"a_string": {"type": "string"}}
            listed = {"enum": [{"$ref": f"#/allOf/{n}/$defs/a_string"}]}
            return {"$defs": defs, **({"not": listed} if key == "not" else listed)}

        compiled = compile_schema({"allOf": [branch(0, "enum"), branch(1, "not")]})
        assert compiled.is_valid({"$ref": "#/allOf/0/$defs/a_string"})
        assert compiled.relation_to(nothing) == "not_subset"

    def test_the_schema_labeled_universal_over_resources_leaves_out_an_empty_object(self):
        # `subtree` names `tree{n}` relative to the node's own `$id`, in its own resource.
        def tree(n):
            subtree = {"$ref": f"tree{n}"}
            node = {
                "$id": f"http://localhost:1234/node{n}",
                "type": "object",
                "properties": {"value": {"type": "number"}, "subtree": subtree},
                "required": ["value"],
            }
            return {
                "$id": f"http://localhost:1234/tree{n}",
                "type": "object",
                "required": ["meta", "nodes"],
                "$defs": {"node": node},
            }

        def fields(n):
            nodes = {"type": "array", "items": {"$ref": f"node{n}"}}
            return {"properties": {"meta": {"type": "string"}, "nodes": nodes}}

        schema = {"anyOf": [{**tree(0), **fields(0)}, {**tree(1), "not": fields(1)}]}
        compiled = compile_schema(schema)
        assert compiled.is_valid({"meta": "m", "nodes": [{"value": 1, "subtree": 2}]})
        assert not compiled.is_valid({})
        assert JSON.relation_to(compiled) == "not_subset"

    def test_the_schema_labeled_empty_holds_an_object_named_like_an_identifier(self):
        # An `$id` inside an `enum` value names nothing, so `real{n}` is the one `$id` names.
        def branch(n, key):
            uri = f"https://localhost:1234/id/my_identifier{n}.json"
            listed = {"enum": [{"$id": uri, "type": "null"}]}
            body = {"anyOf": [listed, {"$ref": uri}]}
            defs = {f"real{n}": {"$id": uri, "type": "string"}}
            return {"$defs": defs, **({"not": body} if key == "not" else body)}

        compiled = compile_schema({"allOf": [branch(0, "enum"), branch(1, "not")]})
        assert compiled.is_valid(
            {"$id": "https://localhost:1234/id/my_identifier0.json", "type": "null"}
        )
        assert not compiled.is_valid("a")
        assert compiled.relation_to(nothing) == "not_subset"


class TestUniverse:
    def test_a_type_list_keeps_the_guard_of_each_other_kind(self):
        # The guard is left out only where `type` confines the value to the keyword's kind.
        compiled = compile_schema({"type": ["integer", "string"], "minimum": 3})
        assert compiled.is_valid("a")
        assert compiled.is_valid(3)
        assert not compiled.is_valid(2)

    @pytest.mark.parametrize(
        "schema", [True, {"type": "number"}, {"not": {"type": "string"}}, {"minimum": 0}]
    )
    def test_nan_is_a_value_of_no_schema(self, schema):
        # RFC 8259 has no NaN; `json.loads` builds one from the token `NaN` alone.
        assert not compile_schema(schema).is_valid(math.nan)

    def test_an_infinity_stands_for_a_number_past_the_float_range(self):
        huge = json.loads("1e400")
        assert compile_schema({"type": "number"}).is_valid(huge)
        assert not compile_schema({"maximum": 1e308}).is_valid(huge)
        assert not compile_schema({"type": "integer"}).is_valid(huge)

    @pytest.mark.parametrize("keyword", ["const", "enum"])
    def test_a_constant_past_the_float_range_is_its_infinity(self, keyword):
        # `1e400` is read by `json.loads` as an infinity in a schema and in an instance alike,
        # so a constant of it holds the instance it equals, as `type` and `maximum` read it.
        for text, sign in (("1e400", 1), ("-1e400", -1)):
            value = json.loads(text)
            schema = {keyword: value if keyword == "const" else [value]}
            compiled = compile_schema(schema)
            assert compiled.is_valid(sign * math.inf)
            assert not compiled.is_valid(-sign * math.inf)
            assert not compiled.is_valid(sign * 1e308)
            zero = compile_schema({keyword: 0 if keyword == "const" else [0]})
            assert compiled.relation_to(zero) == "not_subset"
            assert compiled.relation_to(compile_schema(False)) == "not_subset"
        # NaN is no JSON value, so a constant of it holds none.
        assert compile_schema({"const": math.nan}).relation_to(compile_schema(False)) == "subset"

    @pytest.mark.parametrize(("schema", "deepest"), [(True, 127), ({}, 127), ({"not": _STR}, 126)])
    def test_a_value_past_valgebras_walk_is_refused_by_every_schema(self, schema, deepest):
        # The ledger's row: valgebra's walk bounds its own depth, so a value nested past it is
        # refused whatever the schema, and `validate` says why; a `not` takes a level.
        def nested(lists: int) -> object:
            value: object = 0
            for _ in range(lists):
                value = [value]
            return value

        compiled = compile_schema(schema)
        assert compiled.is_valid(nested(deepest))
        assert not compiled.is_valid(nested(deepest + 1))
        with pytest.raises(ValidationError) as refused:
            compiled.validate(nested(deepest + 1))
        assert refused.value.errors[0]["code"] == "recursion_limit"

    def test_every_number_lies_below_one_of_two_overlapping_bounds(self):
        # A NaN in the universe would be outside both bounds and refute what every number
        # satisfies.
        number = compile_schema({"type": "number"})
        union = compile_schema({"anyOf": [{"maximum": 10}, {"minimum": 5}]})
        assert number.relation_to(union) == "subset"
        negative = compile_schema({"type": "number", "not": {"minimum": 0}})
        assert negative.relation_to(compile_schema({"exclusiveMaximum": 0})) == "subset"

    def test_a_fraction_past_the_float_range_is_a_number_past_every_bound(self):
        # `1` followed by 400 zeros and `.5` is a JSON number with a fraction; `json.loads`
        # reads it as an infinity, which keeps the inclusion false, as JSON's numbers make it.
        fractional = compile_schema({"type": "number", "not": {"type": "integer"}})
        assert json.loads("1" + "0" * 400 + ".5") == math.inf
        assert fractional.relation_to(compile_schema({"maximum": 2**53})) == "not_subset"

    @pytest.mark.parametrize(
        "schema",
        [
            {"prefixItems": [{"type": "integer"}, {"type": "string"}]},
            {"patternProperties": {"f.*o": {"type": "integer"}}},
        ],
    )
    def test_the_universe_is_refuted_below_a_keyword_of_one_kind(self, schema):
        # A keyword's guard complements the bare kind, `list` or `dict`, which agrees with
        # the JSON one inside the universe and which valgebra's set reading decides.
        assert compile_schema(True).relation_to(compile_schema(schema)) == "not_subset"

    @pytest.mark.parametrize(
        "schema",
        [
            {"items": True},
            {"additionalProperties": True},
            {"properties": {}},
            {"required": []},
            {"dependentRequired": {}},
            {"unevaluatedItems": True},
        ],
    )
    def test_a_keyword_admitting_every_value_compiles_to_the_universe(self, schema):
        # Its guard is every value: the refinement holds the whole kind, and the guard of
        # the bare kind, which would not fold, is not written.
        assert compile_schema(schema) == JSON

    @pytest.mark.parametrize(
        ("schema", "kind"),
        [
            ({"type": "array", "items": {"type": "integer"}}, ARRAY),
            ({"type": "array", "prefixItems": [{"type": "string"}], "minItems": 1}, ARRAY),
            (
                {"type": ["array"], "items": {"if": {"type": "integer"}, "then": {"minimum": 0}}},
                ARRAY,
            ),
            ({"type": "array", "minItems": 1}, ARRAY),
            (
                {"type": "object", "properties": {"a": {"type": "integer"}}, "required": ["a"]},
                OBJECT,
            ),
            ({"type": "object", "additionalProperties": False}, OBJECT),
            ({"type": "object", "required": ["a?"]}, OBJECT),
            ({"type": "object", "patternProperties": {"^a": {"type": "integer"}}}, OBJECT),
            # Past four patterns the object group is a predicate over every `dict`.
            (
                {
                    "type": "object",
                    "properties": {"a": {"type": "integer"}},
                    "patternProperties": {f"^p{i}": {"type": "integer"} for i in range(5)},
                },
                OBJECT,
            ),
            ({"type": "object", "minProperties": 1}, OBJECT),
        ],
    )
    def test_a_schema_of_one_kind_lies_inside_the_kind(self, schema, kind):
        # Where `items`, `prefixItems` or the object group stand beside a `type` of their one
        # kind, the kind's own set is not met again, and what is left lies inside it.
        assert compile_schema(schema).is_subtype_of(kind)

    def test_the_kind_a_keyword_lies_inside_is_not_met_again(self):
        # A list or a record of subschemas, each inside the universe, is its meet with it.
        assert compile_schema({"type": "array", "items": {"type": "string"}}) == Validator([str])
        record = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
        assert compile_schema(record) == Validator({"a": str, str: JSON})
        assert compile_schema({"type": "array", "minItems": 1}) == intersection(
            ARRAY, Annotated[list[Any], MinLen(1)]
        )

    @pytest.mark.parametrize("schema", [{"minimum": 3}, {"maxLength": 2}, {"required": ["a"]}])
    def test_a_schema_without_a_type_lies_inside_the_universe(self, schema):
        # A keyword's guard admits every value outside its kind, a tuple included; the meet
        # with the universe keeps the set inside JSON, so `true` is proven to contain it.
        assert compile_schema(schema).is_subtype_of(JSON)


_JSON_VALUES = (None, True, 0, 1, 2, 2.5, -3, "", "a", "abcde", [], [1], [2, 3, 4], {}, {"a": 1})


class TestConstants:
    @pytest.mark.parametrize(
        ("schema", "values"),
        [
            ({"const": [1, 2]}, [[1, 2]]),
            ({"enum": [1, "a"], "title": "t"}, [1, "a"]),
            ({"anyOf": [{"const": 1}, {"enum": [1.0, 2]}]}, [1, 2]),
            ({"oneOf": [{"const": 1}, {"enum": [1.0, 2]}]}, [2]),
            (False, []),
            (True, None),
            ({"const": 1, "type": "integer"}, [1]),
            ({"type": "string", "enum": ["mug", "box"], "description": "d"}, ["mug", "box"]),
            ({"type": "integer", "enum": [1, "a", 2.0, True]}, [1, 2.0]),
            ({"type": ["string", "null"], "enum": ["a", None, 3]}, ["a", None]),
            ({"type": "string", "const": 1}, []),
            ({"type": "nothing", "const": 1}, None),
            ({"type": 3, "const": 1}, None),
            ({"type": [], "const": 1}, None),
            ({"const": 1, "enum": [1]}, None),
            ({"anyOf": [{"const": 1}, {"type": "string"}]}, None),
        ],
    )
    def test_the_values_a_schema_spells_out(self, schema, values):
        assert constants(schema) == values

    def test_a_draft_04_const_is_an_annotation_and_spells_nothing(self):
        assert constants(upgrade({"const": 1}, 4)) is None

    def test_a_finite_set_is_related_by_the_membership_of_each_value(self):
        # valgebra reads no predicate for a relation; each value's membership decides it.
        unique = compile_schema({"uniqueItems": True})
        listed = compile_schema({"enum": [[1, 2], [1, 1]]})
        assert listed.relation_to(unique) == "undecided"
        repeated, distinct = (
            constants({"enum": [[1, 2], [1, 1]]}),
            constants({"enum": [[1, 2], [3]]}),
        )
        assert repeated is not None
        assert distinct is not None
        assert not all(unique.is_valid(v) for v in repeated)
        assert all(unique.is_valid(v) for v in distinct)


class TestComplements:
    # A complement inside the universe reads a schema's body, its keywords' meet without the
    # universe, which valgebra decides where the complement of a meet with it declines.
    @pytest.mark.parametrize(
        ("subject", "schema", "answer"),
        [
            ({"type": "integer"}, {"oneOf": [{"type": "integer"}, {"minimum": 2}]}, "not_subset"),
            (
                {"type": "string"},
                {"not": {"type": "string", "oneOf": [{"minLength": 2}, {"maxLength": 4}]}},
                "not_subset",
            ),
            ({"const": [1]}, {"not": {"maxItems": 2}}, "not_subset"),
            ({"type": "integer"}, {"if": {"minimum": 2}, "then": {"type": "integer"}}, "subset"),
            ({"type": "number"}, {"if": {"minimum": 2}, "then": {"type": "integer"}}, "not_subset"),
            ({"const": ["foo"]}, {"contains": True}, "subset"),
            ({"const": [2, 3, 4]}, {"contains": {"minimum": 5}}, "not_subset"),
        ],
    )
    def test_a_complement_inside_the_universe_is_decided(self, subject, schema, answer):
        assert compile_schema(subject).relation_to(compile_schema(schema)) == answer

    @pytest.mark.parametrize(
        "schema",
        [
            True,
            {},
            {"minimum": 2},
            {"type": "string", "minLength": 2},
            {"oneOf": [{"type": "integer"}, {"minimum": 2}]},
            {"not": {"maxItems": 1}},
            {"properties": {"a": {"type": "string"}}},
            {"prefixItems": [{"type": "integer"}, {"type": "string"}]},
            {"patternProperties": {"f.*o": {"type": "integer"}}},
        ],
    )
    def test_a_body_and_its_schema_agree_on_every_json_value(self, schema):
        compiler = Compiler(schema)
        whole, body = compiler.compile(schema), compiler.compile_body(schema)
        assert [whole.is_valid(v) for v in _JSON_VALUES] == [body.is_valid(v) for v in _JSON_VALUES]


class TestDecisions:
    @pytest.mark.parametrize(
        "schema",
        [{"uniqueItems": True}, {"multipleOf": 0.5}, {"type": "array", "uniqueItems": True}],
    )
    def test_a_schema_over_a_predicate_compiled_twice_is_below_itself(self, schema):
        # The two compilations hold one callable, which valgebra relates to itself.
        assert compile_schema(schema).relation_to(compile_schema(schema)) == "subset"

    def test_disjoint_patterns_are_proven_disjoint(self):
        a = compile_schema({"type": "string", "pattern": "^cus_[a-z0-9]{8}$"})
        b = compile_schema({"type": "string", "pattern": "^sub_[a-z0-9]{8}$"})
        assert intersection(a, b).is_empty()

    def test_a_narrower_enum_is_a_subtype(self):
        narrow = compile_schema({"enum": ["pro", "enterprise"]})
        wide = compile_schema({"enum": ["free", "pro", "enterprise"]})
        assert narrow.relation_to(wide) == "subset"
        assert wide.relation_to(narrow) == "not_subset"

    def test_a_tighter_bound_is_a_subtype(self):
        tight = compile_schema({"type": "integer", "minimum": 5, "maximum": 30})
        loose = compile_schema({"type": "integer", "minimum": 1})
        assert tight.is_subtype_of(loose)

    def test_false_is_empty(self):
        assert compile_schema(False).relation_to(nothing) == "subset"

    @pytest.mark.parametrize(
        "schema",
        [{"const": [1]}, {"enum": [[1], [2]]}, {"minItems": 2}, {"const": 1}],
        ids=["list-const", "list-enum", "min-items", "scalar-const"],
    )
    def test_an_excluded_middle_leaves_no_array_out(self, schema):
        # `anyOf: [{not: C}, C]` holds every JSON value. valgebra proves the arrays below it
        # by splitting them on `C`, and reads the arrays' meet with its complement empty by
        # the same split: on valgebra 0.0.35 a list constant's meet declined.
        everything = compile_schema({"anyOf": [{"not": schema}, schema]})
        array = compile_schema({"type": "array"})
        assert array.relation_to(everything) == "subset"
        assert intersection(array, complement(everything)).is_empty()


class TestRefusals:
    @pytest.mark.parametrize(
        "schema",
        [
            {"$dynamicRef": "#meta"},
            {"$ref": "http://example.com/x.json"},
            {"$ref": "#anchor"},
            {"properties": {"a": {"$id": "x", "$ref": "#/$defs/b"}}, "$defs": {"b": {}}},
        ],
    )
    def test_it_refuses_what_it_cannot_translate(self, schema):
        with pytest.raises(Unsupported):
            compile_schema(schema)

    def test_it_refuses_a_draft_it_does_not_read(self):
        with pytest.raises(Unsupported, match="2020-12, 2019-09, 07, 06 and 04"):
            compile_schema({"$schema": "http://json-schema.org/draft-03/schema#"})


_DRAFTS = {
    "2020-12": None,
    "7": "http://json-schema.org/draft-07/schema#",
    "6": "http://json-schema.org/draft-06/schema#",
    "4": "http://json-schema.org/draft-04/schema#",
}
_KEYWORDS = sorted(
    SUPPORTED | REFUSED | ANNOTATIONS | {"minContains", "maxContains", "dependencies", "id"}
)
_WRONG = [5, -1, 1.5, True, None, "x", "", [], [1], [{}], [[]], {}, {"a": 5}, {"a": []}, [None]]


class TestMalformedSchemas:
    @pytest.mark.parametrize("draft", list(_DRAFTS))
    def test_a_schema_holding_wrong_shapes_is_refused_or_compiled_never_crashed(self, draft):
        # Each reader takes the document from a server it does not control: a value of the
        # wrong shape anywhere must give `Unsupported`, never another exception.
        rng = random.Random(f"malformed:{draft}")
        for _ in range(1500):
            schema = {k: rng.choice(_WRONG) for k in rng.sample(_KEYWORDS, rng.randint(1, 3))}
            if rng.random() < 0.3:
                schema = {"type": "object", "properties": {"p": schema}}
            if _DRAFTS[draft]:
                schema = {"$schema": _DRAFTS[draft], **schema}
            with contextlib.suppress(Unsupported):
                compile_schema(schema)

    @pytest.mark.parametrize(
        ("schema", "keyword"),
        [
            ({"type": {}}, "type"),
            ({"additionalProperties": {}, "properties": True}, "properties"),
            ({"contains": {}, "minContains": "x"}, "minContains"),
            ({"contains": {}, "maxContains": -1}, "maxContains"),
            ({"$ref": 5}, "$ref"),
            ({"$schema": _DRAFTS["7"], "allOf": 5}, "allOf"),
            ({"$schema": _DRAFTS["7"], "dependencies": 5}, "dependencies"),
            ({"$schema": _DRAFTS["4"], "minimum": 1, "exclusiveMinimum": 5}, "exclusiveMinimum"),
        ],
    )
    def test_the_refusal_names_the_keyword(self, schema, keyword):
        with pytest.raises(Unsupported, match=keyword.replace("$", r"\$")):
            compile_schema(schema)


class TestDeepSchemas:
    @pytest.mark.parametrize(
        "wrap",
        [
            lambda s: {"allOf": [s]},
            lambda s: {"anyOf": [s, {"type": "null"}]},
            lambda s: {"not": s},
            lambda s: {"items": s},
            lambda s: {"properties": {"a": s}},
        ],
        ids=["allOf", "anyOf", "not", "items", "properties"],
    )
    def test_a_schema_nested_past_valgebras_depth_is_refused(self, wrap):
        schema = {"type": "string"}
        for _ in range(5000):
            schema = wrap(schema)
        with pytest.raises(Unsupported, match="nests past"):
            compile_schema(schema)
        with pytest.raises(Unsupported, match="nests past"):
            upgrade({"$schema": _DRAFTS["7"], **schema})

    def test_a_chain_of_references_compiled_in_place_past_the_limit_is_refused(self):
        # The document is three levels deep; the compiled set nests 300 deep.
        defs: dict[str, object] = {
            f"d{i}": {"allOf": [{"$ref": f"#/$defs/d{i + 1}"}]} for i in range(300)
        }
        defs["d300"] = {"type": "string"}
        with pytest.raises(Unsupported, match="nests past"):
            compile_schema({"$defs": defs, "$ref": "#/$defs/d0"})

    def test_a_constant_nested_past_the_bound_is_refused(self):
        value: object = 1
        for _ in range(1000):
            value = [value]
        with pytest.raises(Unsupported, match="nests past"):
            compile_schema({"const": value})


def test_a_pointer_index_is_written_as_rfc_6901_writes_it():
    listed = {"$defs": {"l": [{"type": "string"}, {"type": "integer"}]}}
    assert compile_schema({**listed, "$ref": "#/$defs/l/1"}).is_valid(1)
    for index in ("01", "+1", "\u0661", "\u00b2"):
        with pytest.raises(Unsupported, match="names nothing"):
            compile_schema({**listed, "$ref": f"#/$defs/l/{index}"})


def test_json_key_equates_one_and_one_point_zero_but_not_true():
    assert json_key([1, {"a": 2.0}]) == json_key([1.0, {"a": 2}])
    assert json_key(1) != json_key(True)


@pytest.mark.parametrize("key", ["minLength", "maxLength", "minItems", "maxItems"])
def test_an_integral_float_count_is_its_integer_and_leaves_the_integer_intact(key):
    # 7.0 and 7 are one number; reading 7.0 must not change what a later 7 compiles to.
    as_float = compile_schema({key: 7.0})
    as_int = compile_schema({key: 7})
    for value in ("x" * 6, "x" * 7, "x" * 8, [0] * 6, [0] * 7, [0] * 8):
        assert as_float.is_valid(value) == as_int.is_valid(value)


def test_an_integral_float_is_read_alike_by_integral_and_fractional_steps():
    value = float(3 * 2**70)
    assert compile_schema({"multipleOf": 3}).is_valid(value)
    assert compile_schema({"multipleOf": 1.5}).is_valid(value)
    assert compile_schema({"multipleOf": 0.0001}).is_valid(0.0075)


def test_a_schema_past_valgebras_nesting_limit_is_refused_not_raised():
    schema = {"type": "string"}
    for _ in range(80):
        schema = {"properties": {"a": schema}}
    with pytest.raises(Unsupported, match="valgebra refuses"):
        compile_schema(schema)


def test_a_property_name_with_a_lone_surrogate_is_refused():
    with pytest.raises(Unsupported, match="lone surrogate"):
        compile_schema({"properties": {"\ud800": {}}})


def test_a_draft_07_document_compiles_only_through_upgrade():
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "definitions": {"s": {"type": "string"}},
        "properties": {"x": {"$ref": "#/definitions/s", "maxLength": 1}},
    }
    with pytest.raises(Unsupported, match="through `upgrade`"):
        Compiler(schema).compile(schema)
    assert compile_schema(schema).is_valid({"x": "abc"})


def test_two_hundred_definitions_compile_in_place():
    # Each fixpoint is a valgebra definition, and a set admits 128.
    schema = {
        "type": "object",
        "$defs": {f"d{i}": {"type": "string", "pattern": f"^d{i}_$"} for i in range(200)},
        "properties": {f"p{i}": {"$ref": f"#/$defs/d{i}"} for i in range(200)},
    }
    s = compile_schema(schema)
    assert s.is_valid({"p7": "d7_"})
    assert not s.is_valid({"p7": "d8_"})


def test_property_names_true_names_every_key_and_false_none():
    assert compile_schema({"propertyNames": True}) == compile_schema({})
    keyless = compile_schema({"propertyNames": False})
    assert [keyless.is_valid(v) for v in ({}, {"a": 1}, 1)] == [True, False, True]
    assert keyless.is_equivalent(compile_schema({"maxProperties": 0}))


def test_property_names_spelled_out_are_the_keys_of_a_closed_record():
    # Names spelled out are a key set, related to `properties` key by key; a non-string names
    # no key, and a name ending in `?` is that key whole.
    both = {"type": "object", "properties": {"k": {}, "j": {}}, "additionalProperties": False}
    closed = compile_schema(both)
    named = {"type": "object", "propertyNames": {"enum": ["k", "j", 1]}}
    assert compile_schema(named).relation_to(closed) == "subset"
    assert closed.relation_to(compile_schema(named)) == "subset"
    one = compile_schema({"type": "object", "propertyNames": {"const": "k"}})
    assert (one.relation_to(closed), closed.relation_to(one)) == ("subset", "not_subset")
    assert compile_schema({"propertyNames": {"enum": [1]}}) == compile_schema(
        {"propertyNames": False}
    )
    asked = compile_schema({"propertyNames": {"enum": ["a?"]}})
    assert [asked.is_valid(v) for v in ({"a?": 1}, {"a": 1}, {}, 1)] == [True, False, True, True]
    compiler = Compiler(named)
    compiler.compile(named)
    assert not compiler.opaque


def test_a_count_of_properties_decides_the_keys_of_the_record_it_counts():
    # A `minProperties` counting every key a record can hold requires each, and a
    # `maxProperties` counting the required ones admits no other. A count of fewer keys than
    # the record holds proves no one of them: `{"j": 1}` refutes the fourth, left undecided.
    def relation(subject, supertype):
        subject, supertype = {"type": "object", **subject}, {"type": "object", **supertype}
        return compile_schema(subject).relation_to(compile_schema(supertype))

    names = {"propertyNames": {"enum": ["k", "j"]}}
    only_k = {"properties": {"k": {}}, "additionalProperties": False}
    closed = {"properties": {"k": {}, "j": {}}, "additionalProperties": False}
    assert relation({**names, "minProperties": 2}, {"required": ["k", "j"]}) == "subset"
    assert relation({**closed, "minProperties": 2}, {"required": ["k", "j"]}) == "subset"
    one = {"propertyNames": {"const": "k"}, "minProperties": 1}
    assert relation(one, {"required": ["k"]}) == "subset"
    assert relation({**names, "minProperties": 1}, {"required": ["k"]}) == "undecided"
    assert relation({"required": ["k"], "maxProperties": 1}, only_k) == "subset"
    absent_j = {"not": {"required": ["j"]}}
    assert relation({"required": ["k"], "maxProperties": 1}, absent_j) == "subset"
    assert relation({"required": ["k"], "maxProperties": 2}, only_k) == "not_subset"


_TAG = {"enum": ["a", "b"]}


@pytest.mark.parametrize(
    ("schema", "path", "read"),
    [
        (
            {"type": "object", "allOf": [{"properties": {"f": {"enum": ["a", "zz"]}}}]},
            ("f",),
            {"enum": ["a", "zz"]},
        ),
        (
            {
                "properties": {"rs": {"type": "array"}},
                "allOf": [{"properties": {"rs": {"items": _TAG}}}],
            },
            ("rs", ITEM),
            _TAG,
        ),
        (
            {
                "$defs": {"L": {"type": "array", "items": _TAG}},
                "properties": {"rs": {"$ref": "#/$defs/L", "minItems": 1}},
            },
            ("rs", ITEM),
            _TAG,
        ),
        (
            {
                "$id": "https://example.com/root",
                "$defs": {"T": {"properties": {"k": {"type": "string"}}}},
                "properties": {
                    "a": {
                        "$id": "https://example.com/inner",
                        "$defs": {"T": {"properties": {"k": {"type": "integer"}}}},
                        "$ref": "#/$defs/T",
                    }
                },
            },
            ("a", "k"),
            {"type": "integer"},
        ),
        (
            {"anyOf": [{"properties": {"f": {"const": 1}}}, {"properties": {"f": {"const": 2}}}]},
            ("f",),
            {"enum": [1, 2]},
        ),
        ({"type": "string"}, ("f",), False),
        ({"propertyNames": {"enum": ["g"]}}, ("f",), False),
        ({"enum": [{"f": 1}, {"f": "x"}, {"g": 2}, 3]}, ("f",), {"enum": [1, "x"]}),
        (
            {"patternProperties": {"^x-": {"type": "string"}}, "additionalProperties": False},
            ("x-a",),
            {"type": "string"},
        ),
        (
            {"properties": {"a": {}}, "additionalProperties": {"type": "integer"}},
            ("b",),
            {"type": "integer"},
        ),
        (
            {"prefixItems": [{"const": 0}], "items": {"type": "string"}},
            (ITEM,),
            {"anyOf": [{"const": 0}, {"type": "string"}]},
        ),
        (
            {
                "if": {"properties": {"k": {"const": 1}}},
                "then": {"properties": {"f": {"type": "string"}}},
                "else": {"properties": {"f": {"type": "integer"}}},
            },
            ("f",),
            {"type": ["string", "integer"]},
        ),
        (
            {
                "$defs": {
                    "t": {
                        "type": "object",
                        "properties": {
                            "kids": {"type": "array", "items": {"$ref": "#/$defs/t"}},
                            "v": {"type": "integer"},
                        },
                    }
                },
                "$ref": "#/$defs/t",
            },
            ("kids", ITEM, "v"),
            {"type": "integer"},
        ),
    ],
    ids=[
        "a field an allOf declares",
        "items an allOf declares",
        "items a reference with a sibling declares",
        "a field inside a resource of its own",
        "a field each branch declares",
        "a kind holding no object",
        "a name propertyNames refuses",
        "a field listed objects hold",
        "a key a pattern matches",
        "a key no property names",
        "a prefix and the items after it",
        "a field each side of an if declares",
        "a field two levels down a recursive tree",
    ],
)
def test_below_reads_what_each_keyword_says_of_a_field_or_an_item(schema, path, read):
    assert Compiler(schema).below(path).is_equivalent(compile_schema(read))


def test_below_reads_no_keyword_it_cannot_narrow_by_as_narrowing():
    # `not` and a lone `if` constrain the field, but no subschema holds what they leave.
    for schema in ({"not": {"properties": {"f": {"type": "string"}}}}, {"if": True, "then": {}}):
        assert Compiler(schema).below(("f",)).is_equivalent(compile_schema(True))
    with pytest.raises(Unsupported):
        Compiler({"$schema": "http://json-schema.org/draft-07/schema#"}).below(("f",))


def test_a_one_of_whose_branches_are_disjoint_is_their_union():
    branches = [{"type": "string"}, {"type": "null"}]
    assert compile_schema({"oneOf": branches}) == compile_schema({"anyOf": branches})


def test_a_one_of_whose_branches_meet_holds_a_value_in_exactly_one():
    s = compile_schema({"oneOf": [{"type": "integer"}, {"minimum": 0}]})
    assert [s.is_valid(v) for v in (5, -1, 0.5, "x", -1.5)] == [False, True, True, True, False]


def test_a_one_of_naming_two_targets_asks_once_whether_they_meet():
    # Each use of a reference is the one set compiled for its target, so the second `oneOf`
    # is the first one's question, and the two compile to one set.
    a = {"type": "object", "required": ["a"]}
    b = {"type": "object", "required": ["b"]}
    one_of = {"oneOf": [{"$ref": "#/$defs/a"}, {"$ref": "#/$defs/b"}]}
    root = {"$defs": {"a": a, "b": b}, "properties": {"x": one_of, "y": one_of}}
    compiler = Compiler(root)
    s = compiler.compile(root)
    assert len(compiler.asked) == 1
    assert s.is_valid({"x": {"a": 1}, "y": {"b": 1}})
    assert not s.is_valid({"x": {"a": 1, "b": 1}})


def test_a_one_of_nested_in_its_disjoint_branches_stays_under_the_node_bound():
    # Each level's second branch would be spelled twice, whole and complemented: 2**20
    # copies at the root, where twelve levels already pass valgebra's node bound.
    schema: dict = {"type": "null"}
    for _ in range(20):
        leaf = {"type": "object", "required": ["t"], "properties": {"t": {"const": "leaf"}}}
        node = {
            "type": "object",
            "required": ["t", "next"],
            "properties": {"t": {"const": "node"}, "next": schema},
        }
        schema = {"oneOf": [leaf, node]}
    s = compile_schema(schema)
    value: object = {"t": "leaf"}
    for _ in range(19):
        value = {"t": "node", "next": value}
    assert s.is_valid(value)
    assert not s.is_valid({"t": "node", "next": {"t": "other"}})


def test_a_chain_of_references_reads_each_subtree_once(monkeypatch: pytest.MonkeyPatch):
    # Each target's walk for whether it reaches itself reads the subtrees the walks of the
    # targets above it read: once a compile, a chain of n reads n + 1 subtrees, and read at
    # every walk, n * n / 2.
    n = 40
    defs: dict[str, object] = {
        f"d{i}": {"allOf": [{"$ref": f"#/$defs/d{i + 1}"}]} for i in range(n)
    }
    defs[f"d{n}"] = {"type": "string"}
    reads: list[object] = []
    read = schema_module._references

    def counted(node: object, base: str) -> list[str]:
        reads.append(node)
        return read(node, base)

    monkeypatch.setattr(schema_module, "_references", counted)
    s = compile_schema({"$defs": defs, "$ref": "#/$defs/d0"})
    assert s.is_valid("x")
    assert not s.is_valid(1)
    assert len(reads) == n + 1


def test_a_reference_that_reaches_itself_is_a_fixpoint():
    item = {"$ref": "#/$defs/tree"}
    tree = {"type": "object", "properties": {"kids": {"type": "array", "items": item}}}
    s = compile_schema({"$defs": {"tree": tree}, "$ref": "#/$defs/tree"})
    assert s.is_valid({"kids": [{"kids": []}]})
    assert not s.is_valid({"kids": [{"kids": [1]}]})


#: A recursive schema reached through `patternProperties`, whose check is a callback run at
#: membership time, outside every fixpoint's builder.
_PATTERNED = {
    "type": "object",
    "patternProperties": {"^[a-z]": {"$ref": "#/$defs/h"}},
    "additionalProperties": False,
}
_TREE = {"$defs": {"h": {"oneOf": [{"type": "number"}, _PATTERNED]}}, "$ref": "#/$defs/h"}


class TestRecursionThroughCallbacks:
    @pytest.mark.parametrize(
        ("value", "admitted"),
        [({"k": 1}, True), ({"k": {"j": 2}}, True), ({"k": "x"}, False), ({"K": 1}, False)],
    )
    def test_a_pattern_property_reaching_its_fixpoint_checks_the_fixpoint(self, value, admitted):
        assert compile_schema(_TREE).is_valid(value) is admitted

    def test_a_set_built_inside_a_fixpoint_is_not_reused_outside_it(self):
        c = Compiler(_TREE)
        c.ref("#/$defs/h")
        assert c.compile(_PATTERNED).is_valid({"k": 1})

    def test_the_set_compiled_again_reads_format_as_the_compiler_does(self):
        # Five patterns are past what a clause holds, so each key's value is checked through
        # a callback, against the fixpoint compiled again at membership time.
        patterns = {p: {"$ref": "#/$defs/t"} for p in ("^a", "^b", "^c", "^d", "^e")}
        ipv4 = {"type": "string", "format": "ipv4"}
        t = {"anyOf": [{"type": "object", "patternProperties": patterns}, ipv4]}
        compiled = compile_schema({"$defs": {"t": t}, "$ref": "#/$defs/t"}, assert_format=True)
        assert not compiled.is_valid("nope")
        assert not compiled.is_valid({"a": "nope"})
        assert not compiled.is_valid({"a": {"b": "nope"}})
        assert compiled.is_valid({"a": {"b": "1.2.3.4"}})


@pytest.mark.parametrize(
    "schema",
    [
        {"required": "ab"},
        {"enum": "ab"},
        {"exclusiveMinimum": True},
        {"type": []},
        {"type": ["string", "string"]},
        {"multipleOf": 0},
        {"pattern": 5},
        {"properties": {"a": 3}},
        {"allOf": []},
        {"dependentRequired": {"a": "b"}},
    ],
)
def test_a_keyword_holding_what_the_meta_schema_refuses_is_refused(schema):
    with pytest.raises(Unsupported):
        compile_schema(schema)


def test_a_reference_reached_through_a_pointer_resolves_in_its_own_resource():
    # `y` sits in `x`'s resource, so its `#/$defs/z` is `x`'s `z`, however `y` is reached.
    schema = {
        "$defs": {
            "z": {"type": "string"},
            "x": {
                "$id": "http://example.com/x.json",
                "$defs": {"z": {"type": "integer"}, "y": {"$ref": "#/$defs/z"}},
            },
        },
        "$ref": "#/$defs/x/$defs/y",
    }
    assert compile_schema(schema).is_valid(1)
    assert not compile_schema(schema).is_valid("1")


class TestLookaheads:
    @pytest.mark.parametrize(
        ("pattern", "admitted", "refused"),
        [
            ("^(?!@@)[@a-z]+$", ["@a", "a@@"], ["@@a", "a b"]),
            ("^(?!interactive|name|style).+$", ["color", "xname"], ["names", ""]),
            ("^(?!pattern$).*$", ["patterns", ""], ["pattern"]),
            ("^(?=[^=]+$)(?!\\s+$)(.|\\n)+$", ["ab", " a "], ["a=b", "   "]),
            ("^((?!mode)(?!Mode).)*$", ["abc", ""], ["a mode b", "Moder", "a\nb"]),
        ],
    )
    def test_a_lookahead_opening_a_pattern_or_tempering_its_dot_is_a_set(
        self, pattern, admitted, refused
    ):
        s = compile_schema({"type": "string", "pattern": pattern})
        assert [s.is_valid(v) for v in admitted] == [True] * len(admitted)
        assert [s.is_valid(v) for v in refused] == [False] * len(refused)

    @pytest.mark.parametrize(
        "pattern",
        [
            "^(?!a)b|c",  # the lookahead binds the first branch alone
            "^((?!$).)*$",  # `$` matches the empty string at the end alone
            "^((?!x?).)*$",  # `x?` matches the empty string
            "^((?!\\b$).)*$",  # `\b$` matches at the end of "ab" alone, which the loop never tests
            "a(?!b)",  # a lookahead past the start
        ],
    )
    def test_any_other_lookahead_is_refused(self, pattern):
        with pytest.raises(Unsupported, match="regex dialect"):
            compile_schema({"pattern": pattern})

    def test_a_relation_reads_the_lookahead(self):
        words = compile_schema({"type": "string", "pattern": "^[a-z@]+$"})
        unmarked = compile_schema({"type": "string", "pattern": "^(?!@@)[a-z@]+$"})
        assert unmarked.relation_to(words) == "subset"
        assert words.relation_to(unmarked) == "not_subset"


#: A pattern, a text, and whether ECMA-262 finds a match of the one in the other.
_ECMA_READINGS = [
    (r"^\d$", "١", False),
    (r"^\d$", "7", True),
    (r"^\w$", "é", False),
    (r"^\s$", "﻿", True),
    (r"^\s$", "\u0085", False),
    (r"^.$", " ", False),
    (r"^[\d]$", "١", False),
    (r"^[^\d]$", "١", True),
    (r"^\cJ$", "\n", True),
    (r"^abc$", "abc\n", False),
    (r"a\b", "aé", True),
    (r"a\B", "aé", False),
    (r"\bfoo\b", "afoo", False),
    (r"^[\b]$", "\x08", True),
    (r"^[\s\S]$", "\n", True),
    (r"^[a\D]$", "x", True),
    (r"^[a\D]$", "7", False),
    (r"^[^]$", "\n", True),
    (r"^[]$", "", False),
    (r"^[a&&b]$", "&", True),
    (r"^[a~~b]$", "~", True),
    (r"^[a[]$", "[", True),
    (r"^a\0b$", "a\x00b", True),
    # A range from `-`, and a `^` after a negated shorthand: valgebra's class syntax
    # reads both apart from ECMA-262, so every class atom is written as a code point.
    (r"^[--a]$", ".", True),
    (r"^[^--z]$", ".", False),
    (r"^[\D^_]$", "0", False),
    (r"^[\D^_]$", "^", True),
    (r"^[^a\S]$", " ", True),
    (r"^[^a\S]$", "x", False),
    (r"^\uD83D\uDE00$", "\U0001f600", True),
    (r"^\u{1F600}$", "\U0001f600", True),
    (r"^\p{digit}+$", "\u0663", True),
    (r"^\p{sc=Grek}$", "\u03b1", True),
    # Annex B's literals, read as the character as every dialect reads them.
    (r"^a\:b$", "a:b", True),
    (r"^PUBMED:\{d}$", "PUBMED:{d}", True),
    (r"^x]$", "x]", True),
    (r"^a{b$", "a{b", True),
]


class TestEcmaDialect:
    @pytest.mark.parametrize(("pattern", "text", "admitted"), _ECMA_READINGS)
    def test_a_pattern_means_what_ecma_262_says(self, pattern, text, admitted):
        assert compile_schema({"pattern": pattern}).is_valid(text) is admitted

    @pytest.mark.parametrize(
        "pattern",
        [
            r"\A",
            r"\z",
            r"\a",
            r"\x{41}",
            r"\U00000041",
            r"\pL",
            r"\p{Greek}",
            r"\p{lu}",
            r"(?i)a",
            r"(?P<n>a)",
            r"a**",
            r"a{1}{2}",
            r"^*",
            r"a{,3}",
            r"x{2,1}",
            r"[\d-z]",
            r"[z-a]",
            r"a)|(b",
            r"(a",
            "a\\",
        ],
    )
    def test_a_pattern_ecma_262_refuses_under_u_is_refused(self, pattern):
        # Each reads differently in valgebra's engine, Annex B or Python's `re`: `\A` is an
        # anchor to one and the letter to another, and `a)|(b` would close the group the
        # search wraps the pattern in.
        with pytest.raises(Unsupported, match="ECMA-262 refuses"):
            compile_schema({"pattern": pattern})


def _failed(schema: object, value: object) -> tuple[Compiler, dict[str, object]]:
    """Return a compiler of ``schema`` and the one failure valgebra reports of ``value``."""
    compiler = Compiler(schema)
    values = compiler.compile(schema)
    with pytest.raises(ValidationError) as caught:
        values.validate(value)
    (failure,) = caught.value.errors
    return compiler, failure


class TestPatternWording:
    def test_a_failed_pattern_is_named_in_the_schemas_text(self):
        # The client holds the schema's text, which the `jsonschema` package words with.
        compiler, failure = _failed({"type": "string", "pattern": "^[a-f0-9]{24}$"}, "nope")
        named = compiler.reworded(failure)
        assert named["expected"] == "a string matching '^[a-f0-9]{24}$'"
        assert named["message"] == (
            "expected a string matching '^[a-f0-9]{24}$', got 'nope' [string_pattern_mismatch]"
        )
        assert {k: named[k] for k in ("code", "path", "value")} == {
            k: failure[k] for k in ("code", "path", "value")
        }

    @pytest.mark.parametrize(
        ("schema", "value", "expected"),
        [
            (
                {"properties": {"id": {"pattern": "^[a-f]{2}$"}}},
                {"id": "zz"},
                "one of: not str, str and a string matching '^[a-f]{2}$'",
            ),
            (
                {"type": "object", "propertyNames": {"pattern": "^[a-f]+$"}},
                {"zz": 1},
                "a string matching '^[a-f]+$'",
            ),
            (
                {"type": "object", "patternProperties": {"^s_": {}}, "additionalProperties": False},
                {"x": 1},
                "a string matching '^s_'",
            ),
            ({"type": "string", "pattern": "^it's$"}, "its", """a string matching "^it's$\""""),
        ],
    )
    def test_each_keyword_writing_a_pattern_names_it(self, schema, value, expected):
        compiler, failure = _failed(schema, value)
        assert compiler.reworded(failure)["expected"] == expected

    @pytest.mark.parametrize(
        ("pattern", "text"), [(p, t) for p, t, admitted in _ECMA_READINGS if not admitted]
    )
    def test_a_pattern_ecma_262_reads_is_named_as_written(self, pattern, text):
        compiler, failure = _failed({"type": "string", "pattern": pattern}, text)
        assert compiler.reworded(failure)["expected"] == f"a string matching {pattern!r}"

    @pytest.mark.parametrize(
        ("schema", "value"),
        [
            # A part a lookahead is read as, which is not the pattern.
            ({"type": "string", "pattern": "^(?!ab)[a-z]+$"}, "abc"),
            ({"type": "string", "pattern": "^((?!x).)*$"}, "axb"),
            # Two texts valgebra is given as one.
            ({"type": "string", "anyOf": [{"pattern": r"^\d$"}, {"pattern": "^[0-9]$"}]}, "c"),
        ],
    )
    def test_a_part_or_a_shared_text_is_named_as_valgebra_gave_it(self, schema, value):
        compiler, failure = _failed(schema, value)
        assert compiler.reworded(failure) == failure

    def test_a_literal_holding_the_text_valgebra_was_given_keeps_it(self):
        body = "(?s:.*)(?:^a$)(?s:.*)"
        schema = {"type": "string", "anyOf": [{"pattern": "^a$"}, {"const": body}]}
        compiler, failure = _failed(schema, "b")
        named = compiler.reworded(failure)["expected"]
        assert isinstance(named, str)
        assert f"the literal {body!r}" in named
        assert "a string matching '^a$'" in named

    def test_the_value_is_never_renamed(self):
        schema = {"type": "string", "pattern": "^a$"}
        compiler, failure = _failed(schema, "b")
        label = failure["expected"]
        assert isinstance(label, str)
        _, spelled = _failed(schema, label)
        named = compiler.reworded(spelled)
        message, given = named["message"], spelled["message"]
        assert isinstance(message, str)
        assert isinstance(given, str)
        assert named["value"] == spelled["value"] == repr(label)
        assert message.partition(", got ")[2] == given.partition(", got ")[2]
        assert message.startswith("expected a string matching '^a$', got ")
        # A value spelling the whole span leaves two, and the message as valgebra gave it.
        _, twice = _failed(schema, f"expected {label}, got ")
        assert compiler.reworded(twice)["message"] == twice["message"]
        assert compiler.reworded(twice)["expected"] == "a string matching '^a$'"


class TestDraft7:
    def test_an_items_array_is_a_prefix_and_additional_items_its_tail(self):
        s = compile_schema(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "items": [{"type": "integer"}],
                "additionalItems": {"type": "string"},
            }
        )
        assert s.is_valid([1, "a", "b"])
        assert not s.is_valid([1, 2])

    def test_dependencies_split_by_kind(self):
        s = compile_schema(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "dependencies": {"a": ["b"], "c": {"required": ["d"]}},
            }
        )
        assert not s.is_valid({"a": 1})
        assert not s.is_valid({"c": 1})
        assert s.is_valid({"a": 1, "b": 2, "c": 3, "d": 4})

    def test_a_ref_overrides_its_siblings(self):
        s = compile_schema(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "definitions": {"i": {"type": "integer"}},
                "properties": {"x": {"$ref": "#/definitions/i", "maximum": 0}},
            }
        )
        assert s.is_valid({"x": 5})

    def test_a_property_named_like_a_keyword_is_a_name(self):
        s = compile_schema(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "properties": {"items": {"type": "array"}, "dependencies": {"type": "string"}},
            }
        )
        assert s.is_valid({"items": [], "dependencies": "x"})
        assert not s.is_valid({"items": 1})

    @pytest.mark.parametrize(
        ("keywords", "value"),
        [
            ({"contains": {"const": 1}, "minContains": 2}, [1]),
            ({"prefixItems": [{"type": "string"}]}, [1]),
            ({"dependentRequired": {"a": ["b"]}}, {"a": 1}),
            ({"dependentSchemas": {"a": False}}, {"a": 1}),
        ],
    )
    def test_a_keyword_a_later_draft_added_asserts_nothing(self, keywords, value):
        schema = {"$schema": "http://json-schema.org/draft-07/schema#", **keywords}
        assert compile_schema(schema).is_valid(value)

    def test_a_ref_keeps_the_defs_beside_it(self):
        s = compile_schema(
            {
                "$schema": "http://json-schema.org/draft-07/schema#",
                "$defs": {"i": {"type": "integer"}},
                "$ref": "#/$defs/i",
            }
        )
        assert s.is_valid(1)
        assert not s.is_valid("a")


class TestOlderDrafts:
    D4 = "http://json-schema.org/draft-04/schema#"
    D6 = "http://json-schema.org/draft-06/schema#"

    def test_draft_04_exclusive_flags_move_onto_their_bound(self):
        s = compile_schema({"$schema": self.D4, "minimum": 1, "exclusiveMinimum": True})
        assert not s.is_valid(1)
        assert s.is_valid(2)
        assert compile_schema(
            {"$schema": self.D4, "maximum": 1, "exclusiveMaximum": False}
        ).is_valid(1)

    def test_draft_04_names_its_root_id_without_a_dollar(self):
        assert compile_schema(
            {"$schema": self.D4, "id": "http://x.example/s", "type": "string"}
        ).is_valid("a")

    @pytest.mark.parametrize(
        ("draft", "keywords", "value"),
        [
            (D4, {"const": 1}, 2),
            (D4, {"contains": {"const": 1}}, [2]),
            (D4, {"propertyNames": {"maxLength": 1}}, {"long": 1}),
            (D6, {"if": {"const": 1}, "then": False}, 1),
        ],
    )
    def test_a_keyword_the_draft_does_not_know_asserts_nothing(self, draft, keywords, value):
        assert compile_schema({"$schema": draft, **keywords}).is_valid(value)


class TestRecursiveReferences:
    D2019 = "https://json-schema.org/draft/2019-09/schema"

    def _tree(self, uri, leaf):
        return {
            "$schema": self.D2019,
            "$id": uri,
            "$recursiveAnchor": True,
            "anyOf": [leaf, {"type": "object", "additionalProperties": {"$recursiveRef": "#"}}],
        }

    def test_upgrade_writes_the_recursion_as_a_dynamic_anchor_with_no_name(self):
        schema = {"$schema": self.D2019, "$recursiveAnchor": True, "items": {"$recursiveRef": "#"}}
        upgraded = upgrade(schema, 2019)
        assert upgraded == {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$dynamicAnchor": "",
            "items": {"$dynamicRef": "#"},
        }
        # The empty name is no draft 2020-12 anchor, but where `upgrade` writes it.
        with pytest.raises(Unsupported, match="dynamicAnchor"):
            compile_schema(json.loads(json.dumps(upgraded)))

    def test_a_recursive_ref_reaches_the_outermost_anchored_resource(self):
        outer = self._tree("http://example.com/outer.json", _STR)
        outer["$defs"] = {"inner": self._tree("inner.json", _INT)}
        outer["anyOf"] = [_STR, {"$ref": "inner.json"}]
        s = compile_schema(outer)
        assert s.is_valid({"a": {"b": "c"}})
        assert s.is_valid({"a": {"b": 1}})
        assert not s.is_valid({"a": {"b": None}})

    def test_a_recursive_ref_reaches_past_a_resource_without_the_anchor(self):
        # Draft 2019-09 reads the outermost schema in scope setting the anchor (section
        # 8.2.4.2.2); the `jsonschema` package stops at the first resource without it.
        between = {"$schema": self.D2019, "$id": "http://example.com/b", "$ref": "c"}
        outer = self._tree("http://example.com/a", _STR)
        outer["anyOf"] = [_STR, {"$ref": "b"}]
        inner = self._tree("http://example.com/c", _INT)
        documents = {"http://example.com/b": between, "http://example.com/c": inner}
        s = compile_schema(outer, documents=documents)
        assert s.is_valid({"a": "s"})
        assert not s.is_valid({"a": None})

    def test_a_recursive_ref_reads_the_scope_across_supplied_documents(self):
        tree = {
            "$schema": self.D2019,
            "$id": "http://example.com/tree",
            "$recursiveAnchor": True,
            "type": "object",
            "properties": {"data": True, "children": {"items": {"$recursiveRef": "#"}}},
        }
        strict = {
            "$schema": self.D2019,
            "$id": "http://example.com/strict",
            "$recursiveAnchor": True,
            "$ref": "tree",
            "unevaluatedProperties": False,
        }
        s = compile_schema(strict, documents={"http://example.com/tree": tree})
        assert s.is_valid({"children": [{"data": 1}]})
        assert not s.is_valid({"children": [{"daat": 1}]})

    def test_a_dynamic_reference_naming_no_fragment_reads_no_recursive_anchor(self):
        # Inside a scope a 2019-09 resource anchored, a `$dynamicRef` to an anchored root
        # names no anchor, the empty one included: it is the `$ref` it resolves as.
        tree = {
            "$schema": self.D2019,
            "$id": "http://example.com/tree",
            "$recursiveAnchor": True,
            "type": "object",
        }
        named = {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "$id": "http://example.com/named",
            "$dynamicRef": "http://example.com/tree",
        }
        outer = {
            "$schema": self.D2019,
            "$id": "http://example.com/outer",
            "$recursiveAnchor": True,
            "properties": {"t": {"$ref": "named"}},
            "additionalProperties": False,
        }
        documents = {"http://example.com/tree": tree, "http://example.com/named": named}
        s = compile_schema(outer, documents=documents)
        assert s.is_valid({"t": {"other": 1}})
        assert not s.is_valid({"t": 1})

    def test_a_recursive_anchor_starting_no_resource_is_refused(self):
        schema = {"$schema": self.D2019, "properties": {"a": {"$recursiveAnchor": True}}}
        with pytest.raises(Unsupported, match="starts no resource"):
            compile_schema(schema)
        unset = {"$schema": self.D2019, "properties": {"a": {"$recursiveAnchor": False}}}
        assert compile_schema(unset).is_valid({"a": 1})


def test_an_unknown_keyword_is_an_annotation_and_recorded():
    compiler = Compiler({"type": "string", "x-label": "id", "nullable": True})
    s = compiler.compile({"type": "string", "x-label": "id", "nullable": True})
    assert s.is_valid("a")
    assert not s.is_valid(None)
    assert compiler.ignored == {"x-label", "nullable"}


def test_a_nullable_number_keeps_its_non_integral_part():
    # The non-integral numbers inside `null | number` hold 0.5, met with the universe or not.
    nullable = compile_schema({"anyOf": [{"type": "null"}, {"type": "number"}]})
    number, integer = compile_schema({"type": "number"}), compile_schema({"type": "integer"})
    meet = intersection(number, complement(integer), nullable)
    assert meet.is_valid(0.5)
    assert not meet.is_empty()
    assert not intersection(meet, JSON).is_empty()


_HEADERS = {
    "type": "object",
    "patternProperties": {"^x-": {"type": "string"}},
    "additionalProperties": False,
}


def _nested_one_of(depth):
    schema = {"type": "integer"}
    for i in range(depth):
        branches = [{"minimum": i}, {"maximum": i + 3}, {"multipleOf": 2}, schema]
        schema = {"oneOf": branches}
    return schema


_DEFINED = {
    "$defs": {"word": {"type": "string", "maxLength": 3}, "pair": {"type": "array"}},
    "properties": {"a": {"$ref": "#/$defs/word"}, "b": {"$ref": "#/$defs/word"}},
    "oneOf": [{"required": ["a"]}, {"required": ["b"]}, {"$ref": "#/$defs/pair"}],
}


class TestPastTheLimit:
    def test_a_one_of_past_the_limit_is_counted_at_membership(self):
        import jsonschema  # noqa: PLC0415 - the second implementation, a test dependency

        schema = _nested_one_of(6)
        with pytest.raises(Unsupported, match="valgebra refuses"):
            Compiler(schema, by_clauses=False).compile(schema)
        compiled = compile_schema(schema)
        reference = jsonschema.Draft202012Validator(schema)
        values = [*range(-4, 12), 2.5, "a", None]
        assert [compiled.is_valid(v) for v in values] == [reference.is_valid(v) for v in values]

    @pytest.mark.parametrize(
        ("schema", "opaque"), [(_nested_one_of(3), {"oneOf"}), (_DEFINED, {"oneOf", "$ref"})]
    )
    def test_the_predicate_reading_admits_what_the_exact_one_does(self, schema, opaque):
        exact = Compiler(schema).compile(schema)
        counted = Compiler(schema, by_predicate=True)
        compiled = counted.compile(schema)
        values = [*range(-2, 8), 1.5, "ab", "abcd", [], [1], {}, {"a": "x"}, {"b": 1}, None]
        values += [{"a": "x", "b": "y"}, {"a": "toolong"}]
        assert [compiled.is_valid(v) for v in values] == [exact.is_valid(v) for v in values]
        assert counted.opaque == opaque


class TestKeys:
    def test_a_key_ending_in_a_question_mark_is_that_key(self):
        # valgebra's record literal reads a trailing `?` as "optional": a required key is
        # met with its presence, and an optional one escaped.
        asked = "in which school did you spend most of your education?"
        survey = compile_schema(
            {
                "type": "object",
                "properties": {asked: {"type": "string"}, "opt?": {"type": "integer"}},
                "required": [asked],
                "additionalProperties": False,
            }
        )
        assert survey.is_valid({asked: "x", "opt?": 1})
        assert not survey.is_valid({})
        assert not survey.is_valid({asked[:-1]: "x"})
        assert not survey.is_valid({asked: "x", "opt": 1})
        assert not survey.is_valid({asked: "x", "opt?": "1"})
        constant = compile_schema({"const": {"a?": 1}})
        assert constant.is_valid({"a?": 1})
        assert not constant.is_valid({"a": 1})
        assert not constant.is_valid({})
        depends = compile_schema({"dependentRequired": {"x": ["y?"]}})
        assert depends.is_valid({"x": 1, "y?": 1})
        assert not depends.is_valid({"x": 1, "y": 1})

    def test_a_pattern_is_a_clause_a_relation_reads(self):
        headers = compile_schema(_HEADERS)
        strings = compile_schema({"type": "object", "additionalProperties": {"type": "string"}})
        assert headers.is_valid({"x-a": "s"})
        assert not headers.is_valid({"y": "s"})
        assert not headers.is_valid({"x-a": 1})
        assert headers.relation_to(strings) == "subset"
        assert strings.relation_to(headers) == "not_subset"

    def test_a_key_takes_every_pattern_it_matches(self):
        both = compile_schema(
            {
                "type": "object",
                "patternProperties": {"^a": {"type": "integer"}, "z$": {"minimum": 3}},
            }
        )
        assert both.is_valid({"az": 3})
        assert not both.is_valid({"az": 2}), "the two schemas are a conjunction"
        assert both.is_valid({"a": 2})

    def test_a_schema_past_valgebras_limit_reads_by_predicate(self):
        def level(depth):
            value = {"type": "string"} if depth == 0 else level(depth - 1)
            return {
                "type": "object",
                "patternProperties": {f"^{c}": value for c in "abcd"},
                "additionalProperties": False,
            }

        deep = level(4)
        with pytest.raises(Unsupported, match="valgebra refuses"):
            Compiler(deep).compile(deep)
        compiled = compile_schema(deep)
        leaf = {"a": {"b": {"c": {"d": {"a": "s"}}}}}
        assert compiled.is_valid(leaf)
        assert not compiled.is_valid({"e": 1})


def _either(words: list[str]) -> str:
    """Join phrases as fishtest's refusal does: `"mug", "bottle" or "box"`."""
    return words[0] if len(words) == 1 else f"{', '.join(words[:-1])} or {words[-1]}"


#: Input schemas of a robot's skills, as the MADE proof of concept publishes them.
OBJECT_ID = {"type": "string", "pattern": "^obj_[0-9]{1,6}$", "description": "an id"}
METERS: dict[str, Any] = {
    "type": "object",
    "properties": {
        "unit": {"type": "string", "const": "m"},
        "value": {"type": "number", "minimum": 0.2, "maximum": 0.6},
    },
    "required": ["unit", "value"],
    "additionalProperties": False,
}
SKILLS: dict[str, dict[str, Any]] = {
    "detect_object": {
        "type": "object",
        "properties": {"label": {"type": "string", "enum": ["mug", "bottle", "box"]}},
        "required": ["label"],
        "additionalProperties": False,
    },
    "estimate_pose": {
        "type": "object",
        "properties": {"object_id": OBJECT_ID},
        "required": ["object_id"],
        "additionalProperties": False,
    },
    "say": {
        "type": "object",
        "properties": {
            "text": {"type": "string", "minLength": 1, "maxLength": 300, "description": "x"},
            "language": {"type": "string", "enum": ["it", "en"]},
        },
        "required": ["text", "language"],
        "additionalProperties": False,
    },
    "grasp": {
        "type": "object",
        "properties": {"pose_status": {"type": "string", "const": "ok"}, "distance": METERS},
        "required": ["pose_status", "distance"],
        "additionalProperties": False,
    },
}


class TestAdmitted:
    """What a schema admits is worded as both its adopters word it where the schema decides."""

    @pytest.mark.parametrize(
        ("skill", "arguments", "worded"),
        [
            ("detect_object", {"label": "cup"}, [("enum", ['"mug"', '"bottle"', '"box"'])]),
            (
                "estimate_pose",
                {"object_id": "mug"},
                [("pattern", ["a string matching ^obj_[0-9]{1,6}$"])],
            ),
            ("estimate_pose", {"object_id": 5}, [("type", ["a string matching ^obj_[0-9]{1,6}$"])]),
            (
                "say",
                {"text": "", "language": "it"},
                [("minLength", ["a string of 1 to 300 characters"])],
            ),
            (
                "grasp",
                {"pose_status": "pending", "distance": {"unit": "m", "value": 0.3}},
                [("const", ['"ok"'])],
            ),
            (
                "grasp",
                {"pose_status": "ok", "distance": {"unit": "cm", "value": 0.9}},
                [("const", ['"m"']), ("maximum", ["a number from 0.2 to 0.6"])],
            ),
            ("estimate_pose", ["obj_1"], [("type", ["an object"])]),
        ],
    )
    def test_a_refusal_is_worded_at_its_keyword(
        self, skill: str, arguments: object, worded: list[tuple[str, list[str]]]
    ):
        schema = SKILLS[skill]
        compiler = Compiler(schema)
        with pytest.raises(ValidationError) as refused:
            compiler.compile(schema).validate(arguments)
        found = []
        for failure in refused.value.errors:
            named = compiler.located(failure, arguments)
            location = named["keywordLocation"]
            assert isinstance(location, str)
            found.append((named["keyword"], admitted(compiler.at(location))))

        assert found == worded

    def test_the_phrases_join_into_each_adopters_words(self):
        # fishtest joins with "or"; the proof of concept writes "one of" before a list and
        # "exactly" before one value: the joining is the caller's, the phrases the schema's.
        label = admitted(SKILLS["detect_object"]["properties"]["label"])
        assert label is not None
        assert _either(label) == '"mug", "bottle" or "box"'
        assert "one of " + ", ".join(label) == 'one of "mug", "bottle", "box"'
        (status,) = admitted(SKILLS["grasp"]["properties"]["pose_status"]) or []
        assert f"exactly {status}" == 'exactly "ok"'
        assert admitted(METERS["properties"]["value"]) == ["a number from 0.2 to 0.6"]

    @pytest.mark.parametrize(
        ("schema", "words"),
        [
            ({"type": "integer", "minimum": 1, "maximum": 5}, ["an integer from 1 to 5"]),
            ({"type": "number", "exclusiveMinimum": 0}, ["a number greater than 0"]),
            (
                {"type": "integer", "minimum": 0, "multipleOf": 2},
                ["an integer of at least 0, a multiple of 2"],
            ),
            ({"type": "number", "maximum": 2**60}, ["a number of at most 1.152921504606847e+18"]),
            (
                {"type": "array", "minItems": 1, "items": {"type": "string"}},
                ["an array of at least 1 item"],
            ),
            ({"type": "string", "maxLength": 3}, ["a string of at most 3 characters"]),
            ({"type": "string", "minLength": 2, "maxLength": 2}, ["a string of 2 characters"]),
            (
                {"anyOf": [{"const": "a"}, {"type": "integer", "minimum": 3}]},
                ['"a"', "an integer of at least 3"],
            ),
            ({"type": ["string", "null"]}, ["a string", "null"]),
            ({"type": "boolean", "description": "d"}, ["a boolean"]),
            ({"$ref": "#/$defs/x"}, None),
            ({"type": "string", "format": "date"}, None),
            ({"anyOf": [{"type": "string"}, {"not": {}}]}, None),
        ],
    )
    def test_a_schema_is_worded_by_the_readers_or_not_at_all(
        self, schema: dict[str, Any], words: list[str] | None
    ):
        assert admitted(schema) == words


class TestNodeBudget:
    """A listed value past valgebra's node budget is refused before it is built."""

    @pytest.mark.parametrize(
        ("schema", "refused"),
        [
            ({"enum": list(range(50_000))}, "its enum of 50000 values spans 100001 nodes or more"),
            (
                {"enum": list(range(100_000))},
                "its enum of 100000 values spans 100001 nodes or more",
            ),
            ({"const": list(range(60_000))}, "its const spans 100002 nodes or more"),
        ],
    )
    def test_a_listed_value_past_the_budget_is_refused_unbuilt(
        self, schema: dict[str, Any], refused: str, monkeypatch: pytest.MonkeyPatch
    ):
        # An integer spells two nodes and the union one: 50,000 integers are 100,001, past
        # 100,000, which valgebra refused only after seconds of building them.
        built: list[object] = []
        monkeypatch.setattr(schema_module, "_constant", built.append)
        with pytest.raises(Unsupported, match=re.escape(refused)):
            compile_schema(schema)
        assert built == []

    def test_a_count_past_the_bound_is_read_exactly(self):
        # Counted at two nodes each, 50,000 fractions pass the limit; each spells one, so the
        # 50,001 nodes they span are held, and the bound refuses nothing the count holds.
        schema_module._within_budget("enum", [i + 0.5 for i in range(50_000)], union=True)
        assert schema_module._bounded(["mug", "box"], union=True)
        assert schema_module._bounded([list(range(50_000))], union=False)
        assert not schema_module._bounded([list(range(50_001))], union=False)
        with pytest.raises(Unsupported, match="100001 nodes or more"):
            schema_module._within_budget("enum", list(range(50_000)), union=True)

    def test_a_listed_value_within_the_budget_compiles_as_before(self):
        # 49,999 integers are 99,999 nodes, which valgebra holds.
        validator = compile_schema({"enum": list(range(49_999))})
        assert validator.is_valid(49_998)
        assert validator.is_valid(1.0)
        assert not validator.is_valid(49_999)


class TestLocated:
    """A failure names the keyword that made it, as JSON Schema's output names an error."""

    @staticmethod
    def _located(schema: object, value: object) -> list[tuple[object, object, object]]:
        compiler = Compiler(schema)
        with pytest.raises(ValidationError) as refused:
            compiler.compile(schema).validate(value)
        return [
            (named["path"], named.get("keyword"), named.get("keywordLocation"))
            for named in (compiler.located(failure, value) for failure in refused.value.errors)
        ]

    #: VJ-10's arm: a joint behind a reference, a mode one of two branches.
    ARM: ClassVar[dict[str, Any]] = {
        "type": "object",
        "properties": {
            "pos": {"$ref": "#/$defs/joint"},
            "mode": {"anyOf": [{"const": "a"}, {"type": "integer", "minimum": 3}]},
            "grip": {"$ref": "#/$defs/hand"},
            "never": False,
        },
        "$defs": {
            "joint": {"type": "number", "minimum": -1.5, "maximum": 1.5},
            "hand": {"$ref": "#/$defs/joint"},
        },
    }

    @pytest.mark.parametrize(
        ("value", "location", "holding"),
        [
            ({"pos": 9.0}, "/properties/pos/$ref/maximum", ("$defs", "joint")),
            ({"mode": 1}, "/properties/mode/anyOf/1/minimum", None),
            ({"grip": 9.0}, "/properties/grip/$ref/$ref/maximum", ("$defs", "joint")),
        ],
    )
    def test_the_schema_at_a_location_is_the_one_its_keyword_sits_in(
        self, value: object, location: str, holding: tuple[str, str] | None
    ):
        # A plain pointer walk stops at `$ref`; `at` resolves it as evaluation did, and gives the
        # object a failing keyword sits in, as python-jsonschema's `ValidationError.schema` does.
        compiler = Compiler(self.ARM)
        ((path, _, _),) = self._located(self.ARM, value)
        assert isinstance(path, tuple)
        assert location in [where for _, where in compiler.keywords_failed(value, path)]
        expected = (
            self.ARM["properties"]["mode"]["anyOf"][1]
            if holding is None
            else self.ARM[holding[0]][holding[1]]
        )
        assert compiler.at(location) is expected

    @pytest.mark.parametrize(
        ("schema", "value"),
        [
            ({"if": {"type": "string"}, "else": {"minimum": 5}}, 3),
            ({"oneOf": [{"type": "string"}, {"minimum": 5}]}, 3),
            ({"dependentSchemas": {"a": {"maxProperties": 1}}}, {"a": 1, "b": 2}),
            ({"prefixItems": [{"type": "null"}], "items": False}, [None, 1]),
            ({"properties": {"a": False, "b": {"allOf": [{"maximum": 0}]}}}, {"a": 1, "b": 1}),
            ({"$defs": {"n": {"type": "integer"}}, "items": {"$ref": "#/$defs/n"}}, ["x"]),
        ],
    )
    def test_every_location_a_failure_is_named_at_reads_back_to_its_keyword(
        self, schema: dict[str, Any], value: object
    ):
        compiler = Compiler(schema)
        with pytest.raises(ValidationError) as refused:
            compiler.compile(schema).validate(value)
        for failure in refused.value.errors:
            path = failure["path"]
            assert isinstance(path, tuple)
            for keyword, where in compiler.keywords_failed(value, path):
                held = compiler.at(where)
                assert held is False or (isinstance(held, dict) and keyword in held)

    def test_a_location_ending_on_a_subschema_gives_it_and_one_naming_nothing_is_refused(self):
        compiler = Compiler(self.ARM)
        assert compiler.at("/properties/never") is False
        assert compiler.at("") is self.ARM
        for nowhere in ("/properties/hand", "/$defs/joint/maximum/x", "/anyOf/0", "properties"):
            with pytest.raises(Unsupported):
                compiler.at(nowhere)

    def test_a_location_in_a_resource_with_an_absolute_uri_is_located_there_too(self):
        # A failure past a reference into a resource with an absolute `$id` carries the
        # dereferenced location, its canonical URI and a fragment (draft 2020-12, 12.3.2).
        joint = {"$id": "joint", "maximum": 1.5}
        schema = {
            "$id": "https://example.com/arm",
            "properties": {"pos": {"$ref": "joint"}, "a%b": {"maximum": 0}},
            "$defs": {"joint": joint},
        }
        compiler = Compiler(schema)
        with pytest.raises(ValidationError) as refused:
            compiler.compile(schema).validate({"pos": 2, "a%b": 1})
        located = {
            failure["path"]: compiler.located(failure, {"pos": 2, "a%b": 1})
            for failure in refused.value.errors
        }
        assert located[("pos",)]["keywordLocation"] == "/properties/pos/$ref/maximum"
        assert located[("pos",)]["absoluteKeywordLocation"] == "https://example.com/joint#/maximum"
        assert located[("a%b",)]["absoluteKeywordLocation"] == (
            "https://example.com/arm#/properties/a%25b/maximum"
        )
        assert "absoluteKeywordLocation" not in self._located_dict(self.ARM, {"pos": 9.0})

    def test_a_location_is_walked_once_a_compiler(self, monkeypatch: pytest.MonkeyPatch):
        # `located` and `at` read one walk of a location: what it reads is fixed for the
        # compiler's life.
        schema = {
            "$id": "https://example.com/arm",
            "properties": {"pos": {"$ref": "joint"}},
            "$defs": {"joint": {"$id": "joint", "maximum": 1.5}},
        }
        compiler = Compiler(schema)
        with pytest.raises(ValidationError) as refused:
            compiler.compile(schema).validate({"pos": 2})
        walks: list[str] = []
        walk = compiler._walk

        def counted(location: str) -> tuple[object, str | None]:
            walks.append(location)
            return walk(location)

        monkeypatch.setattr(compiler, "_walk", counted)
        failure = refused.value.errors[0]
        first, second = (compiler.located(failure, {"pos": 2}) for _ in range(2))
        assert first == second
        assert first["absoluteKeywordLocation"] == "https://example.com/joint#/maximum"
        assert compiler.at("/properties/pos/$ref/maximum") == {"$id": "joint", "maximum": 1.5}
        assert walks == ["/properties/pos/$ref/maximum"]

    @staticmethod
    def _located_dict(schema: object, value: object) -> dict[str, object]:
        compiler = Compiler(schema)
        with pytest.raises(ValidationError) as refused:
            compiler.compile(schema).validate(value)
        return compiler.located(refused.value.errors[0], value)

    @pytest.mark.parametrize("name", sorted(schema_module.LANGUAGES))
    def test_a_format_s_language_is_its_pattern_s_set_built_once(self, name: str):
        # Every compiler asserting the format holds the set its pattern builds, built once.
        built = Validator(Annotated[str, schema_module.Regex(schema_module.LANGUAGES[name])])
        assert schema_module._language(name) == built
        assert schema_module._language(name) is schema_module._language(name)

    def test_a_format_is_named_where_the_compiler_asserts_it(self):
        # Asserted, `format` refuses as any keyword does; read as an annotation, it refuses
        # nothing and names nothing.
        schema = {"type": "object", "properties": {"at": {"type": "string", "format": "date"}}}
        asserted = Compiler(schema, assert_format=True)
        assert asserted.keywords_failed({"at": "soon"}, ("at",)) == [
            ("format", "/properties/at/format")
        ]
        assert Compiler(schema).keywords_failed({"at": "soon"}, ("at",)) == []

    def test_a_location_is_a_json_pointer_a_walk_reads_back(self):
        # A pointer escapes `~` and `/` alone (RFC 6901, section 3), where a URI fragment also
        # percent-encodes: read as a fragment, `/properties/%41` would name the key `A`.
        name = "a%41/b~c"
        schema = {"properties": {name: {"maximum": 1}}}
        ((path, keyword, where),) = self._located(schema, {name: 2})
        assert (path, keyword, where) == ((name,), "maximum", "/properties/a%41~1b~0c/maximum")
        node: object = schema
        assert isinstance(where, str)
        for token in where.split("/")[1:]:
            assert isinstance(node, dict)
            node = node[token.replace("~1", "/").replace("~0", "~")]
        assert node == 1

    def test_a_bound_names_itself(self):
        assert self._located({"type": "integer", "minimum": 1}, 0) == [((), "minimum", "/minimum")]

    def test_a_value_of_the_wrong_kind_is_named_by_the_kind(self):
        # NaN is no JSON value, so every keyword refuses it; `type` pins the kind and is named.
        number = {"minimum": 0, "maximum": 100, "type": "number"}
        assert self._located(number, math.nan) == [((), "type", "/type")]
        assert self._located(number, "x") == [((), "type", "/type")]

    def test_a_listed_value_missed_is_named_by_the_list(self):
        assert self._located({"enum": ["a", "b"]}, "c") == [((), "enum", "/enum")]

    def test_a_location_runs_through_each_reference(self):
        schema = {
            "properties": {"a": {"$ref": "#/$defs/A"}},
            "$defs": {"A": {"type": "string", "maxLength": 2}},
        }
        assert self._located(schema, {"a": "xyz"}) == [
            (("a",), "maxLength", "/properties/a/$ref/maxLength")
        ]

    def test_an_element_is_named_by_its_place(self):
        schema = {"prefixItems": [{"type": "integer"}], "items": {"type": "string"}}
        assert self._located(schema, [1, 2, "c"]) == [((1,), "type", "/items/type")]

    def test_every_keyword_refusing_is_listed_and_a_path_no_keyword_reaches_names_none(self):
        compiler = Compiler({"type": "integer", "minimum": 1, "maximum": 0})
        assert compiler.keywords_failed(5, ()) == [("maximum", "/maximum")]
        assert compiler.keywords_failed(-1, ()) == [("minimum", "/minimum")]
        failure = {"path": ("nowhere",), "code": "int_type"}
        assert compiler.located(failure, 5) == failure

    @pytest.mark.parametrize(
        ("schema", "value", "refusing"),
        [
            # An `if` asserts nothing, and the branch it does not pick applies to nothing.
            ({"if": {"type": "string"}, "else": {"minimum": 5}}, 3, ["/else/minimum"]),
            (
                {"if": {"minimum": 0}, "then": {"maximum": 2}, "else": {"maximum": -5}},
                3,
                ["/then/maximum"],
            ),
            # A branch of an `anyOf` that holds fails nothing, beside the keyword that does.
            (
                {"anyOf": [{"type": "string"}, {"type": "integer"}], "$ref": "#/$defs/A"},
                3,
                ["/$ref/minimum"],
            ),
            # A `oneOf` two branches hold fails by itself, and the third by nothing.
            (
                {"oneOf": [{"type": "null"}, {"type": "integer"}, {"minimum": 0}]},
                3,
                ["/oneOf"],
            ),
            (
                {"oneOf": [{"type": "null"}, {"minimum": 5}]},
                3,
                ["/oneOf", "/oneOf/0/type", "/oneOf/1/minimum"],
            ),
            # A dependent schema applies where the object holds its key.
            (
                {"dependentSchemas": {"b": {"maxProperties": 0}}, "minProperties": 2},
                {"a": 1},
                ["/minProperties"],
            ),
            (
                {"dependentSchemas": {"a": {"maxProperties": 0}}},
                {"a": 1},
                ["/dependentSchemas/a/maxProperties"],
            ),
            # A keyword is named by its own refusal, and not by one it is read beside.
            (
                {
                    "properties": {"a": {"minimum": 5}},
                    "additionalProperties": False,
                    "minProperties": 2,
                },
                {"a": 3},
                ["/minProperties", "/properties"],
            ),
            ({"prefixItems": [{"type": "null"}], "items": False}, [1], ["/prefixItems"]),
        ],
    )
    def test_a_failure_is_named_by_the_keywords_that_fail(self, schema, value, refusing):
        compiler = Compiler({**schema, "$defs": {"A": {"minimum": 5}}})
        assert [where for _, where in compiler.keywords_failed(value, ())] == refusing

    def test_a_dependent_key_is_asked_for_by_the_key_the_object_holds(self):
        compiler = Compiler({"dependentRequired": {"b": ["a"]}, "required": ["a"]})
        assert compiler.keywords_failed({}, ("a",)) == [("required", "/required")]
        assert compiler.keywords_failed({"b": 1}, ("a",)) == [
            ("required", "/required"),
            ("dependentRequired", "/dependentRequired"),
        ]

    def test_a_reference_is_resolved_against_the_base_around_it(self):
        inner = {"$id": "http://x/a", "$ref": "#/$defs/S", "$defs": {"S": {"minimum": 5}}}
        compiler = Compiler({"properties": {"a": inner}})
        assert compiler.keywords_failed({"a": 3}, ("a",)) == [
            ("minimum", "/properties/a/$ref/minimum")
        ]

    @pytest.mark.parametrize(
        ("schema", "value", "path", "keyword", "where"),
        [
            ({"required": ["a"]}, {}, ("a",), "required", "/required"),
            (
                {"dependentRequired": {"b": ["a"]}},
                {"b": 1},
                ("a",),
                "dependentRequired",
                "/dependentRequired",
            ),
            (
                {"propertyNames": {"enum": ["a"]}},
                {"b": 1},
                ("b",),
                "propertyNames",
                "/propertyNames",
            ),
            (
                {"additionalProperties": False},
                {"b": 1},
                ("b",),
                "additionalProperties",
                "/additionalProperties",
            ),
            (
                {"unevaluatedProperties": False},
                {"b": 1},
                ("b",),
                "unevaluatedProperties",
                "/unevaluatedProperties",
            ),
            ({"properties": {"a": False}}, {"a": 1}, ("a",), "properties", "/properties/a"),
            ({"items": {"type": "string"}, "minItems": 2}, [1], (), "minItems", "/minItems"),
        ],
    )
    def test_a_key_or_an_item_refused_is_named_by_the_keyword_refusing_it(
        self, schema, value, path, keyword, where
    ):
        assert (path, keyword, where) in self._located(schema, value)


class TestLength:
    """A sized schema that is a length range alone reads as one, beside `interval`."""

    @pytest.mark.parametrize(
        ("schema", "expected"),
        [
            ({"type": "string", "minLength": 2, "maxLength": 5}, Length("string", 2, 5)),
            ({"type": "array", "maxItems": 3}, Length("array", 0, 3)),
            ({"type": "object", "minProperties": 1.0}, Length("object", 1, None)),
            ({"type": "string", "description": "a name"}, Length("string", 0, None)),
        ],
    )
    def test_a_kind_and_its_length_bounds_are_a_length(self, schema, expected):
        assert length(schema) == expected

    @pytest.mark.parametrize(
        "schema",
        [
            {"type": "string", "minLength": 2, "pattern": "^a"},
            {"type": ["string", "null"], "maxLength": 2},
            {"type": "array", "minLength": 2},
            {"type": "string", "maxLength": -1},
            {"type": "integer", "minimum": 0},
            True,
        ],
    )
    def test_anything_else_is_no_length(self, schema):
        assert length(schema) is None

    def test_a_length_holds_what_the_schema_holds(self):
        schema = {"type": "string", "minLength": 2, "maxLength": 3}
        read = length(schema)
        assert read is not None
        compiled = compile_schema(schema)
        for text in ("", "a", "ab", "abc", "abcd", "\U0001f600\U0001f600"):
            within = read.least <= len(text) <= (read.most if read.most is not None else len(text))
            assert compiled.is_valid(text) == within, text


#: Each order bound, the bound written and the order a number within it holds.
ORDER_BOUNDS: dict[str, tuple[float, Callable[[Any, Any], bool]]] = {
    "minimum": (1, operator.ge),
    "exclusiveMinimum": (1, operator.gt),
    "maximum": (4, operator.le),
    "exclusiveMaximum": (4, operator.lt),
}

#: Values on each side of both bounds, a number past every bound, and one of each other kind.
AROUND_THE_BOUNDS = [
    *(0, 1, 1.0, 1.5, 2, 4, 4.0, 4.5, 5, -(10**30), 10**30, math.inf, -math.inf, math.nan),
    *(True, False, None, "x", [], {}),
]


class TestOrderBounds:
    """The order bounds of one object are one set: the numbers within every one of them."""

    @pytest.mark.parametrize("typed", [False, True])
    @pytest.mark.parametrize(
        "keys", [keys for n in range(1, 5) for keys in itertools.combinations(ORDER_BOUNDS, n)]
    )
    def test_a_number_lies_within_every_bound_the_object_writes(self, keys, typed):
        schema: dict[str, Any] = {key: ORDER_BOUNDS[key][0] for key in keys}
        compiled = compile_schema({**schema, "type": "number"} if typed else schema)
        for value in AROUND_THE_BOUNDS:
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                expected = all(ORDER_BOUNDS[key][1](value, ORDER_BOUNDS[key][0]) for key in keys)
            else:
                expected = not typed
            assert compiled.is_valid(value) == expected, value

    @pytest.mark.parametrize("bound", [sys.float_info.max, 10**309])
    def test_a_number_below_the_numbers_under_a_bound_is_refuted(self, bound):
        # The kind beside the bounds offers `inf`, which refutes it where an integer past a
        # bound of more than 1,024 bits is one valgebra does not build.
        under = compile_schema({"type": "number", "minimum": -bound, "maximum": bound})
        number = compile_schema({"type": "number"})
        assert number.relation_to(under) == "not_subset"
        assert under.relation_to(number) == "subset"

    @pytest.mark.parametrize(
        ("narrow", "wide"),
        [
            ({"type": "integer", "minimum": 2**121 + 1}, {"type": "integer", "minimum": 2**121}),
            ({"type": "number", "maximum": 1e100}, {"type": "number", "maximum": 1e200}),
            ({"maximum": 1e100}, {"maximum": 1e101}),
            ({"type": "integer", "maximum": 1e100}, {"type": "number", "maximum": 1e100}),
            ({"type": "integer", "maximum": sys.float_info.max}, {"type": "integer"}),
        ],
    )
    def test_two_bounds_past_2_to_the_120_are_decided_both_ways(self, narrow, wide):
        assert compile_schema(narrow).relation_to(compile_schema(wide)) == "subset"
        assert compile_schema(wide).relation_to(compile_schema(narrow)) == "not_subset"
