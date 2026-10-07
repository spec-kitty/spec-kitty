"""Class gate: every evidence gate checks origin freshness before it trusts local evidence (FR-014, C-004, SC-005).

Mission ``second-clone-origin-reconciliation-01M48V8W``. An *evidence gate* is a
command that decides on the Mission's status evidence or on lane content
(``review``, ``accept``, ``consolidate`` and the two orchestrator-api commands).
A second clone that has not heard from origin gives such a gate stale evidence
and the gate passes. The shared cure is :mod:`specify_cli.git.origin_freshness`
(reached through :func:`specify_cli.git.origin_gate.run_origin_gate` or the
consolidation wrapper); this gate fails when a registered entry point cannot
reach a real **call** to it.

How the set is found (no hand-kept list that can rot):

* **Derived roots.** Every function in ``cli/commands/`` and ``orchestrator_api/``
  that (transitively, within its module) calls ``_run_lane_based_consolidation``,
  ``_execute_lane_merge`` or ``collect_feature_summary`` and is not itself called
  by another such function: the outermost door a command takes.
* The ``review`` command (it reconciles its lane; it calls none of the triggers)
  and the executor door ``_run_lane_based_consolidation`` (the one definition the
  triggers name).
* A **floor** of the five known entry points: the derived set may grow, never
  shrink below it, so a refactor that hides an entry point cannot silently empty
  the gate.

Reachability is an ``ast.Call`` walk to one of the ``_CHECK_FUNCTIONS`` (a bare
import or name reference proves nothing, and neither does calling a lane selector) through same-module and imported ``specify_cli`` functions.

**There is no allowlist.** ``consolidate --dry-run`` is not an exemption but a
reasoned non-gate: it forecasts only, never reaches the executor, moves nothing
and trusts no evidence it then acts on (see ``NOT_AN_EVIDENCE_GATE``).

Non-vacuity (standing order 5): the floor, a derived-set size check, a planted
entry point that omits the call (must be flagged), a planted name-only
reference (must be flagged), and a planted entry that does call (must pass).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from dataclasses import dataclass
from functools import cache
from pathlib import Path

import pytest

pytestmark = pytest.mark.architectural

_SRC = Path(__file__).resolve().parents[2] / "src"
_SCAN_DIRS = ("specify_cli/cli/commands", "specify_cli/orchestrator_api")
_TRIGGERS = frozenset({"_run_lane_based_consolidation", "_execute_lane_merge", "collect_feature_summary"})
# The functions that actually contact origin or apply its verdict. Helpers that only
# select lanes or read the setting (``approved_lane_branches``, ``resolve_origin_check_mode``,
# ``verdict_payloads``) are deliberately absent: calling one proves no check ran.
_CHECK_FUNCTIONS = frozenset(
    {
        ("specify_cli.git.origin_gate", "run_origin_gate"),
        ("specify_cli.consolidation.origin_gate", "check_origin_before_status_dir"),
        ("specify_cli.git.origin_freshness", "check_mission_branches"),
        ("specify_cli.git.origin_freshness", "check_branches"),
        ("specify_cli.git.origin_freshness", "enforce_merge_gate"),
        ("specify_cli.git.origin_freshness", "plan_review_lane"),
    }
)
_EXECUTOR_DOOR = ("specify_cli/consolidation/executor.py", "_run_lane_based_consolidation")
_REVIEW_COMMAND = ("specify_cli/cli/commands/agent/workflow.py", "review")

# The five entry points known when the gate was written (floor, never a ceiling).
_KNOWN_FLOOR = frozenset(
    {
        ("specify_cli/consolidation/executor.py", "_run_lane_based_consolidation"),
        ("specify_cli/cli/commands/accept.py", "accept"),
        ("specify_cli/orchestrator_api/consolidation.py", "accept_mission"),
        ("specify_cli/orchestrator_api/consolidation.py", "consolidate_mission"),
        ("specify_cli/cli/commands/agent/workflow.py", "review"),
    }
)

# Not an allowlist: a recorded, reasoned non-gate. ``consolidate --dry-run`` returns
# the conflict forecast before the executor is entered, mutates nothing and
# produces no verdict a later step acts on.
NOT_AN_EVIDENCE_GATE = {
    "consolidate --dry-run": "forecast only; never reaches _run_lane_based_consolidation, moves no branch and acts on no evidence",
}

Entry = tuple[str, str]  # (path relative to src/, function name)


@dataclass(frozen=True)
class _Module:
    rel: str
    defs: dict[str, list[ast.AST]]
    imports: dict[str, tuple[str, str | None]]  # local name -> (module, original name or None for a module alias)


def _module_name(rel: str) -> str:
    parts = rel.removesuffix(".py").split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _rel_for_module(module: str) -> str | None:
    base = module.replace(".", "/")
    for candidate in (f"{base}.py", f"{base}/__init__.py"):
        if (_SRC / candidate).is_file():
            return candidate
    return None


def _index(tree: ast.Module, rel: str) -> _Module:
    defs: dict[str, list[ast.AST]] = {}
    imports: dict[str, tuple[str, str | None]] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            defs.setdefault(node.name, []).append(node)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            for alias in node.names:
                imports[alias.asname or alias.name] = (node.module, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports[alias.asname or alias.name.split(".")[0]] = (alias.name, None)
    return _Module(rel, defs, imports)


@cache
def _load(rel: str) -> _Module:
    return _index(ast.parse((_SRC / rel).read_text(encoding="utf-8")), rel)


def _calls(node: ast.AST) -> Iterator[ast.Call]:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            yield child


def _resolve(module: _Module, call: ast.Call) -> tuple[str, str] | None:
    """The ``(module name, function name)`` a call targets, when it is a defined or imported name."""
    func = call.func
    if isinstance(func, ast.Name):
        if func.id in module.defs:
            return (_module_name(module.rel), func.id)
        origin = module.imports.get(func.id)
        if origin is not None and origin[1] is not None:
            return (origin[0], origin[1])
        return None
    if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
        origin = module.imports.get(func.value.id)
        if origin is None:
            return None
        # ``from pkg import mod`` then ``mod.fn()`` or ``import pkg.mod as m`` then ``m.fn()``.
        target_module = f"{origin[0]}.{origin[1]}" if origin[1] is not None else origin[0]
        return (target_module, func.attr)
    return None


def reaches_check(entries: dict[Entry, ast.AST], module: _Module, node: ast.AST, seen: set[Entry]) -> bool:
    """True when *node* (a function body) makes an ``ast.Call`` to a freshness-check function, transitively."""
    for call in _calls(node):
        target = _resolve(module, call)
        if target is None:
            continue
        target_module, name = target
        if target in _CHECK_FUNCTIONS:
            return True
        rel = _rel_for_module(target_module)
        if rel is None:
            continue
        callee_module = _load(rel)
        key = (rel, name)
        if key in seen:
            continue
        seen.add(key)
        for definition in callee_module.defs.get(name, []):
            if reaches_check(entries, callee_module, definition, seen):
                return True
    return False


def _direct_callers(module: _Module) -> set[str]:
    callers: set[str] = set()
    for name, definitions in module.defs.items():
        for definition in definitions:
            for call in _calls(definition):
                called = call.func.id if isinstance(call.func, ast.Name) else call.func.attr if isinstance(call.func, ast.Attribute) else None
                if called in _TRIGGERS and called != name:
                    callers.add(name)
    return callers


def _caller_closure(module: _Module) -> set[str]:
    closure = _direct_callers(module)
    grew = True
    while grew:
        grew = False
        for name, definitions in module.defs.items():
            if name in closure:
                continue
            for definition in definitions:
                if any(isinstance(c.func, ast.Name) and c.func.id in closure for c in _calls(definition)):
                    closure.add(name)
                    grew = True
                    break
    return closure


def _roots(module: _Module, closure: set[str]) -> set[str]:
    called: set[str] = set()
    for name in closure:
        for definition in module.defs[name]:
            called |= {c.func.id for c in _calls(definition) if isinstance(c.func, ast.Name) and c.func.id in closure and c.func.id != name}
    return closure - called


def _scan_files() -> list[str]:
    files: list[str] = []
    for directory in _SCAN_DIRS:
        files.extend(sorted(p.relative_to(_SRC).as_posix() for p in (_SRC / directory).rglob("*.py")))
    return files


def derived_entries() -> set[Entry]:
    """Every registered evidence-gate entry point, derived from the source."""
    entries: set[Entry] = {_EXECUTOR_DOOR, _REVIEW_COMMAND}
    for rel in _scan_files():
        module = _load(rel)
        entries |= {(rel, name) for name in _roots(module, _caller_closure(module))}
    return entries


def entries_missing_the_check(entries: set[Entry]) -> list[Entry]:
    missing: list[Entry] = []
    for rel, name in sorted(entries):
        module = _load(rel)
        definitions = module.defs.get(name, [])
        seen: set[Entry] = {(rel, name)}
        if not definitions or not any(reaches_check({}, module, d, seen) for d in definitions):
            missing.append((rel, name))
    return missing


def test_every_evidence_gate_entry_point_calls_the_origin_freshness_check() -> None:
    missing = entries_missing_the_check(derived_entries())
    assert not missing, (
        "Evidence-gate entry points with no call to specify_cli.git.origin_freshness / git.origin_gate / consolidation.origin_gate "
        "(there is no allowlist):\n"
        + "\n".join(f"  {rel}::{name}" for rel, name in missing)
        + "\nCall run_origin_gate (or check_origin_before_status_dir) before the gate trusts local evidence."
    )


def test_known_entry_points_are_still_registered_floor() -> None:
    lost = _KNOWN_FLOOR - derived_entries()
    assert not lost, f"the derived entry set lost known entry points (floor): {sorted(lost)}"


def test_dry_run_exemption_is_a_reasoned_non_gate_not_an_allowlist() -> None:
    assert set(NOT_AN_EVIDENCE_GATE) == {"consolidate --dry-run"}
    assert all(reason.strip() for reason in NOT_AN_EVIDENCE_GATE.values())


def _planted(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> list[Entry]:
    pkg = tmp_path / "specify_cli" / "cli" / "commands"
    pkg.mkdir(parents=True)
    (pkg / "planted.py").write_text(body, encoding="utf-8")
    monkeypatch.setattr(f"{__name__}._SRC", tmp_path)
    _load.cache_clear()
    try:
        return entries_missing_the_check({("specify_cli/cli/commands/planted.py", "gate")})
    finally:
        _load.cache_clear()


def test_planted_entry_point_that_omits_the_check_is_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = "def gate(root, slug):\n    return collect_feature_summary(root, slug)\n"
    assert _planted(tmp_path, monkeypatch, body) == [("specify_cli/cli/commands/planted.py", "gate")]


def test_planted_name_only_reference_is_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = "from specify_cli.git.origin_gate import run_origin_gate\n\ndef gate(root, slug):\n    _ = run_origin_gate\n    return slug\n"
    assert _planted(tmp_path, monkeypatch, body) == [("specify_cli/cli/commands/planted.py", "gate")]


def test_planted_entry_point_that_calls_the_check_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = "from specify_cli.git.origin_gate import run_origin_gate\n\ndef gate(root, slug):\n    return run_origin_gate(root, slug)\n"
    assert _planted(tmp_path, monkeypatch, body) == []


def test_planted_entry_point_reaching_the_check_through_a_helper_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = (
        "from specify_cli.git.origin_gate import run_origin_gate\n\n"
        "def _helper(root, slug):\n    return run_origin_gate(root, slug)\n\n"
        "def gate(root, slug):\n    return _helper(root, slug)\n"
    )
    assert _planted(tmp_path, monkeypatch, body) == []


def test_planted_call_to_a_lane_selector_is_not_a_check(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = "from specify_cli.git.origin_freshness import approved_lane_branches\n\ndef gate(root, slug):\n    return approved_lane_branches(root, slug, None)\n"
    assert _planted(tmp_path, monkeypatch, body) == [("specify_cli/cli/commands/planted.py", "gate")]


# The one bypass of the executor's own check: a caller that already ran the origin gate
# passes ``origin_gated=True`` so the same remote is not contacted twice. Every function
# that passes a value other than literal ``False`` must be reached only from roots that
# themselves run a check *outside* the executor door (the door's own check is skipped
# by exactly that keyword).
_BYPASS_KEYWORD = "origin_gated"


def _passes_bypass(call: ast.Call) -> bool:
    return any(kw.arg == _BYPASS_KEYWORD and not (isinstance(kw.value, ast.Constant) and kw.value.value is False) for kw in call.keywords)


def _same_module_callers_of(module: _Module, target: str) -> set[str]:
    closure = {target}
    grew = True
    while grew:
        grew = False
        for name, definitions in module.defs.items():
            if name in closure:
                continue
            if any(isinstance(c.func, ast.Name) and c.func.id in closure for d in definitions for c in _calls(d)):
                closure.add(name)
                grew = True
    return closure


def bypass_sites() -> set[Entry]:
    sites: set[Entry] = set()
    for rel in _scan_files():
        module = _load(rel)
        for name, definitions in module.defs.items():
            if any(_passes_bypass(c) for d in definitions for c in _calls(d)):
                sites.add((rel, name))
    return sites


def _call_runs_check(module: _Module, call: ast.Call, seen: set[Entry]) -> bool:
    """True when this one call is a freshness check or reaches one, transitively."""
    target = _resolve(module, call)
    if target is None:
        return False
    if target in _CHECK_FUNCTIONS:
        return True
    rel = _rel_for_module(target[0])
    if rel is None or (rel, target[1]) in seen:
        return False
    seen.add((rel, target[1]))
    callee_module = _load(rel)
    return any(reaches_check({}, callee_module, d, seen) for d in callee_module.defs.get(target[1], []))


def _check_precedes_bypass(module: _Module, definition: ast.AST, toward_bypass: set[str], seen: set[Entry]) -> bool:
    """True when *definition* runs a check, and no call that leads to the bypass is made on an earlier line.

    A call leads to the bypass when it passes ``origin_gated`` itself or calls a
    same-module function in *toward_bypass* (the closure of callers of the site).
    """
    calls = sorted(_calls(definition), key=lambda c: c.lineno)
    check_lines = [c.lineno for c in calls if _call_runs_check(module, c, seen)]
    bypass_lines = [c.lineno for c in calls if _passes_bypass(c) or (isinstance(c.func, ast.Name) and c.func.id in toward_bypass)]
    return bool(check_lines) and (not bypass_lines or min(check_lines) < min(bypass_lines))


def unguarded_bypasses() -> list[Entry]:
    """Roots that reach an ``origin_gated`` bypass without running a check of their own BEFORE the call that leads to it."""
    unguarded: list[Entry] = []
    for rel, site in sorted(bypass_sites()):
        module = _load(rel)
        callers = _same_module_callers_of(module, site)
        for root in sorted(_roots(module, callers) or {site}):
            seen: set[Entry] = {(rel, root), _EXECUTOR_DOOR}
            if not any(_check_precedes_bypass(module, d, callers, seen) for d in module.defs[root]):
                unguarded.append((rel, root))
    return unguarded


def test_origin_gated_bypass_is_only_taken_after_a_check() -> None:
    """Every root that reaches the bypass runs a freshness check on an earlier line than the call that leads to it."""
    assert unguarded_bypasses() == []


def test_origin_gated_bypass_sites_are_found() -> None:
    # Non-vacuity: the planning-only orchestrator path is the known bypass today.
    assert ("specify_cli/orchestrator_api/consolidation.py", "_execute_planning_only_merge") in bypass_sites()


def _planted_bypass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str) -> list[Entry]:
    pkg = tmp_path / "specify_cli" / "cli" / "commands"
    pkg.mkdir(parents=True)
    (pkg / "planted.py").write_text(body, encoding="utf-8")
    monkeypatch.setattr(f"{__name__}._SRC", tmp_path)
    monkeypatch.setattr(f"{__name__}._SCAN_DIRS", ("specify_cli/cli/commands",))
    _load.cache_clear()
    try:
        return unguarded_bypasses()
    finally:
        _load.cache_clear()


def test_planted_bypass_without_a_check_is_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = "def _run(root):\n    return _run_lane_based_consolidation(root, origin_gated=True)\n\ndef gate(root):\n    return _run(root)\n"
    assert _planted_bypass(tmp_path, monkeypatch, body) == [("specify_cli/cli/commands/planted.py", "gate")]


def test_planted_check_after_the_bypass_is_flagged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = (
        "from specify_cli.git.origin_gate import run_origin_gate\n\n"
        "def _run(root):\n    return _run_lane_based_consolidation(root, origin_gated=True)\n\n"
        "def gate(root):\n    _run(root)\n    run_origin_gate(root)\n"
    )
    assert _planted_bypass(tmp_path, monkeypatch, body) == [("specify_cli/cli/commands/planted.py", "gate")]


def test_planted_bypass_after_a_check_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = (
        "from specify_cli.git.origin_gate import run_origin_gate\n\n"
        "def _run(root):\n    return _run_lane_based_consolidation(root, origin_gated=True)\n\n"
        "def gate(root):\n    run_origin_gate(root)\n    return _run(root)\n"
    )
    assert _planted_bypass(tmp_path, monkeypatch, body) == []


def test_planted_explicit_false_is_not_a_bypass(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    body = "def gate(root):\n    return _run_lane_based_consolidation(root, origin_gated=False)\n"
    assert _planted_bypass(tmp_path, monkeypatch, body) == []
