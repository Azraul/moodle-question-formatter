"""CLI argument parsing."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from build_quiz.adapters.moodle import MoodleAdapter
from build_quiz.core.pipeline import Pipeline


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description='Convert plain text quiz questions to Moodle XML'
    )
    parser.add_argument(
        'input', help='Input file path (plain text questions)'
    )
    parser.add_argument(
        '-o', '--output', help='Output file path (default: stdout)'
    )
    parser.add_argument(
        '--encoding', default='utf-8',
        help='Input file encoding (default: utf-8)'
    )
    parser.add_argument(
        '--negative-mc-weights', action='store_true',
        help='Allow negative scores for wrong multi-select MC answers'
    )
    parser.add_argument(
        '--lint', action='store_true',
        help='Lint mode: validate and report all issues without generating XML'
    )
    args = parser.parse_args(argv)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: file not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    # Read input
    with open(input_path, encoding=args.encoding) as f:
        text = f.read()

    pipeline = Pipeline()

    # Lint mode: report all issues, don't generate XML
    if args.lint:
        result = pipeline.lint(text)
        if result.errors:
            print("ERRORS:")
            for e in result.errors:
                print(f"  \u2717 {e}")
        if result.warnings:
            print("WARNINGS:")
            for w in result.warnings:
                print(f"  \u26a0 {w}")
        if result.infos:
            print("INFO:")
            for i in result.infos:
                print(f"  \u2139 {i}")
        print()
        print(result.summary())
        sys.exit(1 if result.has_issues else 0)

    # Normal mode: generate XML
    quiz = pipeline.process(text)

    # Generate XML
    adapter = MoodleAdapter()
    xml = adapter.generate(quiz, allow_negative_mc=args.negative_mc_weights)

    # Output
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(xml)
            f.write('\n')
    else:
        print(xml)
