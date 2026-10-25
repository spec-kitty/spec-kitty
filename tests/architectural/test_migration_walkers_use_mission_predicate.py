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
"""

from __future__ import annotations

import ast

import pytest

from tests.architectural.test_mission_resolver_walker_gate import _REPO_ROOT, _find_raw_walker_calls

pytestmark = [pytest.mark.architectural, pytest.mark.fast]

_SCANNED_DIRS = ("src/specify_cli/upgrade/migrations", "src/specify_cli/migration", "src/specify_cli/upgrade")

_FILTERS = "filters with is_mission_dir"
_REQUIRES_META = "touches only a directory that already has meta.json, which is never residue (is_kitty_specs_residue)"
_REQUIRES_STATE = "rewrites only pre-existing mission state (status.json / tasks lanes / derived files)"
_READ_ONLY = "read-only"
_GUARDED_DOWNSTREAM = "the shared seam it writes through checks is_mission_dir"
_GUARDED_IDENTITY_ONLY = (
    "shipped 2.0.6 sweep: the baseline meta.json / identity seam checks is_mission_dir; its in-module WP-frontmatter, "
    "orphan-snapshot and status.json refresh still rewrite PRE-EXISTING untracked state in a residue directory (follow-up, #6627)"
)

#: (module, enclosing function) -> how a residue directory is handled.
_WALKER_INVENTORY: dict[tuple[str, str], str] = {
    ("src/specify_cli/upgrade/migrations/m_0_13_0_research_csv_schema_check.py", "apply"): _READ_ONLY,
    ("src/specify_cli/upgrade/migrations/m_0_13_0_research_csv_schema_check.py", "detect"): _READ_ONLY,
    ("src/specify_cli/upgrade/migrations/m_0_13_8_target_branch.py", "apply"): _REQUIRES_META,
    ("src/specify_cli/upgrade/migrations/m_0_13_8_target_branch.py", "detect"): _READ_ONLY,
    ("src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py", "_find_features_to_migrate"): _REQUIRES_STATE,
    ("src/specify_cli/upgrade/migrations/m_0_9_0_frontmatter_only_lanes.py", "detect"): _READ_ONLY,
    ("src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py", "_find_features_with_lanes"): _REQUIRES_STATE,
    ("src/specify_cli/upgrade/migrations/m_0_9_1_complete_lane_migration.py", "detect"): _READ_ONLY,
    ("src/specify_cli/upgrade/migrations/m_2_0_6_consistency_sweep.py", "_iter_feature_dirs"): _GUARDED_IDENTITY_ONLY,
    ("src/specify_cli/upgrade/migrations/m_3_1_1_normalize_status_json.py", "_iter_feature_dirs"): _REQUIRES_STATE,
    ("src/specify_cli/migration/backfill_identity.py", "backfill_mission_ids"): _REQUIRES_META,
    ("src/specify_cli/migration/backfill_identity.py", "backfill_repo"): _REQUIRES_META,
    ("src/specify_cli/migration/backfill_mission_type.py", "backfill_mission_type_repo"): _REQUIRES_META,
    ("src/specify_cli/migration/backfill_runtime_state.py", "_mission_dirs"): _REQUIRES_STATE,
    ("src/specify_cli/migration/backfill_topology.py", "_kitty_specs_mission_dirs"): _REQUIRES_META,
    ("src/specify_cli/migration/mission_state.py", "_select_mission_dirs"): _FILTERS,
    ("src/specify_cli/migration/normalize_mission_lifecycle.py", "_discover_candidates"): _GUARDED_DOWNSTREAM,
    ("src/specify_cli/migration/runner.py", "_discover_features"): _REQUIRES_META,
    ("src/specify_cli/migration/runner.py", "_move_derived_files"): _REQUIRES_STATE,
    ("src/specify_cli/migration/runtime_state_cutover.py", "cutover_repo"): _GUARDED_DOWNSTREAM,
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


def test_filters_classification_is_true() -> None:
    """An inventory entry that claims to filter must actually call is_mission_dir."""
    for (module, function), how in _WALKER_INVENTORY.items():
        if how != _FILTERS:
            continue
        tree = ast.parse((_REPO_ROOT / module).read_text(encoding="utf-8"))
        assert any(fn.name == function and _calls_is_mission_dir(fn) for fn in _functions(tree)), f"{module}::{function}"
