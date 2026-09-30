#!/usr/bin/env python3
"""Style guard for the changelog's ``## [Unreleased]`` section (issue #5426).

Keeps the Unreleased section in the house shape: the six ``###`` headings in order, entries that
lead with a bold headline and show what changed, no internal tokens, and bounded length. It reads
only the Unreleased section; released sections are never restyled.

Run it from the repository root::

    python -m scripts.docs.check_changelog_style [--changelog PATH]

A relative ``--changelog`` resolves against the repository root, like ``check_spelling``'s
``--repo-root``, so the result does not depend on the working directory.

Exit codes: ``0`` no error findings (warnings may print), ``1`` one or more error findings,
``2`` usage error or unreadable file. See ``contracts/check-cli.md`` in mission
``docs-lint-codespell-changelog-guard-01M3RFGJ``.

Standard library only. The Unreleased section is located by the shared
:func:`scripts.release.validate_release.unreleased_section`, so this guard and the spelling check
can never disagree about where the section starts or ends.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal

from scripts.release.validate_release import UnreleasedSection, unreleased_section

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
DEFAULT_CHANGELOG: Final[Path] = REPO_ROOT / "docs" / "changelog" / "CHANGELOG.md"

Severity = Literal["error", "warning"]

_EXCERPT_LIMIT: Final[int] = 60
_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^(#{3,4})\s+(.*?)\s*$")
_NESTED_BULLET_RE: Final[re.Pattern[str]] = re.compile(r"^(\s{2,})- ")
_FOREIGN_BULLET_RE: Final[re.Pattern[str]] = re.compile(r"^[*+]\s")
_HEADLINE_RE: Final[re.Pattern[str]] = re.compile(r"^- \*\*(.+?)\*\*", re.DOTALL)
_CODE_SPAN_RE: Final[re.Pattern[str]] = re.compile(r"`[^`]*`")
_FENCE: Final[str] = "```"
_REF: Final[str] = r"(?:[\w.-]+/[\w.-]+)?#\d+"
_REFS_RE: Final[re.Pattern[str]] = re.compile(rf"^\s*\(\s*{_REF}(?:\s*,\s*{_REF})*\s*\)")
_ISSUE_REF_RE: Final[re.Pattern[str]] = re.compile(r"#\d+")
_SENTENCE_BREAK_RE: Final[re.Pattern[str]] = re.compile(r"(?<=[.!?])\s+")
_BEFORE: Final[str] = "**Before:**"
_WHY: Final[str] = "**Why:**"
_AFTER: Final[str] = "**After:**"
_HEADLINE_SECTIONS: Final[frozenset[str]] = frozenset({"Breaking", "Upgrade Notes", "Added", "Changed", "Fixed"})
_CONTRAST_SECTIONS: Final[frozenset[str]] = frozenset({"Breaking", "Changed", "Fixed"})
_INTERNAL: Final[str] = "Internal"
_CONTRAST_MAX_SENTENCES: Final[int] = 2
_CONTRAST_MAX_CHARS: Final[int] = 300
LENGTH_ERROR_LIMIT: Final[int] = 1200
LENGTH_WARNING_LIMIT: Final[int] = 900
_NESTED_EXCERPT_LIMIT: Final[int] = 40


@dataclass(frozen=True)
class Finding:
    """One guard finding. Only ``error`` severity affects the exit code."""

    severity: Severity
    rule: str
    path: str
    line: int
    where: str
    fix: str

    @property
    def sort_key(self) -> tuple[str, int, str, str, str]:
        """Deterministic order: ``(path, line, rule)``, with ties broken by text (NFR-003)."""
        return (self.path, self.line, self.rule, self.where, self.fix)


@dataclass(frozen=True)
class Entry:
    """One top-level ``- `` bullet of the Unreleased section."""

    section: str
    subsection: str | None
    line: int
    lines: tuple[str, ...]
    nested: tuple[tuple[str, ...], ...]
    nested_lines: tuple[int, ...]
    headline: str | None
    numbered: tuple[tuple[int, str], ...] = ()


@dataclass(frozen=True)
class Heading:
    """A ``###`` or ``####`` heading of the Unreleased section."""

    level: int
    text: str
    line: int


@dataclass(frozen=True)
class Orphan:
    """A non-blank line under a heading that sits before that heading's first bullet."""

    section: str
    line: int
    text: str


@dataclass(frozen=True)
class ForeignBullet:
    """A line that opens a ``* `` or ``+ `` bullet; ``section`` is ``None`` in the preamble."""

    section: str | None
    line: int
    text: str


@dataclass(frozen=True)
class ParsedSection:
    """The Unreleased section split into preamble, headings, entries and the lines no entry owns."""

    preamble: tuple[tuple[int, str], ...]
    headings: tuple[Heading, ...]
    entries: tuple[Entry, ...]
    orphans: tuple[Orphan, ...] = ()
    foreign_bullets: tuple[ForeignBullet, ...] = ()


@dataclass
class _EntryDraft:
    """Mutable accumulator for the entry currently being parsed."""

    section: str
    subsection: str | None
    line: int
    lines: list[str]
    nested: list[list[str]]
    nested_lines: list[int]
    nested_indent: int | None = None
    numbered: list[tuple[int, str]] = field(default_factory=list)

    def add(self, number: int, text: str) -> None:
        """Attach *text* (file line *number*) to the entry or to its open nested item."""
        self.numbered.append((number, text))
        nested = _NESTED_BULLET_RE.match(text)
        if nested is not None and (self.nested_indent is None or len(nested.group(1)) <= self.nested_indent):
            self.nested_indent = len(nested.group(1))
            self.nested.append([text])
            self.nested_lines.append(number)
        elif self.nested and (nested is not None or len(text) - len(text.lstrip()) >= 2):
            self.nested[-1].append(text)
        else:
            self.lines.append(text)

    def freeze(self) -> Entry:
        joined = "\n".join(self.lines)
        headline = _HEADLINE_RE.match(joined)
        return Entry(
            section=self.section,
            subsection=self.subsection,
            line=self.line,
            lines=tuple(self.lines),
            nested=tuple(tuple(item) for item in self.nested),
            nested_lines=tuple(self.nested_lines),
            headline=headline.group(1) if headline else None,
            numbered=tuple(self.numbered),
        )


class _SectionParser:
    """Line-by-line state machine that builds a :class:`ParsedSection`."""

    def __init__(self) -> None:
        self.preamble: list[tuple[int, str]] = []
        self.headings: list[Heading] = []
        self.entries: list[Entry] = []
        self.orphans: list[Orphan] = []
        self.foreign_bullets: list[ForeignBullet] = []
        self._section: str | None = None
        self._subsection: str | None = None
        self._draft: _EntryDraft | None = None
        self._in_fence = False

    def feed(self, number: int, text: str) -> None:
        if text.lstrip().startswith(_FENCE):
            self._in_fence = not self._in_fence
            self._attach(number, text)
        elif self._in_fence:
            self._attach(number, text)
        elif (heading := _HEADING_RE.match(text)) is not None:
            self._start_heading(number, heading)
        elif text.startswith("- "):
            self._start_entry(number, text)
        elif _FOREIGN_BULLET_RE.match(text):
            self.foreign_bullets.append(ForeignBullet(self._section, number, text))
            self._attach(number, text)
        elif text.strip():
            self._attach(number, text)
        elif self._section is None:
            self.preamble.append((number, text))

    def finish(self) -> ParsedSection:
        self._close_entry()
        return ParsedSection(
            tuple(self.preamble),
            tuple(self.headings),
            tuple(self.entries),
            tuple(self.orphans),
            tuple(self.foreign_bullets),
        )

    def _attach(self, number: int, text: str) -> None:
        if self._draft is not None:
            self._draft.add(number, text)
        elif self._section is None:
            self.preamble.append((number, text))
        else:
            self.orphans.append(Orphan(self._section, number, text))

    def _start_heading(self, number: int, match: re.Match[str]) -> None:
        self._close_entry()
        level, title = len(match.group(1)), match.group(2)
        self.headings.append(Heading(level, title, number))
        if level == 3:
            self._section, self._subsection = title, None
        else:
            self._subsection = title

    def _start_entry(self, number: int, text: str) -> None:
        self._close_entry()
        if self._section is None:
            self.preamble.append((number, text))
            return
        self._draft = _EntryDraft(self._section, self._subsection, number, [text], [], [], numbered=[(number, text)])

    def _close_entry(self) -> None:
        if self._draft is not None:
            self.entries.append(self._draft.freeze())
            self._draft = None


def parse_section(section: UnreleasedSection) -> ParsedSection:
    """Split *section* into preamble, headings and entries, with real file line numbers."""
    parser = _SectionParser()
    for offset, text in enumerate(section.lines, start=1):
        parser.feed(section.start_line + offset, text)
    return parser.finish()


def _strip_code_spans(text: str) -> str:
    """Blank out ``code spans`` with spaces (newlines kept) so offsets and line counts survive."""
    return _CODE_SPAN_RE.sub(lambda match: re.sub(r"[^\n]", " ", match.group(0)), text)


def excerpt(entry: Entry) -> str:
    """The entry's headline (or first line), shortened to at most 60 characters."""
    text = entry.headline if entry.headline is not None else entry.lines[0].removeprefix("- ").strip()
    return text if len(text) <= _EXCERPT_LIMIT else text[: _EXCERPT_LIMIT - 1] + "…"


def entry_where(entry: Entry) -> str:
    """The ``[<section>] <headline excerpt>`` locator used in every entry finding."""
    return f"[{entry.section}] {excerpt(entry)}"


SECTION_ORDER: Final[tuple[str, ...]] = ("Breaking", "Upgrade Notes", "Added", "Changed", "Fixed", "Internal")
_SUBHEADING_HOME: Final[str] = "Fixed"
_ORDER_TEXT: Final[str] = ", ".join(SECTION_ORDER)


def _error(rule: str, path: str, line: int, where: str, fix: str) -> Finding:
    return Finding("error", rule, path, line, where, fix)


def _heading_where(heading: Heading) -> str:
    return f"[{heading.text}] {'#' * heading.level} {heading.text}"


def _check_section_heading(heading: Heading, seen: dict[str, int], path: str) -> list[Finding]:
    """FR-008 for one ``###`` heading; records the first line of each valid heading in *seen*."""
    where = _heading_where(heading)
    if heading.text not in SECTION_ORDER:
        return [_error("heading-unknown", path, heading.line, where, f"Use one of: {_ORDER_TEXT}.")]
    if heading.text in seen:
        fix = f"Merge this `### {heading.text}` into the earlier one at line {seen[heading.text]}."
        return [_error("heading-duplicate", path, heading.line, where, fix)]
    rank = SECTION_ORDER.index(heading.text)
    later = sorted((name for name in seen if SECTION_ORDER.index(name) > rank), key=SECTION_ORDER.index)
    seen[heading.text] = heading.line
    if not later:
        return []
    fix = f"Move `### {heading.text}` above `### {later[0]}`; required order: {_ORDER_TEXT}."
    return [_error("heading-order", path, heading.line, where, fix)]


def _check_subheading(heading: Heading, parent: str | None, seen: dict[str, int], path: str) -> list[Finding]:
    """FR-008 for one ``####`` heading: allowed only under ``### Fixed``, unique within it."""
    where = _heading_where(heading)
    if parent != _SUBHEADING_HOME:
        fix = f"Use `####` only under `### {_SUBHEADING_HOME}`; remove it or move the entries into `### {_SUBHEADING_HOME}`."
        return [_error("subheading-placement", path, heading.line, where, fix)]
    if heading.text in seen:
        fix = f"Merge this `#### {heading.text}` into the earlier one at line {seen[heading.text]}."
        return [_error("heading-duplicate", path, heading.line, where, fix)]
    seen[heading.text] = heading.line
    return []


def check_headings(parsed: ParsedSection, path: str) -> list[Finding]:
    """FR-008: the ``###`` set, order and uniqueness, and where ``####`` may appear."""
    findings: list[Finding] = []
    sections: dict[str, int] = {}
    subsections: dict[str, int] = {}
    parent: str | None = None
    for heading in parsed.headings:
        if heading.level == 3:
            findings.extend(_check_section_heading(heading, sections, path))
            parent = heading.text
            subsections = {}
        else:
            findings.extend(_check_subheading(heading, parent, subsections, path))
    return findings


def _entry_finding(rule: str, entry: Entry, path: str, fix: str) -> Finding:
    return _error(rule, path, entry.line, entry_where(entry), fix)


def _entry_text(entry: Entry) -> str:
    """The entry's own lines joined with newlines (nested items excluded)."""
    return "\n".join(entry.lines)


def _full_text(entry: Entry) -> str:
    """The entry's own lines plus every nested item's lines."""
    return "\n".join([*entry.lines, *(line for item in entry.nested for line in item)])


def _body(entry: Entry) -> str:
    """The entry's own text after the bold headline and the reference group."""
    text = " ".join(line.strip() for line in entry.lines)
    headline = _HEADLINE_RE.match(text)
    if headline is not None:
        text = text[headline.end() :]
    text = _REFS_RE.sub("", text, count=1)
    return text.lstrip(". \t").strip()


def _sentence_count(text: str) -> int:
    """Count sentences as runs of text split on ``.``, ``!`` or ``?`` followed by whitespace."""
    return sum(1 for part in _SENTENCE_BREAK_RE.split(text.strip()) if part)


def check_headline(entry: Entry, path: str) -> list[Finding]:
    """FR-009 (a): entries in the first five sections lead with a bold headline."""
    if entry.section not in _HEADLINE_SECTIONS or entry.headline is not None:
        return []
    fix = "Start the entry with a bold headline: `- **What changed** (#1234).`"
    return [_entry_finding("headline-missing", entry, path, fix)]


def check_refs_in_bold(entry: Entry, path: str) -> list[Finding]:
    """FR-009 (a): an issue reference belongs after the bold headline, never inside it."""
    if entry.headline is None:
        return []
    refs = _ISSUE_REF_RE.findall(_strip_code_spans(entry.headline))
    if not refs:
        return []
    group = ", ".join(refs)
    fix = f"Move `({group})` out of the bold headline: `- **Headline** ({group}).`"
    return [_entry_finding("refs-in-bold", entry, path, fix)]


def _has_contrast(entry: Entry) -> bool:
    text = _full_text(entry)
    if _BEFORE in text or (_WHY in text and _AFTER in text):
        return True
    body = _body(entry)
    return _sentence_count(_strip_code_spans(body)) <= _CONTRAST_MAX_SENTENCES and len(body) <= _CONTRAST_MAX_CHARS


def check_contrast(entry: Entry, path: str) -> list[Finding]:
    """FR-009 (b): Breaking, Changed and Fixed entries show the old behavior or stay short."""
    if entry.section not in _CONTRAST_SECTIONS or _has_contrast(entry):
        return []
    fix = (
        f"Add a `{_BEFORE}` sentence describing the old behavior "
        f"(or shorten the body to at most {_CONTRAST_MAX_SENTENCES} sentences / {_CONTRAST_MAX_CHARS} characters)."
    )
    return [_entry_finding("contrast-missing", entry, path, fix)]


def check_internal_shape(entry: Entry, path: str) -> list[Finding]:
    """FR-009 (c): an Internal entry is one physical line, with no nested items or contrast."""
    if entry.section != _INTERNAL:
        return []
    if len(entry.lines) == 1 and not entry.nested and _BEFORE not in _entry_text(entry):
        return []
    fix = "Keep Internal entries to one line; move user-visible detail to Changed or Fixed."
    return [_entry_finding("internal-shape", entry, path, fix)]


@dataclass(frozen=True)
class _BannedToken:
    """One FR-010 token: where it is matched, what it is, and how to fix it."""

    name: str
    pattern: re.Pattern[str]
    outside_code_spans: bool
    fix: str
    exempt_with: str | None = None


_MATCH_SLOT: Final[str] = "{token}"
_RENAME_TARGET: Final[str] = "spec-kitty consolidate"
_BANNED_TOKENS: Final[tuple[_BannedToken, ...]] = (
    _BannedToken(
        "boilerplate",
        re.compile(r"Bug-fix\s*[;\u2014\u2013-]\s*no CLI version bump"),
        False,
        "Delete the boilerplate; the section heading already says it is a fix.",
    ),
    _BannedToken(
        "requirement id",
        re.compile(r"\b(?:FR|NFR|SC|C|D)-\d+[a-z]?(?:\.\d+)?\b"),
        True,
        f"Describe the behavior instead of citing internal requirement `{_MATCH_SLOT}`; put an ID in backticks only when quoting CLI output.",
    ),
    _BannedToken(
        "ULID",
        re.compile(r"\b[0-7][0-9A-HJKMNP-TV-Z]{25}\b"),
        False,
        "Remove the mission/event ULID; link the issue instead.",
    ),
    _BannedToken(
        "evidence path",
        re.compile(re.escape(".kittify/evidence/")),
        False,
        "Remove the local evidence path; it is not reachable by users.",
    ),
    _BannedToken("planning ref", re.compile(r"planning#"), False, "Remove the private planning-repo reference."),
    _BannedToken(
        "all-caps",
        re.compile(r"\b(?:DEFAULT|REFUSE|FAIL)\b"),
        True,
        "Write `default`/`refuses`/`fails` in lowercase prose, or put the literal CLI token in backticks.",
    ),
    _BannedToken(
        "retired command",
        re.compile(r"spec-kitty merge(?![-\w])"),
        False,
        f"Use `{_RENAME_TARGET}`; `spec-kitty merge` was renamed (only the rename entry may name it).",
        exempt_with=_RENAME_TARGET,
    ),
)


@dataclass(frozen=True)
class _Unit:
    """A run of numbered lines judged together: one entry, or one preamble paragraph."""

    where: str
    lines: tuple[tuple[int, str], ...]


def _preamble_units(preamble: tuple[tuple[int, str], ...]) -> list[_Unit]:
    """Split the preamble into paragraphs (runs of non-blank lines)."""
    units: list[_Unit] = []
    paragraph: list[tuple[int, str]] = []
    for number, text in [*preamble, (0, "")]:
        if text.strip():
            paragraph.append((number, text))
        elif paragraph:
            first = paragraph[0][1].strip()
            shown = first if len(first) <= _EXCERPT_LIMIT else first[: _EXCERPT_LIMIT - 1] + "\u2026"
            units.append(_Unit(f"[preamble] {shown}", tuple(paragraph)))
            paragraph = []
    return units


def _scan_unit(unit: _Unit, path: str) -> list[Finding]:
    """Apply every banned token to one unit; a match reports the real line it sits on."""
    text = "\n".join(line for _, line in unit.lines)
    stripped = _strip_code_spans(text)
    found: dict[tuple[str, int, str], Finding] = {}
    for token in _BANNED_TOKENS:
        if token.exempt_with is not None and token.exempt_with in text:
            continue
        for match in token.pattern.finditer(stripped if token.outside_code_spans else text):
            line = unit.lines[text.count("\n", 0, match.start())][0]
            fix = token.fix.replace(_MATCH_SLOT, match.group(0))
            where = f"{unit.where} (token: {match.group(0)})"
            found[(token.name, line, match.group(0))] = _error("banned-token", path, line, where, fix)
    return list(found.values())


def _orphan_units(orphans: tuple[Orphan, ...]) -> list[_Unit]:
    """Group orphan lines into runs of consecutive lines under the same section."""
    runs: list[list[Orphan]] = []
    for orphan in orphans:
        if runs and runs[-1][-1].section == orphan.section and runs[-1][-1].line + 1 == orphan.line:
            runs[-1].append(orphan)
        else:
            runs.append([orphan])
    return [_Unit(f"[{run[0].section}] {_shorten(run[0].text.strip())}", tuple((o.line, o.text) for o in run)) for run in runs]


def _shorten(text: str) -> str:
    return text if len(text) <= _EXCERPT_LIMIT else text[: _EXCERPT_LIMIT - 1] + "\u2026"


def check_banned_tokens(parsed: ParsedSection, path: str) -> list[Finding]:
    """FR-010: no internal tokens in the preamble, in any entry, or in prose before a first bullet."""
    units = [
        *_preamble_units(parsed.preamble),
        *_orphan_units(parsed.orphans),
        *(_Unit(entry_where(entry), entry.numbered) for entry in parsed.entries),
    ]
    return [finding for unit in units for finding in _scan_unit(unit, path)]


def _length_finding(where: str, line: int, lines: Sequence[str], path: str) -> Finding | None:
    """A length finding for one block of raw lines, measured in Unicode code points."""
    size = len("\n".join(lines))
    if size > LENGTH_ERROR_LIMIT:
        fix = f"Entry is {size} characters (limit {LENGTH_ERROR_LIMIT:,}); split it or move detail to the docs."
        return Finding("error", "length", path, line, where, fix)
    if size > LENGTH_WARNING_LIMIT:
        fix = f"Entry is {size} characters; aim for {LENGTH_WARNING_LIMIT} or fewer."
        return Finding("warning", "length-warning", path, line, where, fix)
    return None


def check_length(entry: Entry, path: str) -> list[Finding]:
    """FR-011: cap the entry's own lines, and each nested item on its own, in code points."""
    blocks = [(entry_where(entry), entry.line, entry.lines)]
    for line, item in zip(entry.nested_lines, entry.nested, strict=True):
        first = item[0].strip().removeprefix("- ")
        shown = first if len(first) <= _NESTED_EXCERPT_LIMIT else first[: _NESTED_EXCERPT_LIMIT - 1] + "\u2026"
        blocks.append((f"{entry_where(entry)} > {shown}", line, item))
    findings = (_length_finding(where, line, lines, path) for where, line, lines in blocks)
    return [finding for finding in findings if finding is not None]


def check_bullet_markers(parsed: ParsedSection, path: str) -> list[Finding]:
    """A ``* `` or ``+ `` bullet is not a changelog entry; the entry parser only knows ``- ``."""
    fix = "Use `- ` for changelog entries."
    return [
        _error("bullet-marker", path, bullet.line, f"[{bullet.section or 'preamble'}] {_shorten(bullet.text.strip())}", fix) for bullet in parsed.foreign_bullets
    ]


EntryRule = Callable[[Entry, str], list[Finding]]
SectionRule = Callable[[ParsedSection, str], list[Finding]]

#: Rules that judge the section as a whole (headings).
SECTION_RULES: Final[tuple[SectionRule, ...]] = (check_headings, check_banned_tokens, check_bullet_markers)
#: Rules that judge one entry at a time.
ENTRY_RULES: Final[tuple[EntryRule, ...]] = (
    check_headline,
    check_refs_in_bold,
    check_contrast,
    check_internal_shape,
    check_length,
)


def check(text: str, path: str = "docs/changelog/CHANGELOG.md") -> list[Finding]:
    """Check the Unreleased section of *text*; return findings sorted by ``(path, line, rule)``."""
    section = unreleased_section(text)
    if section is None:
        return []
    parsed = parse_section(section)
    findings: list[Finding] = []
    for section_rule in SECTION_RULES:
        findings.extend(section_rule(parsed, path))
    for entry in parsed.entries:
        for entry_rule in ENTRY_RULES:
            findings.extend(entry_rule(entry, path))
    return sorted(findings, key=lambda finding: finding.sort_key)


def format_finding(finding: Finding) -> str:
    """Render ``path:line: [rule] where — fix``; warnings get a ``warning: `` prefix."""
    line = f"{finding.path}:{finding.line}: [{finding.rule}] {finding.where} — {finding.fix}"
    return f"warning: {line}" if finding.severity == "warning" else line


def _display_path(path: Path) -> str:
    """Repo-relative POSIX path when *path* is inside the repository, else the path as given."""
    try:
        return path.resolve().relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return str(path)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.docs.check_changelog_style",
        description="Check the changelog's [Unreleased] section against the house style.",
    )
    parser.add_argument(
        "--changelog",
        type=Path,
        default=DEFAULT_CHANGELOG,
        help="changelog file to check; a relative path resolves against the repository root (default: docs/changelog/CHANGELOG.md)",
    )
    return parser


def _exit_code_of(exc: SystemExit) -> int:
    return exc.code if isinstance(exc.code, int) else 0 if exc.code is None else 2


def main(argv: Sequence[str] | None = None) -> int:
    """Run the guard; return the process exit code (0 pass, 1 errors, 2 usage error)."""
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return _exit_code_of(exc)
    changelog: Path = args.changelog if args.changelog.is_absolute() else REPO_ROOT / args.changelog
    try:
        text = changelog.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        print(f"cannot read {changelog}: {exc}", file=sys.stderr)
        return 2
    if unreleased_section(text) is None:
        print("no [Unreleased] section found; nothing to check")
        return 0
    findings = check(text, _display_path(changelog))
    for finding in findings:
        print(format_finding(finding))
    errors = sum(1 for finding in findings if finding.severity == "error")
    print(f"{errors} error(s), {len(findings) - errors} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
