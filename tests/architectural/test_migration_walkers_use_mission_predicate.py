"""#6627: every ``kitty-specs/`` walker on the migration surface decides residue through ``is_mission_dir``.

``test_mission_resolver_walker_gate`` exempts ``upgrade/migrations/`` and
``migration/`` wholesale, so a migration walker could treat every directory as a
Mission (and fabricate an identity into residue) unseen. This gate closes that:

* every raw walker site in those trees is inventoried here with how it handles a
  residue directory. A new site fails until it is classified, so its author has
  to route it through :func:`specify_cli.context.mission_resolver.is_mission_dir`
  or record why a residue directory cannot be written by it;
* the shared seams the walkers hand a directory to (the shipped, byte-frozen
  migrations included) must call ``is_mission_dir`` (or its single-directory
  wrapper ``is_kitty_specs_residue``) themselves.

The rule (#6669): a ``kitty-specs/`` child with ``spec.md`` or ``meta.json`` on
disk is never residue, while one holding only ``status.json``, an event log or
``tasks/`` is residue wherever git tracks some Mission path. A walker is
therefore only safe when it requires ``meta.json`` itself, filters through the
predicate, or is a shipped migration whose registered class is a no-op because
a residue-aware successor walks instead (``_SUPERSEDED``).

Blind spots of the detector (``_find_raw_walker_calls``), so a walker can hide
from the inventory below:

* ``rglob`` is not an enumeration method it looks for;
* a walker is only seen on a *tainted* name (``kitty_specs``, ``wt_specs``,
  ``main_specs``, ``specs_dir`` and the rest of ``_SPECS_NAME_VOCABULARY``, or a
  name assigned from ``KITTY_SPECS_DIR`` / ``"kitty-specs"``), so any other
  variable name hides an ``iterdir`` or ``glob``;
* a module constant such as ``_KITTY_SPECS_DIRNAME`` is neither of those, so a
  walk built from it is invisible (``_UNDETECTED_WALKERS`` lists them by hand).

Name every new walker variable from the vocabulary so this gate sees it.
"""

from __future__ import annotations

import ast

import pytest

from specify_cli.upgrade.supersession import SUPERSEDED_MIGRATIONS
from tests.architectural.test_mission_resolver_walker_gate import _REPO_ROOT, _find_raw_walker_calls

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_SCANNED_DIRS = ("src/specify_cli/upgrade/migrations", "src/specify_cli/migration", "src/specify_cli/upgrade")

_FILTERS = "filters with is_mission_dir"
_REQUIRES_META = "touches only a directory that already has meta.json, which is never residue (is_kitty_specs_residue)"
_READ_ONLY = "read-only"
_GUARDED_DOWNSTREAM = "the shared seam it writes through checks is_mission_dir"
_SUPERSEDED = "shipped migration registered as a no-op; its residue-aware successor walks instead"

#: (module, enclosing function) -> how a residue directory is handled.
_WALKER_INVENTORY: dict[tuple[str, str], str] = {
    ("src/specify_cli/upgrade/migrations/m_0_13_0_research_csv_schema_check.py", "apply"): _READ_ONLY,
    ("src/specify_cli/upgrade/migrations/m_0_13_0_research_csv_schema_check.py", "detect"): _READ_ONLY,
    ("src/specify_cli/upgrade/migrations/m_0_13_8_target_branch.py", "apply"): _REQUIRES_META,
    ("src/specify_cli/upgrade/migrations/m_0_13_8_target_branch.py", "detect"): _READ_ONLY,
    # The four shipped walkers below were _REQUIRES_STATE / _GUARDED_IDENTITY_ONLY ("rewrites only pre-existing
    # mission state"). Under the #6669 rule a folder holding only status.json or tasks/ is residue, so that claim is
    # false for them; their registered classes are now recorded no-ops and the successors walk through
    # partition_kitty_specs / is_kitty_specs_residue.
    ("src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py", "_find_features_to_migrate"): _SUPERSEDED,
    ("src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py", "detect"): _SUPERSEDED,
    ("src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py", "_find_features_with_lanes"): _SUPERSEDED,
    ("src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py", "detect"): _SUPERSEDED,
    ("src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py", "_iter_feature_dirs"): _SUPERSEDED,
    ("src/specify_cli/upgrade/migrations/m_3_1_1_normalize_status_json.py", "_iter_feature_dirs"): _SUPERSEDED,
    # The one walk every successor shares (WP02): it splits the children through is_kitty_specs_residue.
    ("src/specify_cli/upgrade/migrations/_residue_successor.py", "partition_kitty_specs"): _FILTERS,
    # Unchanged under the new rule: each reads meta.json first (a folder with meta.json is never residue).
    ("src/specify_cli/migration/backfill_identity.py", "backfill_mission_ids"): _REQUIRES_META,
    ("src/specify_cli/migration/backfill_identity.py", "backfill_repo"): _REQUIRES_META,
    ("src/specify_cli/migration/backfill_mission_type.py", "backfill_mission_type_repo"): _REQUIRES_META,
    # Was _REQUIRES_STATE; the shared walk now drops residue through _without_residue (WP05).
    ("src/specify_cli/migration/backfill_runtime_state.py", "_mission_dirs"): _FILTERS,
    ("src/specify_cli/migration/backfill_topology.py", "_kitty_specs_mission_dirs"): _REQUIRES_META,
    ("src/specify_cli/migration/mission_state.py", "_select_mission_dirs"): _FILTERS,
    ("src/specify_cli/migration/normalize_mission_lifecycle.py", "_discover_candidates"): _GUARDED_DOWNSTREAM,
    ("src/specify_cli/migration/runner.py", "_discover_features"): _REQUIRES_META,
    # Was _REQUIRES_STATE; it now skips residue itself before it moves derived files (WP05).
    ("src/specify_cli/migration/runner.py", "_move_derived_files"): _FILTERS,
    # Was _GUARDED_DOWNSTREAM; cutover_repo now calls the predicate itself before cutover_mission.
    ("src/specify_cli/migration/runtime_state_cutover.py", "cutover_repo"): _FILTERS,
}

#: Walkers the detector cannot see (they enumerate through a module constant, not a tainted name), listed by hand.
#: (module, function) -> why a residue directory is safe.
_UNDETECTED_WALKERS: dict[tuple[str, str], str] = {
    # Walks ``project / _KITTY_SPECS_DIRNAME``; every directory it returns goes through cutover_mission
    # (a guarded seam below), whose is_kitty_specs_residue check leaves residue untouched.
    ("src/specify_cli/upgrade/migrations/m_zz_runtime_state_backfill.py", "_iter_mission_dirs"): _GUARDED_DOWNSTREAM,
}

#: The canonical predicate and its one single-directory wrapper.
_PREDICATES = frozenset({"is_mission_dir", "is_kitty_specs_residue"})

#: Shared seams that write (or mint an identity into) a directory a walker hands them; each must decide residue.
_GUARDED_SEAMS = (
    ("src/specify_cli/upgrade/feature_meta.py", "build_baseline_feature_meta"),
    ("src/specify_cli/migration/normalize_mission_lifecycle.py", "normalize_repo"),
    ("src/specify_cli/migration/runtime_state_cutover.py", "cutover_mission"),
    ("src/specify_cli/migration/mission_state.py", "_select_mission_dirs"),
    ("src/specify_cli/context/mission_resolver.py", "is_kitty_specs_residue"),
    ("src/specify_cli/upgrade/migrations/_residue_successor.py", "partition_kitty_specs"),
    ("src/specify_cli/migration/backfill_runtime_state.py", "_without_residue"),
)


def _functions(tree: ast.AST) -> list[ast.FunctionDef | ast.AsyncFunctionDef]:
    return [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)]


def _enclosing_function(tree: ast.AST, line: int) -> str:
    owners = [fn for fn in _functions(tree) if fn.lineno <= line <= (fn.end_lineno or fn.lineno)]
    return max(owners, key=lambda fn: fn.lineno).name if owners else "<module>"


def _walker_sites() -> set[tuple[str, str]]:
    sites: set[tuple[str, str]] = set()
    for rel_dir in _SCANNED_DIRS:
        for path in sorted((_REPO_ROOT / rel_dir).glob("*.py")):
            hits = _find_raw_walker_calls(path)
            if not hits:
                continue
            tree = ast.parse(path.read_text(encoding="utf-8"))
            rel = path.relative_to(_REPO_ROOT).as_posix()
            sites.update((rel, _enclosing_function(tree, line)) for line, _ in hits)
    return sites


def _called_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return call.func.attr if isinstance(call.func, ast.Attribute) else None


def _calls_is_mission_dir(fn: ast.AST) -> bool:
    return any(isinstance(node, ast.Call) and _called_name(node) in _PREDICATES for node in ast.walk(fn))


def test_every_migration_walker_is_classified() -> None:
    sites = _walker_sites()
    assert sites, "no walker found; the scan did not execute"
    unclassified = sorted(sites - _WALKER_INVENTORY.keys())
    assert not unclassified, (
        "New kitty-specs/ walker(s) on the migration surface. Route each through "
        "specify_cli.context.mission_resolver.is_mission_dir (residue must never be written, #6627), "
        f"then add it to _WALKER_INVENTORY: {unclassified}"
    )
    stale = sorted(_WALKER_INVENTORY.keys() - sites)
    assert not stale, f"_WALKER_INVENTORY lists walkers that no longer exist; remove them: {stale}"


@pytest.mark.parametrize(("module", "function"), _GUARDED_SEAMS)
def test_guarded_seam_calls_is_mission_dir(module: str, function: str) -> None:
    tree = ast.parse((_REPO_ROOT / module).read_text(encoding="utf-8"))
    matches = [fn for fn in _functions(tree) if fn.name == function]
    assert matches, f"{module}::{function} not found"
    assert all(_calls_is_mission_dir(fn) for fn in matches), f"{module}::{function} must decide residue through is_mission_dir or is_kitty_specs_residue (#6627)"


def _reaches_predicate(tree: ast.AST, fn: ast.AST, seen: frozenset[int] = frozenset()) -> bool:
    """True when *fn* calls a predicate, directly or through a function of the same module (transitively)."""
    if id(fn) in seen:
        return False
    seen = seen | {id(fn)}
    local = {f.name: f for f in _functions(tree)}
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        name = _called_name(node)
        if name in _PREDICATES:
            return True
        if name in local and _reaches_predicate(tree, local[name], seen):
            return True
    return False


def test_filters_classification_is_true() -> None:
    """An inventory entry that claims to filter must actually reach is_mission_dir / is_kitty_specs_residue."""
    claimed = [(module, function) for (module, function), how in _WALKER_INVENTORY.items() if how == _FILTERS]
    assert claimed, "no _FILTERS entry; the check did not execute"
    for module, function in claimed:
        tree = ast.parse((_REPO_ROOT / module).read_text(encoding="utf-8"))
        assert any(fn.name == function and _reaches_predicate(tree, fn) for fn in _functions(tree)), f"{module}::{function}"


def _declared_migration_ids(module: str) -> set[str]:
    tree = ast.parse((_REPO_ROOT / module).read_text(encoding="utf-8"))
    return {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "migration_id" for target in node.targets)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }


def test_superseded_classification_is_true() -> None:
    """A _SUPERSEDED entry's shipped migration must really be registered as a no-op (#6589)."""
    modules = {module for (module, _function), how in _WALKER_INVENTORY.items() if how == _SUPERSEDED}
    assert modules, "no _SUPERSEDED entry; the check did not execute"
    for module in sorted(modules):
        ids = _declared_migration_ids(module)
        assert ids, f"{module} declares no migration_id"
        assert ids <= SUPERSEDED_MIGRATIONS.keys(), f"{module}: {sorted(ids - SUPERSEDED_MIGRATIONS.keys())} is not in SUPERSEDED_MIGRATIONS"


@pytest.mark.parametrize(("module", "function"), sorted(_UNDETECTED_WALKERS))
def test_undetected_walker_still_exists_and_is_guarded(module: str, function: str) -> None:
    tree = ast.parse((_REPO_ROOT / module).read_text(encoding="utf-8"))
    assert any(fn.name == function for fn in _functions(tree)), f"{module}::{function} is gone; remove it from _UNDETECTED_WALKERS"
    assert ("src/specify_cli/migration/runtime_state_cutover.py", "cutover_mission") in _GUARDED_SEAMS


def test_detector_blind_spots_stay_blind_to_hand_listed_walkers() -> None:
    """If the detector ever learns to see a hand-listed walker, it belongs in _WALKER_INVENTORY instead."""
    assert not set(_UNDETECTED_WALKERS) & _walker_sites()
