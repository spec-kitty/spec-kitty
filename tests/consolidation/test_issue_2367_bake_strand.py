"""Scope: #2367 Mechanism B — the merge coord write-set is not atomic (permanent guard; #2367-B FIXED).

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
from collections.abc import Iterator
from kernel.clock import now_utc_iso
from pathlib import Path
from typing import cast
from unittest.mock import patch

import pytest

# Import the status package before any coordination submodule (mirror the
# production import order; see the #2711 harness module docstring for rationale).
import specify_cli.status  # noqa: F401  # import-order guard

import specify_cli.consolidation.done_bookkeeping as done_bookkeeping
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
# US1-S3 / US3-S1 / FR-002 / FR-003 / SC-001 / SC-007 — bake-mid-write-set strand
# (RED on the mission base)
# ---------------------------------------------------------------------------


def test_bake_mid_write_set_failure_strands_committed_done(tmp_path: Path) -> None:
    """#2367 Mechanism B / FR-003 (RED): a failure INSIDE
    ``_record_merged_wps_done_for_merge`` after ≥1 committed ``done`` strands that
    WP's committed coordination ``done`` against the byte-restored working
    ``approved`` (the ``executor.py:406-408`` byte-restore-without-revert branch),
    and a ``spec-kitty merge --resume`` heal does NOT reconcile it.

    Committed-ref split-brain contract (FR-002 / SC-007). The stranded set is
    reduced from the COMMITTED coordination ref via
    ``_durable_done_wps_on_coordination_ref`` over THIS merge's write-set — it must
    name EXACTLY the stranded WP (the coherent, only-ever-``approved`` WP
    excluded), falsifying both a hardcoded ``["WP01"]`` and an over-broad
    ``all_wp_ids``. After the heal, ``committed_lane == working_lane`` for the
    stranded WP is RED on the mission base because the resume no-ops the strand;
    the unified #2786/#2367-B fix (mark-not-raise at ≈406-408 + strand-gated
    ``git revert`` heal on ``--resume``) flips it GREEN.

    Git-reducible reds only: no ``pending_coord_reconcile`` / doctor surface is
    referenced (they do not exist on the base — asserting them reds with
    ``AttributeError`` = forbidden setup-red per ADR 2026-07-17-1).
    """
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    feature_dir = _bootstrap_two_wp_coord_mission(repo)

    exc, calls = _run_bake_failing_merge(repo)

    # Non-vacuity witness A: the failure fired INSIDE the bake loop (the 2nd WP
    # emit), AFTER the 1st WP's ``done`` was marked — i.e. the ``executor.py:406-408``
    # byte-restore-without-revert branch, NOT a target-advance/squash-conflict
    # rollback (those are revert-covered and would repro vacuously green).
    assert isinstance(exc, RuntimeError) and _INJECTED_BAKE_FAILURE in str(exc), (
        "precondition: the merge must fail via the injected bake-mid-write-set "
        f"fault (RuntimeError, inside _record_merged_wps_done_for_merge); got {exc!r}"
    )
    assert calls == [STRANDED_WP, COHERENT_WP], (
        "precondition: the bake loop must mark the stranded WP (committing its "
        "``done``) BEFORE the injected failure on the coherent WP — proving ≥1 "
        f"committed ``done`` preceded the abort; got mark order {calls}"
    )

    committed_events = _committed_coord_events(repo, feature_dir)
    working_events = _working_coord_events(repo)

    # Preconditions: the working tree byte-restored BOTH WPs to ``approved`` (the
    # byte-restore leg runs), and the coherent WP was never marked anywhere.
    assert _lane_on(working_events, STRANDED_WP) == Lane.APPROVED, (
        "precondition: the byte-restored working tree should reduce the stranded "
        f"WP to ``approved``; got {_lane_on(working_events, STRANDED_WP)}"
    )
    assert _lane_on(committed_events, COHERENT_WP) == Lane.APPROVED, (
        "precondition: the coherent WP is only ever ``approved`` (never marked), "
        f"so it is NOT stranded; got committed {_lane_on(committed_events, COHERENT_WP)}"
    )

    # Pre-heal WITNESS (the strand exists + names exactly the stranded WP): the
    # committed coordination ref carries the 1st WP's ``done`` while the working
    # tree rolled back to ``approved``. Reduced from the COMMITTED ref (git-
    # reducible authority; NOT a worktree diff — empty at the mark point per
    # data-model D7). GREEN on base AND after mark-not-raise (deliberate pre-repair
    # strand); the coherent WP is EXCLUDED (SC-007 non-fakeability).
    stranded = _durable_done_wps_on_coordination_ref(
        repo_root=repo,
        mission_slug=MISSION_SLUG,
        candidate_wps=[STRANDED_WP, COHERENT_WP],
    )
    assert stranded == {STRANDED_WP}, (
        "precondition: the committed coordination ref must strand EXACTLY the WP "
        "whose ``done`` committed before the abort (the coherent, only-ever-"
        "``approved`` WP excluded) — this is the contract the fix's marker "
        f"``stranded_wp_ids`` must satisfy; got {stranded}"
    )

    # Heal step — ``spec-kitty merge --resume``. On the mission base no coherence
    # repair entry exists (it lands in WP03), so the resume re-drives the same
    # failing bake loop: the injected fault re-raises and is caught, proving the
    # resume RAN into the bake write-set (not an AttributeError/infra early-abort).
    # The strand is left in place — the heal no-ops today.
    resume_exc, _resume_calls = _run_bake_failing_merge(repo)
    assert isinstance(resume_exc, RuntimeError) and _INJECTED_BAKE_FAILURE in str(
        resume_exc
    ), (
        "the ``merge --resume`` heal step must RUN through to the injected "
        "bake-mid-write-set fault (proving the resume reached the coord write-set, "
        f"not an infra/AttributeError early-abort); got {resume_exc!r}"
    )

    committed_lane = _lane_on(_committed_coord_events(repo, feature_dir), STRANDED_WP)
    working_lane = _lane_on(_working_coord_events(repo), STRANDED_WP)

    # Coherence CONTRACT (RED on base, SC-001/US1-S3): after the heal the committed
    # coordination reduction and the working-tree reduction of the stranded WP must
    # AGREE. On the mission base they disagree because the bake failure branch
    # byte-restored working bytes WITHOUT reverting the committed ``done``, and
    # ``merge --resume`` did not reconcile it. The unified #2786/#2367-B fix
    # (mark-not-raise + strand-gated ``git revert`` heal) flips this GREEN.
    assert committed_lane == working_lane, (
        "#2367-B bake-mid-write-set split-brain (post-heal): a failure inside "
        "_record_merged_wps_done_for_merge left the 1st WP's committed "
        "coordination ``done`` stranded (executor.py:406-408 byte-restore-without-"
        "revert) and ``merge --resume`` did NOT reconcile it.\n"
        f"  committed coord ref (git-tracked): {committed_lane}\n"
        f"  byte-restored working tree:        {working_lane}\n"
        "The merge coord write-set must roll back atomically (revert or "
        "mark-and-heal) so an aborted multi-WP bake leaves no committed/working "
        "split-brain (#2367 Mechanism B)."
    )
