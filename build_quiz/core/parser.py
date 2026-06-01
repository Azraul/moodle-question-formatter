"""Tokens -> AST."""

from __future__ import annotations

import re

from build_quiz.core.lexer import Token
from build_quiz.core.models import (
    BilingualText,
    ChoiceOption,
    ClozeQuestion,
    MatchingPair,
    MatchingQuestion,
    MultipleChoiceQuestion,
    NumericalAnswer,
    NumericalQuestion,
    Quiz,
    ShortAnswerQuestion,
    TrueFalseQuestion,
)

# Re-export ParserError so other modules don't need to import from models
class ParserError(Exception):
    """Raised when parsing fails."""
    def __init__(self, message: str, line: int | None = None):
        suffix = f" (near line {line})" if line else ""
        super().__init__(f"Parse error: {message}{suffix}")
        self.line = line


class Parser:
    """State-machine parser: consumes tokens and produces a Quiz AST."""

    def __init__(self):
        self._tokens: list[Token] = []
        self._pos: int = 0
        self._languages: list[str] = []

    # ── Top-level ───────────────────────────────────────

    def parse(self, tokens: list[Token]) -> Quiz:
        self._tokens = tokens
        self._pos = 0

        # Parse header
        self._skip_blanks()
        languages = self._parse_header()
        self._languages = languages

        # Parse questions
        questions = []
        while self._pos < len(self._tokens):
            self._skip_blanks()
            if self._pos >= len(self._tokens):
                break
            tok = self._tokens[self._pos]
            if tok.kind == 'QUESTION':
                qnum, qtype, title = tok.value
                self._pos += 1
                question = self._parse_question_body(qtype, qnum, title)
                questions.append(question)
            else:
                raise ParserError(
                    f"Expected QUESTION token, got {tok.kind}", tok.line
                )

        # Derive category from header tokens
        category = ""
        for tok in self._tokens:
            if tok.kind == 'HEADER' and tok.value[0] == 'category':
                category = tok.value[1].strip()

        return Quiz(languages=languages, category=category, questions=questions)

    # ── Header parsing ──────────────────────────────────

    def _parse_header(self) -> list[str]:
        languages: list[str] = []
        while self._pos < len(self._tokens):
            tok = self._tokens[self._pos]
            if tok.kind == 'HEADER':
                key, value = tok.value
                if key == 'languages':
                    languages = [l.strip().upper() for l in value.split(',')]
                self._pos += 1
                self._skip_blanks()
            else:
                break
        return languages

    # ── Question dispatch ───────────────────────────────

    def _parse_question_body(self, qtype: str, qnum: int, title: str):
        handlers = {
            'TF': self._parse_tf,
            'MC': self._parse_mc,
            'SA': self._parse_sa,
            'NUM': self._parse_num,
            'MATCH': self._parse_match,
            'CLOZE': self._parse_cloze,
        }
        if qtype not in handlers:
            raise ParserError(f"Unknown question type: {qtype}")
        return handlers[qtype](qnum, title)

    # ── Helpers ─────────────────────────────────────────

    def _skip_blanks(self) -> None:
        while self._pos < len(self._tokens) and self._tokens[self._pos].kind == 'BLANK':
            self._pos += 1

    def _current(self) -> Token | None:
        self._skip_blanks()
        if self._pos < len(self._tokens):
            return self._tokens[self._pos]
        return None

    def _peek(self) -> Token | None:
        return self._current()

    def _peek_kind(self) -> str | None:
        tok = self._peek()
        return tok.kind if tok else None

    def _peek_value(self) -> str | None:
        tok = self._peek()
        return tok.value if tok else None

    def _consume(self):
        tok = self._peek()
        if tok is None:
            raise ParserError("Unexpected end of input")
        self._pos += 1
        # skip blanks after consuming (ready for next peek)
        return tok

    def _consume_texts_for_languages(self) -> BilingualText:
        """Read one TEXT per declared language, return BilingualText."""
        result = BilingualText()
        seen: set[str] = set()
        while len(seen) < len(self._languages):
            tok = self._peek()
            if tok is None or tok.kind != 'TEXT':
                break
            lang = tok.value[0]
            if lang in seen:
                break
            if lang not in self._languages:
                break
            result.texts[lang] = tok.value[1]
            seen.add(lang)
            self._consume()
        if len(seen) < len(self._languages):
            missing = sorted(set(self._languages) - seen)
            tok = self._peek()
            line = tok.line if tok else None
            raise ParserError(
                f"Missing TEXT for language(s): {', '.join(missing)}", line
            )
        return result

    def _is_question_start(self) -> bool:
        tok = self._peek()
        return tok is not None and tok.kind == 'QUESTION'

    # ── TF parser ───────────────────────────────────────

    def _parse_tf(self, qnum: int, title: str) -> TrueFalseQuestion:
        question_text = self._consume_texts_for_languages()

        # Svar: → answer
        answer = self._expect_keyword('Svar')
        svar_texts = self._consume_texts_for_languages()
        correct_answer = self._parse_tf_answer(svar_texts)

        # Optional Feedback:
        true_feedback: BilingualText | None = None
        false_feedback: BilingualText | None = None
        if self._peek_kind() == 'KEYWORD' and self._peek_value() == 'Feedback':
            self._consume()
            fb_texts = self._consume_texts_for_languages()
            true_feedback, false_feedback = self._split_feedback(fb_texts)

        return TrueFalseQuestion(
            id=qnum,
            title=title,
            question_text=question_text,
            correct_answer=correct_answer,
            true_feedback=true_feedback,
            false_feedback=false_feedback,
        )

    @staticmethod
    def _parse_tf_answer(texts: BilingualText) -> bool:
        """Determine true/false from answer text (case-insensitive)."""
        true_words = {'sant', 'true'}
        false_words = {'falskt', 'false'}
        for lang, text in texts.texts.items():
            lower = text.strip().lower()
            if lower in true_words:
                return True
            if lower in false_words:
                return False
        # Default: if none of the texts match known words, raise error
        raise ParserError(
            f"Could not determine true/false from answer: {texts.texts}"
        )

    @staticmethod
    def _split_feedback(fb: BilingualText) -> tuple[BilingualText, BilingualText]:
        """Split feedback text on ' / ' into true/false parts."""
        true_fb = BilingualText()
        false_fb = BilingualText()
        for lang, text in fb.texts.items():
            if ' / ' in text:
                parts = text.split(' / ', 1)
                true_fb.texts[lang] = parts[0]
                false_fb.texts[lang] = parts[1]
            else:
                true_fb.texts[lang] = text
                false_fb.texts[lang] = ''
        return true_fb, false_fb

    # ── MC parser ───────────────────────────────────────

    def _parse_mc(self, qnum: int, title: str) -> MultipleChoiceQuestion:
        single = '(flera rätt)' not in title.lower()
        question_text = self._consume_texts_for_languages()

        correct_feedback: BilingualText | None = None
        incorrect_feedback: BilingualText | None = None
        partially_correct_feedback: BilingualText | None = None
        general_feedback: BilingualText | None = None

        # Read keyword blocks before first option
        while self._peek_kind() == 'KEYWORD':
            kw = self._peek_value()
            if kw == 'Feedback':
                # Feedback keyword doesn't make sense at question level in MC
                break
            self._consume()
            texts = self._consume_texts_for_languages()
            if kw == 'Helt rätt':
                correct_feedback = texts
            elif kw == 'Helt fel':
                incorrect_feedback = texts
            elif kw == 'Delvis rätt':
                partially_correct_feedback = texts
            elif kw == 'Allmänt':
                general_feedback = texts
            else:
                # Shouldn't happen but be defensive
                break

        # Read options
        options: list[ChoiceOption] = []
        while self._peek_kind() == 'OPTION':
            self._consume()  # consume the OPTION token (letter)
            opt_text = self._consume_texts_for_languages()

            # Parse option text for * marker and weight
            parsed_texts, correct, weight = self._parse_option_text(opt_text)
            opt_text_cleaned = BilingualText(texts=parsed_texts)

            # Optional per-option Feedback:
            opt_feedback: BilingualText | None = None
            if self._peek_kind() == 'KEYWORD' and self._peek_value() == 'Feedback':
                self._consume()
                opt_feedback = self._consume_texts_for_languages()

            options.append(ChoiceOption(
                text=opt_text_cleaned,
                correct=correct,
                weight=weight,
                feedback=opt_feedback,
            ))

        # After options, check for trailing keyword blocks (Allmänt, etc.)
        while self._peek_kind() == 'KEYWORD':
            kw = self._peek_value()
            if kw not in ('Allmänt', 'Helt rätt', 'Helt fel', 'Delvis rätt'):
                break
            self._consume()
            texts = self._consume_texts_for_languages()
            if kw == 'Allmänt':
                general_feedback = texts
            elif kw == 'Helt rätt':
                correct_feedback = texts
            elif kw == 'Helt fel':
                incorrect_feedback = texts
            elif kw == 'Delvis rätt':
                partially_correct_feedback = texts

        return MultipleChoiceQuestion(
            id=qnum,
            title=title,
            question_text=question_text,
            single=single,
            options=options,
            correct_feedback=correct_feedback,
            incorrect_feedback=incorrect_feedback,
            partially_correct_feedback=partially_correct_feedback,
            general_feedback=general_feedback,
        )

    @staticmethod
    def _parse_option_text(
        bt: BilingualText,
    ) -> tuple[dict[str, str], bool, int]:
        """Parse option text for * marker and weight suffix. Returns (cleaned_texts, correct, weight)."""
        cleaned: dict[str, str] = {}
        is_correct = False
        weight = 0

        if bt.texts:
            # Detect markers from the first language only
            first_lang = next(iter(bt.texts.keys()))
            first_text = bt.texts[first_lang]

            # Extract weight suffix: (N) or (-N)
            m = re.search(r'\((-?\d+)\)\s*$', first_text)
            if m:
                weight = int(m.group(1))
                first_text = first_text[:m.start()].strip()

            # Check for * marker
            if first_text.rstrip().endswith('*'):
                is_correct = True
            elif weight != 0:
                is_correct = weight > 0

            # Clean all language texts
            for lang, text in bt.texts.items():
                t = re.sub(r'\((-?\d+)\)\s*$', '', text).strip()
                if t.endswith('*'):
                    t = t[:-1].strip()
                cleaned[lang] = t

        return cleaned, is_correct, weight

    # ── SA parser ───────────────────────────────────────

    def _parse_sa(self, qnum: int, title: str) -> ShortAnswerQuestion:
        question_text = self._consume_texts_for_languages()

        answers: list[BilingualText] = []
        general_feedback: BilingualText | None = None

        while True:
            tok = self._peek()
            if tok is None or self._is_question_start():
                break
            if tok.kind == 'KEYWORD':
                kw = tok.value
                if kw == 'Svar':
                    self._consume()
                    answers.append(self._consume_texts_for_languages())
                elif kw == 'Feedback':
                    self._consume()
                    general_feedback = self._consume_texts_for_languages()
                else:
                    break
            else:
                break

        return ShortAnswerQuestion(
            id=qnum,
            title=title,
            question_text=question_text,
            answers=answers,
            general_feedback=general_feedback,
        )

    # ── NUM parser ───────────────────────────────────────

    def _parse_num(self, qnum: int, title: str) -> NumericalQuestion:
        question_text = self._consume_texts_for_languages()

        answers: list[NumericalAnswer] = []
        general_feedback: BilingualText | None = None

        while True:
            tok = self._peek()
            if tok is None or self._is_question_start():
                break
            if tok.kind == 'KEYWORD':
                kw = tok.value
                if kw == 'Svar':
                    self._consume()
                    texts = self._consume_texts_for_languages()
                    # Parse all language texts and verify consistency
                    parsed: NumericalAnswer | None = None
                    for lang_text in texts.texts.values():
                        candidate = self._parse_num_answer(lang_text)
                        if parsed is None:
                            parsed = candidate
                        elif (candidate.value != parsed.value
                              or candidate.tolerance != parsed.tolerance
                              or candidate.unit != parsed.unit
                              or candidate.weight != parsed.weight):
                            raise ParserError(
                                f"Numerical answer mismatch across languages: "
                                f"{parsed.value}:{parsed.tolerance} vs "
                                f"{candidate.value}:{candidate.tolerance}"
                            )
                    if parsed is not None:
                        answers.append(parsed)
                elif kw == 'Feedback':
                    self._consume()
                    general_feedback = self._consume_texts_for_languages()
                else:
                    break
            else:
                break

        return NumericalQuestion(
            id=qnum,
            title=title,
            question_text=question_text,
            answers=answers,
            general_feedback=general_feedback,
        )

    @staticmethod
    def _parse_num_answer(text: str) -> NumericalAnswer:
        """Parse value:tolerance [unit] [(weight)]."""
        m = re.match(r'^([\d.]+):([\d.]+)(?:\s+(\S+))?(?:\s+\((\d+)\))?$', text.strip())
        if not m:
            raise ParserError(f"Invalid numerical answer format: {text!r}")
        value = float(m.group(1))
        tolerance = float(m.group(2))
        unit = m.group(3)
        weight = int(m.group(4)) if m.group(4) else None
        return NumericalAnswer(value=value, tolerance=tolerance, unit=unit, weight=weight)

    # ── MATCH parser ─────────────────────────────────────

    def _parse_match(self, qnum: int, title: str) -> MatchingQuestion:
        question_text = self._consume_texts_for_languages()

        pairs: list[MatchingPair] = []
        distractors: list[BilingualText] = []
        general_feedback: BilingualText | None = None

        while True:
            tok = self._peek()
            if tok is None or self._is_question_start():
                break
            if tok.kind == 'MATCH':
                self._consume()
                left, right = tok.value
                # Create BilingualText for left and right (same for all languages)
                left_bt = BilingualText({lang: left for lang in self._languages}) if left else None
                right_bt = BilingualText({lang: right for lang in self._languages})
                if left_bt is not None:
                    pairs.append(MatchingPair(subquestion=left_bt, answer=right_bt))
                else:
                    distractors.append(right_bt)
            elif tok.kind == 'KEYWORD' and tok.value == 'Allmänt':
                self._consume()
                general_feedback = self._consume_texts_for_languages()
            else:
                break

        return MatchingQuestion(
            id=qnum,
            title=title,
            question_text=question_text,
            pairs=pairs,
            distractors=distractors,
            general_feedback=general_feedback,
        )

    # ── CLOZE parser ─────────────────────────────────────

    def _parse_cloze(self, qnum: int, title: str) -> ClozeQuestion:
        question_text = self._consume_texts_for_languages()

        general_feedback: BilingualText | None = None
        if self._peek_kind() == 'KEYWORD' and self._peek_value() == 'Allmänt':
            self._consume()
            general_feedback = self._consume_texts_for_languages()

        return ClozeQuestion(
            id=qnum,
            title=title,
            question_text=question_text,
            general_feedback=general_feedback,
        )

    # ── Keyword helper ───────────────────────────────────

    def _expect_keyword(self, expected: str) -> str:
        tok = self._peek()
        if tok is None or tok.kind != 'KEYWORD' or tok.value != expected:
            got = f"{tok.kind}:{tok.value}" if tok else 'EOF'
            raise ParserError(
                f"Expected KEYWORD '{expected}', got {got}", tok.line if tok else None
            )
        return self._consume().value
