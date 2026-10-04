"""End-to-end divergent-shape merges through the real ``spec-kitty consolidate`` entry
point (#5108).

SC-001: all four US1 divergent-naming shapes (backfilled legacy, mismatched
mid8, invalid identity >= 8 characters, invalid identity < 8 characters) merge
end to end through :func:`~specify_cli.consolidation.executor._run_lane_based_consolidation`
(the same real entry point ``spec-kitty consolidate`` calls) with no traceback, no
refusal, and every approved lane's commits reachable from the target.

SC-002 / US1 AS5: after each successful merge, 0 created lane branches or
worktrees are orphaned, and the retention policy keeps exactly the created
names.

The old-form-tip-record refusal rule (FR-005, US2 AS2-AS3): an old-form
(identity-keyed) persisted tip record refuses a ``--resume`` and names
``spec-kitty consolidate --abort``; a canceled-only or planning-only manifest is
exempt.

Every shape and every lane/worktree/branch name comes from
:mod:`tests.consolidation._divergent_shapes` (the real-allocator fixture) — never a
hand-composed literal in this file.
"""

from __future__ import annotations

import contextlib
import subprocess
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
import typer

from kernel.clock import now_utc_iso
from specify_cli.cli.commands.consolidate import _run_lane_based_consolidation
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.state import ConsolidationState, save_state
from specify_cli.workspace.context import WorkspaceContext, load_context, save_context

from tests.integration.test_merge_lane_planning_data_loss import (
    _real_merge_external_mocks,
)

from ._divergent_shapes import (
    DIVERGENT_SHAPE_BUILDERS,
    DivergentMission,
    all_wp_ids,
    identity_injected_lane_branch,
    shape_backfilled_legacy,
    shape_mismatched_mid8,
)

pytestmark = [pytest.mark.git_repo, pytest.mark.non_sandbox, pytest.mark.slow]


@contextlib.contextmanager
def _real_merge_mocks_for_divergent_shapes(repo_root: Path) -> Iterator[dict[str, object]]:
    """:func:`_real_merge_external_mocks` plus two additions specific to this
    file's fixtures.

    :mod:`tests.consolidation._divergent_shapes` builds a status-only mission (no WP
    prompt files) and always records a ``mission_id`` (the divergence input
    under test), which activates the ``mission_id``-gated non-vacuous branch of
    both post-commit durability invariants:
    :func:`specify_cli.consolidation.done_bookkeeping._assert_merged_wps_done_on_target`
    and :func:`specify_cli.consolidation.baseline.assert_baseline_merge_commit_on_target`.
    With ``_mark_wp_merged_done``/``commit_merge_bookkeeping`` mocked out (the
    same genuine external side effects the reference real-merge tests do not
    drive), neither invariant has anything to find and would refuse a merge
    whose SC-001 concern — every approved lane's commit reachable from the
    target, no traceback, no reconciliation refusal — is otherwise satisfied.
    These two extra patches keep the done-bookkeeping / baseline-review-mode
    concerns (owned by other WPs' status-model and baseline work) out of
    SC-001's scope without weakening the real ``consolidate_lane_into_mission``
    / ``integrate_mission_into_target`` / ``_merge_branch_into`` merge
    machinery under test.
    """
    with (
        _real_merge_external_mocks(repo_root) as mocks,
        patch("specify_cli.consolidation.phase_bookkeeping._assert_merged_wps_done_on_target"),
        patch("specify_cli.consolidation.phase_bookkeeping._assert_baseline_merge_commit_on_target"),
    ):
        yield mocks


# --------------------------------------------------------------------------- #
# Shared helpers
# --------------------------------------------------------------------------- #


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    )


# _identity_injected_lane_branch moved to the shared
# tests/consolidation/_divergent_shapes.py home (identity_injected_lane_branch) —
# test_executor_lane_naming.py consumed a byte-identical copy.
_identity_injected_lane_branch = identity_injected_lane_branch


def _sha(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", "--verify", ref).stdout.strip()


def _branch_exists(repo: Path, branch: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(repo), "merge-base", "--is-ancestor", ancestor, descendant],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def _write_wp_task_files(mission: DivergentMission) -> None:
    """Write a minimal WP prompt file for every non-planning WP.

    Neither ``_mark_wp_merged_done`` nor ``_assert_merged_wps_done_on_target``
    is exercised on the path this file drives — both are mocked in
    :func:`_real_merge_mocks_for_divergent_shapes` (documented there). Writing
    these files is NOT what keeps that mocked path green; it is required
    because this file was probed against the fully REAL done-bookkeeping path
    (nothing mocked but gates/policy/sparse/preflight/stale-check/porcelain)
    to confirm neither failure mode it produces is a naming defect:

    - WITHOUT a task file: ``_mark_wp_merged_done`` resolves
      ``tasks/<wp_id>*.md`` on the PRIMARY checkout before it will synthesize
      done evidence; finding none, it warns and silently skips the WP, which
      then fails ``_assert_merged_wps_done_on_target`` as "WP01=approved"
      (never reached done).
    - WITH a task file carrying an ``agent:`` field (as a real WP prompt
      always does): the frontmatter triggers a
      ``migration:backfill_runtime_state`` planned->claimed event, appended
      AFTER the merge's own ``done`` event, which then fails the same
      assertion as "WP01=claimed" (the backfill event reads as the WP's
      latest lane).

    Both failures are recorded under the CREATED branch names (never a
    Mission-identity-keyed name) -- so neither is the #5108 defect this WP
    fixes. That is why this file mocks the two done-bookkeeping/baseline
    assertions instead of chasing either failure mode: SC-001/SC-002 are
    about lane-naming reachability and orphan cleanup, not the done/baseline
    bookkeeping owned by other WPs' status-model and baseline work. The
    fixture itself builds status-only missions (no WP prompt files); this
    consumer-side write is retained only so a future removal of one of the
    two mocks reproduces a documented, understood failure rather than a
    surprising one.
    """
    tasks_dir = mission.feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    for lane in mission.manifest.lanes:
        if lane.lane_id == "lane-planning":
            continue
        for wp_id in lane.wp_ids:
            wp_path = tasks_dir / f"{wp_id}.md"
            if not wp_path.exists():
                wp_path.write_text(
                    f"---\nwork_package_id: {wp_id}\ntitle: {wp_id}\nagent: implementer-ivy\ndependencies: []\n---\n\nBody.\n",
                    encoding="utf-8",
                )


def _commit_seeded_status_history(mission: DivergentMission) -> None:
    """Commit the fixture's seeded status log onto the current (target) branch.

    :mod:`tests.consolidation._divergent_shapes` seeds each WP's status through the
    real emit pipeline (:func:`~specify_cli.status.emit.emit_status_transition`)
    AFTER its one ``"bootstrap divergent mission"`` commit, so
    ``status.events.jsonl``/``status.json`` land on disk but are never
    committed. The post-merge target-validation invariant reads this file
    FROM the target branch's git history, not the working tree, so this
    consumer-side commit (no change to the shared fixture) is required before
    a real merge can succeed — mirroring the commit
    ``tests/integration/test_merge_lane_planning_data_loss.py``'s own
    real-merge fixtures make after seeding status.
    """
    _write_wp_task_files(mission)
    status = _git(mission.repo_root, "status", "--porcelain").stdout
    if not status.strip():
        return
    _git(mission.repo_root, "add", "-A")
    _git(mission.repo_root, "commit", "-qm", "chore: commit seeded status history")


def _ensure_mission_branch_ref(mission: DivergentMission) -> None:
    """Create the real mission-integration-branch ref the merge flow needs.

    :mod:`tests.consolidation._divergent_shapes` records ``manifest.mission_branch`` as
    divergence-input METADATA only (WP01's own claim tests never require the
    branch itself to exist on disk). The real merge flow does need an actual
    mission branch to consolidate lanes into before merging into the target —
    the same real-git precondition the mission-create workflow establishes.
    This consumer-side setup does not modify the shared fixture; it only
    creates the branch the fixture already RECORDED, at the target branch's
    current tip (after the seeded status history is committed), exactly as
    mission creation would branch off the target.
    """
    _commit_seeded_status_history(mission)
    if not _branch_exists(mission.repo_root, mission.manifest.mission_branch):
        _git(
            mission.repo_root,
            "branch",
            mission.manifest.mission_branch,
            mission.manifest.target_branch,
        )


def _checkout_target(mission: DivergentMission) -> None:
    _git(mission.repo_root, "checkout", mission.manifest.target_branch)


@contextlib.contextmanager
def _run_real_merge(mission: DivergentMission, **overrides: object) -> Iterator[dict[str, object]]:
    """Drive the real merge entry point over *mission*, real git only.

    Mocks only the same non-git side effects
    :func:`tests.integration.test_merge_lane_planning_data_loss._real_merge_external_mocks`
    stubs for its own real-git merge class — never ``consolidate_lane_into_mission``,
    ``integrate_mission_into_target``, or ``_merge_branch_into``.
    """
    _ensure_mission_branch_ref(mission)
    _checkout_target(mission)
    kwargs: dict[str, object] = {
        "push": False,
        "delete_branch": None,
        "remove_worktree": None,
        "strategy": MergeStrategy.SQUASH,
        "allow_sparse_checkout": True,
    }
    kwargs.update(overrides)
    with _real_merge_mocks_for_divergent_shapes(mission.repo_root) as mocks:
        _run_lane_based_consolidation(
            repo_root=mission.repo_root,
            mission_slug=mission.slug,
            **kwargs,
        )
        yield mocks


def _created_lane_branches_and_worktrees(
    mission: DivergentMission,
) -> tuple[list[str], list[Path]]:
    """Every non-planning lane's CREATED branch/worktree, from the fixture's
    own recorded allocator output — never recomposed in this file."""
    branches: list[str] = []
    worktrees: list[Path] = []
    for lane in mission.manifest.lanes:
        if lane.lane_id == "lane-planning":
            continue
        worktree_path, branch = mission.lanes[lane.lane_id]
        branches.append(branch)
        worktrees.append(worktree_path)
    return branches, worktrees


def _blob_sha(repo: Path, ref: str, relpath: str) -> str | None:
    """Return the git blob SHA for ``relpath`` at ``ref``, or ``None`` if absent."""
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", "--quiet", f"{ref}:{relpath}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _seed_workspace_contexts(mission: DivergentMission) -> dict[str, str]:
    """Create a REAL workspace context per non-planning lane, through the
    production :func:`save_context` API — exactly what ``spec-kitty implement``
    would write for that lane, using the recorded allocator-created worktree
    NAME (``mission.lanes[lane_id][0].name``) as the sole naming input; the
    name is never recomposed via :func:`worktree_dir_name` in this file.

    :mod:`tests.consolidation._divergent_shapes` never writes a workspace context
    (only ``spec-kitty implement`` does) -- without this, the merge-time
    tombstone assertion in :func:`_assert_workspace_contexts_tombstoned` would
    be vacuous: ``load_context`` returns ``None`` before the merge ever runs,
    so it would return ``None`` identically whether or not merge-time
    tombstoning existed at all. Seeding a real, present context here is what
    makes "tombstoned by the merge" an observable, non-vacuous claim.

    Returns ``{lane_id: workspace_name}`` for every non-planning lane, so
    callers assert presence/tombstoning by the SAME recorded name this
    function used to create it.
    """
    workspace_names: dict[str, str] = {}
    for lane in mission.manifest.lanes:
        if lane.lane_id == "lane-planning":
            continue
        worktree_path, branch = mission.lanes[lane.lane_id]
        workspace_name = worktree_path.name
        wp_id = lane.wp_ids[0]
        context = WorkspaceContext(
            wp_id=wp_id,
            mission_slug=mission.manifest.mission_slug,
            worktree_path=str(worktree_path.relative_to(mission.repo_root)),
            branch_name=branch,
            base_branch=mission.manifest.target_branch,
            base_commit=mission.coord_base_sha,
            dependencies=[],
            created_at=now_utc_iso(),
            created_by="wp03-divergent-shapes-test",
            vcs_backend="git",
            lane_id=lane.lane_id,
            lane_wp_ids=list(lane.wp_ids),
            current_wp=wp_id,
        )
        save_context(mission.repo_root, context)
        workspace_names[lane.lane_id] = workspace_name
    return workspace_names


def _assert_workspace_contexts_present(mission: DivergentMission, workspace_names: dict[str, str]) -> None:
    """Non-vacuity check (B1): every seeded context is actually loadable
    BEFORE the merge runs, using the recorded name -- never recomposed."""
    for lane_id, workspace_name in workspace_names.items():
        assert load_context(mission.repo_root, workspace_name) is not None, (
            f"workspace context {workspace_name!r} for {lane_id!r} was not seeded (test setup bug, not a merge defect)"
        )


def _assert_workspace_contexts_tombstoned(mission: DivergentMission, workspace_names: dict[str, str]) -> None:
    """SC-002: every seeded context is gone after a removal merge, keyed
    by the recorded name :func:`_seed_workspace_contexts` returned."""
    for lane_id, workspace_name in workspace_names.items():
        assert load_context(mission.repo_root, workspace_name) is None, (
            f"workspace context {workspace_name!r} for lane {lane_id!r} was not tombstoned after the merge"
        )


def _assert_no_orphans(mission: DivergentMission, workspace_names: dict[str, str]) -> None:
    """SC-002: no created lane branch/worktree survives, and each lane's
    workspace context (seeded via :func:`_seed_workspace_contexts`) is
    tombstoned."""
    branches, worktrees = _created_lane_branches_and_worktrees(mission)
    for branch in branches:
        assert not _branch_exists(mission.repo_root, branch), f"lane branch {branch!r} was left behind after a successful merge"
    for worktree_path in worktrees:
        assert not worktree_path.exists(), f"lane worktree {worktree_path} was left behind after a successful merge"
    porcelain = _git(mission.repo_root, "worktree", "list", "--porcelain").stdout
    for worktree_path in worktrees:
        assert str(worktree_path) not in porcelain, f"lane worktree {worktree_path} still registered in `git worktree list`"
    _assert_workspace_contexts_tombstoned(mission, workspace_names)


def _capture_lane_blobs(mission: DivergentMission) -> dict[str, tuple[str, str]]:
    """Capture ``{lane_id: (owned_rel, blob_sha)}`` from each lane's OWN branch,
    BEFORE the merge runs and (for a default merge) deletes that branch.

    N2: reachability must prove CONTENT landed, not merely that a path exists
    in the target tree -- a path could exist with unrelated or stale content.
    Capturing the lane's own blob before its branch is torn down is what lets
    :func:`_assert_all_lane_commits_reachable` compare the target's blob
    against the genuine approved content afterward.
    """
    captured: dict[str, tuple[str, str]] = {}
    for lane_id, (_worktree_path, lane_branch) in mission.lanes.items():
        if lane_id == "lane-planning":
            continue
        wp_id = next(wp for lane in mission.manifest.lanes if lane.lane_id == lane_id for wp in lane.wp_ids)
        owned_rel = f"src/{wp_id.lower()}.py"
        lane_blob = _blob_sha(mission.repo_root, lane_branch, owned_rel)
        assert lane_blob is not None, f"lane {lane_id!r}'s own branch {lane_branch!r} carries no blob for {owned_rel} (fixture invalid)"
        captured[lane_id] = (owned_rel, lane_blob)
    return captured


def _assert_all_lane_commits_reachable(mission: DivergentMission, lane_blobs: dict[str, tuple[str, str]]) -> None:
    """SC-001: every approved lane's recorded commit's CONTENT is reachable
    from the target -- not merely the path (N2): the target's blob for each
    owned file must be byte-identical to the lane branch's own blob
    (``lane_blobs``, captured by :func:`_capture_lane_blobs` before the merge
    tore the lane branch down). Squash allows this content-equivalence check
    even though the lane SHA itself is not reachable as a commit."""
    target = mission.manifest.target_branch
    for lane_id, (owned_rel, lane_blob) in lane_blobs.items():
        target_blob = _blob_sha(mission.repo_root, target, owned_rel)
        assert target_blob == lane_blob, (
            f"lane {lane_id!r}'s file {owned_rel} on {target!r} (blob {target_blob!r}) does not match "
            f"the lane's own content (blob {lane_blob!r}) -- present but altered, not the approved content"
        )


# --------------------------------------------------------------------------- #
# SC-001: 4/4 divergent shapes merge end to end
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("shape_name", sorted(DIVERGENT_SHAPE_BUILDERS))
def test_divergent_shape_merges_end_to_end(shape_name: str, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """SC-001: every divergent shape merges through the real entry point with
    no traceback, no refusal, and every approved lane's commit reachable."""
    mission = DIVERGENT_SHAPE_BUILDERS[shape_name](tmp_path)
    lane_blobs = _capture_lane_blobs(mission)

    with _run_real_merge(mission):
        pass

    output = capsys.readouterr()
    combined = output.out + output.err
    assert "Traceback" not in combined
    assert "no approved lane resolved any commits" not in combined
    assert "Reconciliation refused" not in combined

    _assert_all_lane_commits_reachable(mission, lane_blobs)


@pytest.mark.parametrize("shape_name", sorted(DIVERGENT_SHAPE_BUILDERS))
def test_divergent_shape_merge_orphans_and_retention_default(shape_name: str, tmp_path: Path) -> None:
    """SC-002: a default (no retention) merge leaves no created lane
    branch/worktree behind and tombstones each lane's workspace context."""
    mission = DIVERGENT_SHAPE_BUILDERS[shape_name](tmp_path)
    workspace_names = _seed_workspace_contexts(mission)
    _assert_workspace_contexts_present(mission, workspace_names)

    with _run_real_merge(mission):
        pass

    _assert_no_orphans(mission, workspace_names)


def test_backfilled_legacy_canceled_lane_survivor_still_merges(tmp_path: Path) -> None:
    """US1 AS2: a canceled lane alongside a surviving approved lane still
    merges end to end; the survivor's commit reaches the target and no
    orphaned branch/worktree remains for either lane."""
    mission = shape_backfilled_legacy(tmp_path, with_canceled_lane=True, canceled_lane_status="canceled")
    # Only lane-a survives; lane-b's WP is canceled and its content must NOT
    # reach the target, so the reachability check is scoped to lane-a alone
    # (a generic capture-all would wrongly assert lane-b's canceled content).
    lane_blobs = {"lane-a": _capture_lane_blobs(mission)["lane-a"]}
    workspace_names = _seed_workspace_contexts(mission)
    _assert_workspace_contexts_present(mission, workspace_names)

    with _run_real_merge(mission):
        pass

    _assert_all_lane_commits_reachable(mission, lane_blobs)
    _assert_no_orphans(mission, workspace_names)


def test_mismatched_mid8_retention_keeps_exactly_created_names(tmp_path: Path) -> None:
    """SC-002: with retention requested, exactly the created lane branch,
    worktree, and workspace context survive, and nothing identity-named is
    created."""
    mission = shape_mismatched_mid8(tmp_path)
    branches, worktrees = _created_lane_branches_and_worktrees(mission)
    workspace_names = _seed_workspace_contexts(mission)
    _assert_workspace_contexts_present(mission, workspace_names)

    with _run_real_merge(mission, delete_branch=False, remove_worktree=False):
        pass

    for branch in branches:
        assert _branch_exists(mission.repo_root, branch), f"retained lane branch {branch!r} was deleted despite --keep-branch"
    for worktree_path in worktrees:
        assert worktree_path.exists(), f"retained lane worktree {worktree_path} was removed despite --keep-worktree"
    _assert_workspace_contexts_present(mission, workspace_names)

    identity_form = _identity_injected_lane_branch(mission.manifest.mission_slug, "lane-a", mission.manifest.mission_id)
    assert identity_form not in branches
    # N4: the line above already proves the identity form was never among the
    # created names; the only remaining claim worth stating is that it was
    # never created as a branch at all.
    assert not _branch_exists(mission.repo_root, identity_form)


# --------------------------------------------------------------------------- #
# Old-form persisted tip record refuses a resume
# --------------------------------------------------------------------------- #


# _all_wp_ids moved to the shared tests/consolidation/_divergent_shapes.py home
# (all_wp_ids) — test_executor_lane_naming.py consumed a byte-identical copy.
_all_wp_ids = all_wp_ids


def _persist_old_form_state(mission: DivergentMission, *, lane_tips: dict[str, str]) -> None:
    """Persist a ``ConsolidationState`` shaped like a POST-FIX interrupted attempt whose
    per-lane tip record is still keyed by the IDENTITY-form branch name — a
    literal a post-fix capture never produces
    (:func:`specify_cli.lanes.compute.lane_created_branch` always keys by the
    lane's CREATED branch). The post-fix marker (FR-012) is stamped so the
    resume reaches the H5 unanchored-record guard under test, rather than
    refusing earlier on the unrelated pre-fix-in-flight-state check
    (:func:`specify_cli.consolidation.reconciliation.detect_legacy_in_flight_state`) —
    both refusals happen to share the ``spec-kitty consolidate --abort`` wording, so
    stamping the marker is what makes this test pin H5 specifically."""
    from specify_cli.consolidation.reconciliation import write_post_fix_marker

    write_post_fix_marker(mission.repo_root, mission.mission_id)
    state = ConsolidationState(
        mission_id=mission.mission_id,
        mission_slug=mission.slug,
        target_branch=mission.manifest.target_branch,
        wp_order=_all_wp_ids(mission),
        completed_wps=[],
        strategy="squash",
        pre_mutation_coord_sha=mission.coord_base_sha,
        pre_interrupt_lane_tips=lane_tips,
    )
    save_state(state, mission.repo_root)


def test_resume_with_old_form_tip_record_refuses(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """US2 AS2: a resume whose persisted tip record is keyed by the
    identity-form branch name refuses and names ``spec-kitty consolidate --abort``;
    afterward ``--abort`` plus a fresh merge succeeds."""
    mission = shape_mismatched_mid8(tmp_path)
    lane_blobs = _capture_lane_blobs(mission)
    _ensure_mission_branch_ref(mission)
    _checkout_target(mission)

    _wt_a, created_branch = mission.lanes["lane-a"]
    identity_form = _identity_injected_lane_branch(mission.manifest.mission_slug, "lane-a", mission.manifest.mission_id)
    assert identity_form != created_branch
    _persist_old_form_state(mission, lane_tips={identity_form: _sha(mission.repo_root, created_branch)})

    with _real_merge_mocks_for_divergent_shapes(mission.repo_root), pytest.raises(typer.Exit) as exc:
        _run_lane_based_consolidation(
            repo_root=mission.repo_root,
            mission_slug=mission.slug,
            push=False,
            delete_branch=None,
            remove_worktree=None,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )
    assert exc.value.exit_code == 1
    output = capsys.readouterr().out
    assert "spec-kitty consolidate --abort" in output
    # Pin H5 specifically (not the unrelated pre-fix-in-flight-state refusal,
    # which shares the same "--abort" wording): the message must name the
    # CREATED branch the record has no anchor for.
    assert created_branch in output
    assert "pre-interrupt lane-tip record has no anchor" in output

    from specify_cli.consolidation.state import clear_state

    clear_state(mission.repo_root, mission.mission_id)
    with _real_merge_mocks_for_divergent_shapes(mission.repo_root):
        _run_lane_based_consolidation(
            repo_root=mission.repo_root,
            mission_slug=mission.slug,
            push=False,
            delete_branch=None,
            remove_worktree=None,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )
    _assert_all_lane_commits_reachable(mission, lane_blobs)


def _assert_not_refused_by_h5(capsys: pytest.CaptureFixture[str]) -> None:
    """The H5 exemptions (US2 AS3) only promise the resume is not refused BY
    H5. A canceled-only or planning-only manifest may still legitimately hit
    an unrelated pre-existing refusal (e.g. the #1772 FR-037 zero-diff-noop
    guard, since there is genuinely no code change left to integrate) — that
    is the documented "any other outcome must be the pre-existing behaviour,
    not H5" contract, not a test failure."""
    output = capsys.readouterr().out
    assert "pre-interrupt lane-tip record has no anchor" not in output


def test_resume_canceled_only_not_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """US2 AS3: every lane canceled -> an empty tip record is exempt
    from H5 (nothing to have anchored)."""
    mission = shape_backfilled_legacy(tmp_path)
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import TransitionRequest

    only_wp = mission.manifest.lanes[0].wp_ids[0]
    emit_status_transition(
        TransitionRequest(
            feature_dir=mission.feature_dir,
            mission_slug=mission.slug,
            wp_id=only_wp,
            to_lane="canceled",
            actor="wp03-resume-test",
            force=True,
            reason="test: cancel the sole WP so the manifest is canceled-only",
        )
    )
    _ensure_mission_branch_ref(mission)
    _checkout_target(mission)
    _persist_old_form_state(mission, lane_tips={})

    with _real_merge_mocks_for_divergent_shapes(mission.repo_root), contextlib.suppress(typer.Exit):
        _run_lane_based_consolidation(
            repo_root=mission.repo_root,
            mission_slug=mission.slug,
            push=False,
            delete_branch=None,
            remove_worktree=None,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )
    _assert_not_refused_by_h5(capsys)


def test_resume_planning_only_not_refused(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """US2 AS3: only ``lane-planning`` -> an empty tip record is exempt
    from H5 (the planning lane is never captured)."""
    mission = shape_backfilled_legacy(tmp_path, with_planning_lane=True)
    # Cancel the code lane so the manifest is planning-only for the merge flow.
    from specify_cli.status.emit import emit_status_transition
    from specify_cli.status.models import TransitionRequest

    code_wp = mission.manifest.lanes[0].wp_ids[0]
    emit_status_transition(
        TransitionRequest(
            feature_dir=mission.feature_dir,
            mission_slug=mission.slug,
            wp_id=code_wp,
            to_lane="canceled",
            actor="wp03-resume-test",
            force=True,
            reason="test: cancel the code lane so only lane-planning remains",
        )
    )
    _ensure_mission_branch_ref(mission)
    _checkout_target(mission)
    _persist_old_form_state(mission, lane_tips={})

    with _real_merge_mocks_for_divergent_shapes(mission.repo_root), contextlib.suppress(typer.Exit):
        _run_lane_based_consolidation(
            repo_root=mission.repo_root,
            mission_slug=mission.slug,
            push=False,
            delete_branch=None,
            remove_worktree=None,
            strategy=MergeStrategy.SQUASH,
            allow_sparse_checkout=True,
        )
    _assert_not_refused_by_h5(capsys)
