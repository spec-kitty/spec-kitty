"""#3571 (P0) -- lane-base-honoring regression suite.

An operator's ``spec-kitty implement --base <ref>`` was silently discarded on
coord-topology missions (the default): the CLI seam patched only
``lanes_manifest.mission_branch``, a field the topology-aware allocator never
reads on the coord path. This module proves the fix through the REAL
``implement --base`` seam (AC-1, C-003), the allocator directly (AC-2/AC-3,
NFR-003, FR-010), and the ``for_review`` gate (FR-011).

AC-1 is deliberately driven through ``implement(...)`` -- the Typer command
function -- rather than the manual ``_resolve_active_lanes_manifest ->
create_lane_workspace`` chain: on ``upstream/main`` ``create_lane_workspace``
has no ``base`` parameter, so a manual chain would TypeError (false-red) pre-fix
and, worse, could stay green post-fix while retaining the smuggle (the exact
false-negative this P0 exists to prevent). See spec.md C-003 / AC-1.
"""

from __future__ import annotations

import json
import subprocess
from contextlib import AbstractContextManager
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from kernel.clock import now_utc_iso

from specify_cli.coordination.surface_resolver import ResolvedStatusSurface
from specify_cli.core.vcs import VCSBackend
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.status import Lane
from specify_cli.status.work_package_lifecycle import WorkPackageStartResult
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.implement_support import create_lane_workspace
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.workspace.context import ResolvedWorkspace

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

# C-003 / AC-1: ``UnhonorableBaseError`` does not exist pre-fix (unlike
# ``allocate_lane_worktree``, which does -- only its ``base`` kwarg is new).
# ``UnhonorableBaseError`` is therefore imported LOCALLY inside each test that
# needs it (not at module scope), so this module stays collectible against
# unfixed ``upstream/main``: the mandatory AC-1 red-first proof then fails on
# WRONG ANCESTRY (symptom-red) at test-body execution, never on a
# collection-time ImportError (false-red) that would abort every test in the
# file, including AC-1's.


# ---------------------------------------------------------------------------
# Shared git helpers
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _git_out(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo, capture_output=True,
    )
    return result.returncode == 0


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")


# ---------------------------------------------------------------------------
# Mission-content constants shared by the direct-allocator tests
# ---------------------------------------------------------------------------

MISSION_SLUG = "lane-base-honoring-demo"
MISSION_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}"
LEGACY_MISSION_SLUG = "lane-base-honoring-legacy"
LEGACY_MISSION_BRANCH = f"kitty/mission-{LEGACY_MISSION_SLUG}"
WP_ID = "WP06"
EXPLICIT_BASE_BRANCH = "explicit-base"


def _make_manifest(
    *,
    mission_slug: str = MISSION_SLUG,
    mission_branch: str,
    lane_id: str = "lane-a",
    depends_on_lanes: tuple[str, ...] = (),
    planning_commit_sha: str | None = None,
) -> LanesManifest:
    return LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=MISSION_ID,
        mission_branch=mission_branch,
        target_branch="main",
        lanes=[ExecutionLane(
            lane_id=lane_id,
            wp_ids=(WP_ID,),
            write_scope=(),
            predicted_surfaces=(),
            depends_on_lanes=depends_on_lanes,
            parallel_group=0,
        )],
        computed_at=now_utc_iso(),
        computed_from="test",
        planning_commit_sha=planning_commit_sha,
    )


def _write_meta(feature_dir: Path, *, mission_slug: str, coordination_branch: str | None) -> None:
    meta: dict[str, object] = {
        "mission_id": MISSION_ID,
        "mission_slug": mission_slug,
        "target_branch": "main",
    }
    if coordination_branch is not None:
        meta["coordination_branch"] = coordination_branch
    (feature_dir / "meta.json").write_text(json.dumps(meta))


@pytest.fixture
def coord_repo_with_divergent_base(tmp_path: Path) -> Path:
    """Coord-topology repo: ``coordination_branch`` descends from unrelated
    commit ``U``; a divergent ``explicit-base`` branch ``B`` does NOT contain
    ``U`` (mirrors the mission's AC-1 Given/When/Then and the live repro).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    manifest = _make_manifest(mission_branch=f"kitty/mission-{MISSION_SLUG}")
    write_lanes_json(feature_dir, manifest)
    _write_meta(feature_dir, mission_slug=MISSION_SLUG, coordination_branch=COORD_BRANCH)
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / f"{WP_ID}-task.md").write_text(
        f"---\nwork_package_id: {WP_ID}\ndependencies: []\n---\n# {WP_ID}\n"
    )
    seed_event = {
        "actor": "finalize-tasks",
        "at": "2026-08-21T10:00:00.000000+00:00",
        "event_id": f"01JT00000000000000000{WP_ID}",
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "genesis",
        "mission_id": MISSION_ID,
        "mission_slug": MISSION_SLUG,
        "policy_metadata": None,
        "reason": "canonical bootstrap",
        "review_ref": None,
        "to_lane": "planned",
        "wp_id": WP_ID,
    }
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(seed_event, sort_keys=True) + "\n", encoding="utf-8",
    )
    (repo / "README.md").write_text("seed\n")

    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    seed_sha = _git_out(repo, "rev-parse", "HEAD")

    # U: unrelated pending work on top of the seed.
    (repo / "unrelated.txt").write_text("unrelated work\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "unrelated work (U)")
    u_sha = _git_out(repo, "rev-parse", "HEAD")

    # coordination_branch descends from U (fidelity gate: real coord topology).
    _git(repo, "branch", COORD_BRANCH, u_sha)

    # explicit-base (B) diverges from the seed -- does NOT contain U.
    _git(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    _git(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "base-work.txt").write_text("explicit base work\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "explicit base work (B)")
    _git(repo, "checkout", "-q", "main")

    return repo


@pytest.fixture
def legacy_repo(tmp_path: Path) -> Path:
    """No ``coordination_branch`` -- legacy topology (AC-2)."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    spec_dir = repo / "kitty-specs" / LEGACY_MISSION_SLUG
    spec_dir.mkdir(parents=True)
    _write_meta(spec_dir, mission_slug=LEGACY_MISSION_SLUG, coordination_branch=None)
    (spec_dir / "spec.md").write_text("# spec\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    seed_sha = _git_out(repo, "rev-parse", "HEAD")

    _git(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    _git(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "legacy-base-work.txt").write_text("legacy base work\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "legacy base work")
    _git(repo, "checkout", "-q", "main")

    return repo


# ---------------------------------------------------------------------------
# AC-1 -- red-first, through the REAL implement(--base) seam (C-003)
# ---------------------------------------------------------------------------


def _run_implement_via_seam(
    repo: Path,
    feature_dir: Path,
    *,
    base: str | None,
    wp_id: str = WP_ID,
    mission_slug: str = MISSION_SLUG,
    capture_console: list[str] | None = None,
) -> None:
    """Drive the real ``implement(...)`` Typer command function.

    Mirrors ``tests/cli/commands/test_implement_base_flag.py``'s
    established mocking breadth for the CLI-plumbing concerns orthogonal to
    base-honoring (feature/context detection, planning-artifact commit,
    charter preflight, SaaS/sync fan-out). Crucially this does NOT mock
    ``create_lane_workspace`` -- the real allocator runs, which is the whole
    point of the seam-level proof (C-003).
    """
    from specify_cli.cli.commands.implement import implement
    import specify_cli.cli.commands.implement as impl_mod

    ctx_managers: list[AbstractContextManager[object]] = [
        patch("specify_cli.cli.commands.implement.find_repo_root", return_value=repo),
        patch("specify_cli.cli.commands.implement.detect_feature_context",
              return_value=("1", mission_slug)),
        patch("specify_cli.cli.commands.implement.find_wp_file",
              return_value=feature_dir / "tasks" / f"{wp_id}-task.md"),
        patch("specify_cli.core.dependency_graph.parse_wp_dependencies", return_value=[]),
        patch("specify_cli.cli.commands.implement.resolve_feature_target_branch",
              return_value="main"),
        patch("specify_cli.cli.commands.implement._ensure_planning_artifacts_committed_git"),
        patch("specify_cli.cli.commands.implement._ensure_vcs_in_meta", return_value=VCSBackend.GIT),
        patch("specify_cli.cli.commands.implement._resolve_placement_ref", return_value=None),
        patch(
            "specify_cli.coordination.surface_resolver.resolve_status_surface_with_anchor",
            return_value=ResolvedStatusSurface(
                surface_path=feature_dir / "status.events.jsonl", primary_anchor=feature_dir,
            ),
        ),
        patch(
            "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
            lambda *_args, **_kwargs: None,
        ),
        # #3571 test isolation: the status-transition write side
        # (start_implementation_status -> emit_status_transition_transactional)
        # resolves its OWN coord/primary status surface independently of the
        # ``resolve_status_surface_with_anchor`` patch above (that binding is
        # local to a different module) and would try to materialize a REAL
        # coordination worktree -- orthogonal to what this suite tests
        # (base-honoring in lane ALLOCATION, not status transitions). Faked
        # as a no-op ("already there") result so ``_commit_wp_claim_status``
        # skips (status_changed=False) without touching git.
        patch(
            "specify_cli.cli.commands.implement.start_implementation_status",
            return_value=WorkPackageStartResult(
                wp_id=wp_id, from_lane=Lane.IN_PROGRESS, to_lane=Lane.IN_PROGRESS,
                actor="test", events=(), no_op=True,
            ),
        ),
        patch("specify_cli.status.emit._saas_fan_out"),
        patch("specify_cli.core.agent_config.get_auto_commit_default", return_value=False),
        patch("specify_cli.core.context_validation.require_main_repo", lambda f: f),
    ]

    if capture_console is not None:
        original_print = impl_mod.console.print

        def _capturing_print(*args: object, **kwargs: object) -> None:
            capture_console.append(str(args[0]) if args else "")
            original_print(*args, **kwargs)

        ctx_managers.append(
            patch.object(impl_mod.console, "print", side_effect=_capturing_print)
        )

    import contextlib
    from contextlib import ExitStack

    with ExitStack() as stack:
        for ctx in ctx_managers:
            stack.enter_context(ctx)
        with contextlib.suppress(typer.Exit, SystemExit):
            implement(
                wp_id=wp_id,
                mission=mission_slug,
                auto_commit=False,
                json_output=False,
                recover=False,
                base=base,
            )


class TestAC1SeamLevelRedFirst:
    """AC-1 / FR-001 / FR-002 / C-003: base threads through the real seam."""

    def test_explicit_base_replaces_coord_parent_on_no_dep_lane(
        self, coord_repo_with_divergent_base: Path,
    ) -> None:
        repo = coord_repo_with_divergent_base
        feature_dir = repo / "kitty-specs" / MISSION_SLUG

        # Fixture-fidelity gate (post-plan reviewer): the fixture must
        # genuinely carry coordination topology BEFORE we drive the seam,
        # so a wrong-ancestry RED is provably about base-honoring, not a
        # degraded-to-legacy fixture.
        assert json.loads((feature_dir / "meta.json").read_text())["coordination_branch"] == COORD_BRANCH
        u_sha = _git_out(repo, "rev-parse", COORD_BRANCH)
        assert not _is_ancestor(repo, EXPLICIT_BASE_BRANCH, "main"), (
            "sanity: explicit-base must not already be reachable from main"
        )

        _run_implement_via_seam(repo, feature_dir, base=EXPLICIT_BASE_BRANCH)

        lane_branch = f"kitty/mission-{MISSION_SLUG}-lane-a"
        assert _is_ancestor(repo, EXPLICIT_BASE_BRANCH, lane_branch), (
            f"lane {lane_branch} must descend from the supplied --base "
            f"{EXPLICIT_BASE_BRANCH!r} (FR-001)"
        )
        assert not _is_ancestor(repo, u_sha, lane_branch), (
            "lane must NOT inherit ancestry reachable only through "
            "coordination_branch (FR-002) -- the #3571 unrelated-work leak"
        )


# ---------------------------------------------------------------------------
# NFR-003 -- positive composition: base + recorded planning commit
# ---------------------------------------------------------------------------


def test_nfr003_base_composes_with_recorded_planning_commit(tmp_path: Path) -> None:
    """A no-dep lane's recorded planning commit merges ON TOP of --base, not
    in place of it: both are ancestors of the resulting lane."""
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, mission_slug=MISSION_SLUG, coordination_branch=COORD_BRANCH)
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    seed_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "branch", COORD_BRANCH, seed_sha)

    # base B shares the seed as a common ancestor with the planning commit.
    _git(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    _git(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "base.txt").write_text("base\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "base work")
    _git(repo, "checkout", "-q", "main")

    _git(repo, "checkout", "-q", "-b", "planning-tmp", seed_sha)
    (repo / "planning.txt").write_text("planning artifact\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "planning commit")
    planning_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "planning-tmp")

    manifest = _make_manifest(
        mission_branch=f"kitty/mission-{MISSION_SLUG}", planning_commit_sha=planning_sha,
    )
    worktree_path, branch = allocate_lane_worktree(
        repo_root=repo, mission_slug=MISSION_SLUG, wp_id=WP_ID,
        lanes_manifest=manifest, base=EXPLICIT_BASE_BRANCH,
    )

    assert worktree_path.exists()
    assert _is_ancestor(repo, EXPLICIT_BASE_BRANCH, branch)
    assert _is_ancestor(repo, planning_sha, branch)


def test_fr011_fresh_divergent_base_lane_with_planning_commit_is_not_reuse(
    tmp_path: Path,
) -> None:
    """#3571 follow-up: a FRESH coord lane rooted on a divergent ``--base`` with a
    recorded planning commit merged on top must be treated as a fresh creation
    (``is_reuse`` False) so its ``base_commit`` provenance is written.

    Regression: the retired ``_has_commits_beyond_base(honored_base)`` probe
    misdetected such a lane as *reuse* (the planning-commit merge is "commits
    beyond base"), which skipped the ``base_commit`` frontmatter write and left
    ``for_review_gate._recorded_honored_base`` with no context to read — silently
    defeating the honored-base review scope on exactly the divergent-``--base``
    lane it exists for. Structural reuse detection (worktree/branch
    pre-existence) is immune to base divergence.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, mission_slug=MISSION_SLUG, coordination_branch=COORD_BRANCH)
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    seed_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "branch", COORD_BRANCH, seed_sha)

    # Divergent base B off the seed (does NOT contain the planning commit).
    _git(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    _git(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "base.txt").write_text("base work\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "explicit base work (B)")
    _git(repo, "checkout", "-q", "main")

    # Planning commit off the seed — diverges from B, so its merge onto a
    # B-rooted lane creates "commits beyond B" (the misdetection trigger).
    _git(repo, "checkout", "-q", "-b", "planning-tmp", seed_sha)
    (repo / "planning.txt").write_text("planning artifact\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "planning commit")
    planning_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "planning-tmp")

    manifest = _make_manifest(
        mission_branch=f"kitty/mission-{MISSION_SLUG}", planning_commit_sha=planning_sha,
    )

    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    wp_file = tasks_dir / f"{WP_ID}-task.md"
    wp_file.write_text(
        f"---\nwork_package_id: {WP_ID}\ndependencies: []\n---\n# {WP_ID}\n"
    )

    resolved = ResolvedWorkspace(
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        execution_mode="code_change",
        mode_source="frontmatter",
        resolution_kind="lane_workspace",
        workspace_name=f"{MISSION_SLUG}-lane-a",
        worktree_path=repo / ".worktrees" / f"{MISSION_SLUG}-lane-a",
        branch_name=None,
        lane_id="lane-a",
        lane_wp_ids=[WP_ID],
    )

    result = create_lane_workspace(
        repo_root=repo,
        mission_slug=MISSION_SLUG,
        wp_id=WP_ID,
        wp_file=wp_file,
        resolved_workspace=resolved,
        lanes_manifest=manifest,
        declared_deps=[],
        vcs_backend_value="git",
        base=EXPLICIT_BASE_BRANCH,
    )

    # A freshly-created lane must NOT be misdetected as reuse.
    assert result.is_reuse is False
    # ... so the honored-base provenance IS written to the WP frontmatter.
    frontmatter = wp_file.read_text()
    assert "base_commit:" in frontmatter
    base_b_sha = _git_out(repo, "rev-parse", EXPLICIT_BASE_BRANCH)
    assert base_b_sha in frontmatter


# ---------------------------------------------------------------------------
# FR-010 -- detached-base pre-create atomicity guard
# ---------------------------------------------------------------------------


def test_fr010_detached_base_fails_loud_pre_create_no_residual(tmp_path: Path) -> None:
    """A base sharing NO common ancestor with the recorded planning commit
    hard-errors BEFORE any worktree/branch is created, and an immediate retry
    does not hit the FL1 reuse guard (atomicity)."""
    from specify_cli.lanes.worktree_allocator import UnhonorableBaseError

    repo = tmp_path / "repo"
    _init_repo(repo)
    feature_dir = repo / "kitty-specs" / MISSION_SLUG
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, mission_slug=MISSION_SLUG, coordination_branch=COORD_BRANCH)
    (repo / "README.md").write_text("seed\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")
    seed_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "branch", COORD_BRANCH, seed_sha)

    # base branch: a genuinely UNRELATED root (--root commit, no shared history).
    _git(repo, "checkout", "-q", "--orphan", "detached-root")
    (repo / "detached.txt").write_text("detached root\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "detached root commit")
    detached_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "branch", "-f", EXPLICIT_BASE_BRANCH, detached_sha)
    _git(repo, "checkout", "-q", "main")

    # planning commit lives on the seed's history -- unrelated to the detached base.
    _git(repo, "checkout", "-q", "-b", "planning-tmp", seed_sha)
    (repo / "planning.txt").write_text("planning artifact\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "planning commit")
    planning_sha = _git_out(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "planning-tmp")

    manifest = _make_manifest(
        mission_branch=f"kitty/mission-{MISSION_SLUG}", planning_commit_sha=planning_sha,
    )

    with pytest.raises(UnhonorableBaseError) as exc_info:
        allocate_lane_worktree(
            repo_root=repo, mission_slug=MISSION_SLUG, wp_id=WP_ID,
            lanes_manifest=manifest, base=EXPLICIT_BASE_BRANCH,
        )
    assert exc_info.value.route == "detached_base"
    assert exc_info.value.base == EXPLICIT_BASE_BRANCH

    worktree_path = repo / ".worktrees" / f"{MISSION_SLUG}-lane-a"
    lane_branch = f"kitty/mission-{MISSION_SLUG}-lane-a"
    assert not worktree_path.exists(), "no residual worktree after a pre-create fail-loud"
    result = subprocess.run(
        ["git", "rev-parse", "--verify", lane_branch],
        cwd=repo, capture_output=True,
    )
    assert result.returncode != 0, "no residual branch after a pre-create fail-loud"

    # Immediate retry must fail the SAME way (detached_base), not FL1 (reuse) --
    # proves nothing was half-created that would wedge a retry.
    with pytest.raises(UnhonorableBaseError) as retry_exc_info:
        allocate_lane_worktree(
            repo_root=repo, mission_slug=MISSION_SLUG, wp_id=WP_ID,
            lanes_manifest=manifest, base=EXPLICIT_BASE_BRANCH,
        )
    assert retry_exc_info.value.route == "detached_base"


# ---------------------------------------------------------------------------
# AC-2 -- legacy route unbroken (FR-006 / C-005)
# ---------------------------------------------------------------------------


def test_ac2_legacy_base_threads_through_allocator(legacy_repo: Path) -> None:
    repo = legacy_repo
    manifest = _make_manifest(
        mission_slug=LEGACY_MISSION_SLUG,
        mission_branch=LEGACY_MISSION_BRANCH,
    )
    worktree_path, branch = allocate_lane_worktree(
        repo_root=repo, mission_slug=LEGACY_MISSION_SLUG, wp_id=WP_ID,
        lanes_manifest=manifest, base=EXPLICIT_BASE_BRANCH,
    )
    assert worktree_path.exists()
    assert _is_ancestor(repo, EXPLICIT_BASE_BRANCH, branch)


def test_ac2_legacy_base_none_reproduces_prior_behavior(legacy_repo: Path) -> None:
    """base=None on the legacy route is byte-identical to pre-fix (C-005)."""
    repo = legacy_repo
    manifest = _make_manifest(
        mission_slug=LEGACY_MISSION_SLUG,
        mission_branch=LEGACY_MISSION_BRANCH,
    )
    worktree_path, branch = allocate_lane_worktree(
        repo_root=repo, mission_slug=LEGACY_MISSION_SLUG, wp_id=WP_ID,
        lanes_manifest=manifest,
    )
    assert worktree_path.exists()
    # No base supplied -> parents on the mission_branch field, as before.
    result = subprocess.run(
        ["git", "rev-parse", "--verify", LEGACY_MISSION_BRANCH],
        cwd=repo, capture_output=True,
    )
    assert result.returncode == 0
    assert _is_ancestor(repo, LEGACY_MISSION_BRANCH, branch)


# ---------------------------------------------------------------------------
# AC-3 -- hard-error on unhonorable routes (D2/D3), real state, no mocks
# ---------------------------------------------------------------------------


class TestAC3FailLoud:
    def test_reuse_with_base_fails_loud(self, coord_repo_with_divergent_base: Path) -> None:
        from specify_cli.lanes.worktree_allocator import UnhonorableBaseError

        repo = coord_repo_with_divergent_base
        manifest = _make_manifest(mission_branch=f"kitty/mission-{MISSION_SLUG}")

        # First allocation succeeds (no base) -- creates the lane worktree.
        allocate_lane_worktree(
            repo_root=repo, mission_slug=MISSION_SLUG, wp_id=WP_ID, lanes_manifest=manifest,
        )

        with pytest.raises(UnhonorableBaseError) as exc_info:
            allocate_lane_worktree(
                repo_root=repo, mission_slug=MISSION_SLUG, wp_id=WP_ID,
                lanes_manifest=manifest, base=EXPLICIT_BASE_BRANCH,
            )
        assert exc_info.value.route == "reuse"
        assert exc_info.value.wp_id == WP_ID
        assert exc_info.value.base == EXPLICIT_BASE_BRANCH

    def test_crash_recovery_with_base_fails_loud(self, coord_repo_with_divergent_base: Path) -> None:
        from specify_cli.lanes.worktree_allocator import UnhonorableBaseError

        repo = coord_repo_with_divergent_base
        manifest = _make_manifest(mission_branch=f"kitty/mission-{MISSION_SLUG}")

        worktree_path, _branch = allocate_lane_worktree(
            repo_root=repo, mission_slug=MISSION_SLUG, wp_id=WP_ID, lanes_manifest=manifest,
        )
        # Simulate a crash: worktree directory gone, branch survives.
        import shutil

        shutil.rmtree(worktree_path)
        _git(repo, "worktree", "prune")

        with pytest.raises(UnhonorableBaseError) as exc_info:
            allocate_lane_worktree(
                repo_root=repo, mission_slug=MISSION_SLUG, wp_id=WP_ID,
                lanes_manifest=manifest, base=EXPLICIT_BASE_BRANCH,
            )
        assert exc_info.value.route == "crash_recovery"

    def test_dependency_lane_with_base_fails_loud(self, coord_repo_with_divergent_base: Path) -> None:
        from specify_cli.lanes.worktree_allocator import UnhonorableBaseError

        repo = coord_repo_with_divergent_base
        manifest = _make_manifest(
            mission_branch=f"kitty/mission-{MISSION_SLUG}",
            depends_on_lanes=("lane-b",),
        )
        with pytest.raises(UnhonorableBaseError) as exc_info:
            allocate_lane_worktree(
                repo_root=repo, mission_slug=MISSION_SLUG, wp_id=WP_ID,
                lanes_manifest=manifest, base=EXPLICIT_BASE_BRANCH,
            )
        assert exc_info.value.route == "dependency_lane"

    def test_no_dependency_lane_with_base_succeeds(self, coord_repo_with_divergent_base: Path) -> None:
        """Sibling-negative control: an EMPTY depends_on_lanes must NOT trip
        the FR-009 guard (only a non-empty dependency set is unhonorable)."""
        repo = coord_repo_with_divergent_base
        manifest = _make_manifest(mission_branch=f"kitty/mission-{MISSION_SLUG}")
        worktree_path, branch = allocate_lane_worktree(
            repo_root=repo, mission_slug=MISSION_SLUG, wp_id=WP_ID,
            lanes_manifest=manifest, base=EXPLICIT_BASE_BRANCH,
        )
        assert worktree_path.exists()
        assert _is_ancestor(repo, EXPLICIT_BASE_BRANCH, branch)


# ---------------------------------------------------------------------------
# UnhonorableBaseError -- typed-error unit coverage
# ---------------------------------------------------------------------------


def test_unhonorable_base_error_to_dict_carries_route_wp_id_base() -> None:
    from specify_cli.lanes.worktree_allocator import UnhonorableBaseError

    exc = UnhonorableBaseError(route="reuse", wp_id="WP06", base="op/elu-detached-forward")
    payload = exc.to_dict()
    assert payload["error_code"] == "UNHONORABLE_BASE"
    assert payload["route"] == "reuse"
    assert payload["wp_id"] == "WP06"
    assert payload["base"] == "op/elu-detached-forward"
    assert "WP06" in str(exc)
    assert "op/elu-detached-forward" in str(exc)


# ---------------------------------------------------------------------------
# AC-4 -- success line present/absent, both directions (real entry, no mock)
# ---------------------------------------------------------------------------


class TestAC4SuccessLineBothDirections:
    _SUCCESS_PREFIX = "Using explicit base ref:"

    def test_present_on_honored_no_dep_fresh_create(self, coord_repo_with_divergent_base: Path) -> None:
        repo = coord_repo_with_divergent_base
        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        captured: list[str] = []

        _run_implement_via_seam(
            repo, feature_dir, base=EXPLICIT_BASE_BRANCH, capture_console=captured,
        )

        assert any(self._SUCCESS_PREFIX in line and EXPLICIT_BASE_BRANCH in line for line in captured), (
            f"expected the success line in captured output: {captured!r}"
        )

    def test_absent_on_base_none(self, coord_repo_with_divergent_base: Path) -> None:
        repo = coord_repo_with_divergent_base
        feature_dir = repo / "kitty-specs" / MISSION_SLUG
        captured: list[str] = []

        _run_implement_via_seam(repo, feature_dir, base=None, capture_console=captured)

        # Positive control: some other tracker output must have been
        # captured, or an empty capture would vacuously pass the ABSENT
        # assertion below.
        assert captured, "positive control failed: nothing was captured at all"
        assert not any(self._SUCCESS_PREFIX in line for line in captured), (
            f"success line must not print when base=None: {captured!r}"
        )

    def test_absent_on_error_path(self, coord_repo_with_divergent_base: Path) -> None:
        repo = coord_repo_with_divergent_base
        feature_dir = repo / "kitty-specs" / MISSION_SLUG

        # First call (no base) creates the lane -- now a second call with an
        # explicit base hits the reuse fail-loud guard (FL1).
        _run_implement_via_seam(repo, feature_dir, base=None)

        captured: list[str] = []
        _run_implement_via_seam(
            repo, feature_dir, base=EXPLICIT_BASE_BRANCH, capture_console=captured,
        )

        assert captured, "positive control failed: nothing was captured at all"
        assert not any(self._SUCCESS_PREFIX in line for line in captured), (
            f"success line must not print on a fail-loud error path: {captured!r}"
        )


# ---------------------------------------------------------------------------
# FR-007 -- planning-lane --base ignored, with warning, no allocation effect
# ---------------------------------------------------------------------------


def test_fr007_planning_lane_base_ignored_with_warning(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    mission_slug = "lane-base-honoring-planning"
    feature_dir = repo / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    _write_meta(feature_dir, mission_slug=mission_slug, coordination_branch=None)

    from specify_cli.lanes.compute import PLANNING_LANE_ID

    manifest = LanesManifest(
        version=1, mission_slug=mission_slug, mission_id=MISSION_ID,
        mission_branch=f"kitty/mission-{mission_slug}", target_branch="main",
        lanes=[ExecutionLane(
            lane_id=PLANNING_LANE_ID, wp_ids=("WP01",), write_scope=(),
            predicted_surfaces=(), depends_on_lanes=(), parallel_group=0,
        )],
        computed_at=now_utc_iso(), computed_from="test",
    )
    write_lanes_json(feature_dir, manifest)
    wp_file = feature_dir / "tasks" / "WP01-task.md"
    wp_file.parent.mkdir(exist_ok=True)
    wp_file.write_text(
        "---\nwork_package_id: WP01\ndependencies: []\nexecution_mode: planning_artifact\n---\n# WP01\n"
    )
    seed_event = {
        "actor": "finalize-tasks", "at": "2026-08-21T10:00:00.000000+00:00",
        "event_id": "01JT00000000000000000WP01", "evidence": None,
        "execution_mode": "direct_repo", "force": False, "from_lane": "genesis",
        "mission_id": MISSION_ID, "mission_slug": mission_slug,
        "policy_metadata": None, "reason": "canonical bootstrap", "review_ref": None,
        "to_lane": "planned", "wp_id": "WP01",
    }
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(seed_event, sort_keys=True) + "\n", encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "seed")

    captured: list[str] = []
    _run_implement_via_seam(
        repo, feature_dir, base="main", wp_id="WP01", mission_slug=mission_slug,
        capture_console=captured,
    )

    assert any("ignored" in line and "--base" in line for line in captured), (
        f"expected the FR-007 'ignored' warning: {captured!r}"
    )
    assert not any("Using explicit base ref:" in line for line in captured)
    # No lane worktree was allocated for the planning lane.
    assert not (repo / ".worktrees" / f"{mission_slug}-{PLANNING_LANE_ID}").exists()


# ---------------------------------------------------------------------------
# NFR-004 -- orchestrator-api envelope carries the machine-readable error_code
# ---------------------------------------------------------------------------


def test_nfr004_orchestrator_envelope_carries_unhonorable_base_error_code(tmp_path: Path) -> None:
    """Defensive/synthetic (per plan.md): the orchestrator passes base=None
    (inert), so the raise is mock-injected to prove the envelope wiring."""
    from specify_cli.lanes.worktree_allocator import UnhonorableBaseError
    from specify_cli.orchestrator_api import commands as orch_commands

    captured_envelopes: list[dict[str, object]] = []

    def _fake_allocate(**_kwargs: object) -> tuple[Path, str]:
        raise UnhonorableBaseError(route="reuse", wp_id="WP06", base="some-ref")

    with (
        patch("specify_cli.lanes.worktree_allocator.allocate_lane_worktree", side_effect=_fake_allocate),
        patch.object(orch_commands, "_emit", side_effect=lambda env: captured_envelopes.append(env)),
        patch.object(
            orch_commands, "_lane_assignment_or_legacy",
            return_value=(
                _make_manifest(mission_branch=f"kitty/mission-{MISSION_SLUG}"),
                _make_manifest(mission_branch=f"kitty/mission-{MISSION_SLUG}").lanes[0],
            ),
        ),
        pytest.raises(typer.Exit),
    ):
        orch_commands._resolve_start_workspace(
            "implement-start", tmp_path, MISSION_SLUG, tmp_path / "kitty-specs" / MISSION_SLUG, WP_ID,
        )

    assert captured_envelopes, "expected the failure envelope to be emitted"
    envelope = captured_envelopes[0]
    assert envelope["error_code"] == "LANE_ALLOCATION_FAILED"
    data = envelope["data"]
    assert isinstance(data, dict)
    assert data["error_code"] == "UNHONORABLE_BASE"
    assert data["route"] == "reuse"
    assert data["wp_id"] == "WP06"
    assert data["base"] == "some-ref"
