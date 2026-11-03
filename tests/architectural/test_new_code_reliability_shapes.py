"""Architectural guard: the three #7113 new-code reliability constructs stay removed.

SonarCloud's new-code reliability rating on `main` was E, produced by two BLOCKER findings on
intentional constructs and one provably-dead branch. Each fix removed the construct the analyzer
misread instead of suppressing the finding, so the assertions here are the durable half of that
change: they red if a construct is reintroduced, and each is paired with the behaviour the rewrite
had to preserve so the shape check cannot pass over a broken rewrite.

Findings, from the analysis of `main` on 2026-11-03 (raw responses and the full split live in
`kitty-specs/sonar-new-code-reliability-01M6GRHZ/evidence/`):

* ``python:S5756`` — ``src/specify_cli/cli/commands/events.py``: a value lookup called on an
  ``Enum`` built by the functional API, which the analyzer cannot model.
* ``python:S3827`` — ``src/charter/activation/compiler.py``: a name used in a function-local
  annotation above the statement that binds it (``from __future__ import annotations`` is active,
  so the annotation never evaluates).
* ``pythonbugs:S2583`` — ``src/specify_cli/migration/backfill_identity.py``: a ``None`` guard the
  analyzer proved dead.

The shape probes are textual/AST checks on the module source because the vacancy they guard is a
shape, not a behaviour: no call-level test can distinguish the two spellings of the same lookup.
"""

from __future__ import annotations

import ast
import io
import tokenize
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVENTS = "src/specify_cli/cli/commands/events.py"
_COMPILER = "src/charter/activation/compiler.py"
_BACKFILL = "src/specify_cli/migration/backfill_identity.py"

_SERVICE_FUNCTION = "_default_active_charter_service"
_SERVICE_NAME = "ActiveCharterService"


def _source(relative: str) -> str:
    return (_REPO_ROOT / relative).read_text(encoding="utf-8")


def _code_only(source: str) -> str:
    """``source`` without comments, so prose *about* a construct cannot trip a shape probe."""
    lines = source.splitlines(keepends=True)
    for token in tokenize.generate_tokens(io.StringIO(source).readline):
        if token.type is tokenize.COMMENT:
            row, column = token.start
            end_row, end_column = token.end
            if row == end_row:
                lines[row - 1] = lines[row - 1][:column] + lines[row - 1][end_column:]
    return "".join(lines)


# --------------------------------------------------------------------------------------------
# python:S5756 — the default log kind is resolved by name, not by calling the functional Enum.
# --------------------------------------------------------------------------------------------


def test_events_default_log_kind_is_looked_up_by_name() -> None:
    code = _code_only(_source(_EVENTS))

    # The flagged construct: a value lookup that the analyzer reads as a call on a non-callable.
    assert '_LogKind("status")' not in code

    # Control: the module really does resolve the default through a ``_LogKind[...]`` subscript,
    # so the assertion above is not passing over a module this probe cannot see into.
    assert "_LogKind[" in code

    from specify_cli.cli.commands import events

    # Behaviour the rewrite had to preserve: the default is the registry member whose value is
    # ``status``, reachable by name, and the registry still offers that kind.
    assert events._DEFAULT_LOG_KIND in events.SUPPORTED_LOG_KINDS
    assert events._LOG_KIND_DEFAULT.value == events._DEFAULT_LOG_KIND
    assert events._LOG_KIND_DEFAULT is events._LogKind[events._DEFAULT_LOG_KIND.upper()]


# --------------------------------------------------------------------------------------------
# python:S3827 — the service class is bound before the annotation that names it.
# --------------------------------------------------------------------------------------------


def _statement_bindings(statement: ast.stmt) -> set[str]:
    """Names ``statement`` binds in the enclosing function scope."""
    bound: set[str] = set()
    if isinstance(statement, ast.Import):
        bound.update(alias.asname or alias.name.split(".")[0] for alias in statement.names)
    elif isinstance(statement, ast.ImportFrom):
        bound.update(alias.asname or alias.name for alias in statement.names)
    elif isinstance(statement, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
        targets = statement.targets if isinstance(statement, ast.Assign) else [statement.target]
        bound.update(target.id for target in targets if isinstance(target, ast.Name))
    elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        bound.add(statement.name)
    return bound


def _annotation_uses(statement: ast.stmt) -> set[str]:
    """Names ``statement`` mentions in an annotation."""
    used: set[str] = set()
    annotations: list[ast.expr] = []
    if isinstance(statement, ast.AnnAssign):
        annotations.append(statement.annotation)
    elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        annotations.extend(argument.annotation for argument in statement.args.args if argument.annotation)
        if statement.returns is not None:
            annotations.append(statement.returns)
    for annotation in annotations:
        used.update(node.id for node in ast.walk(annotation) if isinstance(node, ast.Name))
    return used


def _function_source(relative: str, name: str) -> str:
    module = ast.parse(_source(relative))
    for node in ast.walk(module):
        if isinstance(node, ast.FunctionDef) and node.name == name:
            return ast.unparse(node)
    raise AssertionError(f"{relative} has no function {name!r}")


def _annexed_statements(body: list[ast.stmt]) -> list[ast.stmt]:
    """``body`` plus the statements of its nested blocks, in source order, without nested scopes."""
    collected: list[ast.stmt] = []
    for statement in body:
        collected.append(statement)
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        for field in ("body", "orelse", "finalbody"):
            collected.extend(_annexed_statements(getattr(statement, field, []) or []))
        for handler in getattr(statement, "handlers", []) or []:
            collected.extend(_annexed_statements(handler.body))
    return sorted(collected, key=lambda item: (item.lineno, item.col_offset))


def test_compiler_binds_the_service_class_before_the_annotation_that_names_it() -> None:
    module = ast.parse(_source(_COMPILER))
    function = next(node for node in ast.walk(module) if isinstance(node, ast.FunctionDef) and node.name == _SERVICE_FUNCTION)
    statements = _annexed_statements(function.body)

    annotation_lines = [statement.lineno for statement in statements if _SERVICE_NAME in _annotation_uses(statement)]
    assert annotation_lines, "control: the probe can see an annotation naming the service class"

    binding_lines = [statement.lineno for statement in statements if _SERVICE_NAME in _statement_bindings(statement)]
    assert binding_lines, "control: the probe can see the statement that binds the service class"
    assert min(binding_lines) < min(annotation_lines), (
        f"{_SERVICE_FUNCTION} names {_SERVICE_NAME} in an annotation at line {min(annotation_lines)} but binds it first at line {min(binding_lines)} (python:S3827)"
    )

    # Behaviour the rewrite had to preserve: both branches return the resolver's service class.
    from charter.activation.compiler import _default_active_charter_service
    from charter.activation.resolver import ActiveCharterService

    assert isinstance(_default_active_charter_service(None), ActiveCharterService)


def test_compiler_service_builder_branch_returns_the_wrapper(tmp_path: Path) -> None:
    from charter.activation.compiler import _default_active_charter_service
    from charter.activation.resolver import ActiveCharterService

    assert isinstance(_default_active_charter_service(tmp_path), ActiveCharterService)


# --------------------------------------------------------------------------------------------
# pythonbugs:S2583 — the dead refusal guard is an explicit invariant instead.
# --------------------------------------------------------------------------------------------


def test_backfill_identity_states_the_refusal_invariant() -> None:
    code = _code_only(_source(_BACKFILL))
    assert "None if refusal is None else refusal.notice" not in code

    # Control: the probe sees the line that replaced it, so the assertion above is not passing
    # because the whole block is gone.
    assert "refusal.notice" in code

    # The behaviour this rewrite had to preserve is owned and exercised by the file that already
    # covers it, for both outcomes on one fixture shape: an unavailable tracked copy still returns
    # ``(None, <coded notice>)`` and a usable one still returns ``(<mission_id>, None)``. See
    # ``tests/specify_cli/migration/test_backfill_identity_tracked_absent_6673.py``.
    #
    # This module deliberately does NOT re-drive those outcomes through a faked
    # ``specify_cli.mission_metadata.read_tracked_meta``: a fake-seam probe here perturbed a
    # following test's git-backed fixture in the same process (``_tracked_mission_id`` resolves the
    # project root for a non-repository ``tmp_path``), and a shape guard has no business paying
    # that cost to re-assert coverage another file owns.
