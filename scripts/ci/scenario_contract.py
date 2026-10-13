"""Per-PR contract check for the CLI acceptance scenarios (no third-party dependency, no JDK).

Reads the Gherkin files under ``tests/scenarios`` with a small line-based reader and checks,
without running anything:

* every ``.feature`` file parses and every scenario has steps;
* every tag follows the vocabulary documented in ``tests/scenarios/README.md``;
* every step of a gating scenario (not ``@wip``, not ``@manual``) matches exactly one step
  definition. The step vocabulary is read from the Java sources
  (``acceptance-jvm/src/test/java/**/steps/*.java``); it is never duplicated here.

Unbound or ambiguous steps in a non-gating scenario are reported as ``info``.

Known limits of the step matcher (it models Cucumber expressions, not every Cucumber feature):

* ``{string}`` does not understand escaped quotes inside the quoted text (``"say \\"hi\\""``);
* ``^...$`` regular-expression step definitions are not supported: an expression that starts
  with ``^`` or ends with an unescaped ``$`` is reported as ``UNSUPPORTED_EXPRESSION``;
* only ``@Given``, ``@When`` and ``@Then`` annotations are read; ``@And`` and ``@But`` step
  definitions are not seen.

Usage::

    python -m scripts.ci.scenario_contract [--features DIR] [--steps DIR]

Exit status is 1 when any ``error`` problem is found, otherwise 0.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

from kernel.clock import parse_stamp

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_FEATURES = REPO_ROOT / "tests" / "scenarios"
DEFAULT_STEPS = REPO_ROOT / "acceptance-jvm" / "src" / "test" / "java"

ERROR = "error"
INFO = "info"

PARSE_ERROR = "PARSE_ERROR"
NO_STEPS = "NO_STEPS"
NO_EXAMPLES = "NO_EXAMPLES"
UNBOUND_STEP = "UNBOUND_STEP"
AMBIGUOUS_STEP = "AMBIGUOUS_STEP"
UNSUPPORTED_EXPRESSION = "UNSUPPORTED_EXPRESSION"
NO_STEP_DEFINITIONS = "NO_STEP_DEFINITIONS"
STEP_FILE_UNREADABLE = "STEP_FILE_UNREADABLE"
NO_FEATURES = "NO_FEATURES"
NO_GATING_SCENARIOS = "NO_GATING_SCENARIOS"
UNKNOWN_PREFIXED_TAG = "UNKNOWN_PREFIXED_TAG"
BAD_BARE_TAG = "BAD_BARE_TAG"
DUPLICATE_PROMISE = "DUPLICATE_PROMISE"
WIP_MISSING_OWNER = "WIP_MISSING_OWNER"
WIP_MISSING_SINCE = "WIP_MISSING_SINCE"

_ID_PATTERN = r"[A-Za-z0-9][A-Za-z0-9._-]*"
_ID_RE = re.compile(_ID_PATTERN)
_BARE_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_ISSUE_RE = re.compile(r"[1-9][0-9]*")
_DATE_RE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")

_STEP_KEYWORDS = ("Given", "When", "Then")
_STEP_LINE_RE = re.compile(r"^(Given|When|Then|And|But|\*)\s+(\S.*)$")
_FEATURE_RE = re.compile(r"^Feature:")
_RULE_RE = re.compile(r"^Rule:")
_BACKGROUND_RE = re.compile(r"^Background:")
_SCENARIO_RE = re.compile(r"^(?:Scenario|Example):\s*(.*)$")
_OUTLINE_RE = re.compile(r"^Scenario (?:Outline|Template):\s*(.*)$")
_EXAMPLES_RE = re.compile(r"^(?:Examples|Scenarios):")
_PLACEHOLDER_RE = re.compile(r"<([^<>]+)>")
_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
_DOC_DELIMITERS = ('"""', "```")

_JAVA_STEP_RE = re.compile(r'@(Given|When|Then)\("((?:[^"\\]|\\.)*)"\)')
_JAVA_ESCAPE_RE = re.compile(r"\\(u[0-9a-fA-F]{4}|.)", re.DOTALL)
_JAVA_SIMPLE_ESCAPES = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "b": "\b",
    "f": "\f",
    '"': '"',
    "'": "'",
    "\\": "\\",
}

_PARAMETER_TYPES = {
    "string": r"(?:\"[^\"]*\"|'[^']*')",
    "int": r"-?\d+",
    "word": r"[^\s]+",
}


@dataclass(frozen=True)
class Problem:
    """One finding. ``code`` is stable; ``severity`` is ``error`` or ``info``."""

    code: str
    severity: str
    file: str
    line: int
    message: str


@dataclass(frozen=True)
class Step:
    keyword: str
    text: str
    line: int


@dataclass(frozen=True)
class Scenario:
    file: str
    line: int
    name: str
    keyword: str
    tags: tuple[str, ...]
    steps: tuple[Step, ...]


@dataclass(frozen=True)
class StepDefinition:
    keyword: str
    expression: str
    source: str
    regex: re.Pattern[str]


class UnsupportedExpressionError(ValueError):
    """A Cucumber expression feature this check does not model."""


UnsupportedExpression = UnsupportedExpressionError


# ---------------------------------------------------------------------------
# Reader
# ---------------------------------------------------------------------------


@dataclass
class _Block:
    kind: str  # "background" | "scenario" | "outline"
    name: str
    line: int
    tags: tuple[str, ...] = ()
    steps: list[Step] = field(default_factory=list)
    tables: list[list[list[str]]] = field(default_factory=list)
    in_examples: bool = False
    last_keyword: str | None = None


def _split_cells(line: str) -> list[str]:
    inner = line.strip()
    inner = inner[1:] if inner.startswith("|") else inner
    inner = inner[:-1] if inner.endswith("|") and not inner.endswith("\\|") else inner
    return [cell.strip().replace("\\|", "|") for cell in _CELL_SPLIT_RE.split(inner)]


class _Reader:
    """Line-based Gherkin subset reader. One instance reads one file."""

    def __init__(self, file: str) -> None:
        self.file = file
        self.problems: list[Problem] = []
        self.scenarios: list[Scenario] = []
        self.feature_seen = False
        self.feature_tags: tuple[str, ...] = ()
        self.rule_tags: tuple[str, ...] = ()
        self.feature_background: list[Step] = []
        self.rule_background: list[Step] = []
        self.in_rule = False
        self.pending: list[str] = []
        self.current: _Block | None = None
        self.doc_delimiter: str | None = None
        self.doc_line = 0

    # -- problems ----------------------------------------------------------

    def error(self, code: str, line: int, message: str) -> None:
        self.problems.append(Problem(code, ERROR, self.file, line, message))

    def _take_pending(self) -> tuple[str, ...]:
        tags = tuple(self.pending)
        self.pending = []
        return tags

    def _reject_pending(self, line: int) -> None:
        if self.pending:
            self.error(PARSE_ERROR, line, "tags must be followed by Feature, Rule, Scenario or Examples")
            self.pending = []

    # -- driver ------------------------------------------------------------

    def read(self, text: str) -> None:
        for number, raw in enumerate(text.splitlines(), start=1):
            self.line(number, raw.strip())
        self._finish()

    def _finish(self) -> None:
        if self.doc_delimiter is not None:
            self.error(PARSE_ERROR, self.doc_line, "doc string is never closed")
        self._reject_pending(self.doc_line or 1)
        self._close_block()
        if not self.feature_seen:
            self.error(PARSE_ERROR, 1, "no Feature line found")

    def line(self, number: int, stripped: str) -> None:
        if self.doc_delimiter is not None:
            if stripped.startswith(self.doc_delimiter):
                self.doc_delimiter = None
            return
        if not stripped or stripped.startswith("#"):
            return
        handler = self._classify(stripped)
        handler(number, stripped)

    def _classify(self, stripped: str) -> Callable[[int, str], None]:
        if stripped.startswith("@"):
            return self._on_tags
        if stripped.startswith("|"):
            return self._on_row
        if stripped.startswith(_DOC_DELIMITERS):
            return self._on_doc_string
        for pattern, handler in self._structural():
            if pattern.match(stripped):
                return handler
        if _STEP_LINE_RE.match(stripped):
            return self._on_step
        return self._on_text

    def _structural(self) -> list[tuple[re.Pattern[str], Callable[[int, str], None]]]:
        return [
            (_FEATURE_RE, self._on_feature),
            (_RULE_RE, self._on_rule),
            (_BACKGROUND_RE, self._on_background),
            (_OUTLINE_RE, self._on_outline),
            (_SCENARIO_RE, self._on_scenario),
            (_EXAMPLES_RE, self._on_examples),
        ]

    # -- handlers ----------------------------------------------------------

    def _on_tags(self, number: int, stripped: str) -> None:
        for token in stripped.split():
            if token.startswith("#"):
                break
            if token.startswith("@") and len(token) > 1:
                self.pending.append(token[1:])
            else:
                self.error(PARSE_ERROR, number, f"malformed tag {token!r}")

    def _on_feature(self, number: int, _stripped: str) -> None:
        if self.feature_seen:
            self.error(PARSE_ERROR, number, "a second Feature line in one file")
            self._reject_pending(number)
            return
        self.feature_seen = True
        self.feature_tags = self._take_pending()

    def _require_feature(self, number: int) -> bool:
        if not self.feature_seen:
            self.error(PARSE_ERROR, number, "content before the Feature line")
            self.pending = []
        return self.feature_seen

    def _on_rule(self, number: int, _stripped: str) -> None:
        if not self._require_feature(number):
            return
        self._close_block()
        self.rule_tags = self._take_pending()
        self.rule_background = []
        self.in_rule = True

    def _on_background(self, number: int, _stripped: str) -> None:
        if not self._require_feature(number):
            return
        self._close_block()
        self._reject_pending(number)
        self.current = _Block("background", "Background", number)

    def _open_scenario(self, kind: str, number: int, stripped: str) -> None:
        if not self._require_feature(number):
            return
        self._close_block()
        name = stripped.split(":", 1)[1].strip()
        tags = self.feature_tags + self.rule_tags + self._take_pending()
        self.current = _Block(kind, name, number, tags)

    def _on_scenario(self, number: int, stripped: str) -> None:
        self._open_scenario("scenario", number, stripped)

    def _on_outline(self, number: int, stripped: str) -> None:
        self._open_scenario("outline", number, stripped)

    def _on_examples(self, number: int, _stripped: str) -> None:
        self.pending = []
        block = self.current
        if block is None or block.kind != "outline":
            self.error(PARSE_ERROR, number, "Examples outside a Scenario Outline")
            return
        block.in_examples = True
        block.tables.append([])

    def _on_step(self, number: int, stripped: str) -> None:
        self._reject_pending(number)
        block = self.current
        if block is None and self.feature_seen:
            return  # directly under Feature: or Rule: this is description text, not a step
        if block is None or block.in_examples:
            self.error(PARSE_ERROR, number, "step outside a Scenario, Scenario Outline or Background")
            return
        match = _STEP_LINE_RE.match(stripped)
        assert match is not None  # _classify only routes matching lines here
        word, text = match.group(1), match.group(2)
        if word in _STEP_KEYWORDS:
            block.last_keyword = word
        elif block.last_keyword is None and word == "*":
            block.last_keyword = "*"  # a bare bullet may open a scenario; matching ignores keywords
        elif block.last_keyword is None:
            self.error(PARSE_ERROR, number, f"{word!r} step has no preceding Given, When or Then")
            return
        assert block.last_keyword is not None
        block.steps.append(Step(block.last_keyword, text, number))

    def _on_row(self, number: int, stripped: str) -> None:
        block = self.current
        if block is not None and block.in_examples:
            block.tables[-1].append(_split_cells(stripped))
            return
        if block is None or not block.steps:
            self.error(PARSE_ERROR, number, "table row without a preceding step")

    def _on_doc_string(self, number: int, stripped: str) -> None:
        block = self.current
        if block is None or block.in_examples or not block.steps:
            self.error(PARSE_ERROR, number, "doc string without a preceding step")
            return
        self.doc_delimiter = stripped[:3]
        self.doc_line = number

    def _on_text(self, number: int, stripped: str) -> None:
        self._reject_pending(number)
        block = self.current
        description_allowed = self.feature_seen and (block is None or self._in_description(block))
        if not description_allowed:
            self.error(PARSE_ERROR, number, f"unparseable line {stripped!r}")

    @staticmethod
    def _in_description(block: _Block) -> bool:
        """Free text is description before a block's first step, or under Examples: before its rows."""
        if block.in_examples:
            return not block.tables[-1]
        return not block.steps

    # -- block completion --------------------------------------------------

    def _close_block(self) -> None:
        block, self.current = self.current, None
        if block is None:
            return
        if block.kind == "background":
            target = self.feature_background if not self.in_rule else self.rule_background
            target.extend(block.steps)
            return
        if not block.steps:
            self.error(NO_STEPS, block.line, f"scenario {block.name!r} has no steps")
        base = tuple(self.feature_background + self.rule_background)
        if block.kind == "scenario":
            self._emit(block, "Scenario", base + tuple(block.steps))
        else:
            self._emit_outline(block, base)

    def _emit(self, block: _Block, keyword: str, steps: tuple[Step, ...]) -> None:
        self.scenarios.append(Scenario(self.file, block.line, block.name, keyword, block.tags, steps))

    def _emit_outline(self, block: _Block, base: tuple[Step, ...]) -> None:
        rows = self._outline_rows(block)
        if not rows:
            self.error(NO_EXAMPLES, block.line, f"scenario outline {block.name!r} has no Examples rows")
            self._emit(block, "Scenario Outline", base + tuple(block.steps))
            return
        for values in rows:
            expanded = tuple(Step(s.keyword, _substitute(s.text, values), s.line) for s in block.steps)
            self._emit(block, "Scenario Outline", base + expanded)

    def _outline_rows(self, block: _Block) -> list[dict[str, str]]:
        rows: list[dict[str, str]] = []
        for table in block.tables:
            if not table:
                self.error(PARSE_ERROR, block.line, "Examples without a header row")
                continue
            header = table[0]
            for cells in table[1:]:
                if len(cells) != len(header):
                    self.error(PARSE_ERROR, block.line, f"Examples row has {len(cells)} cells, header has {len(header)}")
                    continue
                rows.append(dict(zip(header, cells, strict=True)))
        return rows


def _substitute(text: str, values: dict[str, str]) -> str:
    return _PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), text)


def parse_feature_text(text: str, file: str) -> tuple[list[Scenario], list[Problem]]:
    """Parse Gherkin ``text``; outlines are expanded and Background steps prepended."""
    reader = _Reader(file)
    reader.read(text)
    return reader.scenarios, reader.problems


def parse_feature(path: Path) -> tuple[list[Scenario], list[Problem]]:
    """Read and parse one ``.feature`` file."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [], [Problem(PARSE_ERROR, ERROR, str(path), 1, f"cannot read file: {exc}")]
    return parse_feature_text(text, str(path))


# ---------------------------------------------------------------------------
# Tag vocabulary
# ---------------------------------------------------------------------------


def _valid_date(value: str) -> bool:
    if not _DATE_RE.fullmatch(value):
        return False
    try:
        parse_stamp(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _matches(pattern: re.Pattern[str]) -> Callable[[str], bool]:
    return lambda value: pattern.fullmatch(value) is not None


# prefix -> (value check, problem code, expectation shown to the author)
_VALUE_RULES: dict[str, tuple[Callable[[str], bool], str, str]] = {
    "promise": (_matches(_ID_RE), "BAD_PROMISE_ID", f"an id matching {_ID_PATTERN}"),
    "wip-owner": (_matches(_ID_RE), "BAD_WIP_OWNER", f"a handle matching {_ID_PATTERN}"),
    "wip-since": (_valid_date, "BAD_WIP_SINCE", "a valid date as YYYY-MM-DD"),
    "defect": (_matches(_ISSUE_RE), "BAD_DEFECT", "a positive integer issue number"),
    "qa": (_matches(_ID_RE), "BAD_QA_REF", f"a reference matching {_ID_PATTERN}"),
}
_PLAIN_TAGS = frozenset({"wip", "manual"})


def is_gating(scenario: Scenario) -> bool:
    """A scenario gates the nightly unless it is ``@wip`` or ``@manual``."""
    return not (_PLAIN_TAGS & set(scenario.tags))


def _tag_problem(scenario: Scenario, code: str, message: str) -> Problem:
    return Problem(code, ERROR, scenario.file, scenario.line, message)


def _check_one_tag(scenario: Scenario, tag: str) -> Problem | None:
    prefix, colon, value = tag.partition(":")
    if not colon:
        if tag in _PLAIN_TAGS or _BARE_RE.fullmatch(tag):
            return None
        return _tag_problem(scenario, BAD_BARE_TAG, f"bare tag @{tag} must match {_BARE_RE.pattern}")
    rule = _VALUE_RULES.get(prefix)
    if rule is None:
        return _tag_problem(scenario, UNKNOWN_PREFIXED_TAG, f"unknown prefixed tag @{tag}")
    check, code, expectation = rule
    if check(value):
        return None
    return _tag_problem(scenario, code, f"@{tag}: expected {expectation}")


def _values(tags: Sequence[str], prefix: str) -> list[str]:
    return [t.partition(":")[2] for t in tags if t.partition(":")[0] == prefix and ":" in t]


def _check_duplicate_promises(scenario: Scenario) -> list[Problem]:
    seen: set[str] = set()
    reported: set[str] = set()
    problems: list[Problem] = []
    for value in _values(scenario.tags, "promise"):
        if value in seen and value not in reported:
            reported.add(value)
            problems.append(_tag_problem(scenario, DUPLICATE_PROMISE, f"@promise:{value} is repeated"))
        seen.add(value)
    return problems


def _check_wip(scenario: Scenario) -> list[Problem]:
    if "wip" not in scenario.tags:
        return []
    problems: list[Problem] = []
    if not _values(scenario.tags, "wip-owner"):
        problems.append(_tag_problem(scenario, WIP_MISSING_OWNER, "@wip needs @wip-owner:<handle>"))
    if not _values(scenario.tags, "wip-since"):
        problems.append(_tag_problem(scenario, WIP_MISSING_SINCE, "@wip needs @wip-since:<YYYY-MM-DD>"))
    return problems


def validate_tags(scenario: Scenario) -> list[Problem]:
    """Check ``scenario.tags`` (own plus inherited) against the documented vocabulary."""
    problems = [p for p in (_check_one_tag(scenario, t) for t in scenario.tags) if p is not None]
    return problems + _check_duplicate_promises(scenario) + _check_wip(scenario)


# ---------------------------------------------------------------------------
# Step definitions (read from the Java sources) and matching
# ---------------------------------------------------------------------------


def decode_java_string(raw: str) -> str:
    """Decode the escapes of a Java string literal body; unknown escapes are kept verbatim."""

    def replace(match: re.Match[str]) -> str:
        token = match.group(1)
        if len(token) == 5 and token[0] == "u":
            return chr(int(token[1:], 16))
        return _JAVA_SIMPLE_ESCAPES.get(token, match.group(0))

    return _JAVA_ESCAPE_RE.sub(replace, raw)


def _unsupported(expression: str, what: str) -> UnsupportedExpressionError:
    return UnsupportedExpressionError(
        f"{what} in step expression {expression!r} is not supported by the contract check; "
        "use {string}, {int} or {word}, or escape the character with a backslash"
    )


def _parameter(expression: str, index: int) -> tuple[str, int]:
    end = expression.find("}", index)
    name = expression[index + 1 : end] if end != -1 else ""
    pattern = _PARAMETER_TYPES.get(name)
    if pattern is None:
        raise _unsupported(expression, f"parameter type {{{name}}}" if end != -1 else "unterminated '{'")
    return pattern, end + 1


def _ends_with_unescaped_dollar(expression: str) -> bool:
    if not expression.endswith("$"):
        return False
    backslashes = len(expression) - 1 - len(expression[:-1].rstrip("\\"))
    return backslashes % 2 == 0


def expression_to_regex(expression: str) -> re.Pattern[str]:
    """Translate a Cucumber expression to a regex; use ``fullmatch`` on step text."""
    if expression.startswith("^") or _ends_with_unescaped_dollar(expression):
        raise _unsupported(expression, "regular expression anchor ('^...$' step definitions are not Cucumber expressions)")
    parts: list[str] = []
    index = 0
    while index < len(expression):
        char = expression[index]
        if char == "\\" and index + 1 < len(expression):
            parts.append(re.escape(expression[index + 1]))
            index += 2
        elif char == "{":
            pattern, index = _parameter(expression, index)
            parts.append(pattern)
        elif char in "()/":
            what = "alternation '/'" if char == "/" else "optional text '(...)'"
            raise _unsupported(expression, what)
        else:
            parts.append(re.escape(char))
            index += 1
    return re.compile("".join(parts))


def _step_files(steps_dir: Path) -> list[Path]:
    return sorted(p for p in steps_dir.rglob("*.java") if p.parent.name == "steps" or p.parent == steps_dir)


def _definitions_in(path: Path) -> tuple[list[StepDefinition], list[Problem], bool]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return [], [Problem(STEP_FILE_UNREADABLE, ERROR, str(path), 1, f"cannot read file: {exc}")], False
    defs: list[StepDefinition] = []
    problems: list[Problem] = []
    found = False
    for match in _JAVA_STEP_RE.finditer(text):
        found = True
        line = text.count("\n", 0, match.start()) + 1
        expression = decode_java_string(match.group(2))
        try:
            regex = expression_to_regex(expression)
        except UnsupportedExpressionError as exc:
            problems.append(Problem(UNSUPPORTED_EXPRESSION, ERROR, str(path), line, str(exc)))
            continue
        defs.append(StepDefinition(match.group(1), expression, f"{path.name}:{line}", regex))
    return defs, problems, found


def load_step_definitions(steps_dir: Path) -> tuple[list[StepDefinition], list[Problem]]:
    """Read ``@Given/@When/@Then`` annotations from ``steps/*.java`` under ``steps_dir``."""
    defs: list[StepDefinition] = []
    problems: list[Problem] = []
    found_any = False
    for path in _step_files(steps_dir):
        file_defs, file_problems, found = _definitions_in(path)
        defs += file_defs
        problems += file_problems
        found_any = found_any or found
    if not found_any:
        problems.append(Problem(NO_STEP_DEFINITIONS, ERROR, str(steps_dir), 1, "no @Given/@When/@Then step definitions found"))
    return defs, problems


def match_steps(scenario: Scenario, definitions: Sequence[StepDefinition]) -> list[Problem]:
    """Report steps that match no definition or more than one (keywords are ignored)."""
    severity = ERROR if is_gating(scenario) else INFO
    problems: list[Problem] = []
    for step in scenario.steps:
        hits = [d for d in definitions if d.regex.fullmatch(step.text)]
        if len(hits) == 1:
            continue
        if not hits:
            problems.append(Problem(UNBOUND_STEP, severity, scenario.file, step.line, f"no step definition matches {step.text!r}"))
        else:
            sources = ", ".join(d.source for d in hits)
            problems.append(Problem(AMBIGUOUS_STEP, severity, scenario.file, step.line, f"{step.text!r} matches {len(hits)} step definitions: {sources}"))
    return problems


# ---------------------------------------------------------------------------
# Checks, output and entry point
# ---------------------------------------------------------------------------


def _dedupe(problems: Sequence[Problem]) -> list[Problem]:
    seen: set[Problem] = set()
    unique: list[Problem] = []
    for problem in problems:
        if problem not in seen:
            seen.add(problem)
            unique.append(problem)
    return unique


def _check_parsed(scenarios: Sequence[Scenario], definitions: Sequence[StepDefinition]) -> list[Problem]:
    problems: list[Problem] = []
    for scenario in scenarios:
        problems += validate_tags(scenario)
        problems += match_steps(scenario, definitions)
    return problems


def check_feature_file(path: Path, definitions: Sequence[StepDefinition]) -> list[Problem]:
    """Parse, tag-check and step-match one ``.feature`` file."""
    scenarios, problems = parse_feature(path)
    return _dedupe(problems + _check_parsed(scenarios, definitions))


def check_tree(features_dir: Path, steps_dir: Path) -> list[Problem]:
    """Check every ``.feature`` file under ``features_dir`` against the Java step definitions."""
    definitions, problems = load_step_definitions(steps_dir)
    files = sorted(features_dir.rglob("*.feature"))
    if not files:
        problems.append(Problem(NO_FEATURES, ERROR, str(features_dir), 1, "no .feature files found"))
    gating = 0
    for path in files:
        scenarios, parse_problems = parse_feature(path)
        gating += sum(1 for s in scenarios if is_gating(s))
        problems += parse_problems + _check_parsed(scenarios, definitions)
    if files and gating == 0:
        problems.append(Problem(NO_GATING_SCENARIOS, ERROR, str(features_dir), 1, "no scenario gates the nightly (all are @wip or @manual)"))
    return _dedupe(problems)


def format_problems(problems: Sequence[Problem]) -> str:
    return "\n".join(f"{p.file}:{p.line}: {p.severity} {p.code}: {p.message}" for p in problems)


def _parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="scenario_contract", description=__doc__.split("\n\n")[0] if __doc__ else None)
    parser.add_argument("--features", type=Path, default=DEFAULT_FEATURES, help="directory of .feature files")
    parser.add_argument("--steps", type=Path, default=DEFAULT_STEPS, help="directory holding the Java step definitions")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = _parse_args(argv)
    problems = check_tree(args.features, args.steps)
    if problems:
        print(format_problems(problems))
    errors = sum(1 for p in problems if p.severity == ERROR)
    infos = len(problems) - errors
    if errors:
        print(f"scenario contract: {errors} error(s), {infos} info")
        return 1
    print(f"scenario contract: ok ({infos} info)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
