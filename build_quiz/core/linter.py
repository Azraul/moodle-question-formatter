"""AST -> lint results (errors + warnings)."""

from __future__ import annotations

import re

from build_quiz.core.models import (
    ClozeQuestion,
    MatchingQuestion,
    MultipleChoiceQuestion,
    NumericalQuestion,
    Quiz,
    ShortAnswerQuestion,
    TrueFalseQuestion,
)
from build_quiz.core.validator import Validator


class LintResult:
    """Container for lint findings."""

    def __init__(self) -> None:
        self.errors: list[str] = []     # hard errors
        self.warnings: list[str] = []   # soft warnings
        self.infos: list[str] = []      # informational

    @property
    def has_issues(self) -> bool:
        return bool(self.errors) or bool(self.warnings)

    @property
    def count(self) -> int:
        return len(self.errors) + len(self.warnings) + len(self.infos)

    def summary(self) -> str:
        parts = []
        if self.errors:
            parts.append(f"errors={len(self.errors)}")
        if self.warnings:
            parts.append(f"warnings={len(self.warnings)}")
        if self.infos:
            parts.append(f"info={len(self.infos)}")
        return ", ".join(parts) if parts else "no issues"


class Linter:
    """Runs validation checks and extra lint analysis on a Quiz AST."""

    def lint(self, quiz: Quiz) -> LintResult:
        result = LintResult()

        # 1. Run all validator checks — collect ALL errors
        for err in Validator.collect_errors(quiz):
            result.errors.append(err)

        # 2. Additional lint-specific warnings
        for q in quiz.questions:
            # Duplicate SA answers (check across answers, not across languages)
            if isinstance(q, ShortAnswerQuestion):
                seen: set[str] = set()
                for ans in q.answers:
                    text = next((v.strip() for v in ans.texts.values() if v.strip()), '')
                    if not text:
                        continue
                    normalized = text.lower()
                    if normalized in seen:
                        result.warnings.append(
                            f"Q{q.id}: Duplicate short answer '{text}'"
                        )
                    seen.add(normalized)

            # MC with very few options
            if isinstance(q, MultipleChoiceQuestion) and len(q.options) <= 2:
                result.infos.append(
                    f"Q{q.id}: Multiple choice has only {len(q.options)} options"
                )

            # MATCH with only 1 pair
            if isinstance(q, MatchingQuestion) and len(q.pairs) <= 1:
                result.infos.append(
                    f"Q{q.id}: Matching has only {len(q.pairs)} pair"
                )

            # CLOZE gaps with few distractors (check first language only)
            if isinstance(q, ClozeQuestion):
                first_text = next(iter(q.question_text.texts.values()), '')
                gaps = re.findall(r'\[([^\]]+)\]', first_text)
                for i, gap in enumerate(gaps, 1):
                    opts = gap.split('|')
                    if len(opts) <= 2:
                        result.infos.append(
                            f"Q{q.id}: Cloze gap {i} has only {len(opts)} options"
                        )

            # Long titles
            if len(q.title) > 80:
                result.infos.append(
                    f"Q{q.id}: Title '{q.title[:50]}...' is {len(q.title)} characters"
                )

            # Questions without any feedback
            has_feedback = False
            if isinstance(q, TrueFalseQuestion):
                if q.true_feedback and any(v.strip() for v in q.true_feedback.texts.values()):
                    has_feedback = True
                if q.false_feedback and any(v.strip() for v in q.false_feedback.texts.values()):
                    has_feedback = True
            elif isinstance(q, MultipleChoiceQuestion):
                for fb in [q.correct_feedback, q.incorrect_feedback, q.partially_correct_feedback, q.general_feedback]:
                    if fb and any(v.strip() for v in fb.texts.values()):
                        has_feedback = True
                        break
                if not has_feedback:
                    for opt in q.options:
                        if opt.feedback and any(v.strip() for v in opt.feedback.texts.values()):
                            has_feedback = True
                            break
            elif isinstance(q, ShortAnswerQuestion):
                if q.general_feedback and any(v.strip() for v in q.general_feedback.texts.values()):
                    has_feedback = True
            elif isinstance(q, NumericalQuestion):
                if q.general_feedback and any(v.strip() for v in q.general_feedback.texts.values()):
                    has_feedback = True
            elif isinstance(q, MatchingQuestion):
                if q.general_feedback and any(v.strip() for v in q.general_feedback.texts.values()):
                    has_feedback = True
            elif isinstance(q, ClozeQuestion):
                if q.general_feedback and any(v.strip() for v in q.general_feedback.texts.values()):
                    has_feedback = True

            if not has_feedback:
                result.infos.append(
                    f"Q{q.id}: No feedback provided"
                )

        return result
