"""Scope: #2367 Mechanism B — the merge coord write-set is not atomic (permanent guard; #2367-B FIXED).

**Contract since #5385 (single rollback door).** A bake-mid-write-set failure
still byte-restores the coordination worktree and writes the strand marker
INSIDE the phase (observed here at the phase's exit, before the driver's door
runs); the door then CAS-restores the coordination branch to its pre-run
snapshot, so no strand survives the run and the marker is cleared. The pre-#5385
contract left the committed ``done`` stranded for a ``--resume`` heal; the
history below describes that earlier contract.

**Landing note (2026-08, `tests/regression/` campsite clean).** Relocated
from `tests/regression/` to `tests/merge/` — its functional home alongside
the other merge-executor / coordination-rollback tests — now that Mechanism B
is fixed and this is a green permanent guard, not a red-first reproduction
(no `regression` marker). Issue **#2367 itself remains OPEN** as of this
relocation: Mechanism A of #2367 was split out and closed separately as
#2795, and Mechanism B (this module's scope) is fixed, but the parent issue
may still track a remainder. This module is the Mechanism-B green guard, not
that possible remainder's repro — do not treat it as proof #2367 is fully
closed.

This module reproduces **#2367 Mechanism B** and now guards its fix. It began as
an INTENTIONAL, issue-pinned red-first P0 reproduction (per ADR
``docs/adr/3.x/2026-07-17-1``, expected to fail on the mission base while the P0
was open). The unified #2786/#2367-B fix has now LANDED — mark-not-raise +
strand-gated resume heal — so the reproduction drives the bake strand and asserts
coherence AFTER the heal. The ``regression`` marker (which flagged the
intentional-red phase) is removed now that the defect is closed; the test stays a
green regression guard via its ``git_repo`` marker.

Defect (#2367 Mechanism B)
--------------------------
``spec-kitty merge`` records the per-WP ``approved -> done`` transition for each
merged WP through its OWN ``BookkeepingTransaction`` (N independent COMMITTED
coordination-branch transactions) inside
``specify_cli.consolidation.done_bookkeeping._record_merged_wps_done_for_merge``. That
loop is not one atomic unit. When it FAILS mid write-set — after ≥1 per-WP
``done`` has already COMMITTED to the coordination branch, before the remaining
WPs are marked — the executor's failure branch
(``specify_cli.consolidation.executor._phase_bake_and_pre_target_done``, the
``except Exception:`` at ≈406-408) restores **working-tree bytes only**:
it calls ``_restore_final_bookkeeping_snapshots`` and RE-RAISES. It does **NOT**
call ``_revert_coord_done_commit`` (that runs only on the *target-advance* /
*squash-conflict* rollback paths via ``_restore_pre_target_if_at_baseline``,
executor ≈535-536 — which are therefore revert-covered and would repro
VACUOUSLY GREEN).

Consequently the already-committed per-WP ``done`` commits survive on the
coordination ref while the working tree is byte-restored to ``approved`` — the
identical byte-restore-**without**-revert mechanism as #2786 (#2786 = the revert
itself *failed*; #2367-B = the revert was *never called* because the failure
preceded it). The coordination worktree is left tracked-dirty, and the committed
reduction (``done``) diverges from the working reduction (``approved``) — a
split-brain the #1826 safe-resync guard then correctly refuses to ``reset --hard``
over, blocking the next merge/resume.

Reproduction strategy
---------------------
A ``>=2``-WP coordination-topology fixture (authored locally — the #2711
``_bootstrap_coord_mission`` is single-WP and has NO bake-loop injection hook; it
is in no WP's ``owned_files`` and is NEVER edited here; only the primitive
``_init_git_repo`` / ``_git`` helpers are reused):

* **WP01** commits its ``approved -> done`` to the coordination branch first, then
* the failure is injected **inside** ``_record_merged_wps_done_for_merge`` by a
  ``_mark_wp_merged_done`` ``side_effect`` that delegates to the real helper for
  WP01 (so its ``done`` genuinely lands) and RAISES on **WP02** — exercising the
  real ``executor.py:406-408`` byte-restore-without-revert branch;
* **WP02** is only ever ``approved`` (never marked) — the *coherent* control that
  falsifies both a hardcoded ``["WP01"]`` and an over-broad ``all_wp_ids`` strand
  set.

The stranded set is reduced from the COMMITTED coordination ref via
``_durable_done_wps_on_coordination_ref`` (git-reducible authority; NOT a live
worktree diff, which is empty at the mark point per data-model D7, and NOT any
marker/doctor surface — those do not exist on the base and would red with
``AttributeError`` = forbidden setup-red). The coherence CONTRACT then FAILS for
the RIGHT reason: after a ``spec-kitty merge --resume`` heal (a no-op on the base
until the WP03 repair lands), the committed reduction is stranded at ``done``
while the working tree reduces to ``approved``.

#2367 Mechanism B is FIXED — the bake-path rollback marks-not-raises (durable
``pending_coord_reconcile`` marker) and the resume heal reverts the stranded coord
``done`` via a strand-gated ``git revert``; this module verifies coherence is
restored after the heal and guards against regression. (Mechanism A — claim-time
VCS-lock resync — is deferred to #2795.)
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable, Iterator
from kernel.clock import now_utc_iso
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

# Import the status package before any coordination submodule (mirror the
# production import order; see the #2711 harness module docstring for rationale).
import specify_cli.status  # noqa: F401  # import-order guard

import specify_cli.consolidation.done_bookkeeping as done_bookkeeping
from specify_cli.consolidation import executor
from specify_cli.consolidation.state import load_state
from specify_cli.cli.commands.consolidate import _run_lane_based_consolidation
from specify_cli.coordination.status_service import (
    EventLogReadContract,
    read_event_log,
    wp_lane_actor_from_events,
)
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.done_bookkeeping import _durable_done_wps_on_coordination_ref
from specify_cli.status import Lane, StatusEvent

# Reuse ONLY the primitive git helpers from the #2711 harness (never the
# single-WP ``_bootstrap_coord_mission``, which has no bake-loop injection hook
# and is in no WP's owned_files — WP01 authors its own >=2-WP bootstrap below).
from tests.consolidation.approval_stamps import restamp_log_at_lane_tips
from tests.consolidation.test_issue_2711_merge_rollback_resume_coherence import (
    _git,
    _init_git_repo,
    _merge_external_mocks,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox]

# ---------------------------------------------------------------------------
# Mission identity (slug ends with ``-<mid8>`` so the coordination branch IS the
# lanes-manifest mission branch — the production 083+ coord-topology layout).
# ---------------------------------------------------------------------------

MID8 = "01KXBAKE"
MISSION_ID = "01KXBAKE000000000000000000"
MISSION_SLUG = f"merge-bake-2367-{MID8}"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
STRANDED_WP = "WP01"  # commits ``done`` before the injected failure -> stranded
COHERENT_WP = "WP02"  # only ever ``approved`` -> the coherent control
LANE_ID = "lane-a"

_INJECTED_BAKE_FAILURE = "injected #2367-B bake-mid-write-set failure"


# ---------------------------------------------------------------------------
# Locally-authored >=2-WP coord-topology fixture (owned file — no shared-harness
# edit). Only ``_init_git_repo`` / ``_git`` are reused as primitives.
# ---------------------------------------------------------------------------


def _write_meta(feature_dir: Path) -> None:
    meta = {
        "mission_slug": MISSION_SLUG,
        "mission_id": MISSION_ID,
        "mid8": MID8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": "main",
        "coordination_branch": COORD_BRANCH,
        "purpose_tldr": "#2367-B bake-mid-write-set strand regression",
        "purpose_context": "an aborted multi-WP coord write-set must roll back atomically",
    }
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _write_manifest(feature_dir: Path) -> None:
    """One lane carrying BOTH WPs so a single merge pass bakes a multi-WP write-set."""
    manifest = LanesManifest(
        version=1,
        mission_slug=MISSION_SLUG,
        # mission_id == slug => legacy lane_branch_name form
        # ``kitty/mission-<slug>-lane-a`` (the slug already carries ``-<mid8>``).
        mission_id=MISSION_SLUG,
        mission_branch=COORD_BRANCH,
        target_branch="main",
        lanes=[
            ExecutionLane(
                lane_id=LANE_ID,
                wp_ids=(STRANDED_WP, COHERENT_WP),
                write_scope=("src/wp01_code.py", "src/wp02_code.py"),
                predicted_surfaces=("code",),
                depends_on_lanes=(),
                parallel_group=0,
            )
        ],
        computed_at=now_utc_iso(),
        computed_from="test-fixture",
    )
    write_lanes_json(feature_dir, manifest)


def _write_wp_file(feature_dir: Path, wp_id: str) -> None:
    """Seed WP markdown with approved-review frontmatter so the real
    ``approved -> done`` transition fires during merge bookkeeping."""
    (feature_dir / "tasks" / f"{wp_id}-work.md").write_text(
        "---\n"
        f"work_package_id: {wp_id}\n"
        f"title: {wp_id} work\n"
        "agent: implementer-bot\n"
        "review_status: approved\n"
        "reviewed_by: reviewer-renata\n"
        "---\n"
        f"# {wp_id}\n",
        encoding="utf-8",
    )


def _approved_event(wp_id: str, event_id: str) -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": now_utc_iso(),
        "event_id": event_id,
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": MISSION_SLUG,
        "force": False,
        "from_lane": "in_review",
        "reason": None,
        "review_ref": f"review-{wp_id}",
        "to_lane": "approved",
        "wp_id": wp_id,
    }


def _bootstrap_two_wp_coord_mission(repo: Path) -> Path:
    """Bootstrap a coord-topology mission with TWO approved WPs on one lane.

    Returns the primary-checkout feature_dir. Both WPs sit at ``approved`` so the
    real merge bookkeeping has a genuine ``approved -> done`` transition to emit
    for each through the coordination worktree.
    """
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    _write_meta(feature_dir)
    _write_manifest(feature_dir)
    _write_wp_file(feature_dir, STRANDED_WP)
    _write_wp_file(feature_dir, COHERENT_WP)

    # Pre-record the per-WP APPROVED events (NOT done) so the bake loop has a real
    # ``approved -> done`` transition to commit for each WP.
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(_approved_event(STRANDED_WP, "01HXAPPR0000000000000000W1"), sort_keys=True)
        + "\n"
        + json.dumps(_approved_event(COHERENT_WP, "01HXAPPR0000000000000000W2"), sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({MISSION_SLUG}): bootstrap 2-WP coord mission")

    # Coordination/mission branch at the current tip.
    _git(repo, "branch", COORD_BRANCH)

    # Lane branch with REAL code diffs (both WPs' write-scope) not on the mission
    # branch nor on main.
    lane_branch = f"kitty/mission-{MISSION_SLUG}-{LANE_ID}"
    _git(repo, "branch", lane_branch, COORD_BRANCH)
    _git(repo, "checkout", lane_branch)
    for rel in ("src/wp01_code.py", "src/wp02_code.py"):
        code_path = repo / rel
        code_path.parent.mkdir(parents=True, exist_ok=True)
        code_path.write_text("def feature() -> int:\n    return 2367\n", encoding="utf-8")
    _git(repo, "add", "src")
    _git(repo, "commit", "-m", f"feat({MISSION_SLUG}): lane code for the 2-WP write-set")
    _git(repo, "checkout", "main")
    restamp_log_at_lane_tips(repo, feature_dir, coord_branch=COORD_BRANCH)

    # Materialize the coordination worktree with the mission branch CHECKED OUT
    # (the production topology): the pre-target ``done`` transactions commit
    # through this worktree, and the rollback byte-restores only its working bytes.
    CoordinationWorkspace.resolve(repo, MISSION_SLUG, MID8)

    return feature_dir


# ---------------------------------------------------------------------------
# Bake-mid-write-set failure injection + git-reducible readers
# ---------------------------------------------------------------------------


@contextlib.contextmanager
def _bake_failure_on_second_wp() -> Iterator[list[str]]:
    """Inject the failure INSIDE ``_record_merged_wps_done_for_merge``.

    Wraps ``done_bookkeeping._mark_wp_merged_done`` (the per-WP emit the bake loop
    calls): the STRANDED WP delegates to the real helper (its ``done`` genuinely
    COMMITS to the coordination branch), then the COHERENT WP RAISES — so the
    exception propagates out of the bake loop after ≥1 committed ``done``, hitting
    the real ``executor.py:406-408`` byte-restore-without-revert branch. Yields the
    ordered per-WP call list so the caller can assert the failure was mid-loop
    (non-vacuity: NOT a target-advance/squash-conflict rollback).
    """
    real_mark = done_bookkeeping._mark_wp_merged_done
    calls: list[str] = []

    def fake_mark(
        repo_root: Path, mission_slug: str, wp_id: str, target_branch: str
    ) -> None:
        calls.append(wp_id)
        if wp_id == COHERENT_WP:
            raise RuntimeError(_INJECTED_BAKE_FAILURE)
        real_mark(repo_root, mission_slug, wp_id, target_branch)

    with patch(
        "specify_cli.consolidation.done_bookkeeping._mark_wp_merged_done",
        side_effect=fake_mark,
    ):
        yield calls


def _run_bake_failing_merge(repo: Path) -> tuple[BaseException, list[str]]:
    """Run one merge pass whose bake loop fails on the 2nd WP.

    Returns the propagated exception (asserted to be the injected bake fault) and
    the ordered per-WP mark calls (asserted to reach the 2nd WP).

    Re-invoked as the ``spec-kitty merge --resume`` heal step: the second pass
    detects ``is_resume`` from the persisted ``ConsolidationState`` and re-drives the same
    failing bake loop, so the injected fault re-raises (caught here) while the
    pre-existing strand is left untouched — the resume no-ops the coherence heal
    until the WP03 repair lands.
    """
    with _merge_external_mocks(), _bake_failure_on_second_wp() as calls:
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
            return exc, calls
    raise AssertionError(
        "precondition: the injected bake-mid-write-set failure did not propagate — "
        "the merge unexpectedly succeeded, so the #2367-B rollback path never ran."
    )


@contextlib.contextmanager
def on_phase_failure(phase_name: str, action: Callable[[], object]) -> Iterator[None]:
    """Run *action* when the REAL executor phase raises, before the driver's rollback door runs.

    #5385: the driver wraps the whole post-mutation span in one rollback door, so
    the phase-level outcome (byte restore + strand marker) is only observable at
    the phase's own exit. The wrapper calls the real phase unchanged and re-raises
    its original exception after *action*.
    """
    real = getattr(executor, phase_name)

    def observed(run: object) -> None:
        try:
            real(run)
        except BaseException:
            action()
            raise

    with patch.object(executor, phase_name, observed):
        yield


def foreign_coord_commit(repo: Path, mission_slug: str, mid8: str) -> str:
    """Another actor commits an unrelated file on the coordination branch (through its worktree).

    The rollback authority never restores over a commit it did not record, so the
    coordination branch is then reported NOT restored and the strand marker stays
    for the resume-start heal (the #5385 successor of a failing ``git revert``).
    """
    coord_worktree = CoordinationWorkspace.worktree_path(repo, mission_slug, mid8)
    (coord_worktree / "FOREIGN.md").write_text("another actor\n", encoding="utf-8")
    _git(coord_worktree, "add", "FOREIGN.md")
    _git(coord_worktree, "commit", "-m", "another actor's commit")
    return _git(coord_worktree, "rev-parse", "HEAD").stdout.strip()


def marker_wps(repo: Path) -> list[str] | None:
    """``stranded_wp_ids`` of the persisted ``pending_coord_reconcile`` marker (``None`` if absent)."""
    state = load_state(repo, MISSION_ID)
    marker = state.pending_coord_reconcile if state is not None else None
    return [str(wp) for wp in marker["stranded_wp_ids"]] if marker else None


def _committed_coord_events(repo: Path, feature_dir: Path) -> list[StatusEvent]:
    """Reduce the events COMMITTED to the coordination branch (contract-routed).

    Uses ``EventLogReadContract.coordination_branch_ref`` — NEVER a hand-rolled
    ``git show <branch>:...`` — so the committed-ref read stays on the canonical
    authority.
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


def _lane_on(events: list[StatusEvent], wp_id: str) -> Lane:
    lane = wp_lane_actor_from_events(events, wp_id).lane
    return lane


# ---------------------------------------------------------------------------
# #2367-B under the #5385 single rollback door
# ---------------------------------------------------------------------------


def test_bake_mid_write_set_failure_is_restored_by_the_rollback_door(tmp_path: Path) -> None:
    """#2367-B / #5385: the phase strands + marks, the door restores; no strand survives.

    History: pre-#5385 this test pinned the strand SURVIVING the run and a
    ``--resume`` heal reconciling it. The single rollback door now restores the
    coordination branch to its pre-run snapshot, so the contract is:

    * at the bake phase's exit (before the door) the committed coordination ref
      strands EXACTLY the WP whose ``done`` committed before the abort, the working
      tree is byte-restored to ``approved`` and the marker names that WP (the
      phase-level guard still runs -- non-vacuity);
    * after the run the coordination branch is back at its pre-run SHA, nothing is
      stranded, the marker and ``completed_wps`` are cleared;
    * a later resume is coherent (``committed == working == approved``).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_two_wp_coord_mission(repo)
    pre_run_coord = _git(repo, "rev-parse", COORD_BRANCH).stdout.strip()
    at_phase_exit: dict[str, object] = {}

    def observe() -> None:
        at_phase_exit["stranded"] = _durable_done_wps_on_coordination_ref(
            repo_root=repo, mission_slug=MISSION_SLUG, candidate_wps=[STRANDED_WP, COHERENT_WP]
        )
        at_phase_exit["working"] = _lane_on(_working_coord_events(repo), STRANDED_WP)
        at_phase_exit["marker"] = marker_wps(repo)

    with on_phase_failure("_phase_bake_and_pre_target_done", observe):
        exc, calls = _run_bake_failing_merge(repo)

    assert isinstance(exc, RuntimeError) and _INJECTED_BAKE_FAILURE in str(exc), f"the ORIGINAL bake fault must propagate; got {exc!r}"
    assert calls == [STRANDED_WP, COHERENT_WP], f"the failure must fire mid write-set; got mark order {calls}"
    assert at_phase_exit == {"stranded": {STRANDED_WP}, "working": Lane.APPROVED, "marker": [STRANDED_WP]}, (
        f"phase-level guard (before the door): strand of exactly the stranded WP, byte-restored working tree, marker; got {at_phase_exit}"
    )

    assert _git(repo, "rev-parse", COORD_BRANCH).stdout.strip() == pre_run_coord, "#5385: the door must restore the coordination branch"
    assert _durable_done_wps_on_coordination_ref(repo_root=repo, mission_slug=MISSION_SLUG, candidate_wps=[STRANDED_WP, COHERENT_WP]) == set()
    assert _lane_on(_committed_coord_events(repo, feature_dir), STRANDED_WP) == Lane.APPROVED
    assert _lane_on(_working_coord_events(repo), STRANDED_WP) == Lane.APPROVED
    assert marker_wps(repo) is None, "a full restore clears the strand marker"
    state = load_state(repo, MISSION_ID)
    assert state is not None and state.completed_wps == [], "the kept record claims nothing after a full restore"

    resume_exc, _resume_calls = _run_bake_failing_merge(repo)
    assert isinstance(resume_exc, RuntimeError) and _INJECTED_BAKE_FAILURE in str(resume_exc), f"the resume must reach the bake again; got {resume_exc!r}"
    committed_lane = _lane_on(_committed_coord_events(repo, feature_dir), STRANDED_WP)
    working_lane = _lane_on(_working_coord_events(repo), STRANDED_WP)
    assert committed_lane == working_lane == Lane.APPROVED, f"a later resume must stay coherent; committed={committed_lane} working={working_lane}"
    assert _git(repo, "rev-parse", COORD_BRANCH).stdout.strip() == pre_run_coord
