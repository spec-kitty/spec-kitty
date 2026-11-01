#!/usr/bin/env python3
"""Per-PR changelog fragments and their assembly into ``CHANGELOG.md``.

A pull request records its changelog entries in its own file under ``docs/changelog/unreleased/`` instead of
editing the shared ``docs/changelog/CHANGELOG.md``, so two pull requests never conflict on the
changelog. A fragment is named ``<id>.<section>.md``:

* ``<id>`` is the PR number, the issue number or a short lowercase slug (``[0-9a-z][0-9a-z-]*``);
* ``<section>`` is one of ``breaking``, ``upgrade-notes``, ``added``, ``changed``, ``fixed`` or
  ``internal``, the six ``###`` headings of the ``## [Unreleased]`` section.

Its content is one or more entries exactly as they would read in the changelog: each starts with
``- **Bold headline** (#PR, #issue).``. It carries no headings. ``README.md`` in the directory is
documentation, not a fragment.

At release time the fragments are folded into the ``## [Unreleased]`` section, after that section's
existing entries, and deleted::

    python -m scripts.release.changelog_fragments check            # names and shape only
    python -m scripts.release.changelog_fragments assemble         # print the assembled section
    python -m scripts.release.changelog_fragments assemble --write # fold in and delete fragments

The house style (bold headline, length, banned tokens) is enforced on each fragment by
``scripts/docs/check_changelog_style.py`` and the US spelling by ``scripts/docs/check_spelling.py``.

Standard library only.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from kernel.clock import now_utc
from scripts.release.validate_release import unreleased_section

REPO_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
FRAGMENT_DIR_REL: Final[str] = "docs/changelog/unreleased"
DEFAULT_FRAGMENT_DIR: Final[Path] = REPO_ROOT / FRAGMENT_DIR_REL
DEFAULT_CHANGELOG: Final[Path] = REPO_ROOT / "docs" / "changelog" / "CHANGELOG.md"

#: File-name section slug -> the ``###`` heading it lands under, in the changelog's order.
SECTIONS: Final[dict[str, str]] = {
    "breaking": "Breaking",
    "upgrade-notes": "Upgrade Notes",
    "added": "Added",
    "changed": "Changed",
    "fixed": "Fixed",
    "internal": "Internal",
}
SECTION_ORDER: Final[tuple[str, ...]] = tuple(SECTIONS.values())
#: Files in the fragment directory that are not fragments.
NON_FRAGMENTS: Final[frozenset[str]] = frozenset({"README.md", ".gitkeep"})
ASSEMBLE_COMMAND: Final[str] = "python -m scripts.release.changelog_fragments assemble --write"

_NAME_RE: Final[re.Pattern[str]] = re.compile(r"^(?P<id>[0-9a-z][0-9a-z-]*)\.(?P<section>[a-z-]+)\.md$")
_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^#{1,6}\s")
_SECTION_HEADING_RE: Final[re.Pattern[str]] = re.compile(r"^###\s+(.*?)\s*$")
_UPDATED_RE: Final[re.Pattern[str]] = re.compile(r"^updated:.*$", re.MULTILINE)
_FENCES: Final[tuple[str, ...]] = ("```", "~~~")


@dataclass(frozen=True)
class Fragment:
    """One well-formed fragment: where it lives, its section heading and its entry lines."""

    path: Path
    fragment_id: str
    section: str
    lines: tuple[str, ...]


def _sort_key(path: Path) -> tuple[int, int, str]:
    """Numeric ids first, in numeric order; then slugs by name."""
    fragment_id = path.name.split(".", 1)[0]
    if fragment_id.isdigit():
        return (0, int(fragment_id), path.name)
    return (1, 0, path.name)


def _trimmed(text: str) -> tuple[str, ...]:
    lines = [line.rstrip() for line in text.splitlines()]
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return tuple(lines)


def _shape_problem(lines: Sequence[str]) -> str | None:
    """A heading outside a fence, or a fence left open, breaks the assembled changelog."""
    fence: str | None = None
    for line in lines:
        stripped = line.lstrip()
        marker = next((m for m in _FENCES if stripped.startswith(m)), None)
        if marker is not None and fence in (None, marker):
            fence = None if fence else marker
        elif fence is None and _HEADING_RE.match(line):
            return "a fragment holds entries only; remove the heading (the file name picks the section)"
    if fence is not None:
        return f"close the {fence} code fence; an open fence would swallow every later release section"
    return None


def _parse(path: Path) -> Fragment | str:
    """Return the fragment at *path*, or a one-line problem naming the file."""
    match = _NAME_RE.match(path.name)
    if match is None:
        return f"{path}: name must be <id>.<section>.md with a lowercase id (PR, issue or slug)"
    if match.group("section") not in SECTIONS:
        return f"{path}: unknown section {match.group('section')!r}; use one of: {', '.join(SECTIONS)}"
    try:
        lines = _trimmed(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        return f"{path}: cannot read ({exc})"
    if not lines:
        return f"{path}: empty fragment; add a `- **Headline** (#PR).` entry or delete the file"
    if not lines[0].startswith("- "):
        return f"{path}: a fragment must start with a `- ` entry"
    problem = _shape_problem(lines)
    if problem is not None:
        return f"{path}: {problem}"
    return Fragment(path, match.group("id"), SECTIONS[match.group("section")], lines)


def load_fragments(directory: Path) -> tuple[list[Fragment], list[str]]:
    """Read every fragment in *directory*; return the good ones (sorted) and the problems found."""
    if not directory.is_dir():
        return [], []
    fragments: list[Fragment] = []
    problems: list[str] = []
    candidates = (path for path in directory.iterdir() if path.name not in NON_FRAGMENTS)
    for path in sorted(candidates, key=_sort_key):
        if path.is_dir():
            problems.append(f"{path}: subdirectories are not allowed in {FRAGMENT_DIR_REL}/")
            continue
        parsed = _parse(path)
        if isinstance(parsed, str):
            problems.append(parsed)
        else:
            fragments.append(parsed)
    return fragments, problems


def fragment_problems(directory: Path) -> list[str]:
    """The naming and shape problems of *directory*'s fragments (empty when all are well formed)."""
    return load_fragments(directory)[1]


def fragment_paths(directory: Path) -> list[Path]:
    """Every file in *directory* that counts as a fragment, well formed or not."""
    if not directory.is_dir():
        return []
    return sorted((p for p in directory.iterdir() if p.is_file() and p.name not in NON_FRAGMENTS), key=_sort_key)


def _section_bounds(body: list[str]) -> dict[str, tuple[int, int]]:
    """Map each ``###`` heading of the Unreleased body to its ``[start, end)`` line range."""
    starts = [(index, m.group(1)) for index, line in enumerate(body) if (m := _SECTION_HEADING_RE.match(line))]
    bounds: dict[str, tuple[int, int]] = {}
    for position, (index, title) in enumerate(starts):
        end = starts[position + 1][0] if position + 1 < len(starts) else len(body)
        bounds.setdefault(title, (index, end))
    return bounds


def _insert_into_section(body: list[str], title: str, entries: list[str]) -> list[str]:
    bounds = _section_bounds(body)
    if title in bounds:
        start, end = bounds[title]
        last = end
        while last > start + 1 and not body[last - 1].strip():
            last -= 1
        if last == start + 1:  # heading with no entries yet: keep one blank line after it
            return [*body[: start + 1], "", *entries, *body[start + 1 :]]
        return [*body[:last], *entries, *body[last:]]
    rank = SECTION_ORDER.index(title)
    later = [bounds[name][0] for name in SECTION_ORDER[rank + 1 :] if name in bounds]
    if later:
        at = min(later)
        return [*body[:at], f"### {title}", "", *entries, "", *body[at:]]
    tail = len(body)
    while tail > 0 and not body[tail - 1].strip():
        tail -= 1
    return [*body[:tail], "", f"### {title}", "", *entries, *body[tail:]]


def assemble(changelog_text: str, fragments: Sequence[Fragment]) -> str:
    """Fold *fragments* into the ``## [Unreleased]`` section of *changelog_text*.

    Each fragment's entries follow the existing entries of its section, in fragment order; a
    missing section heading is created in its canonical position. With no fragments the text is
    returned unchanged. Raises :class:`ValueError` when there is no Unreleased section.
    """
    if not fragments:
        return changelog_text
    section = unreleased_section(changelog_text)
    if section is None:
        raise ValueError("the changelog has no ## [Unreleased] section to assemble fragments into")
    lines = changelog_text.splitlines()
    start = section.start_line  # 1-based heading line == 0-based index of the first body line
    end = start + len(section.lines)
    body = list(lines[start:end])
    for title in SECTION_ORDER:
        entries = [line for fragment in fragments if fragment.section == title for line in fragment.lines]
        if entries:
            body = _insert_into_section(body, title, entries)
    trailing_newline = "\n" if changelog_text.endswith("\n") else ""
    assembled = "\n".join([*lines[:start], *body, *lines[end:]]) + trailing_newline
    after = unreleased_section(assembled)
    if after is None or after.start_line + len(after.lines) != start + len(body):
        raise ValueError("the assembled [Unreleased] section would run past the next release heading; check the fragments' code fences")
    return assembled


def _set_updated(text: str, today: str) -> str:
    if not text.startswith("---\n"):
        return text
    close = text.find("\n---", 4)
    if close == -1:
        return text
    head = _UPDATED_RE.sub(f"updated: '{today}'", text[:close], count=1)
    return head + text[close:]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m scripts.release.changelog_fragments",
        description="Check per-PR changelog fragments, or assemble them into CHANGELOG.md at release time.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, text in (("check", "check fragment names and shape"), ("assemble", "fold fragments into [Unreleased]")):
        command = sub.add_parser(name, help=text)
        command.add_argument("--fragments", type=Path, default=DEFAULT_FRAGMENT_DIR, help="fragment directory (default: docs/changelog/unreleased/)")
        if name == "assemble":
            command.add_argument("--changelog", type=Path, default=DEFAULT_CHANGELOG, help="changelog to assemble into")
            command.add_argument("--write", action="store_true", help="write the changelog and delete the fragments")
            command.add_argument("--today", default=None, help="date for the frontmatter `updated:` key (default: today)")
    return parser


def _report(problems: Sequence[str]) -> None:
    for problem in problems:
        print(f"[fragment] {problem}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    """Run ``check`` or ``assemble``; return 0 on success, 1 on bad fragments, 2 on usage errors."""
    try:
        args = _build_parser().parse_args(argv)
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 2
    fragments, problems = load_fragments(args.fragments)
    if problems:
        _report(problems)
        return 1
    if args.command == "check":
        print(f"{len(fragments)} fragment(s) well formed")
        return 0
    try:
        text = args.changelog.read_text(encoding="utf-8")
        assembled = assemble(text, fragments)
    except (OSError, ValueError) as exc:
        print(f"cannot assemble into {args.changelog}: {exc}", file=sys.stderr)
        return 2
    if not args.write:
        section = unreleased_section(assembled)
        print("\n".join(section.lines) if section is not None else assembled)
        return 0
    today = args.today or now_utc().date().isoformat()
    args.changelog.write_text(_set_updated(assembled, today) if fragments else assembled, encoding="utf-8")
    for fragment in fragments:
        fragment.path.unlink()
    print(f"assembled {len(fragments)} fragment(s) into {args.changelog}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
