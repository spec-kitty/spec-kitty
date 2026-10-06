"""Shipped guidance never instructs a ``spec-kitty doctrine`` command that has a ``charter`` successor (#4836).

``spec-kitty doctrine`` is deprecated and prints a banner on every call.
Several of its commands are registered under ``spec-kitty charter`` with the
*same handler* (``new``, ``validate``, ``fetch``, ``org``), so guidance that
still names the ``doctrine`` spelling makes an agent emit the banner and,
following the text verbatim, treat it as a fault.

The successor set is read from the two Typer apps -- a ``doctrine`` command or
group counts as migrated exactly when the ``charter`` app registers the same
handler object. Commands that only share a name (``pack``, ``mission-type``)
or exist only under ``doctrine`` (``regenerate-graph``, ``asset``) are not in
the set, so guidance may still cite them until they get a successor. Nothing
is hand-listed, so the gate needs no allowlist.

Scope: shipped skills, both packs and the living docs, plus every string
literal in ``src/`` Python code -- remediation messages and hints are where an
operator reads these commands. Python docstrings and comments are not scanned:
they describe code (including the deprecated group itself), they do not
instruct an operator. The immutable record roots (terminology-exemptions.md),
design plans, the changelog and generated outputs are out of scope.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from specify_cli.cli.commands.charter._app import charter_app
from specify_cli.cli.commands.doctrine import app as doctrine_app

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAN_ROOTS = ("src/charter/offering/skills", "packs", "docs")
_SUFFIXES = frozenset({".md", ".yaml", ".yml", ".txt"})
_EXCLUDED_PREFIXES = (
    "docs/adr/",
    "docs/reports/",
    "docs/archive/",
    "docs/migrations/",
    # Plans are design records of how past work was planned and delivered,
    # not instructions; rewriting a delivered work package's command would
    # falsify the record.
    "docs/plans/",
    "docs/changelog/",
    # Generated outputs: the CLI reference from the CLI's own help text, the
    # retrieval index from the docs it indexes.
    "docs/api/cli-commands.md",
    "docs/development/docs-retrieval-index.yaml",
)


def _migrated_doctrine_commands() -> frozenset[str]:
    """Names of ``doctrine`` commands/groups whose handler ``charter`` also registers."""
    charter_callbacks = {id(info.callback) for info in charter_app.registered_commands}
    charter_groups = {id(info.typer_instance) for info in charter_app.registered_groups}
    commands = {info.name for info in doctrine_app.registered_commands if info.name and id(info.callback) in charter_callbacks}
    groups = {info.name for info in doctrine_app.registered_groups if info.name and id(info.typer_instance) in charter_groups}
    return frozenset(commands | groups)


_MIGRATED = _migrated_doctrine_commands()
_INVOCATION = re.compile(r"spec-kitty doctrine ([a-z][a-z-]*)")


def _offenders(text: str) -> list[tuple[int, str]]:
    found: list[tuple[int, str]] = []
    for lineno, line in enumerate(text.splitlines(), start=1):
        for match in _INVOCATION.finditer(line):
            if match.group(1) in _MIGRATED:
                found.append((lineno, match.group(0)))
    return found


def _scanned_files() -> list[Path]:
    files: list[Path] = []
    for root in _SCAN_ROOTS:
        for path in sorted((_REPO_ROOT / root).rglob("*")):
            rel = path.relative_to(_REPO_ROOT).as_posix()
            if path.is_file() and path.suffix in _SUFFIXES and not rel.startswith(_EXCLUDED_PREFIXES):
                files.append(path)
    return files


def _docstring_ids(tree: ast.AST) -> set[int]:
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                ids.add(id(first.value))
    return ids


def _python_offenders(source: str) -> list[tuple[int, str]]:
    """Offending invocations inside non-docstring string literals (f-string parts included)."""
    tree = ast.parse(source)
    docstrings = _docstring_ids(tree)
    found: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            found.extend((node.lineno + offset, token) for offset, token in _offenders(node.value))
    return found


def test_migrated_set_is_derived_from_the_cli() -> None:
    """Non-vacuity floor: the four shared handlers are found; name-only clashes are not."""
    assert {"new", "validate", "fetch", "org"} <= _MIGRATED
    assert "pack" not in _MIGRATED
    assert "mission-type" not in _MIGRATED


def test_guidance_names_the_charter_spelling_of_migrated_commands() -> None:
    violations: list[str] = []
    for path in _scanned_files():
        rel = path.relative_to(_REPO_ROOT).as_posix()
        for lineno, token in _offenders(path.read_text(encoding="utf-8", errors="replace")):
            violations.append(f"{rel}:{lineno}  {token}")
    for path in sorted((_REPO_ROOT / "src").rglob("*.py")):
        rel = path.relative_to(_REPO_ROOT).as_posix()
        for lineno, token in _python_offenders(path.read_text(encoding="utf-8")):
            violations.append(f"{rel}:{lineno}  {token}")
    assert not violations, "Use `spec-kitty charter <command>` for doctrine commands that moved to the charter group (same handler):\n  " + "\n  ".join(violations)


def test_gate_flags_a_planted_invocation() -> None:
    assert _offenders("Run `spec-kitty doctrine validate .kittify/` before committing.")


def test_gate_allows_doctrine_only_commands() -> None:
    assert _offenders("spec-kitty doctrine regenerate-graph && spec-kitty doctrine pack validate x") == []


def test_gate_flags_a_planted_python_message_but_not_a_docstring() -> None:
    source = (
        "def hint(path):\n"
        '    """Mirrors ``spec-kitty doctrine validate`` for the deprecated group."""\n'
        '    return f"Run spec-kitty doctrine validate {path} to confirm."\n'
    )
    assert [token for _, token in _python_offenders(source)] == ["spec-kitty doctrine validate"]
