"""SC-004 — Seam-B checkout-identity refusal for implement/review (WP03, #3128).

A LOCAL two-mission fixture (two missions, one git registry, distinct lanes; NO
``spec-kitty-saas`` dependency) proving the checkout-identity invariant at the WP
mutation chokepoint (``workspace.context.resolve_workspace_for_wp``, the single
point ``implement`` AND ``review`` funnel through):

* a WP-execution write invoked from a FOREIGN mission's lane worktree **refuses**
  (distinct :class:`CheckoutIdentityError`, exit ≠ 0, actionable);
* the mission's OWN lane worktree (and any subdir of it) **proceeds**;
* planning writes resolving to the primary checkout **proceed from any checkout**
  (R3, including a foreign lane);
* pure reads (``write_intent`` left ``False``) are **never** refused;
* the refusal exception does NOT subclass ``ActionContextError`` (FR-005 / MF-4).

A companion structural test pins the T016 write-intent marker table: the three
true write sites (compat ``implement`` CLI, canonical ``agent action implement``,
the review gate) carry ``write_intent=True``, while the audited read vehicle
(``resolve_planning_placement``) does not — guarding against both over-marking
(false-refused reads) and under-marking (#3128 stays live for review).
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from mission_runtime import CheckoutIdentityError
from mission_runtime.resolution import ActionContextError as _ActionContextError
from specify_cli.workspace.context import resolve_workspace_for_wp

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Local two-mission fixture (one registry, distinct lanes)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Mission:
    slug: str
    lane_worktree: Path  # the mission's own WP01 lane worktree (lane_workspace)


@dataclass(frozen=True)
class _Registry:
    repo: Path
    alpha: _Mission
    beta: _Mission


def _git(repo: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True, text=True
    )


def _write_mission(repo: Path, human: str, mid8: str) -> str:
    """Materialise one single-branch mission with a code_change WP01 (lane-a) and
    a planning_artifact WP00 (resolves to the primary checkout)."""
    slug = f"{human}-{mid8}"
    mission_id = mid8 + "0" * 18
    feature_dir = repo / "kitty-specs" / slug
    (feature_dir / "tasks").mkdir(parents=True)

    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": mission_id,
                "mission_slug": slug,
                "slug": slug,
                "mission_type": "software-dev",
                "target_branch": "main",
                "vcs": "git",
                "topology": "single_branch",
            }
        ),
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP01.md").write_text(
        "---\nwork_package_id: WP01\ntitle: code change\n"
        "execution_mode: code_change\nsubtasks: []\nowned_files:\n- src/x.py\n---\n# WP01\n",
        encoding="utf-8",
    )
    (feature_dir / "tasks" / "WP00.md").write_text(
        "---\nwork_package_id: WP00\ntitle: planning\n"
        "execution_mode: planning_artifact\nsubtasks: []\n---\n# WP00\n",
        encoding="utf-8",
    )
    (feature_dir / "lanes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mission_slug": slug,
                "mission_id": mission_id,
                "mission_branch": f"kitty/mission-{slug}",
                "target_branch": "main",
                "lanes": [
                    {
                        "lane_id": "lane-a",
                        "wp_ids": ["WP01"],
                        "write_scope": [],
                        "predicted_surfaces": [],
                        "depends_on_lanes": [],
                        "parallel_group": 0,
                    }
                ],
                "computed_at": "2026-06-26T00:00:00+00:00",
                "computed_from": "wp03-sc004-fixture",
                "planning_artifact_wps": ["WP00"],
            }
        ),
        encoding="utf-8",
    )
    return slug


@pytest.fixture()
def registry(tmp_path: Path) -> _Registry:
    """Two missions (alpha, beta) sharing one git repo, each with a distinct lane."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True, text=True
    )
    _git(repo, "config", "user.email", "wp03@spec-kitty.test")
    _git(repo, "config", "user.name", "WP03 Fixture")
    _git(repo, "config", "commit.gpgsign", "false")

    alpha_slug = _write_mission(repo, "alpha", "01AAAAAA")
    beta_slug = _write_mission(repo, "beta", "01BBBBBB")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init: two-mission registry")

    # Resolve each mission's OWN lane worktree path and materialise it on disk so
    # a checkout-cwd is a real directory (the path may not exist until implement
    # allocates it; the fixture creates it to model an agent working inside it).
    alpha_ws = resolve_workspace_for_wp(repo, alpha_slug, "WP01")
    beta_ws = resolve_workspace_for_wp(repo, beta_slug, "WP01")
    assert alpha_ws.resolution_kind == "lane_workspace"
    assert beta_ws.resolution_kind == "lane_workspace"
    assert alpha_ws.worktree_path != beta_ws.worktree_path
    alpha_ws.worktree_path.mkdir(parents=True, exist_ok=True)
    beta_ws.worktree_path.mkdir(parents=True, exist_ok=True)

    return _Registry(
        repo=repo,
        alpha=_Mission(alpha_slug, alpha_ws.worktree_path),
        beta=_Mission(beta_slug, beta_ws.worktree_path),
    )


# ---------------------------------------------------------------------------
# SC-004 behavioural cases
# ---------------------------------------------------------------------------


def test_foreign_lane_wp_write_refuses(registry: _Registry) -> None:
    """A WP-execution write for alpha, invoked from beta's lane worktree, refuses.

    Both ``implement`` and ``review`` reach this exact call
    (``resolve_workspace_for_wp(..., write_intent=True)``); a foreign lane is the
    canonical #3128 case.
    """
    with pytest.raises(CheckoutIdentityError) as exc_info:
        resolve_workspace_for_wp(
            registry.repo,
            registry.alpha.slug,
            "WP01",
            write_intent=True,
            current_cwd=registry.beta.lane_worktree,
        )
    message = str(exc_info.value)
    assert registry.alpha.slug in message
    assert "WP01" in message
    # Actionable: names both the offending checkout and the expected workspace.
    assert str(registry.beta.lane_worktree) in message
    assert str(registry.alpha.lane_worktree) in message


def test_foreign_lane_subdir_also_refuses(registry: _Registry) -> None:
    """The refusal holds from a NESTED subdir of the foreign lane (SC-008)."""
    subdir = registry.beta.lane_worktree / "src" / "deep"
    subdir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(CheckoutIdentityError):
        resolve_workspace_for_wp(
            registry.repo,
            registry.alpha.slug,
            "WP01",
            write_intent=True,
            current_cwd=subdir,
        )


def test_own_lane_proceeds(registry: _Registry) -> None:
    """From the mission's OWN lane worktree the write proceeds (no refusal)."""
    resolved = resolve_workspace_for_wp(
        registry.repo,
        registry.alpha.slug,
        "WP01",
        write_intent=True,
        current_cwd=registry.alpha.lane_worktree,
    )
    assert resolved.worktree_path == registry.alpha.lane_worktree


def test_own_lane_subdir_proceeds(registry: _Registry) -> None:
    """A subdir of the mission's own lane worktree also proceeds."""
    subdir = registry.alpha.lane_worktree / "src"
    subdir.mkdir(parents=True, exist_ok=True)
    resolved = resolve_workspace_for_wp(
        registry.repo,
        registry.alpha.slug,
        "WP01",
        write_intent=True,
        current_cwd=subdir,
    )
    assert resolved.resolution_kind == "lane_workspace"


def test_write_from_primary_root_proceeds(registry: _Registry) -> None:
    """`implement` allocating a lane from the repository root proceeds (legit)."""
    resolved = resolve_workspace_for_wp(
        registry.repo,
        registry.alpha.slug,
        "WP01",
        write_intent=True,
        current_cwd=registry.repo,
    )
    assert resolved.resolution_kind == "lane_workspace"


def test_planning_write_from_any_checkout_proceeds(registry: _Registry) -> None:
    """A planning write resolving to the primary checkout is never refused (R3).

    Even invoked from a FOREIGN lane worktree — planning is CWD-invariant and
    routes to primary, so the checkout-identity gate is exempt.
    """
    for cwd in (registry.repo, registry.beta.lane_worktree):
        resolved = resolve_workspace_for_wp(
            registry.repo,
            registry.alpha.slug,
            "WP00",
            write_intent=True,
            current_cwd=cwd,
        )
        assert resolved.resolution_kind == "repo_root"


def test_pure_read_from_foreign_checkout_never_refused(registry: _Registry) -> None:
    """A pure read (write_intent left False) is never refused, from any checkout."""
    resolved = resolve_workspace_for_wp(
        registry.repo,
        registry.alpha.slug,
        "WP01",
        current_cwd=registry.beta.lane_worktree,
    )
    assert resolved.worktree_path == registry.alpha.lane_worktree


def test_refusal_exception_is_not_action_context_error() -> None:
    """The refusal is a DISTINCT exception NOT subclassing ``ActionContextError``.

    So the audited ``except ActionContextError`` fallbacks cannot degrade it.
    """
    assert not issubclass(CheckoutIdentityError, _ActionContextError)
    # Also not a RuntimeError, so a narrowed ``except RuntimeError`` (the
    # record-analysis best-effort commit set) cannot swallow it either.
    assert not issubclass(CheckoutIdentityError, RuntimeError)
    # ``CheckoutIdentityError`` is surfaced on the package root
    # (``mission_runtime``) — the single sanctioned import surface. It is
    # deliberately NOT re-exported from ``mission_runtime.resolution`` (a second
    # unimported surface there is dead public API, test_no_dead_symbols).
    assert CheckoutIdentityError is not None


# ---------------------------------------------------------------------------
# T016 write-intent marker table — structural regression pin
# ---------------------------------------------------------------------------


def _src(rel: str) -> str:
    return (_REPO_ROOT / rel).read_text(encoding="utf-8")


def test_true_wp_write_sites_carry_write_intent() -> None:
    """All THREE true WP-write sites pass ``write_intent=True`` (no under-marking).

    Under-marking any of these leaves #3128 live for that entry point; the review
    gate in particular is the case an owned-files-only resolution.py approach
    would have missed.
    """
    implement_cli = _src("src/specify_cli/cli/commands/implement.py")
    agent_workflow = _src("src/specify_cli/cli/commands/agent/workflow.py")
    review_executor = _src("src/specify_cli/cli/commands/agent/workflow_executor.py")

    # compat `spec-kitty implement` CLI
    assert "resolve_workspace_for_wp(repo_root, mission_slug, wp_id, write_intent=True)" in implement_cli
    # canonical `agent action implement`
    assert (
        "resolve_workspace_for_wp(main_repo_root, mission_slug, normalized_wp_id, write_intent=True)"
        in agent_workflow
    )
    # review gate (pre-claim) — the review write path
    assert "write_intent=True" in review_executor
    assert "resolve_workspace_for_wp(" in review_executor


def test_read_vehicle_does_not_carry_write_intent() -> None:
    """The audited placement READ (``resolve_planning_placement``) must NOT mark write
    intent (no over-marking → reads stay unrefused)."""
    planning_commit = _src("src/specify_cli/coordination/planning_commit.py")
    # The resolve_action_context call inside resolve_planning_placement carries no
    # write_intent — it is a read-shaped placement resolve (marker table: NO).
    assert "write_intent" not in planning_commit
