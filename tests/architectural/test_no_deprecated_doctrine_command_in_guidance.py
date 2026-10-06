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
instruct an operator -- with one exception: the docstring of a callback registered
as a command or group under the ``charter`` app *is* the ``--help`` text Typer
prints for it, so those docstrings are scanned. The immutable record roots (terminology-exemptions.md),
design plans, the changelog and generated outputs are out of scope.
"""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands.charter._app import charter_app
from tests._support.terminology_scope import FORBIDDEN_SCAN_ROOTS
from specify_cli.cli.commands.doctrine import app as doctrine_app

pytestmark = [pytest.mark.fast, pytest.mark.doctrine]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SCAN_ROOTS = ("src/charter/offering/skills", "packs", "docs", ".github/workflows")
_SUFFIXES = frozenset({".md", ".yaml", ".yml", ".txt"})
#: The shared terminology-exempt roots, plus three extras recorded in
#: terminology-exemptions.md: design plans (records of how past work was planned
#: and delivered; rewriting a delivered work package's command would falsify
#: the record), the changelog (entries quote the old command as the "Before"),
#: and generated outputs (the CLI reference and the retrieval index regenerate
#: from their sources).
_EXCLUDED_PREFIXES = (
    *FORBIDDEN_SCAN_ROOTS,
    "docs/plans/",
    "docs/changelog/",
    "docs/api/cli-commands.md",
    "docs/development/docs-retrieval-index.yaml",
)

#: Non-vacuity floor: a scan that stopped reaching the trees passes over nothing.
_MIN_FILES_SCANNED = 800


def _migrated_doctrine_commands() -> frozenset[str]:
    """Names of ``doctrine`` commands/groups whose handler ``charter`` also registers."""
    charter_callbacks = {id(info.callback) for info in charter_app.registered_commands}
    charter_groups = {id(info.typer_instance) for info in charter_app.registered_groups}
    commands = {info.name for info in doctrine_app.registered_commands if info.name and id(info.callback) in charter_callbacks}
    groups = {info.name for info in doctrine_app.registered_groups if info.name and id(info.typer_instance) in charter_groups}
    return frozenset(commands | groups)


_MIGRATED = _migrated_doctrine_commands()
#: ``spec-kitty doctrine <cmd>``, or the bare backticked form ``\`doctrine <cmd>``.
_INVOCATION = re.compile(r"(?:spec-kitty |`)doctrine ([a-z][a-z-]*)")


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
            found.extend((node.lineno + offset - 1, token) for offset, token in _offenders(node.value))
    return found


def _charter_help_callbacks(app: typer.Typer, path: str = "charter") -> Iterator[tuple[str, Callable[..., object]]]:
    """Every callback registered as a command or group callback under ``app``, recursively."""
    group_callback = app.registered_callback
    if group_callback is not None and group_callback.callback is not None:
        yield path, group_callback.callback
    for command in app.registered_commands:
        if command.callback is not None:
            yield f"{path} {command.name or command.callback.__name__}", command.callback
    for group in app.registered_groups:
        yield from _charter_help_callbacks(group.typer_instance, f"{path} {group.name}")


def _charter_help_offenders() -> list[str]:
    """Offending invocations in the ``--help`` text (docstrings) of the ``charter`` surface."""
    return [
        f"`{command}` --help ({callback.__module__}.{callback.__qualname__})  {token}"
        for command, callback in _charter_help_callbacks(charter_app)
        for _, token in _offenders(inspect.getdoc(callback) or "")
    ]


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
    violations.extend(_charter_help_offenders())
    assert not violations, "Use `spec-kitty charter <command>` for doctrine commands that moved to the charter group (same handler):\n  " + "\n  ".join(violations)


def test_gate_reaches_a_real_file_count() -> None:
    assert len(_scanned_files()) >= _MIN_FILES_SCANNED


def test_gate_flags_the_bare_backticked_form() -> None:
    assert _offenders("and `doctrine org validate` now rejects it")


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
    assert _python_offenders(source) == [(3, "spec-kitty doctrine validate")]
