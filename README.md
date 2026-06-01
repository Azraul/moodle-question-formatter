# moodle-question-formatter

Convert plain text quiz questions to Moodle XML — a **DSL-to-XML** compiler for Moodle quizzes.

Write your quiz questions in a clean, expressive plain text format and generate ready-to-import Moodle XML.

## Quick Start

```bash
# Convert sample file to Moodle XML
python -m build_quiz sample_plain.txt -o quiz.xml

# Or pipe to stdout
python -m build_quiz sample_plain.txt
```

Then import `quiz.xml` in Moodle: **Question bank → Import → Moodle XML format**.

## Installation

```bash
git clone <repo>
cd moodle-question-formatter
pip install -e .
```

Requires **Python 3.10+**. Zero external dependencies — stdlib only.

## CLI Usage

```
usage: build-quiz [-h] [-o OUTPUT] [--encoding ENCODING]
                  [--negative-mc-weights] [--lint]
                  input

Convert plain text quiz questions to Moodle XML.

positional arguments:
  input                 Input file path (plain text questions)

options:
  -h, --help            Show this help message and exit
  -o, --output OUTPUT   Output file path (default: stdout)
  --encoding ENCODING   Input file encoding (default: utf-8)
  --negative-mc-weights
                        Allow negative scores for wrong multi-select
                        MC answers (default: clamp to 0)
  --lint                Validate input and report all issues without
                        generating XML (exit 0 = clean, 1 = issues)
```

## Input Format (DSL)

The input is a plain text file with a header block followed by numbered questions.

### Header

```
languages: sv, en
category: $course$/Geografi/Grundkurs
```

| Field | Description |
|-------|-------------|
| `languages:` | Comma-separated language codes. All text fields must provide text for each language. |
| `category:` | Moodle category path. Supports `$course$` variable. Applied to all questions. |

### Question Structure

Every question follows this pattern:

```
N. [TYPE] Title
   SV: Question text in Swedish
   EN: Question text in English
   [type-specific sections...]
```

- **N.** — sequential question number
- **[TYPE]** — two- or three-letter type code
- **Title** — one line, same for all languages
- **SV: / EN:** — language-tagged text fields, indented 3 spaces. Every user-facing text field appears in every declared language.

---

## Question Types

### True/False `[TF]`

```
1. [TF] Title
   SV: Question text
   EN: Question text
   Svar:
     SV: Sant
     EN: True
   Feedback:
     SV: Correct feedback / Incorrect feedback
     EN: Correct feedback / Incorrect feedback
```

| Field | Required | Description |
|-------|----------|-------------|
| `Svar:` | ✅ | Answer: `Sant`/`True` or `Falskt`/`False` |
| `Feedback:` | ❌ | Split on ` / ` → first half is correct feedback, second half is incorrect feedback |

### Multiple Choice — Single `[MC]`

```
2. [MC] Title
   SV: Question text
   EN: Question text
   Helt rätt:
     SV: Correct!
     EN: Correct!
   Helt fel:
     SV: Wrong!
     EN: Wrong!
   a)
     SV: Option A
     EN: Option A
   b)
     SV: Option B *
     EN: Option B *
     Feedback:
       SV: Per-option feedback
       EN: Per-option feedback
   c)
     SV: Option C
     EN: Option C
```

- `*` marks the correct answer
- Letters `a)` through `e)` for up to 5 options
- `Helt rätt:` / `Helt fel:` are optional overall feedback blocks
- Per-option `Feedback:` is optional

### Multiple Choice — Multi-Select `[MC] (flera rätt)`

```
3. [MC] Title (flera rätt)
   SV: Question text
   EN: Question text
   Allmänt:
     SV: General information
     EN: General information
   Helt rätt:
     SV: All correct!
     EN: All correct!
   Delvis rätt:
     SV: Partially correct
     EN: Partially correct
   Helt fel:
     SV: All wrong
     EN: All wrong
   a)
     SV: Correct answer * (100)
     EN: Correct answer * (100)
   b)
     SV: Wrong answer (-100)
     EN: Wrong answer (-100)
   c)
     SV: Another correct * (100)
     EN: Another correct * (100)
```

- `(flera rätt)` in the title triggers multi-select mode
- `*` marks correct answers, weight `(N)` is a flag (positive = correct, negative = wrong)
- **Weights are flags, not values.** Any positive value marks correct, any negative marks wrong. The numeric value is ignored — scoring is normalized automatically.
- Correct answers get `100/n_correct` points, wrong answers get `0` (default) or `-100/n_correct` (with `--negative-mc-weights`)
- `Delvis rätt:` is partial-credit feedback (multi-select only)
- `Allmänt:` becomes general feedback

### Short Answer `[SA]`

```
4. [SA] Title
   SV: Question text
   EN: Question text
   Svar:
     SV: Accepted answer 1
     EN: Accepted answer 1
   Svar:
     SV: Accepted answer 2
     EN: Accepted answer 2
   Feedback:
     SV: General feedback
     EN: General feedback
```

- Multiple `Svar:` blocks for alternative accepted answers
- Case-insensitive matching (`usecase=0`)
- Answers are plain text (not HTML) — Moodle compares directly to student input
- **Note:** Short answer responses are matched literally and are not language-aware. Provide all accepted variants explicitly. Multilingual spans are not used in answer fields.

### Numerical `[NUM]`

```
5. [NUM] Title
   SV: Question text
   EN: Question text
   Svar:
     SV: 3.14:0.01
     EN: 3.14:0.01
   Svar:
     SV: 10:0.5 km (100)
     EN: 10:0.5 km (100)
```

**Answer format:** `value:tolerance [unit] [(weight)]`

| Part | Example | Description |
|------|---------|-------------|
| `value` | `3.14` | The numeric answer |
| `:tolerance` | `:0.01` | Accepted error margin |
| `unit` | `km` | Optional unit name — shown to student via `showunits=1` |
| `(weight)` | `(100)` | Optional grade fraction |

If one or more answers include units, all unique units across the question are collected and emitted in the Moodle XML `<units>` block. This ensures consistent unit display in the quiz interface.

### Matching `[MATCH]`

```
6. [MATCH] Title
   SV: Question text
   EN: Question text
   Sweden -> Stockholm
   Norway -> Oslo
   -> Reykjavik
   Allmänt:
     SV: General feedback
     EN: General feedback
```

- `Left -> Right` pairs become subquestions
- `-> Right` (no left side) becomes a distractor
- Answer text supports multilingual spans for display in dropdowns

### Cloze / Embedded Answers `[CLOZE]`

```
7. [CLOZE] Title
   SV: Text with [correct|wrong1|wrong2] gaps
   EN: Text with [correct|wrong1|wrong2] gaps
   Allmänt:
     SV: General feedback
     EN: General feedback
```

- Gaps use `[correct|wrong1|wrong2]` syntax (square brackets, pipe-separated)
- **⚠️ Important:** The first option inside `[...]` is always treated as the correct answer. There is currently no syntax for explicitly marking correctness inside cloze gaps — this is a deliberate constraint for simplicity.
- Converted to Moodle's `{1:MULTICHOICE:=correct~wrong1~wrong2}` format
- All languages must have the same number of gaps
- **Note:** Cloze questions combined with multilang spans require the Moodle multilang filter to be enabled and correctly ordered. This works in standard Moodle setups.

---

## Multilingual Support

The tool supports any number of languages declared in the `languages:` header. All text fields are wrapped in Moodle's multilang filter syntax:

```xml
<span lang="sv" class="multilang">Swedish text</span>
<span lang="en" class="multilang">English text</span>
```

**Requirement:** Moodle must have the **Multilang content filter** enabled (Site administration → Plugins → Filters → Manage filters).

## CLI Flags Reference

| Flag | Default | Description |
|------|---------|-------------|
| `input` | — | Path to plain text quiz file |
| `-o, --output` | stdout | Write XML to file instead of stdout |
| `--encoding` | `utf-8` | Input file encoding |
| `--negative-mc-weights` | off | Allow negative fractions in multi-select MC (default: clamp wrong answers to 0) |
| `--lint` | off | Validate input and report all issues without generating XML |

## Lint Mode

Use `--lint` to validate your input file without generating XML. The linter runs all validation checks (collecting **every** issue, not just the first), plus additional analysis. Exits with code `0` if clean, `1` if issues found.

```bash
# Check a file for issues
python -m build_quiz questions.txt --lint
```

**Output levels:**

| Level | Prefix | Example |
|-------|--------|--------|
| `ERRORS` | ✗ | Missing required fields, invalid syntax, parser errors |
| `WARNINGS` | ⚠ | Duplicate short answer texts |
| `INFO` | ℹ | No feedback provided, few cloze distractors, long titles |

**Sample output:**

```
INFO:
  ℹ Q5: No feedback provided
  ℹ Q11: Cloze gap 2 has only 2 options
  ℹ Q11: No feedback provided

info=5
```

Lint checks include:
- All validation errors (language completeness, MC option counts, cloze gap parity, etc.)
- Duplicate short answer texts
- Multiple choice with ≤ 2 options
- Matching with only 1 pair
- Cloze gaps with ≤ 2 options
- Questions with no feedback
- Long question titles (> 80 characters)

## Moodle Import

1. In your Moodle course, go to **Question bank → Questions**
2. Click **Import**
3. Select **Moodle XML format**
4. Choose the generated `.xml` file
5. Click **Import**

The questions appear in the specified category (from the `category:` header).

## Output Format Notes

- **Encoding:** UTF-8 (declared in XML prolog)
- **Text format:** HTML with CDATA wrapping
- **Multilingual:** Uses `<span lang="xx" class="multilang">` for Moodle's multilang filter
- **MC fractions:** Normalized to sum to 100%. Wrong answers default to 0 (use `--negative-mc-weights` for negative scoring)
- **Numerical units:** Shown to students but not graded (`unitgradingtype=0`)
- **Penalties:** TF = `1.0`, all others = `0.3333333`

## Development

```bash
# Run directly
python -m build_quiz sample_plain.txt -o quiz.xml

# Verify XML structure
python3 -c "
import xml.etree.ElementTree as ET
tree = ET.parse('quiz.xml')
root = tree.getroot()
print(f'{len(root.findall(\"question\"))} questions')
"

# Install locally
pip install -e .
build-quiz sample_plain.txt -o quiz.xml
```

### Project Structure

```
build_quiz/
├── __init__.py
├── __main__.py          # python -m build_quiz entry
├── cli.py               # argparse CLI
├── core/
│   ├── __init__.py
│   ├── models.py        # AST dataclasses
│   ├── lexer.py         # Text → tokens
│   ├── parser.py        # Tokens → AST
│   ├── transformer.py   # Defaults & normalization
│   ├── validator.py     # AST validation
│   └── pipeline.py      # Pipeline orchestration
└── adapters/
    ├── __init__.py
    └── moodle.py        # AST → Moodle XML
```

## License

MIT
