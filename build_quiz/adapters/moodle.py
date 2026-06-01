"""Moodle XML generator."""

from __future__ import annotations

import re

from build_quiz.core.models import (
    ChoiceOption,
    ClozeQuestion,
    MatchingQuestion,
    MultipleChoiceQuestion,
    NumericalQuestion,
    Quiz,
    ShortAnswerQuestion,
    TrueFalseQuestion,
)


# ── XML Builder ──────────────────────────────────────────


class _Xml:
    """Helper for building indented XML strings."""

    def __init__(self):
        self._parts: list[str] = []
        self._indent: int = 0

    def _ind(self) -> str:
        return '  ' * self._indent

    def raw(self, text: str) -> None:
        self._parts.append(f"{self._ind()}{text}")

    def tag(self, tag_name: str, content: str | None = None, **attrs) -> None:
        attr_str = ''.join(f' {k}="{self._esc(v)}"' for k, v in attrs.items())
        if content is None:
            self._parts.append(f"{self._ind()}<{tag_name}{attr_str} />")
        else:
            self._parts.append(f"{self._ind()}<{tag_name}{attr_str}>{self._esc(content)}</{tag_name}>")

    def open(self, tag_name: str, **attrs) -> None:
        attr_str = ''.join(f' {k}="{self._esc(v)}"' for k, v in attrs.items())
        self._parts.append(f"{self._ind()}<{tag_name}{attr_str}>")
        self._indent += 1

    def close(self, tag_name: str) -> None:
        self._indent -= 1
        self._parts.append(f"{self._ind()}</{tag_name}>")

    def text(self, tag_name: str, content: str, *, cdata: bool = False) -> None:
        if cdata and content:
            safe = content.replace(']]>', ']]]]><![CDATA[>')
            self._parts.append(
                f"{self._ind()}<{tag_name}><![CDATA[{safe}]]></{tag_name}>"
            )
        else:
            self._parts.append(
                f"{self._ind()}<{tag_name}>{self._esc(content)}</{tag_name}>"
            )

    def text_element(self, tag_name: str, content: str, *,
                     fmt: str = "html", cdata: bool = True,
                     **attrs) -> None:
        """Produce a Moodle <name format="..."><text>content</text></name> block."""
        extra = ''.join(f' {k}="{self._esc(v)}"' for k, v in attrs.items())
        self._parts.append(f"{self._ind()}<{tag_name} format=\"{fmt}\"{extra}>")
        self._indent += 1
        if cdata and content:
            safe = content.replace(']]>', ']]]]><![CDATA[>')
            self._parts.append(f"{self._ind()}<text><![CDATA[{safe}]]></text>")
        else:
            self._parts.append(f"{self._ind()}<text>{self._esc(content)}</text>")
        self._indent -= 1
        self._parts.append(f"{self._ind()}</{tag_name}>")

    @staticmethod
    def _esc(s: str) -> str:
        """XML-escape a string for attribute values and non-CDATA content."""
        return s.replace('&', '&amp;').replace('<', '&lt;').replace(
            '>', '&gt;').replace('"', '&quot;')

    def __str__(self) -> str:
        return '\n'.join(self._parts)


# ── Multilang helpers ────────────────────────────────────


def _multilang(texts: dict[str, str]) -> str:
    """Wrap each language's text in <span lang="xx" class="multilang">.</span>"""
    spans = []
    for lang, text in texts.items():
        escaped = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        spans.append(f'<span lang="{lang.lower()}" class="multilang">{escaped}</span>')
    return ''.join(spans)


def _optional_multilang(texts: dict[str, str]) -> str:
    """Like _multilang but returns '' when all texts are empty."""
    if all(v.strip() == '' for v in texts.values()):
        return ''
    return _multilang(texts)


_TYPE_PREFIX: dict[str, str] = {
    'truefalse': 'TF',
    'multichoice': 'MC',
    'shortanswer': 'SA',
    'numerical': 'NUM',
    'matching': 'MATCH',
    'cloze': 'CLOZE',
}


# ── Adapter ──────────────────────────────────────────────


class MoodleAdapter:
    """Generates Moodle XML from a Quiz AST."""

    def generate(self, quiz: Quiz, include_category: bool = True,
                 allow_negative_mc: bool = False) -> str:
        self._allow_negative_mc = allow_negative_mc
        xml = _Xml()
        xml.raw('<?xml version="1.0" encoding="UTF-8"?>')
        xml.open('quiz')

        if include_category and quiz.category:
            self._generate_category(xml, quiz.category)

        for question in quiz.questions:
            if isinstance(question, TrueFalseQuestion):
                self._generate_tf(xml, question, quiz.languages)
            elif isinstance(question, MultipleChoiceQuestion):
                self._generate_mc(xml, question, quiz.languages)
            elif isinstance(question, ShortAnswerQuestion):
                self._generate_sa(xml, question, quiz.languages)
            elif isinstance(question, NumericalQuestion):
                self._generate_num(xml, question, quiz.languages)
            elif isinstance(question, MatchingQuestion):
                self._generate_match(xml, question, quiz.languages)
            elif isinstance(question, ClozeQuestion):
                self._generate_cloze(xml, question, quiz.languages)

        xml.close('quiz')
        return str(xml)

    # ── Category ─────────────────────────────────────────

    def _generate_category(self, xml: _Xml, category: str) -> None:
        xml.open('question', type='category')
        xml.open('category')
        xml.text('text', category)
        xml.close('category')
        xml.text_element('info', '', fmt='html')
        xml.tag('idnumber')
        xml.close('question')

    # ── Common wrapper ───────────────────────────────────

    def _open_question(self, xml: _Xml, qtype: str, title: str,
                       question_text: str, general_feedback: str,
                       defaultgrade: float, penalty: float) -> None:
        xml.open('question', type=qtype)
        prefix = _TYPE_PREFIX.get(qtype, qtype)
        xml.open('name')
        xml.text('text', f'{prefix}: {title}')
        xml.close('name')
        xml.text_element('questiontext', question_text, fmt='html')
        if general_feedback.strip():
            xml.text_element('generalfeedback', general_feedback, fmt='html')
        grade_str = f"{defaultgrade:.7f}"
        penalty_str = f"{penalty:.7f}"
        xml.tag('defaultgrade', grade_str)
        xml.tag('penalty', penalty_str)
        xml.tag('hidden', '0')
        xml.tag('idnumber')

    @staticmethod
    def _format_grade(n: float) -> str:
        return f"{n:.7f}"

    # ── TF ──────────────────────────────────────────────

    def _generate_tf(self, xml: _Xml, q: TrueFalseQuestion, languages: list[str]) -> None:
        qt = _multilang(q.question_text.texts)

        self._open_question(xml, 'truefalse', q.title, qt, '',
                            defaultgrade=1.0, penalty=1.0)

        true_fraction = '100' if q.correct_answer else '0'
        false_fraction = '0' if q.correct_answer else '100'

        # True answer
        xml.open('answer', fraction=true_fraction, format='plain_text')
        xml.text('text', 'true')
        tf = _optional_multilang(q.true_feedback.texts)
        if tf:
            xml.text_element('feedback', tf, fmt='html')
        xml.close('answer')

        # False answer
        xml.open('answer', fraction=false_fraction, format='plain_text')
        xml.text('text', 'false')
        ff = _optional_multilang(q.false_feedback.texts)
        if ff:
            xml.text_element('feedback', ff, fmt='html')
        xml.close('answer')

        xml.close('question')

    # ── MC ──────────────────────────────────────────────

    def _generate_mc(self, xml: _Xml, q: MultipleChoiceQuestion, languages: list[str]) -> None:
        qt = _multilang(q.question_text.texts)
        gf = _optional_multilang(q.general_feedback.texts)

        self._open_question(xml, 'multichoice', q.title, qt, gf,
                            defaultgrade=1.0, penalty=0.3333333)

        xml.tag('single', 'true' if q.single else 'false')
        xml.tag('shuffleanswers', 'true')
        xml.tag('answernumbering', 'abc')
        xml.tag('showstandardinstruction', '1')

        # Overall feedback
        cf = _optional_multilang(q.correct_feedback.texts)
        if cf:
            xml.text_element('correctfeedback', cf, fmt='html')
        pf = _optional_multilang(q.partially_correct_feedback.texts)
        if pf:
            xml.text_element('partiallycorrectfeedback', pf, fmt='html')
        incf = _optional_multilang(q.incorrect_feedback.texts)
        if incf:
            xml.text_element('incorrectfeedback', incf, fmt='html')

        # Options with normalized fractions
        for opt in q.options:
            fraction = _mc_fraction(opt, q, self._allow_negative_mc)
            opt_text = _multilang(opt.text.texts)
            xml.open('answer', fraction=fraction, format='html')
            xml.text('text', opt_text, cdata=True)
            if opt.feedback and any(v.strip() for v in opt.feedback.texts.values()):
                opt_fb = _optional_multilang(opt.feedback.texts)
                if opt_fb:
                    xml.text_element('feedback', opt_fb, fmt='html')
            xml.close('answer')

        xml.close('question')

    # ── SA ──────────────────────────────────────────────

    def _generate_sa(self, xml: _Xml, q: ShortAnswerQuestion, languages: list[str]) -> None:
        qt = _multilang(q.question_text.texts)
        gf = _optional_multilang(q.general_feedback.texts)

        self._open_question(xml, 'shortanswer', q.title, qt, gf,
                            defaultgrade=1.0, penalty=0.3333333)

        xml.tag('usecase', '0')

        for ans in q.answers:
            texts = set(v.strip() for v in ans.texts.values() if v.strip())
            for plain in texts:
                xml.open('answer', fraction='100', format='moodle_auto_format')
                xml.tag('text', plain)
                xml.close('answer')

        xml.close('question')

    # ── NUM ─────────────────────────────────────────────

    def _generate_num(self, xml: _Xml, q: NumericalQuestion, languages: list[str]) -> None:
        qt = _multilang(q.question_text.texts)
        gf = _optional_multilang(q.general_feedback.texts)

        self._open_question(xml, 'numerical', q.title, qt, gf,
                            defaultgrade=1.0, penalty=0.3333333)

        xml.tag('unitgradingtype', '0')
        xml.tag('unitpenalty', '0.1')
        xml.tag('showunits', '1')
        xml.tag('unitsleft', '0')

        # Emit <units> block from DSL unit annotations
        units_seen: set[str] = set()
        for ans in q.answers:
            if ans.unit and ans.unit not in units_seen:
                units_seen.add(ans.unit)
        if units_seen:
            xml.open('units')
            for unit_name in sorted(units_seen):
                xml.open('unit')
                xml.tag('multiplier', '1')
                xml.tag('unit_name', unit_name)
                xml.close('unit')
            xml.close('units')

        for ans in q.answers:
            fraction = str(ans.weight) if ans.weight is not None else '100'
            xml.open('answer', fraction=fraction)
            xml.tag('text', str(ans.value))
            if ans.feedback and any(v.strip() for v in ans.feedback.texts.values()):
                fb = _optional_multilang(ans.feedback.texts)
                if fb:
                    xml.text_element('feedback', fb, fmt='html')
            xml.tag('tolerance', str(ans.tolerance))
            xml.close('answer')

        xml.close('question')

    # ── MATCH ───────────────────────────────────────────

    def _generate_match(self, xml: _Xml, q: MatchingQuestion, languages: list[str]) -> None:
        qt = _multilang(q.question_text.texts)
        gf = _optional_multilang(q.general_feedback.texts)

        grade = float(len(q.pairs)) if q.pairs else 1.0

        self._open_question(xml, 'matching', q.title, qt, gf,
                            defaultgrade=grade, penalty=0.3333333)

        xml.tag('shuffleanswers', 'true')

        # Overall feedback (Moodle expects these, even if empty)
        xml.text_element('correctfeedback', '', fmt='html')
        xml.text_element('partiallycorrectfeedback', '', fmt='html')
        xml.text_element('incorrectfeedback', '', fmt='html')

        # Subquestions — multilang spans for both sides
        for pair in q.pairs:
            xml.open('subquestion', format='html')
            sq = _multilang(pair.subquestion.texts)
            xml.text('text', sq, cdata=True)
            xml.open('answer')
            ans = _multilang(pair.answer.texts)
            xml.text('text', ans, cdata=True)
            xml.close('answer')
            xml.close('subquestion')

        # Distractors — multilang spans
        for dist in q.distractors:
            xml.open('answer')
            dt = _multilang(dist.texts)
            xml.text('text', dt, cdata=True)
            xml.close('answer')

        xml.close('question')

    # ── CLOZE ───────────────────────────────────────────

    def _generate_cloze(self, xml: _Xml, q: ClozeQuestion, languages: list[str]) -> None:
        # Convert [correct|wrong] to {1:MULTICHOICE:=correct~wrong} per language
        converted: dict[str, str] = {}
        gap_counts: list[int] = []
        for lang, text in q.question_text.texts.items():
            conv, count = self._convert_cloze_text(text)
            converted[lang] = conv
            gap_counts.append(count)

        qt = _multilang(converted)
        gf = _optional_multilang(q.general_feedback.texts)

        defaultgrade = float(max(gap_counts))
        if defaultgrade < 1.0:
            defaultgrade = 1.0

        self._open_question(xml, 'cloze', q.title, qt, gf,
                            defaultgrade=defaultgrade, penalty=0.3333333)

        xml.close('question')

    @staticmethod
    def _convert_cloze_text(text: str) -> tuple[str, int]:
        """Convert [correct|wrong1|wrong2] to {1:MULTICHOICE:=correct~wrong1~wrong2}."""
        count = 0

        def replacer(m: re.Match) -> str:
            nonlocal count
            count += 1
            options = m.group(1).split('|')
            correct = options[0].strip()
            wrongs = [o.strip() for o in options[1:]]
            return '{1:MULTICHOICE:=' + correct + '~' + '~'.join(wrongs) + '}'

        result = re.sub(r'\[([^\]]+)\]', replacer, text)
        return result, count


# ── Helpers ──────────────────────────────────────────────


def _mc_fraction(opt: ChoiceOption, q: MultipleChoiceQuestion,
                 allow_negative: bool = False) -> str:
    """Compute a normalized Moodle fraction string for an MC option.

    Single-select: correct=100, wrong=0.
    Multi-select: normalize so the sum of positive fractions equals 100.
    Negative fractions are clamped to '0' by default; pass
    allow_negative=True to preserve them.
    """
    if q.single:
        return '100' if opt.correct else '0'

    # Multi-select — flag semantics (ignore absolute weight values).
    # Positive weight = correct flag, negative weight = wrong flag.
    # Correct options split 100 evenly; wrong options get 0 (or
    # negative with --negative-mc-weights).
    correct_count = sum(1 for o in q.options if o.correct)
    if correct_count > 0:
        base = 100.0 / correct_count
        if opt.correct:
            return f"{base:.5f}"
        elif opt.weight < 0 and allow_negative:
            return f"{-base:.5f}"
        else:
            return '0'
    return '0'
