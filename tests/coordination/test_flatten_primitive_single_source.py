"""Architectural guard: the coordination-flatten three-mutation set has a
SINGLE canonical owner (#3219 / FR-015 / SC-009).

Background: clearing a mission's coordination metadata is one logical
operation with THREE co-occurring mutations -- pop ``coordination_branch``,
pop the now-stale ``topology``, and set ``flattened: True``. This exact set
has been re-inlined at its own call site FOUR times across the project's
history (#2069 -> #2120 -> #2614 -> #3086/#3218) instead of converging on one
shared primitive, each touch risking a partial (1-of-3 or 2-of-3) copy that
silently drifts from the canonical shape (see
``tests/specify_cli/cli/commands/test_mission_close_discard_pops_topology.py`` for exactly
that kind of drift: the ``mission close --discard`` path only ever cleared
``coordination_branch``).

verdict-seam-write-unification-01KZ9Q35 WP10 (D-PLAN-17) extracts the ONE
canonical primitive --
:func:`specify_cli.mission_metadata.flatten_coordination_metadata` -- and
converges every call site onto it. This test is the non-vacuous ratchet: it
scans every module under ``src/`` for a function performing all three
mutations and asserts there is EXACTLY ONE such function, and it is the
primitive. A 5th re-inline anywhere else must red this test immediately.

Detection is AST-based (not textual): the three mutations recognised are
- ``del meta["coordination_branch"]`` or ``meta.pop("coordination_branch", ...)``
- ``meta.pop("topology", ...)`` / ``meta.pop(TOPOLOGY_KEY, ...)`` (the promoted
  public constant, or the raw string literal)
- ``meta["flattened"] = True`` / ``meta[FLATTENED_KEY] = True``
co-occurring within the SAME function body. A docstring or comment merely
*describing* the pattern (a ``Constant`` string, never call/assignment nodes)
is never flagged -- only real code constructs are.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

import pytest
from tests.architectural._ast_scan import parse_source

pytestmark = pytest.mark.architectural

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC = _REPO_ROOT / "src"

_COORD_BRANCH_LITERAL = "coordination_branch"
_COORD_BRANCH_CONST_NAME = "_COORDINATION_BRANCH_KEY"
_TOPOLOGY_LITERAL = "topology"
_TOPOLOGY_CONST_NAME = "TOPOLOGY_KEY"
_FLATTENED_LITERAL = "flattened"
_FLATTENED_CONST_NAME = "FLATTENED_KEY"

_EXPECTED_OWNER_REL_PATH = "src/specify_cli/mission_metadata.py"
_EXPECTED_OWNER_QUALNAME = "flatten_coordination_metadata"


def _matches_key(expr: ast.expr | None, *, literal: str, name: str) -> bool:
    """True when *expr* is either the raw string literal or the named constant."""
    if isinstance(expr, ast.Constant) and expr.value == literal:
        return True
    return isinstance(expr, ast.Name) and expr.id == name


def _pop_call_key(call: ast.Call) -> ast.expr | None:
    """The key argument of a ``x.pop(key, ...)`` call (positional only)."""
    if call.args:
        return call.args[0]
    return None


def _delete_subscript_keys(node: ast.Delete) -> list[ast.expr]:
    """The subscript keys of a ``del x[key]`` / ``del x[key1], y[key2]`` statement."""
    keys: list[ast.expr] = []
    for target in node.targets:
        if isinstance(target, ast.Subscript):
            keys.append(target.slice)
    return keys


def _clears_coordination_branch(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Delete):
            for delete_key in _delete_subscript_keys(node):
                if _matches_key(
                    delete_key, literal=_COORD_BRANCH_LITERAL, name=_COORD_BRANCH_CONST_NAME
                ):
                    return True
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "pop"
        ):
            pop_key = _pop_call_key(node)
            if _matches_key(
                pop_key, literal=_COORD_BRANCH_LITERAL, name=_COORD_BRANCH_CONST_NAME
            ):
                return True
    return False


def _pops_topology(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "pop"
        ):
            key = _pop_call_key(node)
            if _matches_key(key, literal=_TOPOLOGY_LITERAL, name=_TOPOLOGY_CONST_NAME):
                return True
    return False


def _sets_flattened_true(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(fn):
        if not isinstance(node, ast.Assign):
            continue
        value = node.value
        if not (isinstance(value, ast.Constant) and value.value is True):
            continue
        for target in node.targets:
            if isinstance(target, ast.Subscript) and _matches_key(
                target.slice, literal=_FLATTENED_LITERAL, name=_FLATTENED_CONST_NAME
            ):
                return True
    return False


def _is_full_three_mutation_flatten(fn: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    return (
        _clears_coordination_branch(fn)
        and _pops_topology(fn)
        and _sets_flattened_true(fn)
    )


@dataclass(frozen=True)
class _FlattenFinding:
    """One function performing the full three-mutation coordination-flatten."""

    path: Path
    qualname: str
    lineno: int

    def label(self) -> str:
        rel = self.path if not self.path.is_absolute() else self.path.relative_to(_REPO_ROOT)
        return f"{rel}::{self.qualname} (line {self.lineno})"


def _scan_source_for_full_flatten(source: str, path: Path) -> list[_FlattenFinding]:
    tree = parse_source(source, display=str(path))
    findings: list[_FlattenFinding] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_full_three_mutation_flatten(
            node
        ):
            findings.append(_FlattenFinding(path, node.name, node.lineno))
    return findings


def _scan_module_for_full_flatten(path: Path) -> list[_FlattenFinding]:
    return _scan_source_for_full_flatten(path.read_text(encoding="utf-8"), path)


def _scan_repo_for_full_flatten() -> list[_FlattenFinding]:
    findings: list[_FlattenFinding] = []
    for path in sorted(_SRC.rglob("*.py")):
        findings.extend(_scan_module_for_full_flatten(path))
    return findings


# ---------------------------------------------------------------------------
# The ratchet: exactly one function performs the full three-mutation flatten.
# ---------------------------------------------------------------------------


def test_exactly_one_function_performs_the_full_coordination_flatten() -> None:
    """SC-009: the three mutations co-occur in EXACTLY ONE function repo-wide.

    A count of 0 means the primitive itself regressed/vanished; a count > 1
    means a call site re-inlined the mutation set instead of calling the
    primitive (the exact 5th-touch drift this guard exists to catch).
    """
    findings = _scan_repo_for_full_flatten()

    assert len(findings) == 1, (
        "Expected exactly ONE function performing the canonical three-mutation "
        "coordination-flatten (del coordination_branch + pop topology + "
        "flattened=True) -- the flatten_coordination_metadata primitive "
        "(#3219 / FR-015 / SC-009). A count != 1 means either the primitive is "
        "missing/broken, or a call site re-inlined the mutation set instead of "
        f"calling it. Findings: {[f.label() for f in findings]}"
    )
    owner = findings[0]
    owner_rel_path = owner.path.relative_to(_REPO_ROOT).as_posix()
    assert owner_rel_path == _EXPECTED_OWNER_REL_PATH, (
        f"the sole three-mutation flatten function moved to {owner_rel_path!r}; "
        f"expected {_EXPECTED_OWNER_REL_PATH!r} (update this constant only if "
        "the primitive was deliberately relocated)."
    )
    assert owner.qualname == _EXPECTED_OWNER_QUALNAME, (
        f"the sole three-mutation flatten function is named {owner.qualname!r}; "
        f"expected {_EXPECTED_OWNER_QUALNAME!r}."
    )


# ---------------------------------------------------------------------------
# Non-vacuity: the detector actually bites on a planted re-inline.
# ---------------------------------------------------------------------------


_SYNTHETIC_REINLINE_SOURCE = (
    "def _sneaky_reinline(meta):\n"
    '    """A docstring merely mentioning coordination_branch/topology/flattened\n'
    "    must NOT be flagged -- only real code constructs count.\n"
    '    """\n'
    "    # A comment quoting meta.pop(\"topology\") must NOT be flagged either.\n"
    "    if \"coordination_branch\" in meta:\n"
    "        del meta[\"coordination_branch\"]\n"
    "    meta.pop(\"topology\", None)\n"
    "    meta[\"flattened\"] = True\n"
    "    return meta\n"
)


def test_scanner_flags_a_synthetic_reinline_of_the_mutation_set() -> None:
    """Non-vacuity: the detector FLAGS a planted 3-mutation re-inline.

    Without this, a detector that never matches anything would make the main
    ratchet above pass vacuously even after a real 5th re-inline landed.
    """
    findings = _scan_source_for_full_flatten(
        _SYNTHETIC_REINLINE_SOURCE, Path("synthetic_reinline.py")
    )
    assert len(findings) == 1 and findings[0].qualname == "_sneaky_reinline", (
        "scanner failed to flag a planted 3-mutation re-inline -- the guard "
        f"would be vacuous. Findings: {findings!r}"
    )


def test_synthetic_reinline_combined_with_the_real_owner_breaks_the_invariant() -> None:
    """A planted 5th-touch re-inline, alongside the real primitive, makes the
    'exactly one' invariant fail -- proving the guard is non-vacuous
    end-to-end (not just at the unit level of the scanner itself).
    """
    synthetic_findings = _scan_source_for_full_flatten(
        _SYNTHETIC_REINLINE_SOURCE, Path("synthetic_reinline.py")
    )
    real_findings = _scan_repo_for_full_flatten()

    combined_count = len(real_findings) + len(synthetic_findings)
    assert combined_count >= 2, (
        "combining the real single-owner finding with a synthetic re-inline "
        f"must exceed 'exactly one' (got {combined_count}) -- the guard would "
        "otherwise fail to catch a genuine 5th re-inline."
    )


def test_scanner_ignores_prose_that_merely_quotes_the_pattern() -> None:
    """Docstrings/comments describing the pattern are NOT flagged.

    The detector must see only real AST constructs (Delete/Call/Assign nodes),
    not string literals that happen to quote matching text -- otherwise a
    module documenting the primitive (like this test file's own module
    docstring, or the primitive's own docstring) could false-positive.
    """
    prose_only_source = (
        "def _prose_only(meta):\n"
        '    """This function historically cleared coordination_branch, popped\n'
        '    topology, and set flattened = True -- but no longer does any of it.\n'
        '    """\n'
        "    # meta.pop(\"topology\") and meta[\"flattened\"] = True are just words here.\n"
        "    return meta\n"
    )
    assert _scan_source_for_full_flatten(prose_only_source, Path("prose_only.py")) == []


def test_partial_mutation_functions_are_not_flagged() -> None:
    """A function performing only 1 or 2 of the 3 mutations must NOT be
    flagged -- e.g. ``clear_coordination_metadata`` (coordination_branch only)
    or a hypothetical topology-only helper. Only the full co-occurring set
    trips the guard.
    """
    coordination_branch_only = (
        "def clear_coordination_metadata(meta):\n"
        "    if \"coordination_branch\" in meta:\n"
        "        del meta[\"coordination_branch\"]\n"
        "    return meta\n"
    )
    assert (
        _scan_source_for_full_flatten(coordination_branch_only, Path("partial.py")) == []
    )

    topology_and_flattened_only = (
        "def _topology_backfill_write(meta, topology):\n"
        "    meta[\"topology\"] = topology\n"
        "    meta.setdefault(\"flattened\", False)\n"
        "    return meta\n"
    )
    assert (
        _scan_source_for_full_flatten(topology_and_flattened_only, Path("partial2.py"))
        == []
    )
