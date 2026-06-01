"""AST -> validated AST."""

from __future__ import annotations

from build_quiz.core.models import (
    BilingualText,
    ClozeQuestion,
    MatchingQuestion,
    MultipleChoiceQuestion,
    NumericalQuestion,
    Question,
    Quiz,
    ShortAnswerQuestion,
    TrueFalseQuestion,
)


class ValidationError(Exception):
    """Raised when the AST fails validation."""
    def __init__(self, question_id: int, message: str):
        super().__init__(f"Q{question_id}: {message}")
        self.question_id = question_id


class Validator:
    """Validates the parsed Quiz AST before XML generation."""

    def validate(self, quiz: Quiz) -> None:
        self._languages = quiz.languages
        for q in quiz.questions:
            # Common checks
            self._check_title(q)
            self._check_question_text_languages(q)

            if isinstance(q, TrueFalseQuestion):
                self._validate_tf(q)
            elif isinstance(q, MultipleChoiceQuestion):
                self._validate_mc(q)
            elif isinstance(q, ShortAnswerQuestion):
                self._validate_sa(q)
            elif isinstance(q, NumericalQuestion):
                self._validate_num(q)
            elif isinstance(q, MatchingQuestion):
                self._validate_match(q)
            elif isinstance(q, ClozeQuestion):
                self._validate_cloze(q)

        # Cross-language consistency (optional, but catch issues)
        self._check_cross_language_consistency(quiz)

    # ── Common checks ───────────────────────────────────

    def _check_title(self, q: Question) -> None:
        if not q.title.strip():
            raise ValidationError(q.id, "Title must not be empty")

    def _check_question_text_languages(self, q: Question) -> None:
        """Ensure question_text has entries for all declared languages."""
        self._check_bilingual('question_text', q.id, q.question_text)

    def _check_bilingual(self, field: str, qid: int, bt: BilingualText) -> None:
        for lang in self._languages:
            if lang not in bt.texts:
                raise ValidationError(
                    qid, f"{field} missing language '{lang}'"
                )

    # ── TF ──────────────────────────────────────────────

    def _validate_tf(self, q: TrueFalseQuestion) -> None:
        if not isinstance(q.correct_answer, bool):
            raise ValidationError(q.id, "correct_answer must be a bool")

    # ── MC ──────────────────────────────────────────────

    def _validate_mc(self, q: MultipleChoiceQuestion) -> None:
        if len(q.options) < 2:
            raise ValidationError(q.id, "Must have at least 2 options")

        correct_count = sum(1 for o in q.options if o.correct)
        incorrect_count = len(q.options) - correct_count

        if q.single:
            if correct_count != 1:
                raise ValidationError(
                    q.id, f"Single-select must have exactly 1 correct option, got {correct_count}"
                )
        else:
            if correct_count < 1:
                raise ValidationError(q.id, "Multi-select must have at least 1 correct option")
            if incorrect_count < 1:
                raise ValidationError(q.id, "Multi-select must have at least 1 incorrect option")

        # Check no options have empty text
        for i, opt in enumerate(q.options):
            if all(not text.strip() for text in opt.text.texts.values()):
                raise ValidationError(q.id, f"Option {i} has empty text in all languages")

    # ── SA ──────────────────────────────────────────────

    def _validate_sa(self, q: ShortAnswerQuestion) -> None:
        if len(q.answers) < 1:
            raise ValidationError(q.id, "Must have at least one answer")
        for i, ans in enumerate(q.answers):
            self._check_bilingual(f'answer[{i}]', q.id, ans)

    # ── NUM ─────────────────────────────────────────────

    def _validate_num(self, q: NumericalQuestion) -> None:
        if len(q.answers) < 1:
            raise ValidationError(q.id, "Must have at least one answer")
        for ans in q.answers:
            if ans.tolerance < 0:
                raise ValidationError(q.id, f"Tolerance must be >= 0, got {ans.tolerance}")
            import math
            if not math.isfinite(ans.value):
                raise ValidationError(q.id, f"Answer value must be finite, got {ans.value}")

    # ── MATCH ───────────────────────────────────────────

    def _validate_match(self, q: MatchingQuestion) -> None:
        if len(q.pairs) < 1:
            raise ValidationError(q.id, "Must have at least one matching pair")

    # ── CLOZE ───────────────────────────────────────────

    def _validate_cloze(self, q: ClozeQuestion) -> None:
        import re

        # Count gaps in each language
        gap_counts: dict[str, int] = {}
        for lang, text in q.question_text.texts.items():
            gaps = re.findall(r'\[([^\]]+)\]', text)
            gap_counts[lang] = len(gaps)
            # Check each gap has at least 2 options
            for i, gap in enumerate(gaps, 1):
                options = gap.split('|')
                if len(options) < 2:
                    raise ValidationError(
                        q.id,
                        f"Cloze gap {i} in '{lang}' must have at least 2 options "
                        f"(got {len(options)}): [{gap}]"
                    )
                if any(not o.strip() for o in options):
                    raise ValidationError(
                        q.id,
                        f"Cloze gap {i} in '{lang}' has an empty option: [{gap}]"
                    )

        # All languages must have the same number of gaps
        if len(set(gap_counts.values())) > 1:
            raise ValidationError(
                q.id,
                f"Gap count mismatch across languages: {gap_counts}"
            )

    # ── Collect all errors ─────────────────────────────

    @staticmethod
    def collect_errors(quiz: Quiz) -> list[str]:
        """Run all validation checks and return ALL errors as strings. Never raises."""
        errors: list[str] = []
        v = Validator()
        v._languages = quiz.languages

        for q in quiz.questions:
            # Title check
            try:
                v._check_title(q)
            except ValidationError as e:
                errors.append(str(e))

            # Question text language check
            try:
                v._check_question_text_languages(q)
            except ValidationError as e:
                errors.append(str(e))

            # Type-specific checks
            if isinstance(q, TrueFalseQuestion):
                try:
                    v._validate_tf(q)
                except ValidationError as e:
                    errors.append(str(e))
            elif isinstance(q, MultipleChoiceQuestion):
                try:
                    v._validate_mc(q)
                except ValidationError as e:
                    errors.append(str(e))
            elif isinstance(q, ShortAnswerQuestion):
                try:
                    v._validate_sa(q)
                except ValidationError as e:
                    errors.append(str(e))
            elif isinstance(q, NumericalQuestion):
                try:
                    v._validate_num(q)
                except ValidationError as e:
                    errors.append(str(e))
            elif isinstance(q, MatchingQuestion):
                try:
                    v._validate_match(q)
                except ValidationError as e:
                    errors.append(str(e))
            elif isinstance(q, ClozeQuestion):
                try:
                    v._validate_cloze(q)
                except ValidationError as e:
                    errors.append(str(e))

        # Cross-language consistency
        try:
            v._check_cross_language_consistency(quiz)
        except ValidationError as e:
            errors.append(str(e))

        return errors

    # ── Cross-language consistency ───────────────────────

    def _check_cross_language_consistency(self, quiz: Quiz) -> None:
        """Verify all BilingualText fields have entries for all languages."""
        for q in quiz.questions:
            self._check_all_text_fields(q)

    def _check_all_text_fields(self, q: Question) -> None:
        """Walk all BilingualText fields on a question and verify completeness."""
        if isinstance(q, TrueFalseQuestion):
            if q.true_feedback:
                self._check_bilingual('true_feedback', q.id, q.true_feedback)
            if q.false_feedback:
                self._check_bilingual('false_feedback', q.id, q.false_feedback)
        elif isinstance(q, MultipleChoiceQuestion):
            if q.correct_feedback:
                self._check_bilingual('correct_feedback', q.id, q.correct_feedback)
            if q.incorrect_feedback:
                self._check_bilingual('incorrect_feedback', q.id, q.incorrect_feedback)
            if q.partially_correct_feedback:
                self._check_bilingual('partially_correct_feedback', q.id, q.partially_correct_feedback)
            if q.general_feedback:
                self._check_bilingual('general_feedback', q.id, q.general_feedback)
            for i, opt in enumerate(q.options):
                self._check_bilingual(f'option[{i}].text', q.id, opt.text)
                if opt.feedback:
                    self._check_bilingual(f'option[{i}].feedback', q.id, opt.feedback)
        elif isinstance(q, ShortAnswerQuestion):
            if q.general_feedback:
                self._check_bilingual('general_feedback', q.id, q.general_feedback)
        elif isinstance(q, NumericalQuestion):
            if q.general_feedback:
                self._check_bilingual('general_feedback', q.id, q.general_feedback)
        elif isinstance(q, MatchingQuestion):
            if q.general_feedback:
                self._check_bilingual('general_feedback', q.id, q.general_feedback)
            for i, pair in enumerate(q.pairs):
                self._check_bilingual(f'pair[{i}].subquestion', q.id, pair.subquestion)
                self._check_bilingual(f'pair[{i}].answer', q.id, pair.answer)
            for i, dist in enumerate(q.distractors):
                self._check_bilingual(f'distractor[{i}]', q.id, dist)
        elif isinstance(q, ClozeQuestion):
            if q.general_feedback:
                self._check_bilingual('general_feedback', q.id, q.general_feedback)
