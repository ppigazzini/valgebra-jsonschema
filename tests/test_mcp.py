"""What the Model Context Protocol asks of a schema reader, and what its authors emit."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Literal, Optional

import pytest
from pydantic import BaseModel, Field

from valgebra_jsonschema import (
    Unsupported,
    UnsupportedDialect,
    compile_schema,
    read_tool,
)


class TestDialects:
    @pytest.mark.parametrize(
        "uri",
        [
            "http://json-schema.org/draft-03/schema#",
            "https://example.com/my-dialect",
            "https://json-schema.org/draft/2019-09/hyper-schema",
        ],
    )
    def test_an_unsupported_dialect_fails_saying_so(self, uri):
        with pytest.raises(UnsupportedDialect, match="this dialect is not supported"):
            compile_schema({"$schema": uri, "type": "object"})

    def test_a_dialect_error_is_a_refusal_a_caller_already_catches(self):
        assert issubclass(UnsupportedDialect, Unsupported)

    def test_no_schema_keyword_is_draft_2020_12(self):
        # `prefixItems` asserts in 2020-12, and an array `items` is refused there.
        tuple_of_one = compile_schema({"prefixItems": [{"type": "string"}]})
        assert not tuple_of_one.is_valid([1])
        with pytest.raises(Unsupported):
            compile_schema({"items": [{"type": "string"}]})

    def test_draft_07_is_the_spec_s_example_of_a_declared_dialect(self):
        declared = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "items": [{"type": "string"}],
        }
        assert not compile_schema(declared).is_valid([1])
        assert compile_schema(declared).is_valid(["a", 1])

    @pytest.mark.parametrize("end", ["", "#"])
    def test_draft_2019_09_reads_its_own_words(self, end):
        uri = f"https://json-schema.org/draft/2019-09/schema{end}"
        array = {"$schema": uri, "items": [{"type": "string"}], "additionalItems": False}
        assert compile_schema(array).is_valid(["a"])
        assert not compile_schema(array).is_valid(["a", 1])
        recursive = {
            "$schema": uri,
            "$recursiveAnchor": True,
            "type": "object",
            "properties": {"next": {"$recursiveRef": "#"}},
            "additionalProperties": False,
        }
        assert compile_schema(recursive).is_valid({"next": {"next": {}}})
        assert not compile_schema(recursive).is_valid({"next": {"other": 1}})
        # A `$ref` keeps its siblings from 2019-09 on, where draft-07 drops them.
        sibling = {
            "$schema": uri,
            "$defs": {"a": {"type": "integer"}},
            "$ref": "#/$defs/a",
            "minimum": 3,
        }
        assert not compile_schema(sibling).is_valid(2)
        assert compile_schema(sibling).is_valid(3)

    def test_a_recursive_reference_elsewhere_is_refused(self):
        uri = "https://json-schema.org/draft/2019-09/schema"
        with pytest.raises(Unsupported, match="recursiveRef"):
            compile_schema({"$schema": uri, "$recursiveRef": "other"})

    def test_a_network_reference_is_not_dereferenced(self):
        with pytest.raises(Unsupported, match=r"\$ref"):
            compile_schema({"$ref": "https://example.com/schema.json"})


_ARGUMENTS = {
    "type": "object",
    "properties": {"location": {"type": "string"}},
    "required": ["location"],
}


class TestTool:
    def test_a_tool_reads_as_its_two_contracts(self):
        tool = read_tool(
            {
                "name": "get_weather",
                "inputSchema": _ARGUMENTS,
                "outputSchema": {"type": "number"},
            }
        )
        assert tool.name == "get_weather"
        assert tool.arguments.is_valid({"location": "Paris"})
        assert not tool.arguments.is_valid({})
        assert tool.result is not None
        assert tool.result.is_valid(21.5)
        assert not tool.result.is_valid("warm")

    def test_an_output_schema_is_optional_and_may_be_any_schema(self):
        assert read_tool({"name": "t", "inputSchema": _ARGUMENTS}).result is None
        listed = read_tool(
            {"name": "t", "inputSchema": _ARGUMENTS, "outputSchema": {"type": "array"}}
        )
        assert listed.result is not None
        assert listed.result.is_valid([])

    def test_a_tool_with_no_parameters_is_an_object_schema(self):
        none = read_tool(
            {"name": "t", "inputSchema": {"type": "object", "additionalProperties": False}}
        )
        assert none.arguments.is_valid({})
        assert not none.arguments.is_valid({"a": 1})

    @pytest.mark.parametrize(
        "spec",
        [
            {"name": "t"},
            {"name": "t", "inputSchema": {"type": "string"}},
            {"name": "t", "inputSchema": True},
            {"inputSchema": {"type": "object"}},
        ],
    )
    def test_a_tool_that_names_no_object_is_refused(self, spec):
        with pytest.raises(Unsupported):
            read_tool(spec)

    def test_a_named_root_names_an_object(self):
        # zod's named schema: a draft-07 document whose root is a bare reference.
        named = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$ref": "#/definitions/Args",
            "definitions": {"Args": {"type": "object", "required": ["a"]}},
        }
        tool = read_tool({"name": "t", "inputSchema": named})
        assert tool.arguments.is_valid({"a": 1})
        assert not tool.arguments.is_valid({})

    def test_an_unsupported_dialect_in_either_contract_fails(self):
        wrong = {"$schema": "https://example.com/mine", "type": "object"}
        with pytest.raises(UnsupportedDialect):
            read_tool({"name": "t", "inputSchema": wrong})
        with pytest.raises(UnsupportedDialect):
            read_tool({"name": "t", "inputSchema": _ARGUMENTS, "outputSchema": wrong})


class Address(BaseModel):
    city: str = Field(min_length=1)
    tags: set[str] = Field(default_factory=set)


class Order(BaseModel):
    id: uuid.UUID
    placed: dt.datetime
    status: Literal["open", "closed"]
    total: float = Field(ge=0)
    quantity: int = Field(ge=1, le=100)
    note: Optional[str] = None  # noqa: UP045 - the spelling pydantic emits a null branch for
    address: Address
    parent: Optional[Order] = None  # noqa: UP045 - a recursion through `$defs`


def _order(**changes):
    value = {
        "id": "7f8a1f50-0000-4000-8000-000000000000",
        "placed": "2026-01-02T03:04:05Z",
        "status": "open",
        "total": 1.5,
        "quantity": 2,
        "address": {"city": "Paris", "tags": ["a"]},
    }
    return {**value, **changes}


class TestWhatPydanticEmits:
    """What the Python SDK and FastMCP emit for a tool, read as it is written."""

    def test_the_model_compiles_and_agrees_with_the_model(self):
        emitted = Order.model_json_schema()
        compiled = compile_schema(emitted)
        for good in (_order(), _order(note=None), _order(note="x"), _order(parent=_order())):
            assert Order.model_validate(good)
            assert compiled.is_valid(good), good
        for bad in (
            _order(status="other"),
            _order(total=-1),
            _order(quantity=0),
            _order(quantity=101),
            _order(note=1),
            _order(address={"city": ""}),
            _order(parent={"id": "x"}),
        ):
            with pytest.raises(ValueError, match="validation error"):
                Order.model_validate(bad)
            assert not compiled.is_valid(bad), bad

    def test_format_is_an_annotation_the_default_leaves_unread(self):
        compiled = compile_schema(Order.model_json_schema())
        assert compiled.is_valid(_order(id="not a uuid"))
