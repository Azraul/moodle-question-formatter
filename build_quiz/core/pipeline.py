"""Pipeline composition."""

from __future__ import annotations

from build_quiz.core.lexer import Lexer, LexerError
from build_quiz.core.linter import Linter, LintResult
from build_quiz.core.models import Quiz
from build_quiz.core.parser import Parser, ParserError
from build_quiz.core.transformer import Transformer
from build_quiz.core.validator import Validator


class Pipeline:
    """Orchestrates the full processing pipeline: text → tokens → AST → validated AST."""

    def __init__(self) -> None:
        self.lexer = Lexer()
        self.parser = Parser()
        self.transformer = Transformer()
        self.validator = Validator()

    def process(self, text: str) -> Quiz:
        tokens = self.lexer.tokenize(text)
        quiz = self.parser.parse(tokens)
        quiz = self.transformer.transform(quiz)
        self.validator.validate(quiz)
        return quiz

    def lint(self, text: str) -> LintResult:
        """Parse and validate, returning all issues without raising."""
        try:
            tokens = self.lexer.tokenize(text)
        except LexerError as e:
            result = LintResult()
            result.errors.append(str(e))
            return result

        try:
            quiz = self.parser.parse(tokens)
        except ParserError as e:
            result = LintResult()
            result.errors.append(str(e))
            return result

        quiz = self.transformer.transform(quiz)
        return Linter().lint(quiz)
