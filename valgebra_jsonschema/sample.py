"""Draw JSON values from a JSON Schema: the witnesses that prove a cell inhabited.

valgebra proves emptiness and refutes inclusion, but names no value. A cell it cannot
prove empty may still hold nothing, so a cell counts as inhabited only when a concrete
value is found in it. This module proposes candidates; membership in the compiled set is
the only judge, so a wrong proposal costs a rejection, never a wrong proof.

The generator covers the keywords it can construct values for directly and falls back to
rejection elsewhere: ``not``, ``if`` and an unsatisfiable mix yield nothing. A conjunction is
merged keyword by keyword before a value is drawn, an ``allOf`` with the schema around it, an
``anyOf`` or ``oneOf`` branch with its siblings, a reference's target with the keywords beside
it: and-elimination over a conjunction of one kind, so that a required key's member is drawn
under every constraint on that key (Attouche et al. 2022, §4, §6.3.2).
"""

from __future__ import annotations

import math
import random
import re
import string
from collections.abc import Mapping
from typing import Any

from valgebra_jsonschema.schema import Compiler, Unsupported, compile_with_fallbacks, json_key

_ALPHABET = string.ascii_letters + string.digits + "_-@."
#: The longest string and list a draw builds. Generated schemas bound lengths by 2**31 - 1,
#: and a draw that long costs gigabytes; deciding a cell needs no such value.
_LONGEST_STRING = 4096
_LONGEST_LIST = 16


class Sampler:
    """Draw candidate values for the schemas of one document, from one seeded stream."""

    def __init__(
        self,
        root: object,
        rng: random.Random,
        *,
        depth: int = 4,
        documents: Mapping[str, object] | None = None,
    ) -> None:
        self.root = root
        self.rng = rng
        self.depth = depth
        #: The documents a reference may name beside the root, as `compile_schema` takes them.
        self.documents = documents
        self.compiler = Compiler(root, documents=documents)

    def draw(self, schema: object, tries: int = 40) -> list[Any]:
        """Return up to ``tries`` distinct candidates that the compiled schema admits."""
        # A schema past valgebra's limit reads by predicate, as `compile_schema` has it.
        self.compiler, target = compile_with_fallbacks(self.root, schema, documents=self.documents)
        found: list[Any] = []
        seen: set[str] = set()
        for _ in range(tries):
            value = self._value(schema, self.depth)
            key = repr(value)
            if key not in seen and target.is_valid(value):
                seen.add(key)
                found.append(value)
        return found

    def _value(self, schema: object, depth: int) -> Any:  # noqa: C901, PLR0911, PLR0912
        rng = self.rng
        if schema is True or not isinstance(schema, dict):
            return rng.choice([None, True, 0, 1.5, "a", [], {}])
        if isinstance(schema.get("$ref"), str) and schema["$ref"].startswith("#/"):
            try:
                node = self.compiler.resolve(schema["$ref"])
            except Unsupported:
                return None
            beside = {k: v for k, v in schema.items() if k != "$ref"}
            return self._value(_conjoin(node, beside), depth - 1) if depth > 0 else None
        if "const" in schema:
            return schema["const"]
        if "enum" in schema:
            return rng.choice(schema["enum"]) if schema["enum"] else None
        for key in ("anyOf", "oneOf"):
            if isinstance(schema.get(key), list) and schema[key]:
                beside = {k: v for k, v in schema.items() if k != key}
                return self._value(_conjoin(beside, rng.choice(schema[key])), depth)
        if isinstance(schema.get("allOf"), list):
            merged: object = {k: v for k, v in schema.items() if k != "allOf"}
            for sub in schema["allOf"]:
                merged = _conjoin(merged, sub)
            return self._value(merged, depth)
        kinds = schema.get("type", _kind_of(schema))
        if isinstance(kinds, list) and not kinds:
            # Members naming no kind in common: the conjunction is empty, and nothing is drawn.
            return None
        kind = rng.choice(kinds) if isinstance(kinds, list) else kinds
        if kind == "null":
            return None
        if kind == "boolean":
            return rng.random() < 0.5  # noqa: PLR2004
        if kind in {"integer", "number"}:
            return self._number(schema, integer=kind == "integer")
        if kind == "string":
            return self._string(schema)
        if kind == "array":
            return self._array(schema, depth)
        if kind == "object":
            return self._object(schema, depth)
        return None

    def _number(self, schema: dict[str, Any], *, integer: bool) -> int | float:
        low = _finite(schema.get("minimum", schema.get("exclusiveMinimum")), -1000)
        high = _finite(schema.get("maximum", schema.get("exclusiveMaximum")), 1000)
        if "exclusiveMinimum" in schema:
            low += 1
        if "exclusiveMaximum" in schema:
            high -= 1
        low, high = int(low), max(int(low), int(high))
        value = self.rng.randint(low, high)
        step = schema.get("multipleOf")
        if isinstance(step, int) and step > 0:
            value -= value % step
        if integer or self.rng.random() < 0.5:  # noqa: PLR2004
            return value
        # Past the float range an integer has no non-integral neighbor to draw.
        return value + 0.5 if abs(value) < 2**1023 else value

    def _string(self, schema: dict[str, Any]) -> str:
        low = int(schema.get("minLength", 0))
        if low > _LONGEST_STRING:
            return ""
        high = min(max(low, int(schema.get("maxLength", low + 8))), low + _LONGEST_STRING)
        n = self.rng.randint(low, high)
        text = "".join(self.rng.choice(_ALPHABET) for _ in range(n))
        if "pattern" in schema:
            text = _from_pattern(schema["pattern"], self.rng) or text
        return text

    def _array(self, schema: dict[str, Any], depth: int) -> list[Any]:
        prefix = schema.get("prefixItems", [])
        low = int(schema.get("minItems", 0))
        if low > _LONGEST_LIST:
            return []
        high = min(max(low, int(schema.get("maxItems", low + 3))), low + _LONGEST_LIST)
        n = self.rng.randint(low, high) if depth > 0 else low
        items = schema.get("items", True)
        return [self._value(prefix[i] if i < len(prefix) else items, depth - 1) for i in range(n)]

    def _object(self, schema: dict[str, Any], depth: int) -> dict[str, Any]:
        """Draw an object: a member for each required key, and some of the others declared.

        A required key that ``properties`` does not name takes ``additionalProperties``, as
        the compiler reads it: an object is built member by member until every requirement
        holds, each member under the constraints on its key (Attouche et al. 2022, §6.3.1).
        """
        props: dict[str, Any] = schema.get("properties", {})
        required = [key for key in schema.get("required", []) if isinstance(key, str)]
        out: dict[str, Any] = {}
        for key, sub in props.items():
            if key in required or (depth > 0 and self.rng.random() < 0.5):  # noqa: PLR2004
                out[key] = self._value(sub, depth - 1)
        for key in required:
            if key not in out:
                out[key] = self._value(schema.get("additionalProperties", True), depth - 1)
        return out


#: What a schema with no ``type`` is drawn as, from the keywords of one kind it holds.
_OF_KIND = (
    ("object", frozenset({"properties", "required", "additionalProperties", "minProperties"})),
    ("array", frozenset({"items", "prefixItems", "minItems", "contains"})),
)
#: The keywords a conjunction keeps the tighter of, lower bounds and upper bounds.
_LOWER = frozenset({"minimum", "exclusiveMinimum", "minLength", "minItems", "minProperties"})
_UPPER = frozenset({"maximum", "exclusiveMaximum", "maxLength", "maxItems", "maxProperties"})
#: The keywords whose subschemas a conjunction meets, each under an `allOf`.
_SUBSCHEMA = frozenset({"items", "additionalProperties", "contains", "propertyNames", "not"})


def _kind_of(schema: dict[str, Any]) -> list[str]:
    """Return the kinds a schema naming no ``type`` is drawn as.

    Each scalar kind, which a keyword of another kind passes, and the container kind its
    keywords read, whose values exercise them.
    """
    scalars = ["null", "boolean", "integer", "number", "string"]
    return scalars + [kind for kind, keywords in _OF_KIND if keywords & schema.keys()][:1]


def _conjoin(first: object, second: object) -> object:
    """Return one schema holding the values both hold, merged where the sampler reads it.

    ``properties`` meet key by key, ``required`` unite, ``type`` keeps the kinds both name, a
    bound keeps the tighter, ``enum`` keeps the values both list under JSON's equality, and a
    subschema both hold is their ``allOf``; any other keyword keeps the first's, and membership
    judges what is drawn.
    """
    if first is False or second is False:
        return False
    if not isinstance(first, dict):
        return second if isinstance(second, dict) else first
    if not isinstance(second, dict):
        return first
    out = dict(first)
    for key, value in second.items():
        out[key] = value if key not in out else _met(key, out[key], value)
    return out


def _met(key: str, mine: Any, theirs: Any) -> Any:  # noqa: PLR0911
    """Return the value of keyword ``key`` holding what both its values hold, or ``mine``."""
    if key == "type":
        return _kinds(mine, theirs)
    if key in _SUBSCHEMA:
        return _both(mine, theirs)
    if key in _LOWER | _UPPER:
        if not (_is_number(mine) and _is_number(theirs)):
            return mine
        return max(mine, theirs) if key in _LOWER else min(mine, theirs)
    if isinstance(mine, dict) and isinstance(theirs, dict) and key == "properties":
        return {k: _both(mine.get(k), theirs.get(k)) for k in {**mine, **theirs}}
    if not (isinstance(mine, list) and isinstance(theirs, list)):
        return mine
    if key == "required":
        return list(dict.fromkeys([*mine, *theirs]))
    if key == "enum":
        listed = {json_key(v) for v in theirs}
        return [v for v in mine if json_key(v) in listed]
    return [*mine, *theirs] if key == "allOf" else mine


def _both(first: object, second: object) -> object:
    """Return the conjunction of two subschemas, either of them absent."""
    if first is None:
        return second
    if second is None:
        return first
    return {"allOf": [first, second]}


def _kinds(first: object, second: object) -> list[str]:
    """Return the kinds two ``type`` keywords both admit, an integer being a number."""
    a = set(first) if isinstance(first, list) else {first}
    b = set(second) if isinstance(second, list) else {second}
    met = a & b
    if {"integer", "number"} <= a | b and ("integer" in a or "integer" in b):
        met |= {"integer"} if "number" in a | b else set()
    return sorted(k for k in met if isinstance(k, str))


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite(bound: object, default: int) -> float:
    """Return a numeric bound, or ``default`` for none or one past the float range."""
    if isinstance(bound, bool) or not isinstance(bound, (int, float)):
        return default
    if isinstance(bound, float) and not math.isfinite(bound):
        return default
    return bound


def _from_pattern(pattern: str, rng: random.Random) -> str | None:
    r"""Build a string matching ``pattern``, or None where it holds what is not read here.

    A sequence of literals, classes and escapes is read by `_flat_pattern`, whose open-ended
    counts sometimes run long. A pattern holding a group, an alternation or ``.`` is read as
    alternatives of sequences, groups, ``(?:...)`` and the counts ``+``, ``*``, ``?``,
    ``{m}``, ``{m,}`` and ``{m,n}``, each count short: a long one builds a string Python's
    `re`, the reference readers use, may take time exponential in to read, through a nested or
    overlapping count, and a length bound elsewhere is served by a flat pattern's long run. An
    anchor and a word boundary are read as nothing; a lookaround, a backreference or a
    property escape leaves the caller's fallback, and membership decides either way.
    """
    flat = _flat_pattern(pattern, rng)
    if flat is not None:
        return flat
    try:
        branches, end = _alternation(pattern, 0)
    except _UnreadError:
        return None
    if end != len(pattern):
        return None
    out: list[str] = []
    _emit(rng.choice(branches), rng, out)
    return "".join(out)


def _flat_pattern(pattern: str, rng: random.Random) -> str | None:
    r"""Build a string for a pattern of literals, classes and escapes, or None.

    Covers an anchored sequence of literals, character classes and ``\\d``/``\\w`` with
    ``+``, ``*``, ``?`` and ``{m}``/``{m,n}`` counts. A group, an alternation or ``.`` is
    left to `_from_pattern`.
    """
    body = pattern.removeprefix("^").removesuffix("$")
    out: list[str] = []
    i = 0
    while i < len(body):
        ch = body[i]
        if ch == "\\" and i + 1 < len(body):
            pool = _ESCAPES.get(body[i + 1], body[i + 1])
            i += 2
        elif ch == "[":
            end = body.find("]", i)
            if end < 0:
                return None
            pool = _expand_class(body[i + 1 : end])
            i = end + 1
        elif ch in "()|.":
            return None
        else:
            pool = ch
            i += 1
        low, high, i = _count(body, i, rng)
        out.extend(rng.choice(pool) for _ in range(rng.randint(low, high)))
    return "".join(out)


class _UnreadError(Exception):
    """A construct the pattern generator does not read."""


#: A parsed pattern: alternatives, each a sequence of an atom and its count.
_Sequence = list[tuple[Any, int, int]]


def _alternation(pattern: str, i: int) -> tuple[list[_Sequence], int]:
    """Return the alternatives from ``pattern[i]``, and where they end."""
    branches = []
    sequence, i = _sequence(pattern, i)
    branches.append(sequence)
    while i < len(pattern) and pattern[i] == "|":
        sequence, i = _sequence(pattern, i + 1)
        branches.append(sequence)
    return branches, i


def _sequence(pattern: str, i: int) -> tuple[_Sequence, int]:
    items: _Sequence = []
    while i < len(pattern) and pattern[i] not in "|)":
        if pattern[i] in "^$":
            i += 1
            continue
        atom, i = _atom(pattern, i)
        low, high, i = _count(pattern, i)
        if i < len(pattern) and pattern[i] == "?":
            i += 1  # a lazy count draws as the greedy one does
        items.append((atom, low, high))
    return items, i


def _atom(pattern: str, i: int) -> tuple[str | list[_Sequence], int]:
    """Return the atom at ``pattern[i]``, characters to draw one of or a group, and its end."""
    ch = pattern[i]
    if ch == "(":
        start = i + 3 if pattern.startswith("(?:", i) else i + 1
        if pattern.startswith("(?", i) and start == i + 1:
            raise _UnreadError
        group, i = _alternation(pattern, start)
        if i >= len(pattern) or pattern[i] != ")":
            raise _UnreadError
        return group, i + 1
    if ch == "\\":
        if i + 1 >= len(pattern) or pattern[i + 1] in "123456789pPuxck":
            raise _UnreadError
        escaped = pattern[i + 1]
        return ("" if escaped in "bB" else _ESCAPES.get(escaped, escaped)), i + 2
    if ch == "[":
        close = pattern.find("]", i + 2 if pattern.startswith("[]", i) else i + 1)
        if close < 0:
            raise _UnreadError
        return _expand_class(pattern[i + 1 : close]), close + 1
    if ch in "*+?":
        raise _UnreadError
    return (_PRINTABLE if ch == "." else ch), i + 1


def _emit(sequence: _Sequence, rng: random.Random, out: list[str]) -> None:
    """Append a string of ``sequence`` to ``out``, no longer than `_LONGEST_STRING`."""
    for atom, low, high in sequence:
        for _ in range(rng.randint(low, high)):
            if len(out) >= _LONGEST_STRING:
                return
            if isinstance(atom, list):
                _emit(rng.choice(atom), rng, out)
            elif isinstance(atom, str) and atom:
                out.append(rng.choice(atom))


_PRINTABLE = string.ascii_letters + string.digits + "_-.@!~+"
_ESCAPES = {"d": string.digits, "w": string.ascii_letters + string.digits + "_", "s": " \t"}


def _expand_class(spec: str) -> str:
    """Return the characters a bracket class admits, from a printable stock for ``[^...]``."""
    negated = spec.startswith("^")
    body = spec[1:] if negated else spec
    chars: list[str] = []
    j = 0
    while j < len(body):
        if body[j] == "\\" and j + 1 < len(body):
            chars.extend(_ESCAPES.get(body[j + 1], body[j + 1]))
            j += 2
        elif j + 2 < len(body) and body[j + 1] == "-":
            chars.extend(chr(c) for c in range(ord(body[j]), ord(body[j + 2]) + 1))
            j += 3
        else:
            chars.append(body[j])
            j += 1
    if negated:
        return "".join(c for c in _PRINTABLE if c not in chars) or "a"
    return "".join(chars) or "a"


def _count(body: str, i: int, rng: random.Random | None = None) -> tuple[int, int, int]:
    """Return the repeat range at ``body[i]`` and the index after it.

    An open-ended repeat is usually short and sometimes long, so that cells carved out by a
    length bound elsewhere -- an e-mail address longer than a subject may be -- get drawn.
    """
    if i < len(body) and body[i] in "+*?":
        if body[i] != "?" and rng is not None and rng.random() < 0.2:  # noqa: PLR2004
            return (*rng.choice([(130, 130), (210, 210)]), i + 1)
        return {"+": (1, 4), "*": (0, 4), "?": (0, 1)}[body[i]] + (i + 1,)
    count = _COUNT.match(body, i)
    if count is not None:
        low = int(count[1])
        high = int(count[3]) if count[3] else low + 3 if count[2] else low
        return low, high, count.end()
    return 1, 1, i


#: A repeat count, ``{m}``, ``{m,}`` or ``{m,n}``. Any other ``{`` is a literal brace.
_COUNT = re.compile(r"\{([0-9]+)(,([0-9]*))?\}")
