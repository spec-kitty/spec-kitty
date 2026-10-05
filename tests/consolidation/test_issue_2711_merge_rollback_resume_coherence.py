"""Scope: #2711 merge rollback/resume coherence + duplicate ``done`` (WP02).

Formerly a red-first ``@pytest.mark.regression`` reproduction (ATDD-first,
C-011); relocated here and un-marked (landing fold: make
``@pytest.mark.regression`` mean exactly one thing) once the fix landed and
this test started passing. #2711 is fixed — this is now a permanent guard,
not a red-first pin.

On a coord-topology
mission, ``spec-kitty merge`` records the per-WP ``approved -> done`` transition
on the coordination branch (``_record_merged_wps_done_for_merge`` ->
``_mark_wp_merged_done`` -> ``emit_status_transition_transactional`` ->
``BookkeepingTransaction``) BEFORE it advances the mission branch into the
target (``integrate_mission_into_target``). When that target-advance step fails,
the rollback (``_restore_pre_target_if_at_baseline`` ->
``_restore_final_bookkeeping_snapshots``) reverts ONLY the working-tree bytes of
the coordination worktree's ``status.events.jsonl``. The ``done`` event already
COMMITTED to the coordination branch is left in place. Two observable defects
follow:

* **Split-brain (US1-S2/S3):** the committed coordination-branch reduction says
  ``done`` while the rolled-back working tree reduces to ``approved``.
* **Duplicate ``done`` (US3):** a second (resume) merge pass reads the
  rolled-back working tree (``approved``), fails the dedup guard, and re-emits a
  SECOND ``done`` — the committed coordination ref then carries two ``done``
  events for the same WP.

Both assertions were RED before the fix; the rollback now also reverts (and
the resume de-duplicates) the committed coordination ``done``, so both are
GREEN.

Supersedes the retired ``tests/merge/test_merge_rollback_resume_ledger_2711.py``
(upstream #2764): that test drove ``_restore_final_bookkeeping_snapshots`` (the
byte-restore seam) in ISOLATION and asserted coherence at that seam. The approved
Option A design deliberately restores coherence at the EXECUTOR-revert level
(reverting the committed coord ``done`` commit) and leaves the byte-restore
untouched, so the isolated-seam assertion no longer matches the design. This
module covers the same #2711 coherence contract end-to-end (executor + real
done-bookkeeping + committed coordination ref) and stays green on the fix. The
resume non-re-emission INVARIANT is additionally pinned as a property guard in
``tests/architectural/test_resume_non_reemission_guard.py`` (WP06).

Harness note (WP02): the coord-worktree materialization + real done-bookkeeping
seam is modeled on the proven coord-topology full-merge harness in
``tests/specify_cli/cli/commands/test_merge_coord_worktree_resync_1826.py``
(itself the reconciliation of the #1772 coord-branch/meta-on-coord shape with
the ``CoordinationWorkspace`` worktree materialization used by
``tests/merge/test_merge_target_resolution.py``). All fusion helpers live in
THIS module so the shared harness files are never edited in place (WP01 also
consumes 1772). The failure is injected at the canonical SOURCE-module target
``specify_cli.lanes.consolidation.integrate_mission_into_target`` (a lazy local import
inside ``_phase_mission_to_target``), never the ``specify_cli.consolidation.executor.*``
alias, which is never bound at module level.
"""

from __future__ import annotations

import contextlib
import json
import subprocess
from collections.abc import Iterator
from kernel.clock import now_utc_iso
from pathlib import Path
from typing import cast
from unittest.mock import MagicMock, patch

import pytest

# Import the status package before any coordination submodule. The production
# CLI entrypoint (``specify_cli/__init__``) imports ``status`` before ``merge``;
# importing ``merge`` first (as a test module does) would otherwise reach
# ``coordination/__init__`` -> ``transaction`` -> ``status`` mid-initialization
# and trip a known import-order cycle. Mirroring the production order here keeps
# this regression test importable under ``PYTHONPATH=src``.
import specify_cli.status  # noqa: F401  # import-order guard (see comment above)

from specify_cli.cli.commands.consolidate import _run_lane_based_consolidation
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    read_event_log,
    wp_lane_actor_from_events,
)
from specify_cli.coordination.surface_resolver import (
    is_under_worktrees_segment,
    resolve_status_surface,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.status import Lane, StatusEvent
from tests.consolidation.approval_stamps import restamp_log_at_lane_tips
from tests.consolidation.executor_family import patch_executor_family

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


# ---------------------------------------------------------------------------
# Mission identity (slug ends with ``-<mid8>`` so the coordination branch IS the
# lanes-manifest mission branch — the production 083+ coord-topology layout).
# ---------------------------------------------------------------------------

MID8 = "01KXRRB7"
MISSION_ID = "01KXRRB7000000000000000000"
MISSION_SLUG = f"merge-rollback-2711-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
WP_ID = "WP01"
LANE_ID = "lane-a"
LANE_CODE = "src/feature_code.py"

_INJECTED_TARGET_FAILURE = "injected #2711 target-advance failure"


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        check=True,
        capture_output=True,
        text=True,
    )


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args])


def _init_git_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)])
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("init\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")


# ---------------------------------------------------------------------------
# Coord-topology fixture (local fusion helpers — see module docstring)
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path) -> None:
    """meta.json declaring a coordination_branch (coord-topology mission)."""
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "merge rollback/resume coherence regression (#2711)",
        "purpose_context": "a failed target advance must not strand a committed done",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_manifest(feature_dir: Path) -> LanesManifest:
    """One code lane carrying a real diff not on the mission branch nor main."""
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        # mission_id == slug => legacy lane_branch_name form
        # ``kitty/mission-<slug>-lane-a`` which consolidate_lane_into_mission builds
        # (the slug already carries the ``-<mid8>`` tail, so the legacy body is the
        # resolvable ``<human-slug>-<mid8>`` form).
        mission_id=MISSION_SLUG,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=LANE_ID,
                wp_ids=(WP_ID,),
                write_scope=(LANE_CODE,),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)
    return manifest


def _write_wp_file(feature_dir: Path) -> None:
    """Seed WP markdown with approved-review frontmatter so the real
    ``approved -> done`` transition fires during merge bookkeeping."""
    (feature_dir / "tasks" / f"{WP_ID}-work.md").write_text(
        "---\n"
        f"work_package_id: {WP_ID}\n"
        f"title: {WP_ID} work\n"
        "agent: implementer-bot\n"
        "review_status: approved\n"
        "reviewed_by: reviewer-renata\n"
        "---\n"
        f"# {WP_ID}\n",
        encoding="utf-8",
    )


def _approved_event() -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": now_utc_iso(),
        "event_id": "01HXYZAPPR000000000000002711",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "in_review",
        "reason": None,
        "review_ref": f"review-{WP_ID}",
        "to_lane": "approved",
        "wp_id": WP_ID,
    }


def _bootstrap_coord_mission(repo: Path) -> Path:
    """Bootstrap a coord-topology mission whose only WP sits at ``approved``.

    Returns the primary-checkout feature_dir.
    """
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    _write_wp_file(feature_dir)

    # Pre-record the per-WP APPROVED event (NOT done) so the real bookkeeping
    # pass has a genuine ``approved -> done`` transition to emit through the
    # coordination worktree.
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(_approved_event(), sort_keys=True) + "\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap coord mission")

    # Coordination/mission branch at the current tip.
    _git(repo, "branch", COORD_BRANCH)

    # Lane branch with a REAL code diff not on the mission branch nor on main.
    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_ID}"
    _git(repo, "branch", lane_branch, COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    code_path = repo / LANE_CODE
    code_path.parent.mkdir(parents=True, exist_ok=True)
    code_path.write_text("def feature() -> int:\n    return 2711\n", encoding="utf-8")
    _git(repo, "add", LANE_CODE)
    _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): lane code for {WP_ID}")
    _git(repo, "checkout", "main")
    restamp_log_at_lane_tips(repo, feature_dir, coord_branch=COORD_BRANCH)

    # Materialize the coordination worktree with the mission branch CHECKED OUT
    # (the production topology): the pre-target ``done`` transaction commits
    # through this worktree, and the rollback reverts only its working-tree bytes.
    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)

    return feature_dir


@contextlib.contextmanager
def _merge_external_mocks() -> Iterator[dict[str, MagicMock]]:
    """Mock ONLY side effects outside git/status bookkeeping.

    Deliberately LEFT REAL (the #2711 seam): ``_record_merged_wps_done_for_merge``
    / ``_mark_wp_merged_done`` (they commit ``done`` to the coordination branch
    before the target advance) and ``_restore_pre_target_if_at_baseline`` (the
    working-bytes-only rollback under test).
    """
    patches = {
        "run_check": patch("specify_cli.consolidation.phase_finalize.run_check"),
        "sparse": patch("specify_cli.consolidation.executor.require_no_sparse_checkout"),
        "preflight": patch("specify_cli.cli.commands.consolidate._enforce_git_preflight"),
        "review_consistency": patch(
            "specify_cli.consolidation.executor._enforce_review_artifact_consistency"
        ),
        "status_history": patch(
            "specify_cli.consolidation.phase_claim._enforce_canonical_status_history"
        ),
        "hollow": patch("specify_cli.consolidation.phase_claim._warn_or_confirm_hollow_reviews"),
        "bake": patch(
            "specify_cli.consolidation.phase_advance._bake_mission_number_into_mission_branch",
            return_value=None,
        ),
        "baseline_record": patch(
            "specify_cli.consolidation.phase_bookkeeping._record_baseline_merge_commit",
            return_value=None,
        ),
        "baseline_assert": patch(
            "specify_cli.consolidation.phase_bookkeeping._assert_baseline_merge_commit_on_target"
        ),
        "done_on_target": patch(
            "specify_cli.consolidation.phase_bookkeeping._assert_merged_wps_done_on_target"
        ),
        "safe_commit": patch_executor_family("commit_merge_bookkeeping"),
        "refresh_primary": patch_executor_family("_refresh_primary_checkout_after_merge"),
        "porcelain": patch(
            "specify_cli.consolidation.phase_bookkeeping._classify_porcelain_lines",
            return_value=([], 0),
        ),
        "gates": patch("specify_cli.policy.merge_gates.evaluate_merge_gates"),
        "policy": patch("specify_cli.policy.config.load_policy_config"),
        "remote": patch("specify_cli.consolidation.phase_finalize.has_remote", return_value=False),
    }
    with contextlib.ExitStack() as stack:
        mocks = {name: stack.enter_context(p) for name, p in patches.items()}
        gate_eval = MagicMock()
        gate_eval.overall_pass = True
        gate_eval.gates = []
        mocks["gates"].return_value = gate_eval
        policy = MagicMock()
        policy.merge_gates = []
        mocks["policy"].return_value = policy
        stale_report = MagicMock()
        stale_report.findings = []
        mocks["run_check"].return_value = stale_report
        yield mocks


def _run_failing_merge(repo: Path) -> BaseException:
    """Run one merge pass with the target advance injected to fail.

    Returns the raised exception so the caller can assert the failure came from
    the injected target-advance fault (not an unrelated setup error).
    """
    with (
        _merge_external_mocks(),
        patch(
            "specify_cli.lanes.consolidation.integrate_mission_into_target",
            side_effect=RuntimeError(_INJECTED_TARGET_FAILURE),
        ),
    ):
        try:
            _run_lane_based_consolidation(
                repo_root=repo,
                mission_slug=MISSION_SLUG,
                push=False,
                delete_branch=False,
                remove_worktree=False,
                strategy=MergeStrategy.SQUASH,
                allow_sparse_checkout=True,
            )
        except BaseException as exc:  # noqa: BLE001 — the act under test raises by design
            return exc
    raise AssertionError(
        "precondition: injected target-advance failure did not propagate — the "
        "merge unexpectedly succeeded, so the #2711 rollback path never ran."
    )


def _committed_coord_events(repo: Path, feature_dir: Path) -> list[StatusEvent]:
    """Reduce the events COMMITTED to the coordination branch (contract-routed).

    Uses ``EventLogReadContract.coordination_branch_ref`` — NEVER a hand-rolled
    ``git show <branch>:...`` — so the committed-ref read stays on the canonical
    authority (WP02 AC-4).
    """
    # ``cast`` (not a suppression): mypy checks this test in isolation with
    # ``follow_imports = skip`` for ``specify_cli.*`` (pyproject override), so the
    # real ``read_event_log -> list[StatusEvent]`` signature is invisible here and
    # collapses to ``Any``. The runtime type is genuinely ``list[StatusEvent]``.
    return cast(
        "list[StatusEvent]",
        read_event_log(
            EventLogReadContract.coordination_branch_ref(
                repo_root=repo,
                destination_ref=COORD_BRANCH,
                feature_dir=feature_dir,
                parser_feature_dir=feature_dir,
            )
        ),
    )


def _working_coord_events(repo: Path) -> list[StatusEvent]:
    """Reduce the coordination worktree's rolled-back WORKING-tree event log."""
    coord_worktree = CoordinationWorkspace.worktree_path(repo, MISSION_SLUG, MID8)
    coord_feature_dir = coord_worktree / "kitty-specs" / MISSION_SLUG
    return cast(
        "list[StatusEvent]",
        read_event_log(EventLogReadContract.coordination_worktree(coord_feature_dir)),
    )


def _done_event_ids(events: list[StatusEvent]) -> list[str]:
    """The committed ``done`` event identities for the mission's WP, in order."""
    return [e.event_id for e in events if e.wp_id == WP_ID and str(e.to_lane) == "done"]


def _assert_pre_target_done_path(repo: Path) -> None:
    """Non-vacuity witness (survives the fix): the mission routes its status onto
    the coordination worktree, so ``done_marked_before_target`` is True and the
    merge records the ``approved -> done`` transition to the coordination branch
    BEFORE the target advance (``executor._phase_bake_and_pre_target_done`` calls
    ``_record_merged_wps_done_for_merge`` strictly before
    ``_phase_mission_to_target`` invokes ``integrate_mission_into_target``).
    Combined with the injected-failure marker below, this GUARANTEES a ``done``
    was committed pre-target — the coherence/idempotency contracts therefore
    cannot pass vacuously via "no ``done`` was ever committed"."""
    surface = resolve_status_surface(repo, MISSION_SLUG)
    assert is_under_worktrees_segment(surface), (
        "precondition: the status surface must resolve under the coordination "
        "worktree (done_marked_before_target) so ``done`` is committed BEFORE the "
        f"target advance; got {surface}"
    )


# ---------------------------------------------------------------------------
# US3-S1 / US1-S2/S3 / SC-001 — rollback coherence (RED on the mission base)
# ---------------------------------------------------------------------------


def test_rollback_leaves_committed_done_incoherent_with_working_tree(
    tmp_path: Path,
) -> None:
    """#2711 / FR-002 / US3-S1: after a target-advance failure the committed
    coordination ``done`` must be reverted in lockstep with the working tree.
    Today only the working bytes roll back (``_restore_pre_target_if_at_baseline``
    -> ``_restore_final_bookkeeping_snapshots``), leaving the committed coord ref
    at ``done`` while the working tree reduces to ``approved`` — a split-brain.

    The Option-A fix (revert the coord ``done`` commit on rollback) makes both
    sides reduce to ``approved``, so ``committed_lane == working_lane`` flips
    GREEN."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_coord_mission(repo)

    # --- Non-vacuity witness A (BEFORE the act): pre-target ``done`` path. ---
    _assert_pre_target_done_path(repo)

    exc = _run_failing_merge(repo)

    # --- Non-vacuity witness B: the failure is the injected target-advance fault
    # (fired AFTER the pre-target ``done`` commit), never an unrelated setup
    # error — so a ``done`` genuinely landed on the coordination branch. ---
    assert isinstance(exc, RuntimeError) and _INJECTED_TARGET_FAILURE in str(exc), (
        "precondition: the merge must fail via the injected target-advance fault "
        f"(RuntimeError, AFTER the pre-target done commit); got {exc!r}"
    )

    committed_events = _committed_coord_events(repo, feature_dir)
    working_events = _working_coord_events(repo)
    committed_lane = wp_lane_actor_from_events(committed_events, WP_ID).lane
    working_lane = wp_lane_actor_from_events(working_events, WP_ID).lane

    # --- Precondition: the working tree DID roll back to ``approved`` (survives
    # the fix — the working side is coherent both today and post-fix). ---
    assert working_lane == Lane.APPROVED, (
        "precondition: the rolled-back working tree should reduce to ``approved``; "
        f"got {working_lane}"
    )

    # --- Coherence CONTRACT (RED on base): the committed coordination reduction
    # and the working-tree reduction must agree after rollback. Contract-routed
    # via ``EventLogReadContract.coordination_branch_ref`` (never raw git show). ---
    assert committed_lane == working_lane, (
        "#2711 split-brain: after the target-advance failure the committed "
        "coordination branch and the rolled-back working tree disagree.\n"
        f"  committed coord ref (git-tracked): {committed_lane}\n"
        f"  rolled-back working tree:          {working_lane}\n"
        "Rollback reverted only the working-tree bytes; the committed ``done`` "
        "event on the coordination branch was left stranded."
    )


# ---------------------------------------------------------------------------
# US3-S3 / SC-003 — resume is NOT idempotent: the committed ``done`` churns
# (RED on the mission base)
# ---------------------------------------------------------------------------


def test_resume_re_emits_a_fresh_done_instead_of_staying_idempotent(
    tmp_path: Path,
) -> None:
    """#2711 / FR-002 / US3-S3: after the stranded-``done`` rollback, a resume
    derives progress from the byte-restored ``ConsolidationState.completed_wps`` (empty)
    instead of the durable event log, so it re-emits a FRESH ``done`` transaction
    rather than recognizing the already-committed one. The committed coordination
    ref is therefore NOT byte-stable across ``--resume``: the ``done`` event
    identity churns (a duplicate ``done`` emission), violating idempotency.

    Note (empirical): the coordination-branch tip carries exactly ONE ``done``
    row in BOTH the buggy and fixed states — the transactional safe-commit
    REPLACES the tip rather than appending — so a ``count == 1`` assertion is
    GREEN-on-base (vacuous). The discriminating, RED-on-base contract is the
    idempotency / byte-stability one (US3-S3, spec line 172/186): the committed
    ``done`` identity must be unchanged across the resume.

    The Option-A fix (durable-log-derived resume + coherent rollback) makes the
    resume idempotent, so the committed ``done`` identity is stable and this
    flips GREEN."""
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_coord_mission(repo)

    _assert_pre_target_done_path(repo)

    # First pass strands a committed ``done`` on the coordination branch.
    exc1 = _run_failing_merge(repo)
    assert isinstance(exc1, RuntimeError) and _INJECTED_TARGET_FAILURE in str(exc1)
    done_ids_after_first = _done_event_ids(_committed_coord_events(repo, feature_dir))

    # Second (resume) pass: same injected failure. On the buggy base the resume
    # re-emits ``done`` because it reads the byte-restored working state, not the
    # durable log.
    exc2 = _run_failing_merge(repo)
    assert isinstance(exc2, RuntimeError) and _INJECTED_TARGET_FAILURE in str(exc2)
    done_ids_after_resume = _done_event_ids(_committed_coord_events(repo, feature_dir))

    # --- Idempotency CONTRACT (RED on base): the committed ``done`` identity on
    # the coordination ref must be unchanged across ``--resume``. Contract-routed
    # via ``EventLogReadContract.coordination_branch_ref``. ---
    assert done_ids_after_resume == done_ids_after_first, (
        "#2711 non-idempotent resume: ``spec-kitty merge --resume`` re-emitted a "
        "FRESH ``done`` transaction instead of recognizing the already-committed "
        "one, so the committed coordination ``done`` identity is not byte-stable "
        "across the resume.\n"
        f"  committed done ids after first pass:  {done_ids_after_first}\n"
        f"  committed done ids after --resume:    {done_ids_after_resume}\n"
        "The resume derived progress from the byte-restored ConsolidationState instead of "
        "the durable event log."
    )
