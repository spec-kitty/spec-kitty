"""Always-on gate: every ``load_meta`` call site is accounted for (FR-007 / NFR-003 / D10).

Source: ``tests/specify_cli/test_meta_fail_closed_full_census_contract.py``,
which lives directly under ``tests/specify_cli`` — recorded ``out_of_matrix``
in ``.github/ci-module-registry.yml`` (#4374, decide-out-of-matrix-test-dirs
ledger, lift-invariant disposition).

The source module carries a second guarantee (driving ACTUAL routed-reader
product functions against corrupt/non-dict ``meta.json`` payloads) that is
broad behavioral coverage, not a single invariant, and is left out-of-matrix
pending a future promote/deferred-promotion decision. This lift keeps only
the #4715-pattern half: an AST scan of the LIVE source tree for
``load_meta`` call sites, cross-referenced against a frozen ledger of
accounted-for sites — mirroring the source's own load-bearing design
constraints (the scan must not be sourced from any census document, and must
resolve aliased imports) so a NEW unwrapped call site, a call count that
grows inside an already-accounted function, or a STALE ledger row (the site
was routed away but the row was not deleted) all fail loudly.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

import pytest

pytestmark = [pytest.mark.architectural]

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

_TARGET = "load_meta"


def _local_bindings(tree: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == _TARGET:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.FunctionDef) and node.name == _TARGET:
            names.add(_TARGET)
    return names


def _qualname_by_line(tree: ast.Module) -> dict[int, str]:
    out: dict[int, str] = {}

    def walk(node: ast.AST, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                qual = f"{prefix}.{child.name}" if prefix else child.name
                for lineno in range(child.lineno, (child.end_lineno or child.lineno) + 1):
                    out[lineno] = qual
                walk(child, qual)
            else:
                walk(child, prefix)

    walk(tree, "")
    return out


def scan_load_meta_call_sites(src_root: Path) -> Counter[tuple[str, str]]:
    found: Counter[tuple[str, str]] = Counter()
    for path in sorted(src_root.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):  # pragma: no cover - unreadable source
            continue
        bindings = _local_bindings(tree)
        quals = _qualname_by_line(tree)
        rel = path.relative_to(src_root.parent).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_call = (isinstance(func, ast.Name) and func.id in bindings) or (isinstance(func, ast.Attribute) and func.attr == _TARGET)
            if is_call:
                found[(rel, quals.get(node.lineno, "<module>"))] += 1
    return found


# MAINTENANCE: mirrors the source module's frozen ledger. If you ROUTE a
# site, DELETE its row here too. If you ADD a legitimate new reader, ADD a
# row with a reason. A mismatch in either direction fails the gate.
_ACCOUNTED_SITES: dict[tuple[str, str], tuple[int, str]] = {
    ("src/specify_cli/cli/commands/_coordination_doctor.py", "_apply_coord_staleness_fixes"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/_coordination_doctor.py", "_collect_coordination_findings"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/_coordination_doctor.py", "check_and_warn_coord_staleness"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/_review_cycle_reconcile_doctor.py", "_report_for_mission"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/agent/mission_check_prerequisites.py", "_read_meta_for_emission"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/agent/mission_repair.py", "run_mission_repair"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py", "_resolve_revert_commit_worktree"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/mission_type.py", "_commit_flattened_meta"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/mission_type.py", "_delete_legacy_coordination_branch"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/mission_type.py", "_expected_discard_branches"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/mission_type.py", "_read_mission_mid8"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/tracker.py", "_resolve_active_feature_slug"): (1, "silent-by-contract"),
    ("src/specify_cli/context/mission_resolver.py", "_build_index"): (1, "silent-by-contract"),
    # #4736: selection/discovery listing tolerates a corrupt meta.json (lists with
    # mid8=None) rather than crashing all discovery — mirror row (see source ledger).
    ("src/specify_cli/context/mission_resolver.py", "list_missions_for_selection"): (1, "silent-by-contract"),
    ("src/specify_cli/coordination/commit_router.py", "_resolve_mid8"): (1, "silent-by-contract"),
    ("src/specify_cli/coordination/legacy_resolution.py", "_load_mission_meta"): (1, "silent-by-contract"),
    ("src/specify_cli/core/paths.py", "load_meta_fail_closed"): (1, "authority"),
    ("src/specify_cli/core/vcs/detection.py", "_get_locked_vcs_from_feature"): (2, "silent-by-contract"),
    ("src/specify_cli/dashboard/scanner.py", "_read_dashboard_feature_meta"): (1, "silent-by-contract"),
    ("src/specify_cli/dashboard/scanner.py", "_read_mission_identity"): (1, "silent-by-contract"),
    ("src/specify_cli/git/sparse_checkout.py", "_load_managed_lane_policies"): (1, "silent-by-contract"),
    ("src/specify_cli/lanes/recovery.py", "_mission_id_from_meta"): (1, "silent-by-contract"),
    ("src/specify_cli/lanes/worktree_allocator.py", "_read_coordination_branch"): (1, "silent-by-contract"),
    # #4764/#4474 primary-tree fallback: mirrors the mission-branch write's
    # on_malformed="none" absorption -- a corrupt/non-dict meta.json degrades
    # to the same "cannot bake mission_number" skip, never an uncaught raise.
    ("src/specify_cli/merge/ordering.py", "_bake_mission_number_on_primary_tree"): (1, "silent-by-contract"),
    ("src/specify_cli/merge/ordering.py", "_compute_next_mission_number_or_none"): (1, "silent-by-contract"),
    ("src/specify_cli/merge/ordering.py", "_write_mission_number_to_branch"): (1, "silent-by-contract"),
    ("src/specify_cli/migration/backfill_runtime_state.py", "_mission_id"): (1, "silent-by-contract"),
    ("src/specify_cli/migration/backfill_runtime_state.py", "_synthesize_claim_anchor"): (1, "silent-by-contract"),
    ("src/specify_cli/migration/runtime_state_cutover.py", "_already_at_snapshot_authority"): (1, "silent-by-contract"),
    ("src/specify_cli/migration/runtime_state_cutover.py", "stamp_accept_cutover"): (1, "silent-by-contract"),
    ("src/specify_cli/migration/verdict_provenance_backfill.py", "_resolve_mission_id"): (1, "silent-by-contract"),
    ("src/specify_cli/mission_metadata.py", "load_meta_or_empty"): (1, "silent-by-contract"),
    ("src/specify_cli/mission_metadata.py", "load_meta_strict"): (1, "silent-by-contract"),
    ("src/specify_cli/missions/_read_path_resolver.py", "_declares_coordination_branch"): (1, "silent-by-contract"),
    ("src/specify_cli/status/cutover_eligibility.py", "_read_meta"): (1, "silent-by-contract"),
    ("src/specify_cli/status/emit.py", "_load_mission_id"): (1, "silent-by-contract"),
    ("src/specify_cli/status/emit.py", "_read_status_phase"): (1, "silent-by-contract"),
    ("src/specify_cli/task_utils/support.py", "load_meta"): (1, "authority"),
    ("src/specify_cli/upgrade/migrations/m_zz_runtime_state_backfill.py", "_mission_needs_cutover"): (1, "silent-by-contract"),
}

_ROUTE_HINT = (
    "Route it through `specify_cli.core.paths.load_meta_fail_closed` (FR-007), "
    "or -- if the site is deliberately silent about corruption -- keep "
    '`load_meta(..., on_malformed="none"/"empty")` and add a '
    "`silent-by-contract` row to _ACCOUNTED_SITES explaining why."
)


def test_no_unaccounted_load_meta_call_sites() -> None:
    live = scan_load_meta_call_sites(_SRC_ROOT)

    unaccounted = {key: n for key, n in live.items() if key not in _ACCOUNTED_SITES}
    assert not unaccounted, (
        "NEW unaccounted `load_meta` call site(s) detected (FR-007 / NFR-003 / D10):\n"
        + "\n".join(f"  {rel}::{qual}  x{n}" for (rel, qual), n in sorted(unaccounted.items()))
        + f"\n\n{_ROUTE_HINT}"
    )

    grew = {key: (live[key], expected) for key, (expected, _reason) in _ACCOUNTED_SITES.items() if live.get(key, 0) > expected}
    assert not grew, (
        "EXTRA `load_meta` call(s) added inside an already-accounted function:\n"
        + "\n".join(f"  {rel}::{qual}  live={got} accounted={exp}" for (rel, qual), (got, exp) in sorted(grew.items()))
        + f"\n\n{_ROUTE_HINT}"
    )

    stale = {key: expected for key, (expected, _reason) in _ACCOUNTED_SITES.items() if live.get(key, 0) < expected}
    assert not stale, (
        "STALE _ACCOUNTED_SITES row(s): the live scan no longer finds these.\n"
        "If you just ROUTED the site, delete its row (a stale row would mask a "
        "future reader re-added at the same place):\n"
        + "\n".join(f"  {rel}::{qual}  accounted={exp}, live={live.get((rel, qual), 0)}" for (rel, qual), exp in sorted(stale.items()))
    )
