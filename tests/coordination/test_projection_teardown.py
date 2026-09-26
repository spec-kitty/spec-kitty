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
from unittest.mock import patch

import pytest

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
    from specify_cli.merge.bookkeeping_projection import (
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
    from specify_cli.merge.bookkeeping_projection import (
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
    from specify_cli.merge.bookkeeping_projection import (
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
    from specify_cli.merge.bookkeeping_projection import (
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
    from specify_cli.merge.bookkeeping_projection import (
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
    from specify_cli.merge.bookkeeping_projection import projected_content_matches_target

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
