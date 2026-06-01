"""Defaults and normalisation."""

from __future__ import annotations

from build_quiz.core.models import (
    BilingualText,
    ClozeQuestion,
    MatchingQuestion,
    MultipleChoiceQuestion,
    NumericalQuestion,
    Quiz,
    ShortAnswerQuestion,
    TrueFalseQuestion,
)


class Transformer:
    """Normalises the AST: fills defaults, replaces None values."""

    def transform(self, quiz: Quiz) -> Quiz:
        for q in quiz.questions:
            if isinstance(q, TrueFalseQuestion):
                self._transform_tf(q, quiz.languages)
            elif isinstance(q, MultipleChoiceQuestion):
                self._transform_mc(q, quiz.languages)
            elif isinstance(q, ShortAnswerQuestion):
                self._transform_sa(q, quiz.languages)
            elif isinstance(q, NumericalQuestion):
                self._transform_num(q, quiz.languages)
            elif isinstance(q, MatchingQuestion):
                self._transform_match(q, quiz.languages)
            elif isinstance(q, ClozeQuestion):
                self._transform_cloze(q, quiz.languages)
        return quiz

    def _fill_empty(self, bt: BilingualText | None, languages: list[str]) -> BilingualText:
        """Ensure a BilingualText has entries for all languages."""
        if bt is None:
            bt = BilingualText()
        for lang in languages:
            if lang not in bt.texts:
                bt.texts[lang] = ''
        return bt

    def _transform_tf(self, q: TrueFalseQuestion, languages: list[str]) -> None:
        q.question_text = self._fill_empty(q.question_text, languages)
        q.true_feedback = self._fill_empty(q.true_feedback, languages)
        q.false_feedback = self._fill_empty(q.false_feedback, languages)

    def _transform_mc(self, q: MultipleChoiceQuestion, languages: list[str]) -> None:
        q.question_text = self._fill_empty(q.question_text, languages)
        q.correct_feedback = self._fill_empty(q.correct_feedback, languages)
        q.incorrect_feedback = self._fill_empty(q.incorrect_feedback, languages)
        q.partially_correct_feedback = self._fill_empty(q.partially_correct_feedback, languages)
        q.general_feedback = self._fill_empty(q.general_feedback, languages)

        for opt in q.options:
            opt.text = self._fill_empty(opt.text, languages)
            opt.feedback = self._fill_empty(opt.feedback, languages)

        # Single-select: ensure the correct option has weight 100
        if q.single:
            for opt in q.options:
                if opt.correct:
                    opt.weight = 100

    def _transform_sa(self, q: ShortAnswerQuestion, languages: list[str]) -> None:
        q.question_text = self._fill_empty(q.question_text, languages)
        q.general_feedback = self._fill_empty(q.general_feedback, languages)
        for ans in q.answers:
            self._fill_empty(ans, languages)

    def _transform_num(self, q: NumericalQuestion, languages: list[str]) -> None:
        q.question_text = self._fill_empty(q.question_text, languages)
        q.general_feedback = self._fill_empty(q.general_feedback, languages)
        for ans in q.answers:
            if ans.tolerance < 0:
                ans.tolerance = 0.0

    def _transform_match(self, q: MatchingQuestion, languages: list[str]) -> None:
        q.question_text = self._fill_empty(q.question_text, languages)
        q.general_feedback = self._fill_empty(q.general_feedback, languages)
        for pair in q.pairs:
            self._fill_empty(pair.subquestion, languages)
            self._fill_empty(pair.answer, languages)
        for dist in q.distractors:
            self._fill_empty(dist, languages)

    def _transform_cloze(self, q: ClozeQuestion, languages: list[str]) -> None:
        q.question_text = self._fill_empty(q.question_text, languages)
        q.general_feedback = self._fill_empty(q.general_feedback, languages)
