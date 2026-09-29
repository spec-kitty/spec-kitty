"""Architectural gate (WP02/T006, #5100 FR-001/FR-002): every call to
``lane_branch_name`` must pass ``target_branch=`` as an explicit keyword.

``lane_branch_name``'s planning-lane arm resolves ``PLANNING_LANE_ID`` to
whatever ``target_branch`` it is given; before this gate existed a caller
could omit it and silently get ``"main"`` (the #5100 defect). ``mypy --strict``
already makes the keyword required at the type level, but several modules
that call this function are under a "transitional quarantine" mypy override
(``pyproject.toml``'s ``[[tool.mypy.overrides]]`` — e.g.
``orchestrator_api/commands.py``, ``cli/commands/implement.py``) where a
stale positional/keyword-missing call would NOT be caught by
``mypy --strict src/``. This AST-based gate is a mypy-independent backstop
that also covers those quarantined modules, closing the defect class by
construction rather than by hoping every caller stays type-checked.

Non-vacuity floor (charter DIRECTIVE_043 / architectural-gate-non-vacuity):
at least 5 real call sites must be found under ``src/`` — a floor of 0 would
let the gate silently stop applying (e.g. every caller switching to
``code_lane_branch_name``) without anyone noticing it had gone dark.

Self-mutation test: the checker is proven to actually catch a missing
keyword by feeding it a synthetic source string, not just by observing the
real tree is clean today.

No allowlist: every call site under ``src/`` must pass the keyword. There is
no carve-out list to keep in sync.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_SRC_ROOT = _REPO_ROOT / "src"
_MIN_CALL_SITES = 5
_TARGET_FUNC_NAME = "lane_branch_name"
_REQUIRED_KEYWORD = "target_branch"


def _iter_lane_branch_name_calls(tree: ast.AST) -> list[ast.Call]:
    """Every ``lane_branch_name(...)`` call node in *tree*, however invoked
    (bare name or ``module.lane_branch_name`` attribute access)."""
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name: str | None = None
        if isinstance(func, ast.Name):
            name = func.id
        elif isinstance(func, ast.Attribute):
            name = func.attr
        if name == _TARGET_FUNC_NAME:
            calls.append(node)
    return calls


def _call_missing_target_branch_keyword(call: ast.Call) -> bool:
    return not any(kw.arg == _REQUIRED_KEYWORD for kw in call.keywords)


def _violations_in_source(source: str, label: str) -> list[str]:
    """Return ``"<label>:<lineno>"`` for every call missing the keyword."""
    tree = ast.parse(source, filename=label)
    return [f"{label}:{call.lineno}" for call in _iter_lane_branch_name_calls(tree) if _call_missing_target_branch_keyword(call)]


def test_checker_self_mutation_catches_missing_keyword() -> None:
    """Prove the checker itself flags a synthetic call missing the keyword,
    and stays silent on an equivalent call that supplies it."""
    bad_source = "def f(slug, lane_id):\n    return lane_branch_name(slug, lane_id)\n"
    assert _violations_in_source(bad_source, "<synthetic-bad>") == ["<synthetic-bad>:2"]

    positional_bad_source = "def f(slug, lane_id, tb):\n    return lane_branch_name(slug, lane_id, tb)\n"
    assert _violations_in_source(positional_bad_source, "<synthetic-positional>") == ["<synthetic-positional>:2"]

    good_source = "def f(slug, lane_id, tb):\n    return lane_branch_name(slug, lane_id, target_branch=tb)\n"
    assert _violations_in_source(good_source, "<synthetic-good>") == []

    unrelated_source = "def f():\n    return some_other_call(1, 2)\n"
    assert _violations_in_source(unrelated_source, "<synthetic-unrelated>") == []


def test_every_lane_branch_name_call_passes_target_branch_keyword() -> None:
    """No call to ``lane_branch_name`` under ``src/`` may omit ``target_branch=``."""
    py_files = sorted(_SRC_ROOT.rglob("*.py"))
    assert py_files, f"expected to find source files under {_SRC_ROOT}"

    all_calls: list[str] = []
    violations: list[str] = []
    for path in py_files:
        source = path.read_text(encoding="utf-8")
        if _TARGET_FUNC_NAME not in source:
            continue
        tree = ast.parse(source, filename=str(path))
        rel = path.relative_to(_REPO_ROOT).as_posix()
        for call in _iter_lane_branch_name_calls(tree):
            all_calls.append(f"{rel}:{call.lineno}")
            if _call_missing_target_branch_keyword(call):
                violations.append(f"{rel}:{call.lineno}")

    assert len(all_calls) >= _MIN_CALL_SITES, (
        f"non-vacuity floor: expected at least {_MIN_CALL_SITES} lane_branch_name() call sites under {_SRC_ROOT}, found {len(all_calls)}: {all_calls}"
    )
    assert not violations, "lane_branch_name() called without the required target_branch= keyword (FR-001/FR-002, #5100): " + ", ".join(violations)
