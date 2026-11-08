"""#5058 — merge-domain target-branch tip captures resolve the BRANCH, not a same-named tag.

PR #5039 gave the classifier-tip question one canonical authority
(``capture_branch_tip`` in ``core/vcs/git.py``, resolving
``git rev-parse --verify refs/heads/{branch}``), closing the #4857 tag-collision
class for classifiers. The consolidation domain still open-codes the same
"resolve ``target_branch``'s tip" question with a bare ``git rev-parse <branch>``
— which resolves a branch+tag name collision to the **tag** SHA (verified on
git 2.43: a bare ``rev-parse main`` with a tag ``main`` present resolves the
tag). These red-first reproductions pin each remaining site to the branch tip.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

from specify_cli.consolidation import bookkeeping_projection as bp
from specify_cli.consolidation import phase_advance as pa
from specify_cli.consolidation import phase_claim as pc
from specify_cli.consolidation.config import MergeStrategy
from specify_cli.consolidation.run_state import _MergeRunState
from specify_cli.consolidation.state import ConsolidationState

MISSION_ID = "5058-merge-target-tip-capture"
MISSION_SLUG = "merge-target-tip-capture"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _rev(repo: Path, ref: str) -> str:
    return _git(repo, "rev-parse", "--verify", ref)


def _commit(repo: Path, content: str, msg: str) -> str:
    (repo / "f.txt").write_text(content, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", msg)
    return _rev(repo, "HEAD")


def _repo_with_tagged_target(root: Path) -> tuple[Path, str, str]:
    """A repo whose target branch ``main`` has a tag **also named** ``main``.

    Returns ``(repo, tag_sha, branch_tip_sha)`` — the tag intentionally points
    at the branch tip's parent, so a bare ``rev-parse main`` (which resolves
    the tag) and a ``refs/heads/main``-qualified read (which resolves the
    branch) disagree.
    """
    repo = root / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-qb", "main", str(repo)], check=True, capture_output=True, text=True)
    _git(repo, "config", "user.email", "t@t.com")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "f.txt").write_text("0\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "c0")
    tag_sha = _rev(repo, "HEAD")
    branch_tip = _commit(repo, "1\n", "c1")
    _git(repo, "tag", "main", tag_sha)
    return repo, tag_sha, branch_tip


def _make_state() -> ConsolidationState:
    return ConsolidationState(
        mission_id=MISSION_ID,
        mission_slug=MISSION_SLUG,
        target_branch="main",
        wp_order=["WP01"],
    )


def _make_run(repo: Path) -> _MergeRunState:
    manifest = MagicMock()
    manifest.target_branch = "main"
    manifest.mission_slug = MISSION_SLUG
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    return _MergeRunState(
        main_repo=repo,
        mission_slug=MISSION_SLUG,
        canonical_id=MISSION_SLUG,
        canonical_mission_id=None,
        feature_dir=feature_dir,
        target_feature_dir=feature_dir,
        lanes_manifest=manifest,
        all_wp_ids=["WP01"],
        push=False,
        delete_branch=False,
        remove_worktree=False,
        strategy=MergeStrategy.SQUASH,
        assume_yes=True,
        planning_artifact_only=False,
        state=_make_state(),
        is_resume=False,
    )


def test_target_branch_still_at_baseline_uses_branch_tip(tmp_path: Path) -> None:
    repo, _tag_sha, branch_tip = _repo_with_tagged_target(tmp_path)
    # The baseline IS the branch tip; a tag named like the target must not
    # make the comparison read the tag SHA and report the target as moved.
    assert bp._target_branch_still_at_baseline(repo, "main", branch_tip) is True


def test_target_branch_still_at_baseline_still_detects_real_moves(tmp_path: Path) -> None:
    repo, tag_sha, _branch_tip = _repo_with_tagged_target(tmp_path)
    # A baseline that is NOT the branch tip (it happens to be the tag's commit
    # here) must still report "moved" — the guard stays discriminating.
    assert bp._target_branch_still_at_baseline(repo, "main", tag_sha) is False


def test_resolve_pre_mutation_target_sha_uses_branch_tip(tmp_path: Path) -> None:
    repo, _tag_sha, branch_tip = _repo_with_tagged_target(tmp_path)
    state = _make_state()
    resolved = pc._resolve_pre_mutation_target_sha(repo, "main", state)
    assert resolved == branch_tip
    assert state.pre_mutation_target_sha == branch_tip


def test_phase_baseline_and_surface_uses_branch_tip(tmp_path: Path) -> None:
    repo, _tag_sha, branch_tip = _repo_with_tagged_target(tmp_path)
    run = _make_run(repo)
    pa._phase_baseline_and_surface(run)
    assert run.target_baseline_sha == branch_tip


def test_reanchor_baseline_past_primary_tree_bake_uses_branch_tip(tmp_path: Path) -> None:
    repo, _tag_sha, branch_tip = _repo_with_tagged_target(tmp_path)
    run = _make_run(repo)
    run.target_baseline_sha = "stale-baseline"
    # A bake commit landed on the target branch after the baseline capture:
    # the re-anchor must observe the branch's NEW tip, not the tag's SHA.
    new_tip = _commit(repo, "2\n", "bake-on-target")
    pa._reanchor_baseline_past_primary_tree_bake(run)
    assert run.target_baseline_sha == new_tip


def test_reanchor_baseline_keeps_baseline_when_branch_tip_unchanged(tmp_path: Path) -> None:
    repo, _tag_sha, branch_tip = _repo_with_tagged_target(tmp_path)
    run = _make_run(repo)
    run.target_baseline_sha = branch_tip
    pa._reanchor_baseline_past_primary_tree_bake(run)
    # No bake commit moved the branch: the re-anchor is a proven no-op and
    # must not swap the baseline for the same-named tag's SHA.
    assert run.target_baseline_sha == branch_tip
