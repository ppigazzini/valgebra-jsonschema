"""An MCP tool's contract: what it takes and what it returns, as sets.

A server lists each tool with an ``inputSchema``, the arguments object, and optionally an
``outputSchema``. Both are JSON Schema in the dialect their ``$schema`` names, 2020-12 where
it names none, and the protocol has an unsupported dialect fail, which `compile_schema` does.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from valgebra_jsonschema._valgebra import Validator
from valgebra_jsonschema.schema import (
    ANNOTATIONS,
    Compiler,
    Unsupported,
    compile_schema,
    older,
    upgrade,
)


@dataclass(frozen=True, slots=True)
class Tool:
    """A tool's two contracts. A tool with no ``outputSchema`` promises no structure."""

    name: str
    arguments: Validator[Any]
    result: Validator[Any] | None


def _names_an_object(schema: object) -> bool:
    """Return whether a root schema is an object schema, following bare references.

    The protocol has ``inputSchema`` state ``type: "object"``. A root that is a bare ``$ref``
    names one, as a generated schema's named root does, so it holds there.
    """
    draft = older(schema)
    root = upgrade(schema, draft) if draft is not None else schema
    here = root
    for _ in range(8):
        if not (isinstance(here, dict) and "$ref" in here):
            break
        if set(here) - ANNOTATIONS - {"$ref", "$id", "$defs", "definitions"}:
            return False
        here = Compiler(root).resolve(here["$ref"])
    return isinstance(here, dict) and here.get("type") in ("object", ["object"])


def read_tool(spec: Mapping[str, Any]) -> Tool:
    """Read one entry of a server's tool list into its two contracts.

    Raises `Unsupported` for an ``inputSchema`` that is missing or names no object, and for
    anything `compile_schema` refuses, and `UnsupportedDialect` for a dialect it does not read.
    """
    name = spec.get("name")
    if not isinstance(name, str):
        msg = f"a tool's name is a string, and this one is {name!r:.60}"
        raise Unsupported(msg)
    if "inputSchema" not in spec:
        msg = f"tool {name!r} has no inputSchema"
        raise Unsupported(msg)
    arguments = compile_schema(spec["inputSchema"])
    if not _names_an_object(spec["inputSchema"]):
        msg = f"tool {name!r} has an inputSchema that names no object"
        raise Unsupported(msg)
    output = spec.get("outputSchema")
    return Tool(name, arguments, None if output is None else compile_schema(output))
