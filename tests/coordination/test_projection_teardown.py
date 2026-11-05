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

    # #5697: decision-log/*-verdict.md is unclassified (None) and intentionally no longer projected;
    # traces/ is a projected coord kind (TRACER_FILE), so the carry-forward semantic is kept there.
    verdict_rel = f"kitty-specs/{SLUG}/traces/WP01-verdict.md"
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
    # #5697: decision-log/*-verdict.md is unclassified (None) and intentionally no longer projected;
    # traces/ is a projected coord kind (TRACER_FILE), so the carry-forward semantic is kept there.
    verdict_rel = f"kitty-specs/{SLUG}/traces/WP01-verdict.md"
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


# ---------------------------------------------------------------------------
# #6871 -- a FIRST run (not a resume) must not delete what it never landed
# ---------------------------------------------------------------------------


def _commit_path_on_main(repo: Path, rel_path: str, content: str, msg: str) -> str:
    """Commit *rel_path* onto the target (``main``) in the primary checkout."""
    path = repo / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", msg)
    return _rev(repo, "main")


def _delete_coord_path(repo: Path, coord_branch: str, rel_path: str, msg: str) -> str:
    """Commit the DELETION of *rel_path* on *coord_branch* (same throwaway-worktree shape)."""
    wt = repo.parent / f"_coordwt_del_{rel_path.replace('/', '_')}"
    _git(repo, "worktree", "add", "-q", str(wt), coord_branch)
    try:
        _git(wt, "rm", "-q", rel_path)
        _git(wt, "commit", "-q", "-m", msg)
        sha = _rev(wt, "HEAD")
    finally:
        _git(repo, "worktree", "remove", "--force", str(wt))
    return sha


def _materialise_coord_worktree(repo: Path, coord_branch: str) -> tuple[Path, str]:
    """A REAL coordination worktree on *coord_branch*, with its status directory committed.

    The general late-window projection only runs when the STATUS surface is a coordination checkout
    (``_project_status_bookkeeping_to_target`` short-circuits for a primary one), so a faithful
    first-run fixture needs the worktree a coordination Mission really has. The canonical path is
    what the teardown's destroy leg removes, so the branch is releasable afterwards.
    """
    from specify_cli.coordination.workspace import CoordinationWorkspace

    worktree = CoordinationWorkspace.worktree_path(repo, SLUG, MID8)
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-q", str(worktree), coord_branch)
    mission_dir = worktree / "kitty-specs" / SLUG
    mission_dir.mkdir(parents=True, exist_ok=True)
    # A parseable event log: the fold stage leg reads it, and the bootstrap fixture's placeholder
    # row predates the merge reader.
    event = {
        "event_id": "01M380R6EVENTWP01000000000001",
        "mission_slug": SLUG,
        "mission_id": MISSION_ID,
        "wp_id": "WP01",
        "from_lane": "planned",
        "to_lane": "approved",
        "at": "2026-11-02T00:00:00+00:00",
        "actor": "tester",
        "force": False,
        "execution_mode": "worktree",
    }
    for base in (mission_dir, _mission_dir(repo)):
        (base / "status.events.jsonl").write_text(json.dumps(event) + "\n", encoding="utf-8")
        (base / "status.json").write_text('{"work_packages": {}}\n', encoding="utf-8")
    _git(worktree, "add", "-A")
    staged = subprocess.run(["git", "-C", str(worktree), "diff", "--cached", "--quiet"], check=False)
    if staged.returncode != 0:
        _git(worktree, "commit", "-q", "-m", "status(WP01): approved")
    return worktree, _rev(worktree, "HEAD")


def _commit_in_coord_worktree(worktree: Path, rel_path: str, content: str, msg: str) -> str:
    """Commit a coordination write IN the coordination checkout: the concurrent-writer shape."""
    path = worktree / rel_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    _git(worktree, "add", "-A")
    _git(worktree, "commit", "-q", "-m", msg)
    return _rev(worktree, "HEAD")


def _first_run_with_coord_worktree(tmp_path: Path) -> tuple[_MergeRunState, Path, str]:
    """The gated FIRST-run state of a coordination Mission, with its real coordination worktree."""
    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    worktree, tip = _materialise_coord_worktree(repo, coord)
    run = _coord_run_state(repo, coord, tip)
    run.feature_dir = worktree / "kitty-specs" / SLUG
    assert run.is_resume is False, "fixture invalid: this is the FIRST-run path"
    assert run.coord_tip_after_projection == tip
    return run, worktree, tip


def test_first_run_lands_a_coordination_commit_made_between_the_gate_and_teardown(tmp_path: Path) -> None:
    """#6871: on a FIRST run, a coordination commit after ``coord_tip_after_projection`` is LANDED.

    The merge captures ``coord_tip_after_projection`` after its own last coordination write and
    builds the projection teardown gate on it. A commit that lands after that capture used to be
    refused on a first run: ``_land_late_coordination_commits`` returned early for
    ``is_resume=False``, so the projection teardown gate's compare-and-swap refused, leaving an
    operator to hand-assemble a landing that was already complete. It must instead be projected
    onto the target, committed, and proven landed before the branch is deleted. (A first run with
    no recorded coordination tip builds no window at all; that loss is #7121.)
    """
    run, worktree, tip = _first_run_with_coord_worktree(tmp_path)
    before = _rev(run.main_repo, "main")
    rel = f"kitty-specs/{SLUG}/traces/late.md"
    _commit_in_coord_worktree(worktree, f"kitty-specs/{SLUG}/traces/earlier.md", "earlier\n", "earlier verdict")
    late = _commit_in_coord_worktree(worktree, rel, "late coordination record\n", "late verdict")

    phase_teardown._teardown_coordination_triple(run)

    assert not _branch_exists(run.main_repo, run.lanes_manifest.mission_branch), "the branch is deleted only after the window landed"
    landed = _git(run.main_repo, "show", f"main:{rel}").stdout
    assert landed == "late coordination record\n", "the late record must be COMMITTED on the target, not merely in its working tree"
    log = _git(run.main_repo, "log", "--format=%s", f"{before}..main").stdout
    assert log.count("project coordination commits that landed after the merge captured the coordination tip") == 1, "the window lands as ONE commit"
    meta = json.loads((_mission_dir(run.main_repo) / "meta.json").read_text(encoding="utf-8"))
    assert "coordination_branch" not in meta
    assert run.coord_tip_after_projection == late, "the proven tip becomes the tip teardown approved"
    assert tip != late, "fixture invalid: the late commit moved the coordination branch"


def test_first_run_whose_coordination_branch_is_already_gone_reads_no_window(tmp_path: Path) -> None:
    """#6871 positive control: an absent coordination branch is a no-op, never an unreadable-window refusal.

    A first run now reads the late window before the teardown. When the branch was already deleted by
    something else, that read must not turn the run into a "commits could not be read" refusal: there is
    nothing left to project and nothing left to destroy, so the step returns and the teardown's own
    compare-and-swap logic owns the outcome.
    """
    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)
    _git(repo, "branch", "-D", coord)

    phase_teardown._land_late_coordination_commits(run)  # no ref: no window, no commit, no refusal

    assert run.coord_tip_after_projection == projected_tip, "a run with nothing to project approves nothing new"


def test_first_run_does_not_approve_a_tip_that_moved_during_the_projection(tmp_path: Path) -> None:
    """#6871 fail-closed leg: the approved tip never advances to a tip the assertion did not cover.

    A concurrent commit landing WHILE the projection runs must leave the anchor at the pre-window tip.
    The teardown then refuses at the projection teardown gate's compare-and-swap (the anchor no longer
    matches the live ref) and keeps the branch, so a tip nobody proved can never become "what teardown
    approved". The injected commit touches ``status.json``, the DERIVED snapshot: the late-window
    assertion excludes it by rule (#7198 -- the projection rematerializes it from the proved event log,
    so its own bytes are never an independent record) and the projection never carries it -- so the
    refusal under test is the gate's, not the assertion's. A ``meta.json`` injection would now refuse at
    the assertion instead, which is the #7198 behaviour and not what this case is pinning.
    """
    from specify_cli.coordination.teardown import ProjectionTeardownAbort

    run, worktree, tip = _first_run_with_coord_worktree(tmp_path)
    _commit_in_coord_worktree(worktree, f"kitty-specs/{SLUG}/traces/late.md", "late\n", "late verdict")
    real_commit = phase_teardown._commit_projection_and_carry
    foreign_landed: list[bool] = []

    def commit_then_land_a_foreign_one(target_run: object, paths: list[Path], message: str) -> None:
        real_commit(target_run, paths, message)  # type: ignore[arg-type]
        snapshot = worktree / "kitty-specs" / SLUG / "status.json"
        snapshot.write_text('{"work_packages": {"WP01": "approved", "concurrent": "emit"}}\n', encoding="utf-8")
        _git(worktree, "add", "kitty-specs")
        _git(worktree, "commit", "-q", "-m", "concurrent emit")
        foreign_landed.append(True)

    with patch.object(phase_teardown, "_commit_projection_and_carry", commit_then_land_a_foreign_one), pytest.raises(ProjectionTeardownAbort) as caught:
        phase_teardown._teardown_coordination_triple(run)

    assert foreign_landed == [True], "fixture invalid: the foreign commit was never injected (the late.md assert below proves the projection ran)"
    assert _git(run.main_repo, "show", f"main:kitty-specs/{SLUG}/traces/late.md").stdout == "late\n", "the projection landed before the gate refused"
    assert "compare-and-swap failed" in str(caught.value), "the gate refuses, because the anchor no longer matches the live ref"
    assert run.coord_tip_after_projection == tip, "the anchor stays at the pre-window tip: a tip the assertion did not cover is never stamped approved"
    assert _branch_exists(run.main_repo, run.lanes_manifest.mission_branch), "the branch keeps the unproven commit"


def test_first_run_refuses_rather_than_skips_a_window_it_cannot_read(tmp_path: Path) -> None:
    """#6871 review: an UNREADABLE coordination ref is not an absent one.

    ``_resolve_ref_sha`` collapses "absent" and "git failed" into ``""``. Treating a failure as absence
    would skip the window silently, and the delete would then flatten the marker over a live branch. Only
    a definite absence (exit 1) is a no-op; anything else refuses with the branch kept.
    """
    repo, coord, projected_tip = _gated_coord_fixture(tmp_path)
    run = _coord_run_state(repo, coord, projected_tip)

    unreadable = patch.object(phase_teardown, "run_command", return_value=(128, "", "fatal: not a git repository"))
    with unreadable, pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._land_late_coordination_commits(run)

    message = " ".join(str(caught.value).split())
    assert "could not be read" in message
    assert "spec-kitty consolidate --resume" in message


def test_first_run_refuses_a_late_deletion_it_cannot_express_and_keeps_the_triple(tmp_path: Path) -> None:
    """#6871: a late coordination commit the projection cannot carry REFUSES, loudly.

    A deletion of a record the target still holds cannot be expressed by a content projection. On a
    first run that used to end with the branch deleted and the deletion silently applied to nothing;
    now it refuses before the delete, keeps the coordination branch at the late tip, keeps the
    Mission's coordination marker, and names the recovery.
    """
    repo = _init_repo(tmp_path)
    coord = _make_coord_branch(repo)
    rel = f"kitty-specs/{SLUG}/traces/record.md"
    _commit_path_on_main(repo, rel, "the record the target holds\n", "record on the target")
    verified = _append_coord_commit(repo, coord, rel, "the record the target holds\n", "record on the coordination branch")
    run = _coord_run_state(repo, coord, verified)
    late = _delete_coord_path(repo, coord, rel, "late: drop the record")

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    message = " ".join(str(caught.value).split())
    assert coord in message, "the refusal names the branch it kept"
    assert "main" in message, "the refusal names the target"
    assert "restore the deleted file" in message, "the deletion kind keeps its own remedy (#6791)"
    assert "spec-kitty consolidate --resume" in message, "the refusal names the recovery"
    assert _branch_exists(repo, coord), "the branch was NOT deleted"
    assert _rev(repo, coord) == late, "the late commit is still the branch tip"
    meta = json.loads((_mission_dir(repo) / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("coordination_branch") == coord, "the marker must not be flattened while the branch survives"


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


def test_a_clean_first_run_projects_nothing(tmp_path: Path) -> None:
    """#6871: a first run whose tip is the tip it captured has an EMPTY window -- no commit, no claim."""

    run, _worktree, tip = _first_run_with_coord_worktree(tmp_path)
    target_before = _rev(run.main_repo, "main")

    phase_teardown._land_late_coordination_commits(run)

    assert _rev(run.main_repo, "main") == target_before, "a clean first run must not commit onto the target"
    assert run.coord_tip_after_projection == tip, "a clean first run approves no new tip"


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


# ---------------------------------------------------------------------------
# #7198 -- EVERY change in the late window is landed or deliberately excluded
# ---------------------------------------------------------------------------


def _late_event(event_id: str, to_lane: str, from_lane: str = "in_progress") -> dict[str, object]:
    """A parseable status event for the coverage fixture (the canonical field set)."""
    return {
        "event_id": event_id,
        "mission_slug": SLUG,
        "mission_id": MISSION_ID,
        "wp_id": "WP01",
        "from_lane": from_lane,
        "to_lane": to_lane,
        "at": "2026-11-05T00:00:00+00:00",
        "actor": "tester",
        "force": False,
        "execution_mode": "worktree",
    }


def _advance_branch_from_another_checkout(repo: Path, branch: str, rel_path: str, content: str, msg: str) -> str:
    """Commit onto *branch* from a checkout that is NOT the coordination worktree (#7198).

    The coordination worktree holds ``branch`` checked out, so a second worktree cannot check it out and
    ``git branch -f`` refuses a checked-out branch. Committing detached and moving the ref with
    ``git update-ref`` is exactly the shape the issue describes: the branch moved, the coordination
    worktree's working tree did not -- and the union stage reads the working tree.
    """
    wt = repo.parent / f"_detachedwt_{rel_path.replace('/', '_')}"
    _git(repo, "worktree", "add", "-q", "--detach", str(wt), branch)
    try:
        target = wt / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        _git(wt, "add", "-A")
        _git(wt, "commit", "-q", "-m", msg)
        sha = _rev(wt, "HEAD")
    finally:
        _git(repo, "worktree", "remove", "--force", str(wt))
    subprocess.run(["git", "-C", str(repo), "update-ref", f"refs/heads/{branch}", sha], check=True, capture_output=True)
    return sha


def _status_log(worktree: Path) -> str:
    return (worktree / "kitty-specs" / SLUG / "status.events.jsonl").read_text(encoding="utf-8")


def test_first_run_refuses_a_status_event_the_union_could_not_see(tmp_path: Path) -> None:
    """#7198 shape 1: an event committed OUTSIDE the coordination worktree is never unioned.

    The union stage merges the coordination worktree's WORKING-TREE event log, not the branch's commits,
    so a branch-only append is not in the target's log. Before this change the assertion exempted the
    status byte-sets, the approved tip advanced to the late commit and the branch was deleted at exit 0,
    dropping the event.
    """
    run, worktree, tip = _first_run_with_coord_worktree(tmp_path)
    branch = run.lanes_manifest.mission_branch
    rel = f"kitty-specs/{SLUG}/status.events.jsonl"
    event = _late_event("01M380R6EVENTWP01000000000042", "done")
    base_log = _git(run.main_repo, "show", f"{branch}:{rel}").stdout
    # The target's committed log parses and matches the worktree baseline, so the only thing missing is
    # the branch-only append (not an unreadable-target artifact of the fixture).
    _commit_path_on_main(run.main_repo, rel, _status_log(worktree), "target log matches the worktree baseline")
    late = _advance_branch_from_another_checkout(run.main_repo, branch, rel, base_log + json.dumps(event) + "\n", "late status emit from another checkout")

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    message = " ".join(str(caught.value).split())
    assert branch in message, "the refusal names the coordination branch it kept"
    assert "status.events.jsonl" in message, "the refusal names the record it could not prove landed"
    assert "01M380R6EVENTWP01000000000042" in message, "the refusal names the missing event id"
    assert "coordination worktree" in message, "the remedy names the copy the union stage actually reads"
    assert "spec-kitty consolidate --resume" in message
    assert _branch_exists(run.main_repo, branch), "the branch was NOT deleted over an unlanded event"
    assert _rev(run.main_repo, branch) == late, "the late commit is still the branch tip"
    assert run.coord_tip_after_projection == tip, "an unproven tip is never stamped approved"
    meta = json.loads((_mission_dir(run.main_repo) / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("coordination_branch") == branch, "the marker must not be flattened while the branch survives"


def test_the_status_event_repair_clears_its_own_refusal(tmp_path: Path) -> None:
    """#7198 review: the remedy must actually clear the refusal, not repeat it.

    The printed repair for a missing event is to make the COORDINATION WORKTREE's copy hold the branch's
    log (that is what the union folds). Doing exactly that and re-running must land the event and finish
    the teardown -- proving the instruction and the machinery agree.
    """
    run, worktree, _tip = _first_run_with_coord_worktree(tmp_path)
    branch = run.lanes_manifest.mission_branch
    rel = f"kitty-specs/{SLUG}/status.events.jsonl"
    event = _late_event("01M380R6EVENTWP01000000000045", "done")
    base_log = _git(run.main_repo, "show", f"{branch}:{rel}").stdout
    _commit_path_on_main(run.main_repo, rel, _status_log(worktree), "target log matches the worktree baseline")
    _advance_branch_from_another_checkout(run.main_repo, branch, rel, base_log + json.dumps(event) + "\n", "late status emit from another checkout")
    with pytest.raises(run_state.CoordinationTeardownError):
        phase_teardown._teardown_coordination_triple(run)

    # The printed repair, verbatim: in the coordination worktree, check the branch's log out.
    _git(worktree, "checkout", branch, "--", rel)
    phase_teardown._teardown_coordination_triple(run)

    assert not _branch_exists(run.main_repo, branch), "the repaired window lands and tears down"
    assert "01M380R6EVENTWP01000000000045" in _git(run.main_repo, "show", f"main:{rel}").stdout


def test_first_run_lands_when_the_target_log_is_a_superset(tmp_path: Path) -> None:
    """#7198 positive control: byte equality is the special case; id containment is the proof.

    The target's committed log carries a late event the coordination branch does not (a concurrent target
    writer) AND the branch's late event. The window is proven landed, the target-only event survives, and
    teardown completes.
    """
    run, worktree, _tip = _first_run_with_coord_worktree(tmp_path)
    branch = run.lanes_manifest.mission_branch
    rel = f"kitty-specs/{SLUG}/status.events.jsonl"
    target_only = _late_event("01M380R6EVENTWP01000000000046", "for_review")
    late = _late_event("01M380R6EVENTWP01000000000043", "done")
    base_log = _git(run.main_repo, "show", f"{branch}:{rel}").stdout
    _commit_path_on_main(run.main_repo, rel, base_log + json.dumps(target_only) + "\n" + json.dumps(late) + "\n", "the target also wrote its own event")
    _advance_branch_from_another_checkout(run.main_repo, branch, rel, base_log + json.dumps(late) + "\n", "late status emit from another checkout")

    phase_teardown._teardown_coordination_triple(run)

    assert not _branch_exists(run.main_repo, branch), "a proven window tears down"
    landed_log = _git(run.main_repo, "show", f"main:{rel}").stdout
    assert "01M380R6EVENTWP01000000000043" in landed_log, "the branch's late event landed"
    assert "01M380R6EVENTWP01000000000046" in landed_log, "the target-only event was not erased by the union"


def test_a_status_log_that_does_not_parse_refuses_as_not_reconcilable(tmp_path: Path) -> None:
    """#7198 review: an unreadable log is NOT the missing-event case, and its repair is not a checkout."""
    run, worktree, tip = _first_run_with_coord_worktree(tmp_path)
    branch = run.lanes_manifest.mission_branch
    rel = f"kitty-specs/{SLUG}/status.events.jsonl"
    _commit_path_on_main(run.main_repo, rel, _status_log(worktree), "target log matches the worktree baseline")
    _advance_branch_from_another_checkout(run.main_repo, branch, rel, "this is not jsonl\n", "late status emit from another checkout")

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    message = " ".join(str(caught.value).split())
    assert "cannot be reconciled" in message
    assert "repair the coordination branch's status.events.jsonl" in message
    assert "coordination worktree" not in message, "checking out a corrupt log would hand the union the same bytes"
    assert _branch_exists(run.main_repo, branch)
    assert run.coord_tip_after_projection == tip


def test_two_payloads_for_one_event_id_refuse_through_the_canonical_union(tmp_path: Path) -> None:
    """#7198 review: id containment alone would trust whichever side sorts last; the union refuses the pair."""
    run, worktree, _tip = _first_run_with_coord_worktree(tmp_path)
    branch = run.lanes_manifest.mission_branch
    rel = f"kitty-specs/{SLUG}/status.events.jsonl"
    shared = _late_event("01M380R6EVENTWP01000000000047", "for_review")
    _commit_path_on_main(run.main_repo, rel, _status_log(worktree) + json.dumps(shared) + "\n", "the target recorded the event")
    conflicting = {**shared, "to_lane": "approved"}
    conflicting_log = _status_log(worktree) + json.dumps(conflicting) + "\n"
    _advance_branch_from_another_checkout(run.main_repo, branch, rel, conflicting_log, "late status emit from another checkout")

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    message = " ".join(str(caught.value).split())
    assert "Conflicting payloads" in message, "the canonical union's refusal is the one that surfaces"
    assert "cannot be reconciled" in message
    assert _branch_exists(run.main_repo, branch)


def test_first_run_refuses_a_meta_json_change_the_target_does_not_carry(tmp_path: Path) -> None:
    """#7198 shape 2: a late primary-artifact change is judged, not exempted.

    ``meta.json`` is the target's own file (the merge bakes the mission number and stamps the baseline),
    so the projection never carries it. That made it exempt too -- a late coordination-side document
    change was deleted with the branch. It is now carried by the target's copy or refused.
    """
    run, worktree, tip = _first_run_with_coord_worktree(tmp_path)
    branch = run.lanes_manifest.mission_branch
    rel = f"kitty-specs/{SLUG}/meta.json"
    coord_meta = json.loads((worktree / rel).read_text(encoding="utf-8"))
    coord_meta["late_field"] = "only on the coordination branch"
    late = _commit_in_coord_worktree(worktree, rel, json.dumps(coord_meta) + "\n", "late meta field")

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    message = " ".join(str(caught.value).split())
    assert rel in message, "the refusal names the document it could not prove landed"
    assert "projection cannot carry" in message, "the remedy says why copying is not the answer here"
    assert "BY HAND" in message, "a whole-file checkout would overwrite the fields the target owns"
    assert "spec-kitty consolidate --resume" in message
    assert _branch_exists(run.main_repo, branch)
    assert _rev(run.main_repo, branch) == late
    assert run.coord_tip_after_projection == tip
    meta = json.loads((_mission_dir(run.main_repo) / "meta.json").read_text(encoding="utf-8"))
    assert meta.get("coordination_branch") == branch


def test_first_run_refuses_a_meta_json_key_the_window_removed(tmp_path: Path) -> None:
    """#7198 review (BLOCKER): containment would approve every REMOVAL. A removed key must be gone from
    the target, not merely absent from the coordination document."""
    run, worktree, _tip = _first_run_with_coord_worktree(tmp_path)
    branch = run.lanes_manifest.mission_branch
    rel = f"kitty-specs/{SLUG}/meta.json"
    seeded = {**json.loads((worktree / rel).read_text(encoding="utf-8")), "remove_me": "present at the checkpoint"}
    base = _commit_in_coord_worktree(worktree, rel, json.dumps(seeded) + "\n", "seed the key")
    run.coord_tip_after_projection = base
    _commit_path_on_main(run.main_repo, rel, json.dumps(seeded) + "\n", "the target holds the key too")
    without = {key: value for key, value in seeded.items() if key != "remove_me"}
    _commit_in_coord_worktree(worktree, rel, json.dumps(without) + "\n", "drop the key on the coordination branch")

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    message = " ".join(str(caught.value).split())
    assert rel in message
    assert _branch_exists(run.main_repo, branch), "a removal the target still holds is not landed"


def test_first_run_proceeds_when_the_target_copy_carries_the_late_delta(tmp_path: Path) -> None:
    """#7198 review (MAJOR): the comparison is the CHECKPOINT -> branch delta, not the whole document.

    The mission-number bake rewrites ``meta.json`` on the target and the baseline writer replaces a null
    baseline. Neither is a change the window made, so neither may turn a landed late edit into a refusal.
    """
    run, worktree, _tip = _first_run_with_coord_worktree(tmp_path)
    rel = f"kitty-specs/{SLUG}/meta.json"
    checkpoint_meta = {**json.loads((worktree / rel).read_text(encoding="utf-8")), "baseline_merge_commit": None}
    base = _commit_in_coord_worktree(worktree, rel, json.dumps(checkpoint_meta) + "\n", "seed the null baseline")
    run.coord_tip_after_projection = base
    coord_meta = {**checkpoint_meta, "mission_number": 12}
    _commit_in_coord_worktree(worktree, rel, json.dumps(coord_meta) + "\n", "the bake records the mission number")
    target_meta = {
        **coord_meta,
        "baseline_merge_commit": "b" * 40,
        "coordination_branch": run.lanes_manifest.mission_branch,
    }
    _commit_path_on_main(run.main_repo, rel, json.dumps(target_meta) + "\n", "the target stamped its own baseline")

    phase_teardown._teardown_coordination_triple(run)

    assert not _branch_exists(run.main_repo, run.lanes_manifest.mission_branch), "a carried delta tears down"


def test_first_run_refuses_a_rename_whose_source_the_target_still_holds(tmp_path: Path) -> None:
    """#7198 review (MAJOR): rename detection reported only the destination, so the source deletion was
    never judged and the target kept BOTH paths."""
    run, worktree, _tip = _first_run_with_coord_worktree(tmp_path)
    branch = run.lanes_manifest.mission_branch
    old_rel = f"kitty-specs/{SLUG}/traces/old-name.md"
    new_rel = f"kitty-specs/{SLUG}/traces/new-name.md"
    body = "the record\n"
    _commit_path_on_main(run.main_repo, old_rel, body, "the target holds the record")
    base = _commit_in_coord_worktree(worktree, old_rel, body, "the coordination branch holds the record")
    run.coord_tip_after_projection = base
    _git(worktree, "mv", old_rel, new_rel)
    _git(worktree, "commit", "-q", "-m", "rename the record")

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    message = " ".join(str(caught.value).split())
    assert old_rel in message, "the refusal names the deletion the projection cannot express"
    assert "restore the deleted file" in message
    assert _branch_exists(run.main_repo, branch)


def test_first_run_refuses_a_status_snapshot_outside_the_derived_surface(tmp_path: Path) -> None:
    """#7198 review (MAJOR): the derived exclusion is for the MISSION's snapshot, not any basename.

    ``research/status.json`` is a research artifact. Classifying by basename alone exempted it, so its
    branch-only bytes were approved with no target copy at all.
    """
    run, worktree, _tip = _first_run_with_coord_worktree(tmp_path)
    branch = run.lanes_manifest.mission_branch
    rel = f"kitty-specs/{SLUG}/research/status.json"
    _commit_in_coord_worktree(worktree, rel, json.dumps({"finding": "only on the coordination branch"}) + "\n", "a research note, not the snapshot")

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    message = " ".join(str(caught.value).split())
    assert rel in message
    assert _branch_exists(run.main_repo, branch)


def test_resume_refuses_a_status_event_the_target_log_does_not_carry(tmp_path: Path) -> None:
    """#7198: the same verdict on a --resume, over the REAL coordination worktree.

    The resume base is the persisted pre-mutation snapshot (here the run's own captured tip), the union
    still reads the worktree, and the assertion refuses on the branch-only event -- so the rule does not
    depend on the window base or on the status surface being the primary checkout.
    """
    run, worktree, tip = _first_run_with_coord_worktree(tmp_path)
    run.is_resume = True
    run.state.pre_mutation_coord_sha = tip
    branch = run.lanes_manifest.mission_branch
    rel = f"kitty-specs/{SLUG}/status.events.jsonl"
    event = _late_event("01M380R6EVENTWP01000000000044", "done")
    base_log = _git(run.main_repo, "show", f"{branch}:{rel}").stdout
    _commit_path_on_main(run.main_repo, rel, _status_log(worktree), "target log matches the worktree baseline")
    _advance_branch_from_another_checkout(run.main_repo, branch, rel, base_log + json.dumps(event) + "\n", "late status emit from another checkout")

    with pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._land_late_coordination_commits(run)

    message = " ".join(str(caught.value).split())
    assert "status.events.jsonl" in message
    assert "01M380R6EVENTWP01000000000044" in message, "the fixture is a MISSING-event case, not an unreadable one"
    assert "coordination worktree" in message, "the remedy names the copy the union stage actually reads"
    assert _branch_exists(run.main_repo, branch)
    assert run.coord_tip_after_projection == tip


def test_a_status_json_only_window_tears_down(tmp_path: Path) -> None:
    """#7198: ``status.json`` stays excluded -- by RULE, because the target's copy IS the log's reduction.

    The derived file is rematerialized from the unioned events by the projection itself, so its own bytes
    are not an independent record. This is the path the gate-CAS fixture injects, so the exclusion has to
    be real and checkable rather than accidental.
    """
    run, worktree, _tip = _first_run_with_coord_worktree(tmp_path)
    _commit_in_coord_worktree(worktree, f"kitty-specs/{SLUG}/status.json", '{"work_packages": {"WP01": "approved"}}\n', "derived snapshot")

    phase_teardown._teardown_coordination_triple(run)

    assert not _branch_exists(run.main_repo, run.lanes_manifest.mission_branch), "a derived snapshot is not a record to prove"


# ---------------------------------------------------------------------------
# #7198 review -- the delta rule's edges, at the assertion seam
# ---------------------------------------------------------------------------


def _assert_window(repo: Path, coord: str, base: str) -> None:
    from specify_cli.consolidation.bookkeeping_projection import assert_late_window_landed

    assert_late_window_landed(
        main_repo=repo,
        mission_slug=SLUG,
        coord_ref=coord,
        checkpoint_sha=base,
        target_feature_dir=_mission_dir(repo),
        target_ref="main",
    )


def _seeded_meta_fixture(
    tmp_path: Path,
    checkpoint_meta: dict[str, object],
    coord_meta: dict[str, object],
    target_meta: dict[str, object],
) -> tuple[Path, str, str]:
    """Repo whose meta.json is *checkpoint_meta* at the window base, *coord_meta* on the branch and
    *target_meta* on the target -- so the assertion sees exactly the checkpoint -> branch delta."""
    repo = _init_repo(tmp_path)
    rel = f"kitty-specs/{SLUG}/meta.json"
    _commit_path_on_main(repo, rel, json.dumps(checkpoint_meta) + "\n", "checkpoint metadata")
    coord = _make_coord_branch(repo)
    base = _rev(repo, coord)
    _commit_path_on_main(repo, rel, json.dumps(target_meta) + "\n", "the target's own copy")
    _append_coord_commit(repo, coord, rel, json.dumps(coord_meta) + "\n", "the window's change")
    return repo, coord, base


def test_json_delta_refuses_a_boolean_that_changed_type(tmp_path: Path) -> None:
    """#7198 review: ``True == 1`` in Python, so a type change must not read as carried."""
    from specify_cli.consolidation.bookkeeping_projection import LateProjectionRefused

    repo, coord, base = _seeded_meta_fixture(
        tmp_path,
        {"flag": False},
        {"flag": True},
        {"flag": 1},
    )

    with pytest.raises(LateProjectionRefused, match="meta.json"):
        _assert_window(repo, coord, base)


def test_json_delta_carries_a_nested_addition_on_the_target(tmp_path: Path) -> None:
    """A nested key the window added is carried when the target's nested object holds it."""
    repo, coord, base = _seeded_meta_fixture(
        tmp_path,
        {"nested": {"a": 1}},
        {"nested": {"a": 1, "b": 2}},
        {"nested": {"a": 1, "b": 2, "c": 3}},
    )

    _assert_window(repo, coord, base)  # no refusal


def test_json_delta_refuses_a_list_element_the_target_does_not_have(tmp_path: Path) -> None:
    """Arrays compare whole: a changed element is not carried by a different array."""
    from specify_cli.consolidation.bookkeeping_projection import LateProjectionRefused

    repo, coord, base = _seeded_meta_fixture(
        tmp_path,
        {"list": [1, 2]},
        {"list": [1, 2, 3]},
        {"list": [1, 2, 4]},
    )

    with pytest.raises(LateProjectionRefused, match="meta.json"):
        _assert_window(repo, coord, base)


def test_a_fully_landed_rename_passes(tmp_path: Path) -> None:
    """#7198 review: with renames enumerated as delete + add, a rename applied on BOTH sides still passes."""
    repo = _init_repo(tmp_path)
    old_rel = f"kitty-specs/{SLUG}/traces/old.md"
    new_rel = f"kitty-specs/{SLUG}/traces/new.md"
    body = "the record\n"
    _commit_path_on_main(repo, old_rel, body, "the record exists on the target")
    coord = _make_coord_branch(repo)
    base = _rev(repo, coord)
    _git(repo, "rm", "-q", old_rel)
    _commit_path_on_main(repo, new_rel, body, "the target applied the rename")
    _delete_coord_path(repo, coord, old_rel, "the coordination branch renamed the record")
    _append_coord_commit(repo, coord, new_rel, body, "the coordination branch renamed the record")

    _assert_window(repo, coord, base)  # no refusal: both halves match


def test_a_snapshot_that_is_not_the_logs_reduction_is_not_exempt(tmp_path: Path) -> None:
    """#7198 review: ``status.json`` is exempt only while it IS the reduction of the committed log.

    The target's log is VALID and reduces successfully, but the target's committed snapshot disagrees with
    that reduction -- so the snapshot is not derived, and the coordination-side copy is a record the target
    does not carry. (An unreadable log would prove the same thing for a different reason; this fixture
    keeps the reduction path exercised.)
    """
    from specify_cli.consolidation.bookkeeping_projection import LateProjectionRefused

    repo = _init_repo(tmp_path)
    log_rel = f"kitty-specs/{SLUG}/status.events.jsonl"
    snapshot_rel = f"kitty-specs/{SLUG}/status.json"
    approved = _late_event("01M380R6EVENTWP01000000000048", "approved")
    _commit_path_on_main(repo, log_rel, json.dumps(approved) + "\n", "a VALID committed log")
    from specify_cli.status import materialize_to_json, read_events_from_text, reduce

    target_snapshot = json.loads((_mission_dir(repo) / "status.json").read_text(encoding="utf-8"))
    reduction = materialize_to_json(reduce(read_events_from_text(_mission_dir(repo), json.dumps(approved) + "\n")))
    assert json.loads(reduction) != target_snapshot, "fixture invalid: the target snapshot is the reduction after all"
    coord = _make_coord_branch(repo)
    base = _rev(repo, coord)
    _append_coord_commit(repo, coord, snapshot_rel, '{"work_packages": {"WP01": "approved"}}\n', "a snapshot the target does not hold")

    with pytest.raises(LateProjectionRefused, match="status.json"):
        _assert_window(repo, coord, base)


def test_a_failed_blob_read_is_never_a_verdict(tmp_path: Path) -> None:
    """#7198 review: a git failure must surface as an error, not as two equal ``None`` blobs.

    The refs are VALID, so the window enumerates and the read is actually reached; ``blob_at`` is then made
    to fail, which is the case a result-collapsing reader would have turned into ``None == None`` -- a
    "landed" verdict. The full teardown path must keep the triple and report the read error instead.
    """
    from kernel.git import GitCommandError
    from specify_cli.consolidation import bookkeeping_projection

    run, worktree, tip = _first_run_with_coord_worktree(tmp_path)
    late = _commit_in_coord_worktree(worktree, f"kitty-specs/{SLUG}/traces/late.md", "late\n", "late verdict")
    assert late != tip, "fixture invalid: the window must not be empty"
    failure = GitCommandError(argv=("git", "cat-file", "blob"), cwd=run.main_repo, returncode=128, stderr="fatal: unable to read object")

    with patch.object(bookkeeping_projection, "blob_at", side_effect=failure), pytest.raises(run_state.CoordinationTeardownError) as caught:
        phase_teardown._teardown_coordination_triple(run)

    message = " ".join(str(caught.value).split())
    assert "late window's blobs could not be read" in message
    assert "unable to read object" in message, "the git error is reported, not swallowed"
    assert run.coord_tip_after_projection == tip, "a failed read proves nothing, so nothing is approved"
    assert _branch_exists(run.main_repo, run.lanes_manifest.mission_branch), "the triple is kept"
