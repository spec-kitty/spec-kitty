"""Unit tests for ``specify_cli.coordination.policy`` (WP05 T021 / T025).

Covers every stable error code:

* ``DESTINATION_REF_INVALID_SHAPE`` (refs/heads prefix, empty, leading -)
* ``DESTINATION_REF_NOT_FOUND``
* ``DESTINATION_REF_NOT_LOCAL`` (remote-tracking)
* ``PROTECTED_BRANCH_REFUSED`` (``main`` / ``master``)
* :class:`Allowed` for the happy path.

Plus a side-effect-free assertion: calling ``assert_allowed`` does not
modify the index, working tree, or .git directory.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import OwnedCheckout
from mission_runtime.context import MissionTopology
from specify_cli.coordination.policy import WorkflowMutationPolicy
from specify_cli.coordination.types import Allowed, GitChangeSet, Refused

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Tmp repo with main + a non-protected ``feature`` branch."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / "seed.txt").write_text("seed\n")
    _git(r, "add", "seed.txt")
    _git(r, "commit", "-q", "-m", "initial")
    _git(r, "branch", "feature")
    _git(r, "branch", "kitty/mission-foo-01ABCDEF")
    return r


def _change(
    repo: Path,
    ref: str,
    operation: str = "test",
) -> GitChangeSet:
    return GitChangeSet(
        destination_ref=ref,
        repo_root=repo,
        worktree_root=repo,
        paths=(),
        message="m",
        operation=operation,
    )


def test_allowed_for_non_protected_branch(repo: Path) -> None:
    verdict = WorkflowMutationPolicy.assert_allowed(
        _change(repo, "kitty/mission-foo-01ABCDEF"),
    )
    assert isinstance(verdict, Allowed)


def test_refused_invalid_shape_refs_heads_prefix(repo: Path) -> None:
    verdict = WorkflowMutationPolicy.assert_allowed(
        _change(repo, "refs/heads/feature"),
    )
    assert isinstance(verdict, Refused)
    assert verdict.error_code == "DESTINATION_REF_INVALID_SHAPE"


def test_refused_invalid_shape_empty(repo: Path) -> None:
    verdict = WorkflowMutationPolicy.assert_allowed(
        _change(repo, ""),
    )
    assert isinstance(verdict, Refused)
    assert verdict.error_code == "DESTINATION_REF_INVALID_SHAPE"


def test_refused_invalid_shape_leading_dash(repo: Path) -> None:
    verdict = WorkflowMutationPolicy.assert_allowed(
        _change(repo, "-bad-name"),
    )
    assert isinstance(verdict, Refused)
    assert verdict.error_code == "DESTINATION_REF_INVALID_SHAPE"


def test_refused_not_found(repo: Path) -> None:
    verdict = WorkflowMutationPolicy.assert_allowed(
        _change(repo, "kitty/never-existed"),
    )
    assert isinstance(verdict, Refused)
    assert verdict.error_code == "DESTINATION_REF_NOT_FOUND"


def test_refused_protected_main(repo: Path) -> None:
    verdict = WorkflowMutationPolicy.assert_allowed(
        _change(repo, "main", operation="emit_status_transition"),
    )
    assert isinstance(verdict, Refused)
    assert verdict.error_code == "PROTECTED_BRANCH_REFUSED"
    assert "main" in verdict.destination_ref
    assert "emit_status_transition" in verdict.message


def test_refused_not_local_remote_tracking(repo: Path, tmp_path: Path) -> None:
    """A ref that only exists as ``refs/remotes/origin/<name>`` → NOT_LOCAL."""
    # Create a fake "origin" remote-tracking ref by fetching from a
    # second tmp repo. Simplest path: write directly into refs/remotes.
    rem_dir = repo / ".git" / "refs" / "remotes" / "origin"
    rem_dir.mkdir(parents=True, exist_ok=True)
    head_sha = subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
    ).strip()
    (rem_dir / "only-remote").write_text(head_sha + "\n")

    verdict = WorkflowMutationPolicy.assert_allowed(
        _change(repo, "only-remote"),
    )
    assert isinstance(verdict, Refused)
    assert verdict.error_code == "DESTINATION_REF_NOT_LOCAL"


def test_assert_allowed_is_side_effect_free(repo: Path) -> None:
    """Calling assert_allowed many times leaves repo state unchanged."""

    def state_hash() -> str:
        # Hash the index file + working-tree mtime tree summary.
        index_path = repo / ".git" / "index"
        h = hashlib.sha256()  # noqa: TID251 — file-integrity checksum of git index + working-tree bytes, not charter freshness hashing
        if index_path.exists():
            h.update(index_path.read_bytes())
        for f in sorted(repo.glob("*")):
            if f.is_file():
                h.update(f.read_bytes())
        return h.hexdigest()

    before = state_hash()
    for ref in (
        "main",
        "feature",
        "kitty/mission-foo-01ABCDEF",
        "refs/heads/feature",
        "",
        "kitty/never-existed",
    ):
        WorkflowMutationPolicy.assert_allowed(_change(repo, ref))
    after = state_hash()
    assert before == after


# ---------------------------------------------------------------------------
# Owned arm: the mission-scoped ``commit_to_target`` fold reads the fact's
# own ``meta.json`` (P), never a copy under the repository root (R).
# ---------------------------------------------------------------------------

_OWNED_SLUG = "owned-policy-01M1A900"


def _protect_feature(repo: Path) -> None:
    (repo / ".kittify").mkdir(exist_ok=True)
    (repo / ".kittify" / "config.yaml").write_text("protection:\n  protected_branches: [feature]\n", encoding="utf-8")


def _write_meta(mission_dir: Path, *, commit_to_target: bool | None) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "mission_id": "01M1A900000000000000000001",
        "mission_slug": _OWNED_SLUG,
        "slug": _OWNED_SLUG,
        "topology": "single_branch",
        "target_branch": "feature",
    }
    if commit_to_target is not None:
        meta["commit_to_target"] = commit_to_target
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")


def _owned_fact(repo: Path, tmp_path: Path, *, p_commit_to_target: bool | None) -> OwnedCheckout:
    owned_root = tmp_path / "owned"
    mission_dir = owned_root / "kitty-specs" / _OWNED_SLUG
    _write_meta(mission_dir, commit_to_target=p_commit_to_target)
    return OwnedCheckout._mint(
        repository_root=repo,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=_OWNED_SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="feature",
    )


def _mission_change(repo: Path) -> GitChangeSet:
    return GitChangeSet(
        destination_ref="feature",
        repo_root=repo,
        worktree_root=repo,
        paths=(),
        message="m",
        operation="test",
        mission_slug=_OWNED_SLUG,
    )


def test_owned_commit_to_target_is_read_from_the_fact_not_the_repository_root(repo: Path, tmp_path: Path) -> None:
    """P opted out (``commit_to_target: true``), R holds no copy: the owned write is allowed."""
    _protect_feature(repo)
    fact = _owned_fact(repo, tmp_path, p_commit_to_target=True)

    assert isinstance(WorkflowMutationPolicy.assert_allowed(_mission_change(repo)), Refused)
    assert isinstance(WorkflowMutationPolicy.assert_allowed(_mission_change(repo), owned=fact), Allowed)


def test_owned_arm_ignores_a_stale_repository_root_opt_out(repo: Path, tmp_path: Path) -> None:
    """R's stale copy opted out but P did not: the owned write stays refused (fail-closed on P)."""
    _protect_feature(repo)
    _write_meta(repo / "kitty-specs" / _OWNED_SLUG, commit_to_target=True)
    fact = _owned_fact(repo, tmp_path, p_commit_to_target=None)

    assert isinstance(WorkflowMutationPolicy.assert_allowed(_mission_change(repo)), Allowed)
    verdict = WorkflowMutationPolicy.assert_allowed(_mission_change(repo), owned=fact)
    assert isinstance(verdict, Refused)
    assert verdict.error_code == "PROTECTED_BRANCH_REFUSED"
