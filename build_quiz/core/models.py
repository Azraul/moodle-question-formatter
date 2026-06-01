"""Typed dataclasses for the question AST."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar


# ── Base Types ────────────────────────────────────────────

@dataclass
class BilingualText:
    """Text content in multiple languages. Key = language code (e.g. 'sv', 'en')."""
    texts: dict[str, str] = field(default_factory=dict)


# ── Question Types ────────────────────────────────────────

@dataclass
class TrueFalseQuestion:
    TYPE: ClassVar[str] = "TF"
    id: int
    title: str
    question_text: BilingualText
    correct_answer: bool                     # parsed from Svar: (Sant/True→True, Falskt/False→False)
    true_feedback: BilingualText | None = None   # before " / " in Feedback:
    false_feedback: BilingualText | None = None  # after " / " in Feedback:


@dataclass
class ChoiceOption:
    text: BilingualText
    correct: bool                            # * marker present?
    weight: int = 0                          # (100) or (-100) suffix, 0 if absent
    feedback: BilingualText | None = None    # per-option Feedback:


@dataclass
class MultipleChoiceQuestion:
    TYPE: ClassVar[str] = "MC"
    id: int
    title: str
    question_text: BilingualText
    single: bool                             # True = single-select, False = multi-select
    options: list[ChoiceOption]
    correct_feedback: BilingualText | None = None
    incorrect_feedback: BilingualText | None = None
    partially_correct_feedback: BilingualText | None = None
    general_feedback: BilingualText | None = None


@dataclass
class ShortAnswerQuestion:
    TYPE: ClassVar[str] = "SA"
    id: int
    title: str
    question_text: BilingualText
    answers: list[BilingualText]             # list of accepted answer texts
    general_feedback: BilingualText | None = None


@dataclass
class NumericalAnswer:
    value: float                             # e.g. 3.14
    tolerance: float                         # e.g. 0.01
    unit: str | None = None                  # e.g. 'km'
    weight: int | None = None                # e.g. 100 from '(100)'
    feedback: BilingualText | None = None


@dataclass
class NumericalQuestion:
    TYPE: ClassVar[str] = "NUM"
    id: int
    title: str
    question_text: BilingualText
    answers: list[NumericalAnswer]
    general_feedback: BilingualText | None = None


@dataclass
class MatchingPair:
    subquestion: BilingualText               # left side of ->
    answer: BilingualText                    # right side of ->


@dataclass
class MatchingQuestion:
    TYPE: ClassVar[str] = "MATCH"
    id: int
    title: str
    question_text: BilingualText
    pairs: list[MatchingPair]
    distractors: list[BilingualText]         # orphan -> Answer lines
    general_feedback: BilingualText | None = None


@dataclass
class ClozeQuestion:
    TYPE: ClassVar[str] = "CLOZE"
    id: int
    title: str
    question_text: BilingualText             # raw text with [correct|wrong|...] gaps
    general_feedback: BilingualText | None = None


# ── Document ──────────────────────────────────────────────

# Union of all question types (Python 3.10+)
Question = (
    TrueFalseQuestion
    | MultipleChoiceQuestion
    | ShortAnswerQuestion
    | NumericalQuestion
    | MatchingQuestion
    | ClozeQuestion
)


@dataclass
class Quiz:
    languages: list[str]                     # e.g. ['sv', 'en']
    category: str                            # e.g. '$course$/Geografi/Grundkurs'
    questions: list[Question]
