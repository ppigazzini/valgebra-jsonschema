"""The study files: the counts the repository publishes, and the check that reads them back.

A study is written by a tool with ``--json`` and read back by the same tool with
``--check``, which reruns the measurement and requires the same counts. It is a wire
format between two versions of this code, so its shape is declared once, here, as closed
records checked by valgebra: a key the format does not name is a defect, and every
failure is reported at once with its path.
"""

from __future__ import annotations

import json
from typing import Annotated, Literal, TypeVar

from annotated_types import Ge
from typing_extensions import TypedDict

from valgebra_jsonschema._valgebra import NOT_BOOL, ValidationError, Validator

Count = Annotated[int, NOT_BOOL, Ge(0)]

T = TypeVar("T")


class SuiteFile(TypedDict, closed=True):
    """Outcomes of one file of the JSON-Schema-Test-Suite."""

    file: str
    passed: Count
    failed: Count
    skipped: Count
    opaque: Count


class SuiteStudy(TypedDict, closed=True):
    """The compiler against the official suite for one draft, per file."""

    format: Literal[1]
    draft: Literal["2020-12", "7", "6", "4"]
    suite_commit: str
    files: list[SuiteFile]


class CorpusSubset(TypedDict, closed=True):
    """The compiler on one subset of a corpus of real-world schemas."""

    subset: str
    schemas: Count
    compiled: Count
    refused: Count
    crashed: Count
    timed_out: Count
    values: Count
    disagreed: Count


class Refusal(TypedDict, closed=True):
    """How many schemas of a corpus the compiler refuses for one reason."""

    reason: str
    schemas: Count


class CorpusStudy(TypedDict, closed=True):
    """The compiler on a corpus of real-world schemas, fetched at a pinned commit."""

    format: Literal[1]
    corpus: str
    commit: str
    subsets: list[CorpusSubset]
    refusals: list[Refusal]


class ContainmentRow(TypedDict, closed=True):
    """valgebra's answers on one category of a draft of the containment test suite.

    Each pair labels one direction or both; a question is one labeled direction.
    """

    draft: Literal["2020-12", "7", "6", "4"]
    category: str
    questions: Count
    refused: Count
    timed_out: Count
    proven: Count
    refuted: Count
    undecided: Count
    proven_against: Count
    refuted_against: Count


class ContainmentStudy(TypedDict, closed=True):
    """Inclusions between pairs of schemas, against a suite's labels, at a pinned commit."""

    format: Literal[1]
    suite: str
    commit: str
    rows: list[ContainmentRow]


class StudyError(ValueError):
    """A study file that is malformed or contradicts itself."""


SUITE = Validator(SuiteStudy)
CORPUS = Validator(CorpusStudy)
CONTAINMENT = Validator(ContainmentStudy)


def _load(schema: Validator[T], text: str) -> T:
    try:
        return schema.load(text)
    except ValidationError as exc:
        raise StudyError(str(exc)) from exc


def load_suite(text: str) -> SuiteStudy:
    """Parse and check a suite study."""
    return _load(SUITE, text)


def load_corpus(text: str) -> CorpusStudy:
    """Parse and check a corpus study, and the rules between fields of each subset."""
    study = _load(CORPUS, text)
    for row in study["subsets"]:
        outcomes = row["compiled"] + row["refused"] + row["crashed"] + row["timed_out"]
        if outcomes != row["schemas"] or row["disagreed"] > row["values"]:
            msg = f"corpus subset {row['subset']} contradicts itself"
            raise StudyError(msg)
    refused = sum(r["schemas"] for r in study["refusals"])
    if refused != sum(row["refused"] for row in study["subsets"]):
        msg = "the refusals by reason do not add up to the refused schemas"
        raise StudyError(msg)
    return study


def load_containment(text: str) -> ContainmentStudy:
    """Parse and check a containment study, and the rules between fields of each row."""
    study = _load(CONTAINMENT, text)
    for row in study["rows"]:
        answers = row["refused"] + row["timed_out"] + row["proven"]
        answers += row["refuted"] + row["undecided"]
        if answers != row["questions"]:
            msg = f"containment row {row['draft']}/{row['category']} does not add up"
            raise StudyError(msg)
        if row["proven_against"] > row["proven"] or row["refuted_against"] > row["refuted"]:
            msg = f"containment row {row['draft']}/{row['category']} contradicts itself"
            raise StudyError(msg)
    return study


def dumps(study: T, schema: Validator[T]) -> str:
    """Serialize a study, refusing one this code should never have built."""
    try:
        schema.validate(study)
    except ValidationError as exc:
        raise StudyError(str(exc)) from exc
    return json.dumps(study, indent=1) + "\n"
