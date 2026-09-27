"""The ``load_meta`` call-site census: ONE scanner, ONE ledger (#5138).

Every ``load_meta`` call site under ``src/`` must be accounted for in
:data:`ACCOUNTED_SITES` -- routed sites leave the scan, deliberately silent
readers carry a ``silent-by-contract`` row (FR-007 / NFR-003 / D10).

This module is the single home of the scanner and the ledger. The always-on
gate (``tests/architectural/test_lifted_root_meta_fail_closed_census.py``) and
the out-of-matrix contract module
(``tests/specify_cli/test_meta_fail_closed_full_census_contract.py``) both
import it. Before #5138 each file carried its own copy of both, and the copies
drifted: the lifted ledger gained the ``_bake_mission_number_on_primary_tree``
row while the source did not, which reddened only the out-of-matrix contract
(#5135).

Two design constraints are load-bearing:

* **The scan must not be sourced from the census.** It walks the live tree, so
  a site added after any census snapshot is still discovered.
* **The scan must resolve aliased imports.** ``from ... import load_meta as
  _lm`` followed by ``_lm(...)`` is a real form in this tree; a text grep
  cannot see it.
"""

from __future__ import annotations

import ast
from collections import Counter
from pathlib import Path

from tests.architectural._ast_scan import parse_file, qualname_by_line

__all__ = ["ACCOUNTED_SITES", "ROUTE_HINT", "TARGET", "scan_load_meta_call_sites"]

#: The canonical reader name both ``load_meta`` definitions share (DEF A,
#: ``mission_metadata.py``; DEF B, the ``task_utils`` path adapter).
TARGET = "load_meta"


def _local_bindings(tree: ast.Module) -> set[str]:
    """Resolve every local name in *tree* that is bound to a ``load_meta``.

    Covers the three binding forms that occur in this tree:

    * ``from x import load_meta``            -> ``load_meta``
    * ``from x import load_meta as _alias``  -> ``_alias``   (the grep blind spot)
    * ``def load_meta(...)`` in this module  -> ``load_meta`` (the definition's
      own module calling itself, e.g. ``mission_metadata.py``)

    Module-qualified calls (``import x as mm`` then ``mm.load_meta(...)``) need
    no binding: :func:`scan_load_meta_call_sites` matches those on the
    attribute name directly, so every file is scanned regardless of what this
    function returns.

    Imports are collected with :func:`ast.walk` rather than at module scope
    only, because this codebase deliberately uses in-function deferred imports
    to break circular-import cycles. Over-approximating the binding scope is
    the safe direction: it can only make the gate stricter.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == TARGET:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.FunctionDef) and node.name == TARGET:
            names.add(TARGET)
    return names


def scan_load_meta_call_sites(src_root: Path) -> Counter[tuple[str, str]]:
    """Discover every live ``load_meta`` CALL site under *src_root*.

    Returns a count keyed by ``(repo-relative path, enclosing qualname)``.

    This is the gate's independent discovery step: it reads the source tree,
    never the census. A site routed onto ``load_meta_fail_closed`` disappears
    from this set (it no longer calls ``load_meta``) — which is exactly how
    routing is observed as progress.
    """
    found: Counter[tuple[str, str]] = Counter()
    for path in sorted(src_root.rglob("*.py")):
        rel = path.relative_to(src_root.parent).as_posix()
        # Fail closed (#4362 / #5139): a skipped file would drop its call
        # sites from the census and let the gate pass over unread code.
        tree = parse_file(path, display=rel)
        bindings = _local_bindings(tree)
        quals = qualname_by_line(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            func = node.func
            is_call = (isinstance(func, ast.Name) and func.id in bindings) or (isinstance(func, ast.Attribute) and func.attr == TARGET)
            if is_call:
                found[(rel, quals.get(node.lineno, "<module>"))] += 1
    return found


# --------------------------------------------------------------------------- #
# The frozen ledger of KNOWN, ACCOUNTED-FOR sites.
# --------------------------------------------------------------------------- #
#
# Every entry is ``(relpath, enclosing qualname) -> (count, reason)``.
#
# Reasons:
#   ``silent-by-contract`` — opted into the silent arm (``on_malformed="none"``
#       / ``"empty"`` / ``load_meta_or_empty``). Corruption is INTENTIONALLY
#       absorbed; the spec's Edge Cases require these stay unrouted.
#   ``authority``          — the canonical parser/adapter definitions
#       themselves: DEF A's ``def load_meta`` (``mission_metadata.py``), the
#       one public fail-closed wrapper (``core/paths.py``), and the DEF B path
#       adapter (``task_utils/support.py``) that delegates to DEF A. These are
#       the reader, not a caller of it -- there is nothing to route.
#       (Landing-fold correction, PR #3155 second-round accuracy review: this
#       bucket used to also hold 11 of ``mission_metadata.py``'s own mutation
#       helpers -- e.g. ``set_vcs_lock``, ``record_acceptance`` -- under the
#       claim that "routing these onto the wrapper would be circular". That
#       claim was refuted: ``core/paths.py``'s ``load_meta_fail_closed``
#       already resolves the identical cycle via a documented deferred
#       in-function import, so mirroring that pattern inside
#       ``mission_metadata.py`` is not circular either. All 11 are now routed
#       through ``load_meta_fail_closed`` and removed from this ledger --
#       being colocated with the parser was never a real routing obstacle,
#       just an unrouted site with an overbroad exemption.)
#   ``pending-batch-a``    — (historical) the bucket of routing targets that
#       were verified absent from BOTH ``tasks/WP08-meta-fail-closed-route-batch-a.md``
#       and ``tasks/WP09-meta-fail-closed-route-batch-b.md``'s ``owned_files``
#       lists — neither WP claimed those files, so #3140's closure did not
#       cover them. Every row in this bucket (13 functions / 14 call sites —
#       issue #3162's 13 bullets name 12 of the functions, ``read_primary_meta``
#       twice, and the bucket's one row beyond that list is
#       ``_resolve_status_surface_dir``) was routed through
#       ``load_meta_fail_closed`` by the #3162 pass and its row DELETED — the
#       bucket is empty now, and any site that reappears here is a regression,
#       not a leftover.
#
# MAINTENANCE: this ledger is checked for exact equality against the live scan.
# If you ROUTE a site, DELETE its row. If you ADD a legitimate new reader,
# ADD a row with a reason. A mismatch in either direction fails the gate on
# purpose — that is the anti-rot mechanic, mirroring the allow-list staleness
# detection in ``tests/architectural/test_inline_meta_read_gate.py``.
ACCOUNTED_SITES: dict[tuple[str, str], tuple[int, str]] = {
    ("src/specify_cli/cli/commands/_coordination_doctor.py", "_apply_coord_staleness_fixes"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/_coordination_doctor.py", "_collect_coordination_findings"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/_coordination_doctor.py", "check_and_warn_coord_staleness"): (1, "silent-by-contract"),
    # PR #3211 landing pass (2026-08-05, F4): reads with
    # `on_malformed="none"` and returns None (no reconciliation) on an
    # unreadable meta.json -- deliberately silent, not fail-closed.
    ("src/specify_cli/cli/commands/_review_cycle_reconcile_doctor.py", "_report_for_mission"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/agent/mission_check_prerequisites.py", "_read_meta_for_emission"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/agent/mission_repair.py", "run_mission_repair"): (1, "silent-by-contract"),
    # PR #3211 landing pass (2026-08-05, F4): reads the primary metadata with
    # `allow_missing=True, on_malformed="none"` to best-effort resolve a
    # coord worktree for a revert compensator -- a missing/malformed
    # mission_id is handled explicitly below (raises a typed
    # VerdictRevertError), so this read itself is deliberately silent.
    ("src/specify_cli/cli/commands/agent/tasks_verdict_persistence.py", "_resolve_revert_commit_worktree"): (1, "silent-by-contract"),
    # #3716: the discard flatten's commit leg reads meta.json only to resolve the
    # primary `target_branch` for the commit; `allow_missing=True,
    # on_malformed="none"` keeps it deliberately silent — a missing/malformed meta
    # falls back to the current branch and the leg is fail-open-but-loud (warns,
    # never aborts an otherwise-successful discard), so a fail-closed read would be
    # wrong here.
    ("src/specify_cli/cli/commands/mission_type.py", "_commit_flattened_meta"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/mission_type.py", "_delete_legacy_coordination_branch"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/mission_type.py", "_expected_discard_branches"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/mission_type.py", "_read_mission_mid8"): (1, "silent-by-contract"),
    ("src/specify_cli/cli/commands/tracker.py", "_resolve_active_feature_slug"): (1, "silent-by-contract"),
    ("src/specify_cli/context/mission_resolver.py", "_build_index"): (1, "silent-by-contract"),
    # #4736: the mission SELECTION/discovery listing must tolerate a corrupt
    # meta.json — it lists the mission with `mid8=None` (best-effort
    # `friendly_name`) rather than crashing the whole listing; a fail-closed
    # read would break `next`/plan/tasks discovery for ALL missions because one
    # mission has a malformed meta.
    ("src/specify_cli/context/mission_resolver.py", "list_missions_for_selection"): (1, "silent-by-contract"),
    ("src/specify_cli/coordination/commit_router.py", "_resolve_mid8"): (1, "silent-by-contract"),
    ("src/specify_cli/coordination/legacy_resolution.py", "_load_mission_meta"): (1, "silent-by-contract"),
    # ``load_meta_fail_closed`` is the canonical fail-closed authority; it calls
    # ``load_meta`` once via a deferred (function-local) import — the D4-sanctioned
    # shape that avoids the module-level ``core.paths -> mission_metadata`` cycle
    # while keeping the legacy path-named messages + ``MissionMetaReadError`` wrap.
    # (Landing #3319: the mission had briefly re-expressed this to decode via the
    # kernel L1 primitive directly and deleted this row; that changed observable
    # error messages and the ``MissionMetaReadError.cause`` chain and broke the
    # D4 import-shape guard, so the delegation — and this "authority" row — are
    # restored to match ``main``.)
    ("src/specify_cli/core/paths.py", "load_meta_fail_closed"): (1, "authority"),
    ("src/specify_cli/core/vcs/detection.py", "_get_locked_vcs_from_feature"): (2, "silent-by-contract"),
    ("src/specify_cli/dashboard/scanner.py", "_read_dashboard_feature_meta"): (1, "silent-by-contract"),
    ("src/specify_cli/dashboard/scanner.py", "_read_mission_identity"): (1, "silent-by-contract"),
    ("src/specify_cli/git/sparse_checkout.py", "_load_managed_lane_policies"): (1, "silent-by-contract"),
    ("src/specify_cli/lanes/recovery.py", "_mission_id_from_meta"): (1, "silent-by-contract"),
    ("src/specify_cli/lanes/worktree_allocator.py", "_read_coordination_branch"): (1, "silent-by-contract"),
    # #5135: the #4474 / FR-011 primary-tree fallback for the mission_number
    # bake was added without joining this ledger. It mirrors the mission-branch
    # write (`_write_mission_number_to_branch`, below) in tolerating a
    # malformed meta.json: it reads as None and is surfaced through
    # `_surface_unbaked_mission_number` (operator-visible "re-run merge
    # --resume" line + logger warning), never raised -- the bake is
    # best-effort bookkeeping that runs after the lanes have already landed,
    # so a fail-closed raise would abort a merge that has nothing left to
    # protect. silent-by-contract is the correct accounting, not a reroute.
    ("src/specify_cli/consolidation/ordering.py", "_bake_mission_number_on_primary_tree"): (1, "silent-by-contract"),
    ("src/specify_cli/consolidation/ordering.py", "_compute_next_mission_number_or_none"): (1, "silent-by-contract"),
    ("src/specify_cli/consolidation/ordering.py", "_write_mission_number_to_branch"): (1, "silent-by-contract"),
    ("src/specify_cli/migration/backfill_runtime_state.py", "_mission_id"): (1, "silent-by-contract"),
    ("src/specify_cli/migration/backfill_runtime_state.py", "_synthesize_claim_anchor"): (1, "silent-by-contract"),
    # #3212: the pre-flip authority probe is a read-only verdict input on the
    # shared dry-run/live path — `on_malformed="none"` is deliberate so the
    # probe can never turn a verdict-bearing dry-run (the `doctor cutover`
    # audit behind it) into a crash on a malformed meta a live run would
    # classify through its own fail-closed seams (`_flip_phase` ->
    # `load_meta_fail_closed`). Missing/malformed reads as "not yet
    # migrated", the truthful pre-write answer.
    ("src/specify_cli/migration/runtime_state_cutover.py", "_already_at_snapshot_authority"): (1, "silent-by-contract"),
    ("src/specify_cli/migration/runtime_state_cutover.py", "stamp_accept_cutover"): (1, "silent-by-contract"),
    # PR #3209 landing pass (2026-08-08): mission 191
    # (verdict-seam-write-unification-01KZ9Q35) added this backfill reader but
    # did not join it here, so the census gate was latently red on main the
    # moment that mission landed (verified: the file is absent at bccb4b4b5,
    # the last green run of this shard). `_resolve_mission_id` reads with
    # `on_malformed="none"` and returns None on a missing/malformed meta.json
    # (pre-mission_id-era mission or a bare fixture) -- the backfilled event's
    # mission_id field is optional per StatusEvent -- so this read is
    # deliberately silent, not fail-closed; a silent-by-contract row is the
    # correct accounting, never a reroute through load_meta_fail_closed.
    ("src/specify_cli/migration/verdict_provenance_backfill.py", "_resolve_mission_id"): (1, "silent-by-contract"),
    # NOTE (landing-fold, PR #3155): the 11 mutation helpers formerly ledgered
    # here as "authority" (clear_coordination_metadata, clear_merge_metadata,
    # get_change_mode, record_acceptance, resolve_mission_identity,
    # set_change_mode, set_documentation_state, set_origin_ticket,
    # set_purpose_summary, set_target_branch, set_vcs_lock) are ROUTED now --
    # they call load_meta_fail_closed via mission_metadata.py's own
    # _require_meta()/_load_meta_fail_closed() helpers, not load_meta, so the
    # live scan no longer finds them and their rows are correctly gone rather
    # than stale.
    ("src/specify_cli/mission_metadata.py", "load_meta_or_empty"): (1, "silent-by-contract"),
    ("src/specify_cli/mission_metadata.py", "load_meta_strict"): (1, "silent-by-contract"),
    ("src/specify_cli/missions/_read_path_resolver.py", "_declares_coordination_branch"): (1, "silent-by-contract"),
    ("src/specify_cli/status/cutover_eligibility.py", "_read_meta"): (1, "silent-by-contract"),
    ("src/specify_cli/status/emit.py", "_load_mission_id"): (1, "silent-by-contract"),
    ("src/specify_cli/status/emit.py", "_read_status_phase"): (1, "silent-by-contract"),
    ("src/specify_cli/task_utils/support.py", "load_meta"): (1, "authority"),
    # #2477 / #2479: the historical 0.13.0 / 0.13.8 migrations' inline
    # json.load(s) reads were routed onto the canonical reader. Their detect()
    # scans (and the 0.13.0 apply() mission-type probe) have always skipped a
    # malformed legacy meta.json -- a frozen migration replaying over old
    # projects must not abort on one corrupt mission -- so they take the
    # silent arm. The 0.13.8 apply() write path and the 0.13.5 project-level
    # read route through load_meta_fail_closed instead (no row).
    ("src/specify_cli/upgrade/migrations/m_0_13_0_research_csv_schema_check.py", "ResearchCSVSchemaCheckMigration.apply"): (1, "silent-by-contract"),
    ("src/specify_cli/upgrade/migrations/m_0_13_0_research_csv_schema_check.py", "ResearchCSVSchemaCheckMigration.detect"): (1, "silent-by-contract"),
    ("src/specify_cli/upgrade/migrations/m_0_13_8_target_branch.py", "TargetBranchMigration.detect"): (1, "silent-by-contract"),
    ("src/specify_cli/upgrade/migrations/m_zz_runtime_state_backfill.py", "_mission_needs_cutover"): (1, "silent-by-contract"),
}

ROUTE_HINT = (
    "Route it through `specify_cli.core.paths.load_meta_fail_closed` (FR-007), "
    "or -- if the site is deliberately silent about corruption -- keep "
    '`load_meta(..., on_malformed="none"/"empty")` and add a '
    "`silent-by-contract` row to ACCOUNTED_SITES in tests/architectural/_load_meta_census.py explaining why."
)
