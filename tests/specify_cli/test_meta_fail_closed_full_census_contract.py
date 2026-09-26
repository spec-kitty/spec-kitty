"""FR-007 / NFR-003 — the fail-closed ``meta.json`` contract gate.

This module carries TWO independent guarantees. They are deliberately
separate mechanisms, because either one alone is forgeable:

1. **The live call-site gate** (:func:`test_no_unaccounted_load_meta_call_sites`).
   An **AST scan of the actual source tree** discovers every ``load_meta``
   call site that exists *right now*, and cross-references it against the
   frozen :data:`_ACCOUNTED_SITES` ledger below. Any site the scan finds that
   the ledger does not name FAILS the build (research.md **D10**).

2. **The real-reader contract** (:func:`test_routed_reader_fails_closed`).
   For a representative routed site in every subsystem WP09 owns, the ACTUAL
   product function is invoked against a corrupt and a non-dict ``meta.json``
   and must answer with its declared typed/sentinel outcome. A raw
   ``ValueError`` is an explicit, unconditional failure — that leak is
   precisely what NFR-003 forbids.

Two design constraints are load-bearing; changing either re-opens a hole a
previous revision of this file actually shipped:

* **The scan must not be sourced from the census.** ``notes/meta-load-census.md``
  is a WP07 *historical snapshot* used to seed the initial classification. If
  the live site set is derived FROM the census, a site added afterwards can
  never be discovered — it is outside the census by construction, so the gate
  is vacuous against exactly the regression it exists to catch.

* **The scan must resolve aliased imports.** A text ``grep`` for ``load_meta(``
  cannot see ``from ... import load_meta as _load_meta`` followed by
  ``_load_meta(...)``. Real call sites in this tree use that form (the WP07
  census itself missed ``tasks_parsing_validation.py`` for this reason), so the
  scan resolves import bindings via :mod:`ast`, mirroring the AST-based
  architectural gates in ``tests/architectural/``.
"""

from __future__ import annotations

import ast
import subprocess
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from specify_cli.core.paths import MissionMetaReadError

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_THIS = Path(__file__).resolve()
_REPO_ROOT = _THIS.parents[2]
_SRC_ROOT = _REPO_ROOT / "src"

#: The canonical reader name both ``load_meta`` definitions share (DEF A,
#: ``mission_metadata.py``; DEF B, the ``task_utils`` path adapter).
_TARGET = "load_meta"

#: Corrupt: truncated, syntactically invalid JSON — genuinely unparseable.
_CORRUPT_META = '{"mission_id": "01JABCDEFGHJKMNPQRSTVWXYZ", '
#: Non-dict: parses cleanly but the top level is a list, not an object.
#: This is a DIFFERENT failure mode from the corrupt case, not a synonym.
_NON_DICT_META = "[1, 2, 3]"

_MISSION_SLUG = "probe-mission"
_MISSION_ID = "01JABCDEFGHJKMNPQRSTVWXYZ"


# --------------------------------------------------------------------------- #
# 1. Independent discovery: AST scan of the live source tree.
# --------------------------------------------------------------------------- #


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
                if alias.name == _TARGET:
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.FunctionDef) and node.name == _TARGET:
            names.add(_TARGET)
    return names


def _qualname_by_line(tree: ast.Module) -> dict[int, str]:
    """Map each line number to its innermost enclosing ``def``/``class`` qualname.

    The ledger is keyed on the enclosing function rather than on a line
    number so that unrelated edits above a call site do not churn the gate.
    """
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
    """Discover every live ``load_meta`` CALL site under *src_root*.

    Returns a count keyed by ``(repo-relative path, enclosing qualname)``.

    This is the gate's independent discovery step: it reads the source tree,
    never the census. A site routed onto ``load_meta_fail_closed`` disappears
    from this set (it no longer calls ``load_meta``) — which is exactly how
    routing is observed as progress.
    """
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


# --------------------------------------------------------------------------- #
# 2. The frozen ledger of KNOWN, ACCOUNTED-FOR sites.
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
_ACCOUNTED_SITES: dict[tuple[str, str], tuple[int, str]] = {
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
    # write (`_write_mission_number_to_branch`, below) exactly: a malformed
    # primary meta.json reads as None and is surfaced through
    # `_surface_unbaked_mission_number` (operator-visible "re-run merge
    # --resume" line + logger warning), never raised -- the bake is
    # best-effort bookkeeping that runs after the lanes have already landed,
    # so a fail-closed raise would abort a merge that has nothing left to
    # protect. silent-by-contract is the correct accounting, not a reroute.
    ("src/specify_cli/merge/ordering.py", "_bake_mission_number_on_primary_tree"): (1, "silent-by-contract"),
    ("src/specify_cli/merge/ordering.py", "_compute_next_mission_number_or_none"): (1, "silent-by-contract"),
    ("src/specify_cli/merge/ordering.py", "_write_mission_number_to_branch"): (1, "silent-by-contract"),
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
    ("src/specify_cli/upgrade/migrations/m_zz_runtime_state_backfill.py", "_mission_needs_cutover"): (1, "silent-by-contract"),
}

#: WP09's owned batch-B subsystems. After routing, the ONLY sites these files
#: may still contain are ``silent-by-contract`` ones.
_WP09_OWNED_FILES: frozenset[str] = frozenset(
    {
        "src/specify_cli/merge/baseline.py",
        "src/specify_cli/merge/executor.py",
        "src/specify_cli/merge/ordering.py",
        "src/specify_cli/dashboard/diagnostics.py",
        "src/specify_cli/dashboard/scanner.py",
        "src/specify_cli/cli/commands/agent/mission_check_prerequisites.py",
        "src/specify_cli/cli/commands/agent/mission_feature_resolution.py",
        "src/specify_cli/cli/commands/agent/mission_repair.py",
        "src/specify_cli/cli/commands/agent/mission_setup_plan.py",
        "src/specify_cli/cli/commands/agent/workflow.py",
        "src/specify_cli/cli/commands/_coordination_doctor.py",
        "src/specify_cli/cli/commands/_identity_audit.py",
        "src/specify_cli/cli/commands/implement.py",
        "src/specify_cli/cli/commands/merge.py",
        "src/specify_cli/cli/commands/mission_type.py",
        "src/specify_cli/cli/commands/tracker.py",
        "src/specify_cli/doc_analysis/doc_state.py",
        "src/specify_cli/tracker/origin.py",
        "src/specify_cli/acceptance/__init__.py",
    }
)

_ROUTE_HINT = (
    "Route it through `specify_cli.core.paths.load_meta_fail_closed` (FR-007), "
    "or -- if the site is deliberately silent about corruption -- keep "
    '`load_meta(..., on_malformed="none"/"empty")` and add a '
    "`silent-by-contract` row to _ACCOUNTED_SITES explaining why."
)


# --------------------------------------------------------------------------- #
# 3. The live call-site gate (research.md D10).
# --------------------------------------------------------------------------- #


def test_no_unaccounted_load_meta_call_sites() -> None:
    """A ``load_meta`` call site outside the frozen ledger FAILS the build.

    This is the anti-scope-creep guard for the whole of IC-03. It compares an
    AST scan of the LIVE tree against :data:`_ACCOUNTED_SITES` in BOTH
    directions, so neither a new unwrapped reader nor a stale ledger row can
    hide.
    """
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


def test_wp09_owned_files_retain_only_silent_sites() -> None:
    """WP09's batch-B routing is complete: no raise-contract readers remain."""
    live = scan_load_meta_call_sites(_SRC_ROOT)
    offenders = sorted(
        f"  {rel}::{qual} ({_ACCOUNTED_SITES.get((rel, qual), (0, 'UNACCOUNTED'))[1]})"
        for (rel, qual) in live
        if rel in _WP09_OWNED_FILES and _ACCOUNTED_SITES.get((rel, qual), (0, "UNACCOUNTED"))[1] != "silent-by-contract"
    )
    assert not offenders, "WP09-owned files still hold non-silent `load_meta` sites:\n" + "\n".join(offenders)


# --------------------------------------------------------------------------- #
# 4. Non-vacuity proofs for the scanner itself.
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    ("label", "source"),
    [
        (
            "plain import",
            "from specify_cli.mission_metadata import load_meta\ndef reader(d):\n    return load_meta(d)\n",
        ),
        (
            "aliased import (the grep blind spot)",
            "from specify_cli.mission_metadata import load_meta as _lm\ndef reader(d):\n    return _lm(d)\n",
        ),
        (
            "deferred in-function aliased import",
            "def reader(d):\n    from specify_cli.mission_metadata import load_meta as _x\n    return _x(d)\n",
        ),
        (
            "module-qualified attribute call",
            "import specify_cli.mission_metadata as mm\ndef reader(d):\n    return mm.load_meta(d)\n",
        ),
    ],
)
def test_scanner_detects_every_call_form(tmp_path: Path, label: str, source: str) -> None:
    """The scanner must see all four binding forms, not just the literal name.

    Without the aliased cases this gate is forgeable: reverting a routed site
    to an aliased ``load_meta`` import would slip past a text-grep scan.
    """
    pkg = tmp_path / "src" / "probe_pkg"
    pkg.mkdir(parents=True)
    (pkg / "mod.py").write_text(source, encoding="utf-8")

    found = scan_load_meta_call_sites(tmp_path / "src")

    assert found.get(("src/probe_pkg/mod.py", "reader")) == 1, f"scanner missed the {label} call form"


def test_scanner_ignores_unrelated_calls(tmp_path: Path) -> None:
    """Negative control: similarly-named symbols are NOT counted."""
    pkg = tmp_path / "src" / "probe_pkg"
    pkg.mkdir(parents=True)
    (pkg / "mod.py").write_text(
        "from specify_cli.core.paths import load_meta_fail_closed\n"
        "def reader(d):\n"
        "    # load_meta( in a comment is not a call site\n"
        '    """load_meta( in a docstring is not one either."""\n'
        "    return load_meta_fail_closed(d)\n",
        encoding="utf-8",
    )

    assert scan_load_meta_call_sites(tmp_path / "src") == Counter()


# --------------------------------------------------------------------------- #
# 5. The real-reader contract: drive ACTUAL product functions.
# --------------------------------------------------------------------------- #

_RAISES_TYPED = "raises-typed"
_RAISES_DOMAIN = "raises-domain"
_RETURNS = "returns"


@dataclass(frozen=True)
class RoutedReader:
    """One routed census site, driven through its real public entry point."""

    subsystem: str
    label: str
    invoke: Callable[[Path], Any]
    outcome: str
    domain_exc: type[BaseException] | None = None
    expected: Any = None


def _seed_mission(tmp_path: Path, payload: str) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(payload, encoding="utf-8")
    return feature_dir


def _drive_merge_baseline(feature_dir: Path) -> Any:
    from specify_cli.merge.baseline import record_baseline_merge_commit

    return record_baseline_merge_commit(feature_dir, "deadbeef", mission_id=_MISSION_ID)


def _drive_merge_baseline_soft(feature_dir: Path) -> Any:
    from specify_cli.merge.baseline import _recorded_baseline_from_working_meta

    return _recorded_baseline_from_working_meta(feature_dir)


def _drive_dashboard(feature_dir: Path) -> Any:
    from specify_cli.dashboard.diagnostics import _resolve_mission_from_feature

    return _resolve_mission_from_feature(feature_dir)


def _drive_cli_mission_type(feature_dir: Path) -> Any:
    from specify_cli.cli.commands.mission_type import _safe_load_meta

    return _safe_load_meta(feature_dir)


def _drive_cli_identity_audit(feature_dir: Path) -> Any:
    from specify_cli.cli.commands._identity_audit import _read_stored_topology

    return _read_stored_topology(feature_dir)


def _drive_cli_agent_setup_plan(feature_dir: Path) -> Any:
    from specify_cli.cli.commands.agent.mission_setup_plan import _resolve_plan_template

    return _resolve_plan_template(feature_dir.parent.parent, feature_dir)


def _drive_doc_read(feature_dir: Path) -> Any:
    from specify_cli.doc_analysis.doc_state import read_documentation_state

    return read_documentation_state(feature_dir / "meta.json")


def _drive_doc_write(feature_dir: Path) -> Any:
    from specify_cli.doc_analysis.doc_state import set_iteration_mode

    return set_iteration_mode(feature_dir / "meta.json", "initial")


def _drive_tracker(feature_dir: Path) -> Any:
    from specify_cli.tracker.origin import bind_mission_origin
    from specify_cli.tracker.origin_models import OriginCandidate

    candidate = OriginCandidate(
        external_issue_id="1",
        external_issue_key="PROBE-1",
        title="probe",
        status="open",
        url="https://example.invalid/1",
        match_type="exact",
    )
    return bind_mission_origin(feature_dir, candidate, "github")


def _drive_acceptance(feature_dir: Path) -> Any:
    """Drive ``acceptance._commit_acceptance_meta`` against a real git repo.

    ``record_acceptance`` is stubbed because it lives in ``mission_metadata.py``
    -- the module that defines the DEF A parser itself, classified
    ``authority`` in the ledger above (routing it onto the wrapper would be
    circular) -- and would raise its own raw ``ValueError`` before control
    ever reaches the acceptance-owned routed read. Stubbing it isolates the
    site actually under test here; it does not weaken the assertion, which
    still runs against the real product function.
    """
    import specify_cli.acceptance as acc

    repo_root = feature_dir.parent.parent

    def _git(*args: str) -> None:
        subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True)

    _git("init", "-b", "mission-lane")
    _git("config", "user.email", "pedro@example.com")
    _git("config", "user.name", "Python Pedro")
    (repo_root / "README.md").write_text("probe\n", encoding="utf-8")
    # Commit ONLY the README: meta.json must stay untracked so the function's
    # own ``git add`` stages it and the flow reaches the routed read (an
    # already-committed meta.json short-circuits on "nothing staged").
    _git("add", "README.md")
    _git("commit", "-m", "init")

    summary = acc.AcceptanceSummary(
        feature=_MISSION_SLUG,
        repo_root=repo_root,
        feature_dir=feature_dir,
        tasks_dir=feature_dir / "tasks",
        branch="mission-lane",
        worktree_root=repo_root,
        primary_repo_root=repo_root,
        lanes={},
        work_packages=[],
        metadata_issues=[],
        activity_issues=[],
        unchecked_tasks=[],
        needs_clarification=[],
        missing_artifacts=[],
        optional_missing=[],
        git_dirty=[],
        path_violations=[],
        warnings=[],
    )

    original = acc.record_acceptance
    acc.record_acceptance = lambda *a, **k: None
    try:
        return acc._commit_acceptance_meta(summary, "pedro", "standard")
    finally:
        acc.record_acceptance = original


def _routed_readers() -> list[RoutedReader]:
    from specify_cli.merge.baseline import BaselineMergeCommitError
    from specify_cli.tracker.origin import OriginBindingError

    return [
        RoutedReader("merge", "baseline.record_baseline_merge_commit", _drive_merge_baseline, _RAISES_DOMAIN, BaselineMergeCommitError),
        RoutedReader("merge", "baseline._recorded_baseline_from_working_meta", _drive_merge_baseline_soft, _RETURNS, expected=""),
        RoutedReader("dashboard", "diagnostics._resolve_mission_from_feature", _drive_dashboard, _RETURNS, expected=None),
        RoutedReader("cli", "mission_type._safe_load_meta", _drive_cli_mission_type, _RETURNS, expected=None),
        RoutedReader("cli", "_identity_audit._read_stored_topology", _drive_cli_identity_audit, _RETURNS),
        RoutedReader("cli/agent", "mission_setup_plan._resolve_plan_template", _drive_cli_agent_setup_plan, _RAISES_TYPED),
        RoutedReader("doc_analysis", "doc_state.read_documentation_state", _drive_doc_read, _RAISES_TYPED),
        RoutedReader("doc_analysis", "doc_state.set_iteration_mode", _drive_doc_write, _RAISES_TYPED),
        RoutedReader("tracker", "origin.bind_mission_origin", _drive_tracker, _RAISES_DOMAIN, OriginBindingError),
        RoutedReader("acceptance", "_commit_acceptance_meta", _drive_acceptance, _RAISES_TYPED),
    ]


def _reader_ids() -> list[str]:
    return [f"{r.subsystem}:{r.label}" for r in _routed_readers()]


@pytest.mark.parametrize("reader", _routed_readers(), ids=_reader_ids())
@pytest.mark.parametrize(
    ("scenario", "payload"),
    [("corrupt-json", _CORRUPT_META), ("non-dict-json", _NON_DICT_META)],
)
def test_routed_reader_fails_closed(tmp_path: Path, reader: RoutedReader, scenario: str, payload: str) -> None:
    """NFR-003: a routed reader answers typed-or-sentinel — never raw ValueError.

    Each case invokes the REAL product function at a routed census site (not a
    synthetic call to the raw reader) against a genuinely unparseable
    ``meta.json`` and, separately, a well-formed but non-object one.
    """
    feature_dir = _seed_mission(tmp_path, payload)

    try:
        result = reader.invoke(feature_dir)
    except MissionMetaReadError:
        assert reader.outcome == _RAISES_TYPED, f"{reader.label} ({scenario}) raised MissionMetaReadError but its declared contract is {reader.outcome!r}"
        return
    except ValueError as exc:  # noqa: TRY302 - the assertion IS the point
        # MissionMetaReadError is a RuntimeError, so it never lands here. A raw
        # ValueError reaching this arm is exactly the NFR-003 leak.
        pytest.fail(
            f"NFR-003 VIOLATION: {reader.label} ({scenario}) surfaced a raw "
            f"{type(exc).__name__}: {exc}. A routed reader must raise "
            f"MissionMetaReadError (or its own typed domain error), never ValueError."
        )
    except BaseException as exc:  # noqa: BLE001 - classify anything else explicitly
        assert reader.outcome == _RAISES_DOMAIN and reader.domain_exc is not None, f"{reader.label} ({scenario}) raised unexpected {type(exc).__name__}: {exc}"
        assert isinstance(exc, reader.domain_exc), (
            f"{reader.label} ({scenario}) raised {type(exc).__name__}, expected the declared domain error {reader.domain_exc.__name__}"
        )
        assert not isinstance(exc, ValueError), f"NFR-003 VIOLATION: {reader.label} ({scenario}) domain error {type(exc).__name__} subclasses ValueError"
        return
    else:
        assert reader.outcome == _RETURNS, (
            f"{reader.label} ({scenario}) returned {result!r} but its declared contract is {reader.outcome!r} (it should have raised)"
        )
        if reader.expected is not None or reader.label.endswith("_resolve_mission_from_feature"):
            assert result == reader.expected, f"{reader.label} ({scenario}) returned {result!r}, expected {reader.expected!r}"
