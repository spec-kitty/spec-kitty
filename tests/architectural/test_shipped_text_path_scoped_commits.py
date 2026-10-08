"""FR-015 (#5443): shipped guidance must teach path-scoped staging only.

Scans shipped skills, the built-in git toolguide and the two upgrade docs for
sweeping ``git add`` forms (``-A``, ``--all``, ``-u``, ``.``, directory adds).
Directive 033 (Targeted Staging Policy) requires explicit file paths.

Known blind spot: a directory named without a trailing slash
(``git add kitty-specs``) is indistinguishable from a file in plain text;
reviewers own that case.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.regression, pytest.mark.unit, pytest.mark.fast]

REPO_ROOT = Path(__file__).resolve().parents[2]
SKILLS_ROOT = "src/charter/offering/skills"
NAMED_FILES = (
    "packs/built-in/toolguides/GIT_WORKTREE_PR_WORKFLOW.md",
    "docs/api/upgrade-lifecycle.md",
    "docs/guides/how-to/installation/upgrade-project.md",
)

_GIT_PREFIX = r"(?<![\w-])git(?:\s+-[Cc]\s+\S+)*\s+"
_GIT_ADD = re.compile(_GIT_PREFIX + r"add(?=\s|$)")
_GIT_COMMIT = re.compile(_GIT_PREFIX + r"commit(?=\s|$)")
_TERMINATOR = re.compile(r"&&|\|\||;|\||`|\)")
_HARMLESS = {"--force", "-f", "--", "-p", "--patch", "-N", "--intent-to-add", "-v"}
_SWEEPING = {"-A", "--all", "-u", "--update", ".", "./", ":/", "*"}
_COMBINED_SWEEP = re.compile(r"^-[A-Za-z]*[Au][A-Za-z]*$")
_COMMIT_SWEEP = re.compile(r"^(--all|-[A-Za-z]*a[A-Za-z]*)$")
_COMMIT_ARG_FLAGS = {"-m", "--message", "-F", "--file", "-C", "-c"}


def _args(rest: str) -> list[str]:
    rest = re.sub(r"'[^']*'|\"[^\"]*\"", "Q", rest)  # quoted messages are not flags
    term = _TERMINATOR.search(rest)
    return (rest[: term.start()] if term else rest).split()


def find_sweeping_adds(text: str) -> list[tuple[int, str]]:
    """Return ``(1-based line, offending command)`` for each sweeping stage.

    Covers ``git [-C dir] add`` (``-A``, ``--all``, ``-u``, ``.``, directories,
    combined flag clusters) and ``git [-C dir] commit -a/-am/--all``.
    """
    hits: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in _GIT_ADD.finditer(line):
            args = _args(line[match.end() :])
            for tok in args:
                if tok in _HARMLESS:
                    continue
                if tok in _SWEEPING or tok.endswith("/") or _COMBINED_SWEEP.match(tok):
                    hits.append((lineno, f"git add {' '.join(args)}".strip()))
                    break
        for match in _GIT_COMMIT.finditer(line):
            args = _args(line[match.end() :])
            skip = False
            for tok in args:
                if skip:
                    skip = False
                    continue
                if _COMMIT_SWEEP.match(tok):
                    hits.append((lineno, f"git commit {' '.join(args)}".strip()))
                    break
                if tok in _COMMIT_ARG_FLAGS:
                    skip = True
                elif tok.startswith("-") and not tok.startswith("--") and tok.endswith(("m", "F")):
                    break  # message follows a cluster such as -sm; nothing further is a flag
    return hits


@pytest.mark.parametrize(
    "text",
    [
        "git add -A",
        "git add --all",
        "git add .",
        "git add -u",
        "git add kitty-specs/",
        "git add src/ tests/",
        "`git add . && git rebase --continue`",
        "| `git add -A` |",
        "cd x && git add -A && git commit -m y",
        "git -C ../repo add -A",
        "git -C ../repo add .",
        "git add -uv",
        "git add -Av",
        "git commit -a -m msg",
        "git commit -am msg",
        "git commit --all -m msg",
        "git -C ../repo commit -am msg",
        "`git commit -a`",
    ],
)
def test_detector_flags_each_sweeping_form(text: str) -> None:
    assert len(find_sweeping_adds(text)) == 1


@pytest.mark.parametrize(
    "text",
    [
        "git add <files>",
        "git add -- src/app.py tests/test_app.py",
        "git add --force -- .kittify/metadata.yaml",
        "spec-kitty safe-commit src/app.py",
        "git add -p src/app.py",
        "git -C ../repo add -- src/app.py",
        "git add -v -- src/app.py",
        "git commit -m 'fix: handle -a flag'",
        "git commit --amend --no-edit",
        "git commit --no-edit",
        "git commit -S -m msg -- src/app.py",
        "git -C ../repo commit -m msg -- src/app.py",
    ],
)
def test_detector_allows_path_scoped_forms(text: str) -> None:
    assert find_sweeping_adds(text) == []


def _scanned_files() -> list[Path]:
    skills = sorted((REPO_ROOT / SKILLS_ROOT).rglob("*.md"))
    return [*skills, *(REPO_ROOT / n for n in NAMED_FILES)]


def test_scanned_set_is_not_vacuous() -> None:
    skills = list((REPO_ROOT / SKILLS_ROOT).rglob("*.md"))
    assert len(skills) >= 20
    for name in NAMED_FILES:
        assert (REPO_ROOT / name).is_file(), name


def test_shipped_text_teaches_path_scoped_commits() -> None:
    found: dict[str, list[tuple[int, str]]] = {}
    for path in _scanned_files():
        hits = find_sweeping_adds(path.read_text(encoding="utf-8"))
        if hits:
            found[path.relative_to(REPO_ROOT).as_posix()] = hits
    lines = [f"{p}:{n}: {cmd}" for p, hs in found.items() for n, cmd in hs]
    assert not found, (
        "Sweeping staging found in shipped text:\n"
        + "\n".join(lines)
        + "\nStage explicit files: `spec-kitty safe-commit <paths>` or `git add -- <files>` (Directive 033)."
    )
