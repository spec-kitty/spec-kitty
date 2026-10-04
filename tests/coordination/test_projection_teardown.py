"""S-B / FR-004 — projection of ALL post-checkpoint commits + CAS-gated teardown.

Mission ``terminus-merge-integrity-01M380R6`` WP07 (traces #4981 / #4970 / #4973).

Two coupled guarantees, proven with REAL git fixtures (no git-layer mocking):

1. **Projection (T032/T033)** — a NON-status commit appended to the coordination
   ref *after* the bookkeeping checkpoint is projected onto the target before
   teardown, so a concurrent status-emit / acceptance-verdict committed during
   the merge is not lost. Today ``_project_status_bookkeeping_to_target`` copies
   only ``status.events.jsonl`` / ``status.json``; the concurrent verdict dies in
   teardown (#4981). The projection preserves append-only semantics (content is
   brought forward, never range-reverted — WP08 owns the SHA-scoped heal).

2. **Gated teardown (T034)** — teardown proceeds only when (a) the reachability
   check passed AND (b) the coordination tip is unchanged since the projection
   captured its window (compare-and-swap). A moved tip or a failed reachability
   check aborts teardown fail-closed, tearing down nothing (the coord triple is
   one coupled decision), with a structured, non-zero refusal.

The projection also exposes the squash-content-proof artifact
(:func:`projected_content_matches_target`) the WP06 reconciliation gate defers to
for squash strategies (it drops ``verify_reachability`` because squash loses lane
SHAs/patch-ids); a follow-up wires that proof to flip squash back to full
verification.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
from specify_cli.consolidation import (
    phase_teardown,
    run_state,
)

if TYPE_CHECKING:
    from specify_cli.consolidation.executor import _MergeRunState

pytestmark = [pytest.mark.git_repo, pytest.mark.integration]

MISSION_ID = "01M380R6WP07000000000000AA"
MID8 = "01M380R6"
SLUG = f"terminus-projection-{MID8.lower()}"


# ---------------------------------------------------------------------------
# Real-git fixture helpers (no git-layer mocking — contract §"Property test")
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _rev(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", ref).stdout.strip()


def _mission_dir(repo: Path) -> Path:
    return repo / "kitty-specs" / SLUG


def _init_repo(tmp_path: Path) -> Path:
    """A real repo on ``main`` with a bootstrapped coord mission dir + status files."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")

    home = _mission_dir(repo)
    home.mkdir(parents=True)
    (home / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mid8": MID8, "mission_slug": SLUG}) + "\n",
        encoding="utf-8",
    )
    (home / "status.events.jsonl").write_text('{"wp_id": "WP01", "to_lane": "approved"}\n', encoding="utf-8")
    (home / "status.json").write_text('{"work_packages": {}}\n', encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "bootstrap coord mission")
    return repo


def _make_coord_branch(repo: Path) -> str:
    """Branch the coord ref off the bootstrap tip (checkpoint window base)."""
    branch = f"kitty/mission-{SLUG}"
    _git(repo, "branch", branch)
    return branch


def _append_coord_commit(repo: Path, coord_branch: str, rel_path: str, content: str, msg: str) -> str:
    """Commit ``rel_path`` onto ``coord_branch`` without disturbing the main checkout.

    Uses a throwaway worktree so the primary ``main`` checkout (the projection
    target) stays put — mirroring how a concurrent status-emit lands on the coord
    ref during a merge.
    """
    wt = repo.parent / f"_coordwt_{rel_path.replace('/', '_')}"
    _git(repo, "worktree", "add", "-q", str(wt), coord_branch)
    try:
        target = wt / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", msg)
        sha = _rev(wt, "HEAD")
    finally:
        _git(repo, "worktree", "remove", "--force", str(wt))
    return sha


# ---------------------------------------------------------------------------
# Projection — all post-checkpoint commits, not just status files (T033)
# ---------------------------------------------------------------------------


def test_post_checkpoint_verdict_commit_is_projected_onto_target(tmp_path: Path) -> None:
    """A concurrent verdict commit on the coord ref lands on the target (not lost)."""
    from specify_cli.consolidation.bookkeeping_projection import (
        project_post_checkpoint_commits_to_target,
    )

    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    checkpoint = _rev(repo, coord)

    verdict_rel = f"kitty-specs/{SLUG}/decision-log/WP01-verdict.md"
    verdict_body = "verdict: approved\nreviewer: renata\n"
    concurrent_sha = _append_coord_commit(repo, coord, verdict_rel, verdict_body, "verdict(WP01): approved")

    result = project_post_checkpoint_commits_to_target(
        main_repo=repo,
        mission_slug=SLUG,
        coord_ref=coord,
        checkpoint_sha=checkpoint,
    )

    # The concurrent commit is inside the projected window and its file landed.
    assert concurrent_sha in result.projected_commits
    assert verdict_rel in result.projected_paths
    projected_file = repo / verdict_rel
    assert projected_file.exists()
    assert projected_file.read_text(encoding="utf-8") == verdict_body

    # "Reachable from the target ref": once the harness commits the projected
    # content onto the target, the concurrent verdict is present at the target ref
    # (content-reachable — a content projection cannot graft the coord SHA, and
    # the epic property is that the concurrent work SURVIVES teardown, #4981).
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "chore: project post-checkpoint bookkeeping")
    shown = _git(repo, "show", f"main:{verdict_rel}").stdout
    assert shown == verdict_body


def test_projection_excludes_status_files_from_general_projection(tmp_path: Path) -> None:
    """Status byte-sets stay owned by the union path — the general projection skips them."""
    from specify_cli.consolidation.bookkeeping_projection import (
        project_post_checkpoint_commits_to_target,
    )

    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    checkpoint = _rev(repo, coord)

    # The only post-checkpoint change is a status-log append.
    status_rel = f"kitty-specs/{SLUG}/status.events.jsonl"
    _append_coord_commit(
        repo,
        coord,
        status_rel,
        '{"wp_id": "WP01", "to_lane": "approved"}\n{"wp_id": "WP01", "to_lane": "done"}\n',
        "status(WP01): done",
    )

    result = project_post_checkpoint_commits_to_target(
        main_repo=repo,
        mission_slug=SLUG,
        coord_ref=coord,
        checkpoint_sha=checkpoint,
    )

    # The general projection must NOT touch the status files (the union /
    # rematerialize path in _project_status_bookkeeping_to_target owns them);
    # blindly overwriting would drop a target-newer event (FR-005).
    assert status_rel not in result.projected_paths


def test_projection_is_a_noop_when_nothing_changed_since_checkpoint(tmp_path: Path) -> None:
    """No post-checkpoint commit ⇒ nothing projected (bounded, no-op)."""
    from specify_cli.consolidation.bookkeeping_projection import (
        project_post_checkpoint_commits_to_target,
    )

    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    checkpoint = _rev(repo, coord)

    result = project_post_checkpoint_commits_to_target(
        main_repo=repo,
        mission_slug=SLUG,
        coord_ref=coord,
        checkpoint_sha=checkpoint,
    )

    assert result.projected_paths == ()
    assert result.projected_commits == ()
    assert result.coord_tip_sha == checkpoint


def test_status_projection_call_site_signature_is_backward_compatible(tmp_path: Path) -> None:
    """The existing 3-arg call (no checkpoint/coord kwargs) keeps its behavior + return."""
    from specify_cli.consolidation.bookkeeping_projection import (
        _project_status_bookkeeping_to_target,
    )

    repo = _init_repo(tmp_path)
    events_path, status_path = _project_status_bookkeeping_to_target(
        main_repo=repo,
        mission_slug=SLUG,
        status_feature_dir=_mission_dir(repo),
    )
    assert events_path.name == "status.events.jsonl"
    assert status_path.name == "status.json"


# ---------------------------------------------------------------------------
# Squash content proof (WP06 handoff — verify_reachability=False deferral)
# ---------------------------------------------------------------------------


def test_projected_content_matches_target_after_projection(tmp_path: Path) -> None:
    """The content proof holds once the projected paths are committed onto the target."""
    from specify_cli.consolidation.bookkeeping_projection import (
        project_post_checkpoint_commits_to_target,
        projected_content_matches_target,
    )

    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    checkpoint = _rev(repo, coord)
    pre_squash_target_sha = _rev(repo, "main")
    verdict_rel = f"kitty-specs/{SLUG}/decision-log/WP01-verdict.md"
    _append_coord_commit(repo, coord, verdict_rel, "verdict: approved\n", "verdict(WP01)")

    result = project_post_checkpoint_commits_to_target(main_repo=repo, mission_slug=SLUG, coord_ref=coord, checkpoint_sha=checkpoint)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "project bookkeeping")

    assert projected_content_matches_target(
        main_repo=repo,
        coord_ref=coord,
        target_ref="main",
        projected_paths=result.projected_paths,
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash_target_sha,
    )


def test_projected_content_proof_fails_when_target_diverges(tmp_path: Path) -> None:
    """The proof is non-vacuous: a target that never received the content fails it."""
    from specify_cli.consolidation.bookkeeping_projection import projected_content_matches_target

    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    checkpoint = _rev(repo, coord)
    verdict_rel = f"kitty-specs/{SLUG}/decision-log/WP01-verdict.md"
    _append_coord_commit(repo, coord, verdict_rel, "verdict: approved\n", "verdict")

    # Never projected onto main → the content proof must report divergence.
    assert not projected_content_matches_target(
        main_repo=repo,
        coord_ref=coord,
        target_ref="main",
        projected_paths=(verdict_rel,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref="main",
    )


# ---------------------------------------------------------------------------
# CAS + reachability-gated teardown (T034)
# ---------------------------------------------------------------------------


def _patched_teardown_legs():
    """Patch the persist + destroy legs so the gate decision is what's under test."""
    return (
        patch("specify_cli.coordination.teardown._persist_retrospective"),
        patch(
            "specify_cli.coordination.teardown._destroy_coordination_worktree",
            return_value=True,
        ),
    )


def test_teardown_proceeds_when_gate_passes(tmp_path: Path) -> None:
    """Reachability OK + coord tip unchanged ⇒ persist then destroy, in order."""
    from specify_cli.coordination.teardown import (
        ProjectionTeardownGate,
        teardown_coordination_topology,
    )

    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    tip = _rev(repo, coord)
    gate = ProjectionTeardownGate(coord_ref=coord, expected_coord_sha=tip, reachability_ok=True)

    persist_p, destroy_p = _patched_teardown_legs()
    with persist_p as persist, destroy_p as destroy:
        ok = teardown_coordination_topology(repo, SLUG, MID8, projection_gate=gate)

    assert ok is True
    assert persist.called
    assert destroy.called


def test_teardown_aborts_when_coord_tip_moved_since_checkpoint(tmp_path: Path) -> None:
    """CAS: a coord tip that moved after projection aborts teardown fail-closed."""
    from specify_cli.coordination.teardown import (
        ProjectionTeardownAbort,
        ProjectionTeardownGate,
        teardown_coordination_topology,
    )

    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    projected_tip = _rev(repo, coord)
    gate = ProjectionTeardownGate(coord_ref=coord, expected_coord_sha=projected_tip, reachability_ok=True)

    # A concurrent writer lands a commit AFTER projection captured its window.
    _append_coord_commit(repo, coord, f"kitty-specs/{SLUG}/notes/late.md", "late note\n", "late emit")
    assert _rev(repo, coord) != projected_tip

    persist_p, destroy_p = _patched_teardown_legs()
    with (
        persist_p as persist,
        destroy_p as destroy,
        pytest.raises(ProjectionTeardownAbort),
    ):
        teardown_coordination_topology(repo, SLUG, MID8, projection_gate=gate)

    # Nothing torn down, nothing persisted — the coupled triple survives whole.
    assert not destroy.called
    assert not persist.called


def test_teardown_aborts_when_reachability_check_failed(tmp_path: Path) -> None:
    """A failed reachability check aborts teardown even if the coord tip is stable."""
    from specify_cli.coordination.teardown import (
        ProjectionTeardownAbort,
        ProjectionTeardownGate,
        teardown_coordination_topology,
    )

    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    tip = _rev(repo, coord)
    gate = ProjectionTeardownGate(coord_ref=coord, expected_coord_sha=tip, reachability_ok=False)

    persist_p, destroy_p = _patched_teardown_legs()
    with (
        persist_p as persist,
        destroy_p as destroy,
        pytest.raises(ProjectionTeardownAbort),
    ):
        teardown_coordination_topology(repo, SLUG, MID8, projection_gate=gate)

    assert not destroy.called
    assert not persist.called


def test_teardown_without_gate_is_unchanged(tmp_path: Path) -> None:
    """Backward compatibility: no projection_gate ⇒ current persist→destroy path."""
    from specify_cli.coordination.teardown import teardown_coordination_topology

    repo = _init_repo(tmp_path)
    _make_coord_branch(repo)

    persist_p, destroy_p = _patched_teardown_legs()
    with persist_p as persist, destroy_p as destroy:
        ok = teardown_coordination_topology(repo, SLUG, MID8)

    assert ok is True
    assert persist.called
    assert destroy.called


# ---------------------------------------------------------------------------
# WP17 (T090 R16 teardown half, FR-009c, #5023) -- a coordination-only ledger
# refuses teardown, fail-closed, before persist/destroy.
# ---------------------------------------------------------------------------


def test_teardown_refuses_coord_only_ledger(tmp_path: Path) -> None:
    """Red at base: ``teardown_coordination_topology`` has no concept of the
    decisions ledger at all, so it destroys a coordination branch that holds
    the ONLY copy of ``decisions/index.json`` + ``DM-*.md`` (the pre-fix
    #3928 placement) -- the bookkeeping projection excludes PRIMARY kinds,
    so that ledger is lost for good. Fixed: teardown raises
    ``ProjectionTeardownAbort(error_code="COORDINATION_LEDGER_UNREPAIRED")``
    BEFORE persist/destroy, naming the mission, the coordination branch and
    the `doctor decisions --repair` hint -- and the coordination branch still
    exists afterwards.
    """
    import subprocess

    from mission_runtime import MissionTopology
    from specify_cli.coordination.teardown import (
        ProjectionTeardownAbort,
        teardown_coordination_topology,
    )
    from tests._factories.coord_mission import make_fork_fixture

    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)

    persist_p, destroy_p = _patched_teardown_legs()
    with persist_p as persist, destroy_p as destroy, pytest.raises(ProjectionTeardownAbort) as excinfo:
        teardown_coordination_topology(fixture.repo_root, fixture.mission_dir_name, fixture.mid8)

    assert excinfo.value.error_code == "COORDINATION_LEDGER_UNREPAIRED"
    assert "doctor decisions" in str(excinfo.value)
    assert "--repair" in str(excinfo.value)
    assert fixture.mission_dir_name in str(excinfo.value)
    # Nothing torn down, nothing persisted (fail-closed BEFORE either leg).
    assert not destroy.called
    assert not persist.called

    branch_list = subprocess.run(
        ["git", "-C", str(fixture.repo_root), "branch", "--list", fixture.coordination_branch],
        capture_output=True,
        text=True,
        check=True,
    )
    assert branch_list.stdout.strip(), "the coordination branch must still exist after the refusal"


def test_teardown_refuses_when_the_coordination_ledger_probe_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A git failure on an EXISTING coordination ref refuses teardown; it never reads as an empty ledger.

    The ref resolves but the listing then fails, so the ledger probe FAILS
    (rather than finding the ledger absent). Teardown must not proceed to
    persist or destroy: the typed probe error propagates out of the guard.
    """
    from kernel.git import GitCommandError
    from mission_runtime import MissionTopology
    from specify_cli.coordination.teardown import teardown_coordination_topology
    from specify_cli.decisions import fork
    from specify_cli.decisions.fork import LedgerProbeError
    from tests._factories.coord_mission import make_fork_fixture

    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)

    def _failing_tree_entry(*_args: object, **_kwargs: object) -> object:
        raise GitCommandError(argv=("ls-tree",), cwd=Path("."), returncode=128, stderr="fatal: simulated ls-tree failure")

    monkeypatch.setattr(fork, "tree_entry", _failing_tree_entry)

    persist_p, destroy_p = _patched_teardown_legs()
    with persist_p as persist, destroy_p as destroy, pytest.raises(LedgerProbeError):
        teardown_coordination_topology(fixture.repo_root, fixture.mission_dir_name, fixture.mid8)

    assert not destroy.called
    assert not persist.called


def test_teardown_of_a_missing_coordination_branch_is_not_refused(tmp_path: Path) -> None:
    """A coordination branch that is already gone has no ledger left to protect: teardown proceeds.

    This is the idempotent-teardown contract -- a second teardown after the
    branch was deleted is a no-op, not a ``LedgerProbeError``.
    """
    import json

    from mission_runtime import MissionTopology
    from specify_cli.coordination.teardown import teardown_coordination_topology
    from tests._factories.coord_mission import make_fork_fixture

    fixture = make_fork_fixture(tmp_path, "ledger_only_on_coordination", MissionTopology.COORD)
    meta_path = fixture.root_mission_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["coordination_branch"] = "kitty/mission-does-not-exist"
    meta_path.write_text(json.dumps(meta), encoding="utf-8")

    persist_p, destroy_p = _patched_teardown_legs()
    with persist_p as persist, destroy_p as destroy:
        ok = teardown_coordination_topology(fixture.repo_root, fixture.mission_dir_name, fixture.mid8)

    assert ok is True
    assert persist.called
    assert destroy.called


# ---------------------------------------------------------------------------
# #5570 -- the coordination branch is deleted only at the tip the gate approved.
# ---------------------------------------------------------------------------


def _coord_run_state(repo: Path, coord_branch: str, projected_tip: str) -> _MergeRunState:
    """A gated coord-topology merge run, as ``_teardown_coordination_triple`` finds it.

    The gate inputs (checkpoint, passing reconciliation, post-projection tip)
    are the ones the real merge records; only the git repository is a fixture.
    """
    from types import SimpleNamespace

    from specify_cli.consolidation import executor as ex
    from specify_cli.consolidation.reconciliation import VerifyResult, VerifyStatus
    from specify_cli.consolidation.state import ConsolidationState

    meta_path = _mission_dir(repo) / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update({"coordination_branch": coord_branch, "topology": "coord", "flattened": False})
    meta_path.write_text(json.dumps(meta) + "\n", encoding="utf-8")

    feature_dir = _mission_dir(repo)
    lanes_manifest = SimpleNamespace(target_branch="main", mission_branch=coord_branch, lanes=[])
    run = ex._MergeRunState(
        main_repo=repo,
        mission_slug=SLUG,
        canonical_id=MISSION_ID,
        canonical_mission_id=MISSION_ID,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=lanes_manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=True,
        remove_worktree=True,
        teardown_coordination=True,
        strategy=ex.MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=ConsolidationState(mission_id=MISSION_ID, mission_slug=SLUG, target_branch="main", wp_order=["WP01"]),
        is_resume=False,
        baseline_mission_id=MISSION_ID,
    )
    run.coord_checkpoint = run_state._CoordCheckpoint(ref=coord_branch, sha=projected_tip)
    run.coord_tip_after_projection = projected_tip
    run.reconciliation_result = VerifyResult(status=VerifyStatus.PASS)
    return run


def _gated_coord_fixture(tmp_path: Path) -> tuple[Path, str, str]:
    """Repo + a coord branch whose projected tip is distinct from ``main`` (CAS leg active)."""
    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    projected_tip = _append_coord_commit(repo, coord, f"kitty-specs/{SLUG}/notes/projected.md", "projected\n", "projected emit")
    assert projected_tip != _rev(repo, "main"), "fixture invalid: the coord tip must differ from the target"
    return repo, coord, projected_tip


def _branch_exists(repo: Path, branch: str) -> bool:
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "--verify", f"refs/heads/{branch}"], capture_output=True, check=False).returncode == 0


def test_status_commit_landing_between_gate_and_delete_is_never_destroyed(tmp_path: Path) -> None:
    """#5570: a commit that lands AFTER the teardown gate passed but BEFORE the branch delete survives.

    The gate compare-and-swaps the coord tip once, then persist and the worktree
    destroy run, then the branch is deleted. Only ``_destroy_coordination_worktree``
    is wrapped (a concurrency-injection seam: it appends a REAL commit to the coord
    branch, then runs the REAL destroy). Ideal: the delete is a compare-and-swap at
    the gated tip, so it refuses, the branch keeps the late commit, the marker is
    not flattened, and the error reaches the CLI as a non-zero teardown failure.
    Before the fix ``git branch -D`` deleted the branch unconditionally and the late
    commit became unreachable while the call returned normally.
    """
    from specify_cli.coordination import teardown

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    real_destroy = teardown._destroy_coordination_worktree
    late: list[str] = []

    def destroy_after_late_commit(repo_root: Path, mission_slug: str, mid8: str) -> bool:
        late.append(_append_coord_commit(repo, coord, f"kitty-specs/{SLUG}/notes/late.md", "late status emit\n", "late status emit"))
        return real_destroy(repo_root, mission_slug, mid8)

    with patch.object(teardown, "_destroy_coordination_worktree", destroy_after_late_commit), pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    assert late, "fixture invalid: the injection seam never ran"
    assert _branch_exists(repo, coord), "#5570: the coordination branch was deleted over a commit it did not approve"
    assert _rev(repo, coord) == late[0], "the late commit must still be the branch tip"
    message = str(caught.value)
    assert coord in message
    assert late[0][:12] in message, "the refusal must name the moved tip"
    meta = json.loads((_mission_dir(repo) / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("coordination_branch") == coord, "the marker must not be flattened while the branch survives"


def test_unmoved_coord_branch_is_still_deleted_and_flattened(tmp_path: Path) -> None:
    """Positive control: when nothing moved in the window the delete proceeds as before."""

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)

    phase_teardown._teardown_coordination_triple(run)

    assert not _branch_exists(repo, coord)
    meta = json.loads((_mission_dir(repo) / "meta.json").read_text(encoding="utf-8"))
    assert "coordination_branch" not in meta


def test_ungated_teardown_deletes_only_at_the_tip_read_before_the_window(tmp_path: Path) -> None:
    """No gate ran (no checkpoint): the delete still compare-and-swaps, at the tip read before teardown began."""
    from specify_cli.coordination import teardown

    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    run = _coord_run_state(repo, coord, _rev(repo, coord))
    run.coord_checkpoint = None
    run.reconciliation_result = None
    real_destroy = teardown._destroy_coordination_worktree
    late: list[str] = []

    def destroy_after_late_commit(repo_root: Path, mission_slug: str, mid8: str) -> bool:
        late.append(_append_coord_commit(repo, coord, f"kitty-specs/{SLUG}/notes/late.md", "late\n", "late emit"))
        return real_destroy(repo_root, mission_slug, mid8)

    with patch.object(teardown, "_destroy_coordination_worktree", destroy_after_late_commit), pytest.raises(run_state.CoordinationTeardownError):
        phase_teardown._teardown_coordination_triple(run)

    assert _rev(repo, coord) == late[0], "the late commit must survive an ungated teardown too"


def test_branch_that_vanishes_inside_the_window_is_treated_as_already_gone(tmp_path: Path) -> None:
    """Something else already removed the branch: nothing of ours was destroyed, teardown completes."""
    from specify_cli.coordination import teardown

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    real_destroy = teardown._destroy_coordination_worktree

    def destroy_after_branch_removed(repo_root: Path, mission_slug: str, mid8: str) -> bool:
        _git(repo, "branch", "-D", coord)
        return real_destroy(repo_root, mission_slug, mid8)

    with patch.object(teardown, "_destroy_coordination_worktree", destroy_after_branch_removed):
        phase_teardown._teardown_coordination_triple(run)

    assert not _branch_exists(repo, coord)
    meta = json.loads((_mission_dir(repo) / "meta.json").read_text(encoding="utf-8"))
    assert "coordination_branch" not in meta


def test_a_held_ref_lock_keeps_the_branch_and_the_marker(tmp_path: Path) -> None:
    """A git refusal that is not a moved tip (a held ref lock) reports 'still exists' and flattens nothing."""

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    (repo / ".git" / "refs" / "heads" / f"{coord}.lock").write_text("", encoding="utf-8")

    with pytest.raises(run_state.CoordinationTeardownError, match="still exists after teardown"):
        phase_teardown._teardown_coordination_triple(run)

    assert _rev(repo, coord) == projected_tip
    meta = json.loads((_mission_dir(repo) / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("coordination_branch") == coord


def test_delete_mission_branch_with_no_branch_is_a_no_op(tmp_path: Path) -> None:

    repo = _init_repo(tmp_path)
    run = _coord_run_state(repo, f"kitty/mission-{SLUG}", _rev(repo, "main"))

    assert phase_teardown._delete_mission_branch(run) is True


def _commit_on_main(repo: Path, name: str) -> str:
    (repo / name).write_text(f"{name}\n", encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", name)
    return _rev(repo, "main")


def test_pass_anchor_carries_only_over_the_commit_this_run_returned(tmp_path: Path) -> None:
    """#5570: the anchor moves to the exact SHA our own commit produced, on top of the current anchor."""

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    before = _rev(repo, "main")
    run.state.reconciliation_passed_target_sha = before
    own = _commit_on_main(repo, "persisted.txt")

    phase_teardown._carry_pass_anchor_over_own_commit(run, own)

    assert run.state.reconciliation_passed_target_sha == own


def test_pass_anchor_does_not_follow_a_foreign_commit_after_ours(tmp_path: Path) -> None:
    """A foreign commit that landed after ours is never stamped verified: the anchor stays put."""

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    before = _rev(repo, "main")
    run.state.reconciliation_passed_target_sha = before
    own = _commit_on_main(repo, "persisted.txt")
    _commit_on_main(repo, "foreign.txt")

    phase_teardown._carry_pass_anchor_over_own_commit(run, own)

    assert run.state.reconciliation_passed_target_sha == before


def test_pass_anchor_does_not_carry_a_commit_that_is_not_on_the_anchor(tmp_path: Path) -> None:
    """A foreign commit sits between the anchor and our commit (first parent != anchor): no carry."""

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    before = _rev(repo, "main")
    run.state.reconciliation_passed_target_sha = before
    _commit_on_main(repo, "foreign.txt")
    own = _commit_on_main(repo, "persisted.txt")

    phase_teardown._carry_pass_anchor_over_own_commit(run, own)

    assert run.state.reconciliation_passed_target_sha == before


@pytest.mark.parametrize("anchor", [None, ""], ids=["no-anchor", "empty-anchor"])
def test_pass_anchor_is_never_invented_without_a_recorded_pass(tmp_path: Path, anchor: str | None) -> None:

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    run.state.reconciliation_passed_target_sha = anchor
    own = _commit_on_main(repo, "persisted.txt")

    phase_teardown._carry_pass_anchor_over_own_commit(run, own)

    assert run.state.reconciliation_passed_target_sha == anchor


def test_teardown_hands_the_persist_commit_to_the_caller(tmp_path: Path) -> None:
    """``on_persist_commit`` receives the SHA the persist leg returned, and only a real SHA."""
    from specify_cli.coordination import teardown

    seen: list[str] = []
    with patch.object(teardown, "_persist_retrospective", return_value="a" * 40), patch.object(teardown, "_destroy_coordination_worktree", return_value=True):
        teardown.teardown_coordination_topology(tmp_path, SLUG, "", on_persist_commit=seen.append)
    assert seen == ["a" * 40]

    seen.clear()
    with patch.object(teardown, "_persist_retrospective", return_value=None), patch.object(teardown, "_destroy_coordination_worktree", return_value=True):
        teardown.teardown_coordination_topology(tmp_path, SLUG, "", on_persist_commit=seen.append)
    assert seen == [], "a persist that committed nothing has no commit to hand over"


def test_late_commits_are_only_landed_by_a_resume(tmp_path: Path) -> None:
    """A fresh run is covered by the teardown gate; nothing is projected or committed by the landing step."""

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    run.is_resume = False
    target_before = _rev(repo, "main")

    phase_teardown._land_late_coordination_commits(run)

    assert _rev(repo, "main") == target_before


def test_resume_with_nothing_landed_late_commits_nothing(tmp_path: Path) -> None:

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    run.is_resume = True
    run.state.pre_mutation_coord_sha = projected_tip
    target_before = _rev(repo, "main")

    phase_teardown._land_late_coordination_commits(run)

    assert _rev(repo, "main") == target_before


def test_resume_with_an_unreadable_window_refuses_and_keeps_the_branch(tmp_path: Path) -> None:

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    run.is_resume = True
    run.state.pre_mutation_coord_sha = "0" * 40

    with pytest.raises(run_state.CoordinationTeardownError, match="could not be read"):
        phase_teardown._teardown_coordination_triple(run)

    assert _branch_exists(repo, coord)


def _move_branch_past(repo: Path, branch: str) -> tuple[str, str]:
    """Return ``(approved_tip, moved_tip)`` after landing one more commit on *branch*."""
    approved = _rev(repo, branch)
    moved = _append_coord_commit(repo, branch, f"kitty-specs/{SLUG}/notes/late.md", "late\n", "late emit")
    return approved, moved


def test_moved_tip_refusal_names_the_coordination_branch_for_a_coordination_mission(tmp_path: Path) -> None:

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    approved, moved = _move_branch_past(repo, coord)

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._delete_mission_branch(run, approved)

    message = str(caught.value)
    assert message.startswith(f"coordination branch {coord!r} moved to {moved[:12]}")
    assert "coordination marker was left intact" in message
    assert "spec-kitty consolidate --resume" in message


def test_moved_tip_refusal_names_the_mission_branch_without_coordination_topology(tmp_path: Path) -> None:
    """#5570: a mission with no coordination topology has no coordination branch, marker or projection to resume."""

    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    meta_path = _mission_dir(repo) / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["coordination_branch"]
    meta_path.write_text(json.dumps(meta) + "\n", encoding="utf-8")
    approved, moved = _move_branch_past(repo, coord)

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._delete_mission_branch(run, approved)

    message = str(caught.value)
    assert message.startswith(f"mission branch {coord!r} moved to {moved[:12]}")
    assert "coordination" not in message
    assert "--resume" not in message
    assert f"git log {approved[:12]}..{coord}" in message
    assert _branch_exists(repo, coord)
