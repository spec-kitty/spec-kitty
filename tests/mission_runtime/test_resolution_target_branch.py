"""Focused T017 unit tests — mode-correct target branch + mainline write guard.

WP04 (execution-state-canonical-surface-01KTG6P9), FR-007/FR-012, C-001/C-002.

These tests pin two invariants for the canonical resolver
:func:`mission_runtime.resolve_action_context`:

1. **Mode-correct ``target_branch``** — the resolver returns the mission's
   declared ``target_branch`` from ``meta.json`` (the planning mode records the
   coordination / direct-to-target / worktree target there). It never invents a
   branch and never silently rewrites it.

2. **Mainline write-target refusal (C-001/C-002)** — resolving a mission whose
   declared target is a mainline / protected branch is *not* itself an error
   (read paths for missions targeting ``main`` must keep working), but an
   unauthorized *write* to that branch is refused at the canonical write
   chokepoint :class:`specify_cli.coordination.policy.WorkflowMutationPolicy`.
   This test proves the two surfaces compose: the resolver surfaces the
   mode-correct branch, and the write guard refuses the unauthorized mainline
   write with the stable ``PROTECTED_BRANCH_REFUSED`` code — no silent fallback.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime import resolve_action_context
from specify_cli.coordination.policy import WorkflowMutationPolicy
from specify_cli.coordination.types import Allowed, GitChangeSet, Refused
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests._owned_fixtures import mint_test_fact

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_MISSION_SLUG = "t017-target-branch-mission"


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _change_set(repo: Path, destination_ref: str) -> GitChangeSet:
    """Build a minimal status-event-append change set for the write guard."""
    return GitChangeSet(
        destination_ref=destination_ref,
        repo_root=repo,
        worktree_root=repo,
        paths=(),
        message="status-event-append",
        operation="status-event-append",
    )


def _build_mission(repo_root: Path, *, target_branch: str) -> None:
    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": "01T017TARGETBRANCH00000001",
                "mission_slug": _MISSION_SLUG,
                "mission_type": "software-dev",
                "target_branch": target_branch,
                "friendly_name": "T017 target branch mission",
            }
        ),
        encoding="utf-8",
    )


def _write_review_wp(feature_dir: Path) -> None:
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01-review.md").write_text(
        "---\nwork_package_id: WP01\ntitle: Review target\ndependencies: []\nexecution_mode: planning_artifact\nowned_files: []\n---\n# WP01\n",
        encoding="utf-8",
    )


def _seed_for_review(feature_dir: Path) -> None:
    append_event(
        feature_dir,
        StatusEvent(
            event_id="test-WP01-for-review",
            mission_slug=feature_dir.name,
            wp_id="WP01",
            from_lane=Lane.IN_PROGRESS,
            to_lane=Lane.FOR_REVIEW,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Minimal git repo with a mission and a non-protected target branch."""
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.com")
    _git(r, "config", "user.name", "Test")
    _git(r, "config", "commit.gpgsign", "false")
    (r / ".kittify").mkdir()
    (r / ".kittify" / "config.yaml").write_text("agents:\n  available:\n    - claude\n", encoding="utf-8")
    return r


def test_resolver_returns_mode_correct_target_branch(repo: Path) -> None:
    """FR-012: the resolver surfaces the declared (mode-correct) target branch."""
    _build_mission(repo, target_branch="feat/execution-state-strangler")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")

    ctx = resolve_action_context(repo, action="tasks", feature=_MISSION_SLUG)

    assert ctx.target_branch == "feat/execution-state-strangler"


def test_review_context_resolves_wp_from_frontmatter(repo: Path) -> None:
    """Review resolution must use real split_frontmatter's 3-field contract."""
    _build_mission(repo, target_branch="main")
    feature_dir = repo / "kitty-specs" / _MISSION_SLUG
    _write_review_wp(feature_dir)
    _seed_for_review(feature_dir)

    ctx = resolve_action_context(repo, action="review", feature=_MISSION_SLUG, agent="codex")

    assert ctx.wp_id == "WP01"
    assert ctx.commands["workflow"].endswith("review WP01 --agent codex")


def test_resolver_does_not_invent_branch_for_mainline_target(repo: Path) -> None:
    """C-001: resolving a mainline-target mission is not silently rewritten.

    The resolver returns the declared target verbatim — it does not mask a
    mainline target by inventing a different branch. The *write* refusal is the
    job of the write-target guard (asserted below), not the read-path resolver.
    """
    _build_mission(repo, target_branch="main")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")

    ctx = resolve_action_context(repo, action="tasks", feature=_MISSION_SLUG)

    assert ctx.target_branch == "main"


def test_mainline_write_target_refused_without_authorization(repo: Path) -> None:
    """C-001/C-002: an unauthorized write to the mainline target is refused.

    The canonical write chokepoint refuses a bookkeeping commit aimed at a
    protected branch (``main``) with the stable ``PROTECTED_BRANCH_REFUSED``
    code — proving the mode-correct branch surfaced by the resolver cannot be
    used to silently write to mainline.
    """
    _build_mission(repo, target_branch="main")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")

    ctx = resolve_action_context(repo, action="tasks", feature=_MISSION_SLUG)
    assert ctx.target_branch == "main"

    change_set = _change_set(repo, ctx.target_branch)
    verdict = WorkflowMutationPolicy.assert_allowed(change_set)

    assert isinstance(verdict, Refused)
    assert verdict.error_code == "PROTECTED_BRANCH_REFUSED"


def test_non_mainline_write_target_allowed(repo: Path) -> None:
    """Anti-vacuity: a non-protected target branch is permitted to write.

    Without this control the refusal test could pass vacuously (e.g. if every
    ref were refused). A real, non-protected target must be allowed.
    """
    _build_mission(repo, target_branch="feat/execution-state-strangler")
    _git(repo, "checkout", "-q", "-b", "feat/execution-state-strangler")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")

    ctx = resolve_action_context(repo, action="tasks", feature=_MISSION_SLUG)

    change_set = _change_set(repo, ctx.target_branch)
    verdict = WorkflowMutationPolicy.assert_allowed(change_set)

    assert isinstance(verdict, Allowed)


# ---------------------------------------------------------------------------
# Owned-checkout target-branch threading (PR #3691 adversarial-review fixes)
#
# When a caller passes ``owned`` (a linked worktree that owns its own copy of
# the mission), the resolver takes the branch from the fact -- the single
# authority -- and never re-reads a caller-surface or primary ``meta.json``
# (the WP00/FR-004 bug class: silently dropping the mission's declared branch
# when a surface's meta lacks the field). WP18 re-pointed both tests from the
# retired bare ``effective_root=`` keyword to the fact.
# ---------------------------------------------------------------------------


def _add_caller_worktree(repo: Path, tmp_path: Path) -> Path:
    """Create a real linked worktree of ``repo`` and return its root."""
    caller = tmp_path / "caller-worktree"
    _git(repo, "worktree", "add", "-q", "-b", "caller-wt", str(caller), "main")
    return caller


def _caller_fact(repo: Path, caller: Path, *, target_branch: str):
    return mint_test_fact(
        repository_root=repo,
        owned_root=caller,
        mission_dir=caller / "kitty-specs" / _MISSION_SLUG,
        mission_slug=_MISSION_SLUG,
        write_branch=target_branch,
    )


def test_owned_fact_prefers_caller_surface_stored_target(repo: Path, tmp_path: Path) -> None:
    """The caller-owned worktree's stored target_branch wins when present."""
    _build_mission(repo, target_branch="feat/primary-stored")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    caller = _add_caller_worktree(repo, tmp_path)

    caller_meta = caller / "kitty-specs" / _MISSION_SLUG / "meta.json"
    meta = json.loads(caller_meta.read_text(encoding="utf-8"))
    meta["target_branch"] = "feat/caller-stored"
    caller_meta.write_text(json.dumps(meta), encoding="utf-8")

    ctx = resolve_action_context(
        repo,
        action="tasks",
        feature=_MISSION_SLUG,
        cwd=caller,
        owned=_caller_fact(repo, caller, target_branch="feat/caller-stored"),
    )

    assert ctx.target_branch == "feat/caller-stored"


def test_owned_fact_supplies_target_when_caller_meta_lacks_it(repo: Path, tmp_path: Path) -> None:
    """A caller surface whose meta lacks target_branch still yields the fact's.

    Regression: the first cut of the owned path degraded to the bare
    repo-default branch here, silently dropping the mission's stored
    ``target_branch`` (diff-coverage lines 2278/2280-2281).
    """
    _build_mission(repo, target_branch="feat/primary-stored")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "fixture")
    caller = _add_caller_worktree(repo, tmp_path)

    caller_meta = caller / "kitty-specs" / _MISSION_SLUG / "meta.json"
    meta = json.loads(caller_meta.read_text(encoding="utf-8"))
    del meta["target_branch"]
    caller_meta.write_text(json.dumps(meta), encoding="utf-8")

    ctx = resolve_action_context(
        repo,
        action="tasks",
        feature=_MISSION_SLUG,
        cwd=caller,
        owned=_caller_fact(repo, caller, target_branch="feat/primary-stored"),
    )

    assert ctx.target_branch == "feat/primary-stored"
