"""Text -> tokens."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


class LexerError(Exception):
    """Raised when the input text cannot be tokenized."""
    def __init__(self, message: str, line: int):
        super().__init__(f"Line {line}: {message}")
        self.line = line


@dataclass
class Token:
    kind: str       # HEADER, BLANK, QUESTION, TEXT, KEYWORD, OPTION, MATCH
    value: Any      # Tuple or string depending on kind
    line: int       # 1-indexed line number
    indent: int     # Number of leading whitespace characters


class Lexer:
    """Line-oriented tokenizer for the quiz plain-text format."""

    def tokenize(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        lines = text.splitlines()

        for line_num, raw_line in enumerate(lines, start=1):
            line = raw_line.rstrip('\n\r')
            indent = len(raw_line) - len(raw_line.lstrip())

            tok = self._classify(line, line_num, indent)
            tokens.append(tok)

        return tokens

    def _classify(self, line: str, line_num: int, indent: int) -> Token:
        if not line.strip():
            return Token('BLANK', None, line_num, indent)

        # 1. Headers
        m = re.match(r'^(languages|category):\s*(.+)$', line)
        if m:
            return Token('HEADER', (m.group(1), m.group(2)), line_num, indent)

        # 2. Question header: N. [TYPE] Title
        m = re.match(r'^(\d+)\.\s*\[(\w+)\]\s*(.+)$', line)
        if m:
            qnum = int(m.group(1))
            qtype = m.group(2).upper()
            title = m.group(3).strip()
            return Token('QUESTION', (qnum, qtype, title), line_num, indent)

        # 3. TEXT: indented language tag + text
        m = re.match(r'^(\s+)([A-Z]{2,3}):\s+(.*)$', line)
        if m:
            lang = m.group(2)
            text = m.group(3)
            return Token('TEXT', (lang, text), line_num, indent)

        # 4. OPTION: indented letter followed by )
        m = re.match(r'^(\s+)([a-e])\)\s*$', line)
        if m:
            return Token('OPTION', m.group(2), line_num, indent)

        # 5. MATCH (distractor): indented -> Right
        m = re.match(r'^(\s+)->\s*(.+)$', line)
        if m:
            return Token('MATCH', (None, m.group(2)), line_num, indent)

        # 6. MATCH (pair): indented Left -> Right
        m = re.match(r'^(\s+)(.+?)\s*->\s*(.+)$', line)
        if m:
            return Token('MATCH', (m.group(2), m.group(3)), line_num, indent)

        # 7. KEYWORD: indented keyword followed by colon
        m = re.match(r'^(\s+)(Svar|Feedback|Helt rätt|Helt fel|Delvis rätt|Allmänt):\s*$', line)
        if m:
            return Token('KEYWORD', m.group(2), line_num, indent)

        raise LexerError(f"Unrecognized line: {line!r}", line_num)
