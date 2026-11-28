"""#7860 (WP03, FR-013): a status commit in the shared coordination worktree carries only status paths.

Before a default Mission lands, its planning work packages are worked in the coordination worktree,
the same checkout the CLI commits status into. A planning agent's uncommitted work there (a new file,
a modified tracked file, a staged change) must survive another work package's status transition
untouched: not committed with it, not unstaged, not reverted.

Ratchet through the production path: :func:`emit_status_transition_transactional`, the transactional
door ``move-task`` and ``orchestrator-api`` reach, which commits through ``BookkeepingTransaction``.
Real git, no mocks.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from specify_cli.coordination.status_transition import emit_status_transition_transactional
from specify_cli.status import TransitionRequest
from specify_cli.workspace.context import clear_workspace_resolution_caches
from tests._support.git_cli import git_out
from tests.lanes.test_planning_claim_base_7860 import PLANNING_WP, SIBLING_WP, SLUG, owned_path, settled_default_mission
from tests.status.conftest import seed_wp_to_planned

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_STATUS_PREFIXES = (f"kitty-specs/{SLUG}/status.",)


@pytest.fixture(autouse=True)
def _reset_caches() -> Iterator[None]:
    clear_workspace_resolution_caches()
    yield
    clear_workspace_resolution_caches()


def _porcelain(checkout: Path) -> set[str]:
    return set(git_out(checkout, "status", "--porcelain", "--untracked-files=all").splitlines())


def test_a_status_commit_in_the_coordination_worktree_leaves_planning_edits_alone(tmp_path: Path) -> None:
    mission = settled_default_mission(tmp_path)
    holder = mission.holder
    seed_wp_to_planned(mission.mission_dir, SIBLING_WP, slug=SLUG)
    git_out(holder, "add", "-A")
    git_out(holder, "commit", "-q", "-m", "finalize: seed WP02 planned")

    # WP01's planning agent, mid-work in the shared checkout: an untracked new file, a modified
    # tracked file and a staged change to a third file.
    untracked = holder / owned_path(PLANNING_WP)
    untracked.parent.mkdir(parents=True, exist_ok=True)
    untracked.write_text("new research\n", encoding="utf-8")
    (mission.mission_dir / "spec.md").write_text("# Spec\n\nedited, not staged\n", encoding="utf-8")
    (mission.mission_dir / "plan.md").write_text("# Plan\n\nedited and staged\n", encoding="utf-8")
    git_out(holder, "add", f"kitty-specs/{SLUG}/plan.md")
    before_head = git_out(holder, "rev-parse", "HEAD")
    staged_before = git_out(holder, "diff", "--cached", "--name-only")
    porcelain_before = _porcelain(holder)

    event = emit_status_transition_transactional(
        TransitionRequest(
            feature_dir=mission.mission_dir,
            mission_slug=SLUG,
            wp_id=SIBLING_WP,
            to_lane="claimed",
            actor="tester",
            repo_root=mission.repo,
        )
    )

    assert str(event.to_lane) == "claimed"
    new_commits = git_out(holder, "rev-list", f"{before_head}..HEAD").splitlines()
    assert new_commits, "the transition committed nothing in the coordination worktree"
    committed = {path for sha in new_commits for path in git_out(holder, "show", "--name-only", "--format=", sha).splitlines() if path}
    assert committed, new_commits
    assert all(path.startswith(_STATUS_PREFIXES) for path in committed), committed
    # The three edits are still there, uncommitted, and the staged one is still staged.
    assert untracked.read_text(encoding="utf-8") == "new research\n"
    assert "edited, not staged" in (mission.mission_dir / "spec.md").read_text(encoding="utf-8")
    assert "edited and staged" in (mission.mission_dir / "plan.md").read_text(encoding="utf-8")
    assert git_out(holder, "diff", "--cached", "--name-only") == staged_before == f"kitty-specs/{SLUG}/plan.md"
    assert _porcelain(holder) == porcelain_before
