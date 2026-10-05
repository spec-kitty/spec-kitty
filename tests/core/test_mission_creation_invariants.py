"""Create invariants the golden snapshot cannot observe.

One test per invariant. Each pins observable state (refs, HEAD, worktrees,
files) rather than private call order, except where an invariant names an order --
and there the order is pinned through its observable consequence (a branch
still checked out cannot be deleted; a dirty worktree refuses teardown).
Each test goes red on a planted break of its invariant.

Routes are real wherever one exists (real repos, a real ``pre-commit`` hook,
the public ``core.adapters`` pending-origin registration). One invariant has
no real route, because every disposable commit refusal raised inside the
scaffold commit is swallowed as a bootstrap skip, so it injects one:

Patched façade names:
    - ``specify_cli.core.mission_creation._commit_create_scaffold`` --
      invariant 1 (failed-create restore order): raises a disposable
      ``SafeCommitHeadMismatch`` after the protected mint has checked out the
      mission branch, so the full restore path (checkout, orphan branch
      delete, disposable scaffold removal) runs.
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from mission_runtime import MissionTopology
from specify_cli.core import adapters as origin_adapters
from specify_cli.core import mission_creation
from specify_cli.core.mission_creation import (
    MissionAlreadyExistsError,
    MissionCreationError,
    MissionCreationResult,
    create_mission_core,
)
from specify_cli.git.commit_helpers import SafeCommitHeadMismatch
from specify_cli.mission_metadata import write_meta
from tests._factories.coord_mission import _init_repo_with_target

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MAIN = "main"
_TOPIC = "topic"
_SPECS = "kitty-specs"
_MISSION_BRANCH_GLOB = "kitty/mission-*"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _git_rc(repo: Path, *args: str) -> int:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False).returncode


def _mission_branches(repo: Path) -> list[str]:
    out = _git(repo, "branch", "--list", _MISSION_BRANCH_GLOB, "--format=%(refname:short)")
    return [line for line in out.splitlines() if line.strip()]


def _create(repo: Path, slug: str, *, topology: MissionTopology, target_branch: str) -> MissionCreationResult:
    return create_mission_core(
        repo,
        slug,
        topology=topology,
        target_branch=target_branch,
        allow_worktree_context=True,
    )


_HOOK_REFUSE = 'case "$(git rev-parse --abbrev-ref HEAD)" in\n  kitty/mission-*) {side_effect}echo "refused by test hook" >&2; exit 1 ;;\nesac\nexit 0\n'
#: Hook side effect for invariant 2: an interrupted create leaves non-churn content in the
#: coordination Mission dir (``status.events.jsonl`` alone is toolchain churn, which the
#: teardown's dirty guard ignores), so only a clear-BEFORE-teardown rollback can remove it.
_LEAVE_PARTIAL_SEED = 'for d in kitty-specs/*/; do echo partial > "$d/interrupted-seed.md"; done; '


def _install_hook_refusing_mission_branch_commits(repo: Path, *, side_effect: str = "") -> None:
    """Real fault: a ``pre-commit`` hook refusing every commit on ``kitty/mission-*``.

    Hooks live in the common git dir, so the coordination worktree runs it too;
    ``core.hooksPath`` is pinned repo-locally so a global setting cannot bypass it.
    """
    hooks_dir = repo / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook = hooks_dir / "pre-commit"
    hook.write_text("#!/bin/sh\n" + _HOOK_REFUSE.format(side_effect=side_effect), encoding="utf-8")
    hook.chmod(0o755)
    _git(repo, "config", "core.hooksPath", str(hooks_dir))


def _untracked(repo: Path) -> list[str]:
    out = _git(repo, "status", "--porcelain", "--untracked-files=all")
    return [line[3:] for line in out.splitlines() if line.startswith("?? ")]


# ---------------------------------------------------------------------------
# 1. Failed-create restore order (protected SINGLE_BRANCH)
# ---------------------------------------------------------------------------


def test_inv1_failed_create_restores_checkout_then_deletes_minted_branch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """After a failure that strikes post-mint, HEAD is back on ``main``, the minted mission
    branch is gone (only possible once it is no longer checked out), the disposable
    scaffold is removed, and no worktree is left behind."""
    repo = _init_repo_with_target(tmp_path, target_branch=_MAIN, protected_primary=True)
    main_tip = _git(repo, "rev-parse", _MAIN)
    head_at_failure: list[str] = []

    def _refuse_after_mint(**kwargs: Any) -> Any:
        write_root: Path = kwargs["write_root"]
        head_at_failure.append(_git(write_root, "branch", "--show-current"))
        raise SafeCommitHeadMismatch(destination_ref=_MAIN, observed_head=head_at_failure[-1], worktree_root=write_root)

    monkeypatch.setattr(mission_creation, "_commit_create_scaffold", _refuse_after_mint, raising=True)

    with pytest.raises(SafeCommitHeadMismatch):
        _create(repo, "inv-one", topology=MissionTopology.SINGLE_BRANCH, target_branch=_MAIN)

    assert len(head_at_failure) == 1 and head_at_failure[0].startswith("kitty/mission-inv-one-"), (
        "non-vacuity: the failure must strike while the minted mission branch is checked out"
    )
    assert _git(repo, "branch", "--show-current") == _MAIN
    assert _git(repo, "rev-parse", _MAIN) == main_tip
    assert _mission_branches(repo) == [], "the minted mission branch must be deleted after the checkout is restored"
    assert list(repo.glob(f"{_SPECS}/inv-one-*")) == [], "the disposable scaffold must be removed"
    worktree_lines = [line for line in _git(repo, "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]
    assert worktree_lines == [f"worktree {repo}"]


# ---------------------------------------------------------------------------
# 2. Coordination rollback order (COORD)
# ---------------------------------------------------------------------------


def test_inv2_coordination_rollback_clears_dir_then_tears_down_then_deletes_branch(tmp_path: Path) -> None:
    """A failure after the coordination seed (the creation-events commit is refused by a real
    hook that also leaves non-churn content in the coordination Mission dir) leaves no
    coordination worktree, no coordination branch, no untracked coordination Mission dir, and
    the repository root checkout on its original branch and tip.

    Clear-before-teardown is pinned through its consequence: the teardown refuses a worktree
    holding non-churn content, and a branch still checked out there cannot be deleted."""
    repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
    _install_hook_refusing_mission_branch_commits(repo, side_effect=_LEAVE_PARTIAL_SEED)
    topic_tip = _git(repo, "rev-parse", _TOPIC)

    with pytest.raises(MissionCreationError, match="Failed to commit mission-creation events onto the coordination branch"):
        _create(repo, "inv-two", topology=MissionTopology.COORD, target_branch=_TOPIC)

    assert _mission_branches(repo) == [], "the coordination branch must be deleted"
    worktree_lines = [line for line in _git(repo, "worktree", "list", "--porcelain").splitlines() if line.startswith("worktree ")]
    assert worktree_lines == [f"worktree {repo}"], "the coordination worktree must be torn down"
    assert list(repo.glob(".worktrees/inv-two*")) == [], "no coordination worktree dir may survive"
    assert [path for path in _untracked(repo) if path.startswith(".worktrees/")] == [], "no untracked coordination Mission dir may be left"
    assert _git(repo, "branch", "--show-current") == _TOPIC
    assert _git(repo, "rev-parse", "HEAD") == topic_tip


def test_inv2_coordination_rollback_tears_down_worktree_before_deleting_branch(tmp_path: Path) -> None:
    """Direct seam call on a real, fully materialized coordination surface (a successful COORD
    create): the rollback removes the worktree first, so deleting the branch THIS create minted
    succeeds. (Through ``create_mission_core`` the generic orphan-branch sweep would mask a
    swapped order, so this order is pinned at the seam.)"""
    repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
    result = _create(repo, "inv-two-seam", topology=MissionTopology.COORD, target_branch=_TOPIC)
    coordination_branch = result.meta["coordination_branch"]
    assert isinstance(coordination_branch, str) and coordination_branch in _mission_branches(repo)
    assert list(repo.glob(".worktrees/inv-two-seam*")), "non-vacuity: the coordination worktree must exist"

    mission_creation._rollback_coordination_surface(
        mission_creation._CoordCreateRollbackContext(
            repo_root=repo,
            mission_slug_formatted=result.mission_slug,
            mid8=result.meta["mid8"],
            coordination_branch=coordination_branch,
            coordination_branch_created=True,
        )
    )

    assert _mission_branches(repo) == []
    assert list(repo.glob(".worktrees/inv-two-seam*")) == []


# ---------------------------------------------------------------------------
# 3. MISSION_ALREADY_EXISTS precedes the mint refusal
# ---------------------------------------------------------------------------


def test_inv3_mission_already_exists_precedes_dirty_mint_refusal(tmp_path: Path) -> None:
    """On protected ``main`` with a dirty checkout, a re-create of a live mission raises
    ``MissionAlreadyExistsError`` -- never the dirty-mint ``MissionCreationError``."""
    repo = _init_repo_with_target(tmp_path, target_branch=_MAIN, protected_primary=True)
    prior = repo / _SPECS / "inv-three-ABCDEFGH"
    prior.mkdir(parents=True)
    (prior / "meta.json").write_text(json.dumps({"mission_type": "software-dev", "mid8": "ABCDEFGH"}), encoding="utf-8")
    (prior / "spec.md").write_text("# Live prior\n\nSubstantive content.\n", encoding="utf-8")
    # commit the prior's spec.md -- a genesis-only prior is abandoned.
    _git(repo, "add", f"{_SPECS}/inv-three-ABCDEFGH")
    _git(repo, "commit", "-m", "chore(fixture): live prior mission")
    (repo / "operator-notes.txt").write_text("unrelated dirt\n", encoding="utf-8")

    with pytest.raises(MissionCreationError) as excinfo:
        _create(repo, "inv-three", topology=MissionTopology.SINGLE_BRANCH, target_branch=_MAIN)

    assert type(excinfo.value) is MissionAlreadyExistsError
    assert excinfo.value.error_code == "MISSION_ALREADY_EXISTS"
    assert "uncommitted changes" not in str(excinfo.value)

    # Non-vacuity: without the prior, the very same dirt does trip the mint refusal.
    _git(repo, "rm", "-r", "-q", f"{_SPECS}/inv-three-ABCDEFGH")
    _git(repo, "commit", "-q", "-m", "chore(fixture): drop prior")
    with pytest.raises(MissionCreationError, match="uncommitted changes outside this mission's own scaffold: operator-notes.txt"):
        _create(repo, "inv-three", topology=MissionTopology.SINGLE_BRANCH, target_branch=_MAIN)


# ---------------------------------------------------------------------------
# 4. Scaffold commit lands on the minted branch
# ---------------------------------------------------------------------------


def test_inv4_scaffold_commit_lands_on_minted_branch_not_target(tmp_path: Path) -> None:
    repo = _init_repo_with_target(tmp_path, target_branch=_MAIN, protected_primary=True)
    main_tip = _git(repo, "rev-parse", _MAIN)

    result = _create(repo, "inv-four", topology=MissionTopology.SINGLE_BRANCH, target_branch=_MAIN)

    minted = result.meta["mission_branch"]
    assert isinstance(minted, str) and minted.startswith("kitty/mission-inv-four-")
    scaffold_commit = _git(repo, "log", "-1", "--format=%H", minted, "--", f"{_SPECS}/{result.mission_slug}/meta.json")
    assert scaffold_commit, "the scaffold commit must exist on the minted branch"
    assert _git_rc(repo, "merge-base", "--is-ancestor", scaffold_commit, minted) == 0
    assert _git_rc(repo, "merge-base", "--is-ancestor", scaffold_commit, _MAIN) != 0
    assert _git(repo, "rev-parse", _MAIN) == main_tip
    assert result.feature_dir / "meta.json" not in result.uncommitted_files


# ---------------------------------------------------------------------------
# 5. #846 commit boundary at create
# ---------------------------------------------------------------------------


def test_inv5_create_commit_boundary_spec_untracked_tasks_readme_committed(tmp_path: Path) -> None:
    """Observed boundary (probe-confirmed): ``spec.md`` stays untracked (#846, the agent commits
    it from specify) while ``tasks/README.md`` IS part of the scaffold commit.

    Note: the invariant list in the decomposition spec says "The tasks README is not committed at create"; the
    code commits it (it is in ``scaffold_paths``). This test pins the observed state.
    """
    repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)

    result = _create(repo, "inv-five", topology=MissionTopology.SINGLE_BRANCH, target_branch=_TOPIC)

    rel = f"{_SPECS}/{result.mission_slug}"
    committed = set(_git(repo, "ls-tree", "-r", "--name-only", "HEAD", "--", rel).splitlines())
    assert f"{rel}/tasks/README.md" in committed
    assert f"{rel}/meta.json" in committed
    assert f"{rel}/spec.md" not in committed
    assert f"{rel}/spec.md" in _untracked(repo)
    assert result.uncommitted_files == [result.feature_dir / "spec.md"]


# ---------------------------------------------------------------------------
# 6. Meta commit after origin binding
# ---------------------------------------------------------------------------


class _CommitStateProbingConsumer:
    """Pending-origin consumer that records the committed ``meta.json`` when it is called."""

    def __init__(self, repo: Path) -> None:
        self.repo = repo
        self.committed_meta_at_call: list[dict[str, Any] | None] = []

    def __call__(self, repo_root: Path, feature_dir: Path, meta: dict[str, Any]) -> tuple[bool, bool, str | None, dict[str, Any]]:
        rel = feature_dir.relative_to(self.repo).as_posix()
        shown = subprocess.run(
            ["git", "-C", str(self.repo), "show", f"HEAD:{rel}/meta.json"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.committed_meta_at_call.append(json.loads(shown.stdout) if shown.returncode == 0 else None)
        bound = dict(meta)
        bound["origin_ticket"] = {"provider": "test", "key": "invariant-6"}
        write_meta(feature_dir, bound)
        return True, True, None, bound


@pytest.fixture
def probing_consumer(tmp_path: Path) -> Iterator[_CommitStateProbingConsumer]:
    previous = origin_adapters._origin_consumer
    consumer = _CommitStateProbingConsumer(tmp_path / "repo")
    origin_adapters.register_pending_origin_consumer(consumer)
    try:
        yield consumer
    finally:
        if previous is None:
            origin_adapters.reset_origin_consumer()
        else:
            origin_adapters.register_pending_origin_consumer(previous)


def test_inv6_origin_binding_meta_commit_follows_the_binding(tmp_path: Path, probing_consumer: _CommitStateProbingConsumer) -> None:
    """The consumer runs after the scaffold commit and before the origin-ticket meta commit:
    at call time HEAD's ``meta.json`` has no binding; afterwards HEAD carries it, clean."""
    repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)
    assert probing_consumer.repo == repo

    result = _create(repo, "inv-six", topology=MissionTopology.SINGLE_BRANCH, target_branch=_TOPIC)

    assert len(probing_consumer.committed_meta_at_call) == 1
    at_call = probing_consumer.committed_meta_at_call[0]
    assert at_call is not None, "the scaffold commit (with meta.json) must precede the origin binding"
    assert "origin_ticket" not in at_call, "the binding must not be committed before the consumer ran"
    rel_meta = f"{_SPECS}/{result.mission_slug}/meta.json"
    head_meta = json.loads(_git(repo, "show", f"HEAD:{rel_meta}"))
    assert head_meta["origin_ticket"] == {"provider": "test", "key": "invariant-6"}
    assert _git(repo, "status", "--porcelain", "--", rel_meta) == "", "meta.json must not sit modified-uncommitted after binding"
    assert result.origin_binding_succeeded is True


# ---------------------------------------------------------------------------
# 7. mid8 derived once
# ---------------------------------------------------------------------------


def test_inv7_mid8_is_shared_by_meta_and_directory_name(tmp_path: Path) -> None:
    repo = _init_repo_with_target(tmp_path, target_branch=_TOPIC, protected_primary=True)

    result = _create(repo, "inv-seven", topology=MissionTopology.SINGLE_BRANCH, target_branch=_TOPIC)

    mission_id = result.meta["mission_id"]
    assert result.meta["mid8"] == mission_id[:8]
    assert result.feature_dir.name == f"inv-seven-{result.meta['mid8']}"
    assert result.mission_slug == result.feature_dir.name
    on_disk = json.loads((result.feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert on_disk["mid8"] == result.meta["mid8"]
