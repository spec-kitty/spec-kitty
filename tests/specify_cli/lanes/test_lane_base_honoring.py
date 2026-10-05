"""#3571 (P0) -- lane-base-honoring regression suite.

An operator's ``spec-kitty implement --base <ref>`` was silently discarded on
coord-topology missions (the default): the CLI seam patched only
``lanes_manifest.mission_branch``, a field the topology-aware allocator never
reads on the coord path. This module proves the fix through the REAL
``implement --base`` seam (AC-1, C-003), the allocator directly (AC-2/AC-3,
NFR-003, FR-010), and the ``for_review`` gate (FR-011).

AC-1 is deliberately driven through the ``implement`` Typer command (the
function ``agent action implement`` calls) rather than a hand-assembled
``create_lane_workspace`` chain: a manual chain could stay green while the
command itself kept smuggling the base into a field the allocator never reads
(the exact false-negative this P0 exists to prevent). See spec.md C-003 / AC-1.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
from click.testing import Result
from kernel.clock import now_utc_iso
from mission_runtime import MissionArtifactKind, placement_seam

from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.implement_support import create_lane_workspace
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree
from specify_cli.workspace.context import ResolvedWorkspace
from tests._support.ansi import strip_ansi
from tests._support.git_cli import git_out
from tests.specify_cli.cli.commands._implement_fixtures import (
    activate_repo,
    build_mission,
    flat,
    implement_cli,
    init_repo,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Shared git helpers
# ---------------------------------------------------------------------------


def _flat(text: str) -> str:
    return flat(strip_ansi(text))


def _is_ancestor(repo: Path, ancestor: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", ancestor, descendant],
        cwd=repo, capture_output=True,
    )
    return result.returncode == 0


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    git_out(repo, "init", "-q", "-b", "main")
    git_out(repo, "config", "user.email", "t@example.com")
    git_out(repo, "config", "user.name", "Test")
    git_out(repo, "config", "commit.gpgsign", "false")


# ---------------------------------------------------------------------------
# Mission-content constants shared by the direct-allocator tests
# ---------------------------------------------------------------------------

MISSION_SLUG = "lane-base-honoring-demo"
MISSION_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
COORD_BRANCH = f"kitty/mission-{MISSION_SLUG}-{MISSION_ID[:8].lower()}"
LEGACY_MISSION_SLUG = "lane-base-honoring-legacy"
LEGACY_MISSION_BRANCH = f"kitty/mission-{LEGACY_MISSION_SLUG}"
WP_ID = "WP06"
EXPLICIT_BASE_BRANCH = "explicit-base"
#: The line ``implement --base`` prints once it honoured the operator's base (AC-4).
_SUCCESS_PREFIX = "Using explicit base ref:"


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

    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "seed")
    seed_sha = git_out(repo, "rev-parse", "HEAD")

    # U: unrelated pending work on top of the seed.
    (repo / "unrelated.txt").write_text("unrelated work\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "unrelated work (U)")
    u_sha = git_out(repo, "rev-parse", "HEAD")

    # coordination_branch descends from U (fidelity gate: real coord topology).
    git_out(repo, "branch", COORD_BRANCH, u_sha)

    # explicit-base (B) diverges from the seed -- does NOT contain U.
    git_out(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    git_out(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "base-work.txt").write_text("explicit base work\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "explicit base work (B)")
    git_out(repo, "checkout", "-q", "main")

    return repo


@pytest.fixture
def coord_mission_with_divergent_base(tmp_path: Path) -> Path:
    """The ``coord_repo_with_divergent_base`` shape, seeded the way a finalized
    mission really is (the characterization suite's ``init_repo`` /
    ``build_mission``), so the real ``implement`` command accepts it unpatched.

    ``coordination_branch`` descends from unrelated commit ``U``; a divergent
    ``explicit-base`` branch ``B`` does NOT contain ``U``.
    """
    repo = init_repo(tmp_path / "repo", branch="main")
    build_mission(
        repo, MISSION_SLUG, MISSION_ID,
        topology="lanes_with_coord",
        wps={WP_ID: ("code_change", [])},
        target="main",
        meta_extra={"coordination_branch": COORD_BRANCH},
    )
    seed_sha = git_out(repo, "rev-parse", "HEAD")

    # U: unrelated pending work on top of the seed.
    (repo / "unrelated.txt").write_text("unrelated work\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "unrelated work (U)")
    u_sha = git_out(repo, "rev-parse", "HEAD")

    # coordination_branch descends from U (fidelity gate: real coord topology).
    git_out(repo, "branch", COORD_BRANCH, u_sha)

    # explicit-base (B) diverges from the seed -- does NOT contain U.
    git_out(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    git_out(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "base-work.txt").write_text("explicit base work\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "explicit base work (B)")
    git_out(repo, "checkout", "-q", "main")

    # A real coordination Mission has its coordination surface materialized
    # and seeded by its first coordination write (finalize-tasks): resolve the
    # status write location through the one sanctioned accessor, which does
    # exactly that. The claim then reads and writes status there.
    placement_seam(repo, MISSION_SLUG).write_dir(MissionArtifactKind.STATUS_STATE)

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
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "seed")
    seed_sha = git_out(repo, "rev-parse", "HEAD")

    git_out(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    git_out(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "legacy-base-work.txt").write_text("legacy base work\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "legacy base work")
    git_out(repo, "checkout", "-q", "main")

    return repo


# ---------------------------------------------------------------------------
# AC-1 -- red-first, through the REAL implement(--base) seam (C-003)
# ---------------------------------------------------------------------------


def _run_implement_for_real(
    repo: Path,
    *,
    base: str | None,
    wp_id: str = WP_ID,
    mission_slug: str = MISSION_SLUG,
) -> Result:
    """Drive the real ``implement`` Typer command against the real repository and return its result.

    Uses the shared implement plumbing (``activate_repo`` points the command at *repo* and isolates
    it from the developer's git config; ``implement_cli`` invokes the very ``implement`` function
    ``agent action implement`` calls). Nothing in the implement command family is patched: the real
    mission detection, planning-artifact commit, claim status write and lane allocator all run, so a
    base-honoring regression anywhere along the seam shows up here (C-003). The caller asserts the
    exit code: a run that dies for an unrelated reason must not pass as a refusal.
    """
    with pytest.MonkeyPatch.context() as monkeypatch:
        activate_repo(repo, monkeypatch, repo.parent)
        args = [wp_id, "--mission", mission_slug, "--no-auto-commit"]
        if base is not None:
            args += ["--base", base]
        return implement_cli(*args)


class TestAC1SeamLevelRedFirst:
    """AC-1 / FR-001 / FR-002 / C-003: base threads through the real seam."""

    def test_explicit_base_replaces_coord_parent_on_no_dep_lane(
        self, coord_mission_with_divergent_base: Path,
    ) -> None:
        repo = coord_mission_with_divergent_base
        feature_dir = repo / "kitty-specs" / MISSION_SLUG

        # Fixture-fidelity gate (post-plan reviewer): the fixture must
        # genuinely carry coordination topology BEFORE we drive the seam,
        # so a wrong-ancestry RED is provably about base-honoring, not a
        # degraded-to-legacy fixture.
        assert json.loads((feature_dir / "meta.json").read_text())["coordination_branch"] == COORD_BRANCH
        u_sha = git_out(repo, "rev-parse", COORD_BRANCH)
        assert not _is_ancestor(repo, EXPLICIT_BASE_BRANCH, "main"), (
            "sanity: explicit-base must not already be reachable from main"
        )

        result = _run_implement_for_real(repo, base=EXPLICIT_BASE_BRANCH)

        assert result.exit_code == 0, result.output
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
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "seed")
    seed_sha = git_out(repo, "rev-parse", "HEAD")
    git_out(repo, "branch", COORD_BRANCH, seed_sha)

    # base B shares the seed as a common ancestor with the planning commit.
    git_out(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    git_out(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "base.txt").write_text("base\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "base work")
    git_out(repo, "checkout", "-q", "main")

    git_out(repo, "checkout", "-q", "-b", "planning-tmp", seed_sha)
    (repo / "planning.txt").write_text("planning artifact\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "planning commit")
    planning_sha = git_out(repo, "rev-parse", "HEAD")
    git_out(repo, "checkout", "-q", "main")
    # #4827: merge the planning commit into "main" (target_branch) BEFORE
    # discarding "planning-tmp" -- in real usage the recorded
    # planning_commit_sha is always initially reachable from target_branch
    # (finalize-tasks commits it there directly); leaving it an orphaned
    # island branch here would misclassify it under the #4827 orphan
    # detector this fixture predates, defeating this test's actual base +
    # planning-commit composition assertions.
    git_out(repo, "merge", "-q", "--no-ff", "--no-edit", "planning-tmp")
    git_out(repo, "branch", "-D", "planning-tmp")

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
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "seed")
    seed_sha = git_out(repo, "rev-parse", "HEAD")
    git_out(repo, "branch", COORD_BRANCH, seed_sha)

    # Divergent base B off the seed (does NOT contain the planning commit).
    git_out(repo, "branch", EXPLICIT_BASE_BRANCH, seed_sha)
    git_out(repo, "checkout", "-q", EXPLICIT_BASE_BRANCH)
    (repo / "base.txt").write_text("base work\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "explicit base work (B)")
    git_out(repo, "checkout", "-q", "main")

    # Planning commit off the seed — diverges from B, so its merge onto a
    # B-rooted lane creates "commits beyond B" (the misdetection trigger).
    git_out(repo, "checkout", "-q", "-b", "planning-tmp", seed_sha)
    (repo / "planning.txt").write_text("planning artifact\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "planning commit")
    planning_sha = git_out(repo, "rev-parse", "HEAD")
    git_out(repo, "checkout", "-q", "main")
    # #4827: merge the planning commit into "main" (target_branch) BEFORE
    # discarding "planning-tmp" -- in real usage the recorded
    # planning_commit_sha is always initially reachable from target_branch
    # (finalize-tasks commits it there directly); leaving it an orphaned
    # island branch here would misclassify it under the #4827 orphan
    # detector this fixture predates, defeating this test's actual base +
    # planning-commit composition assertions.
    git_out(repo, "merge", "-q", "--no-ff", "--no-edit", "planning-tmp")
    git_out(repo, "branch", "-D", "planning-tmp")

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
    base_b_sha = git_out(repo, "rev-parse", EXPLICIT_BASE_BRANCH)
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
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "seed")
    seed_sha = git_out(repo, "rev-parse", "HEAD")
    git_out(repo, "branch", COORD_BRANCH, seed_sha)

    # base branch: a genuinely UNRELATED root (--root commit, no shared history).
    git_out(repo, "checkout", "-q", "--orphan", "detached-root")
    (repo / "detached.txt").write_text("detached root\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "detached root commit")
    detached_sha = git_out(repo, "rev-parse", "HEAD")
    git_out(repo, "branch", "-f", EXPLICIT_BASE_BRANCH, detached_sha)
    git_out(repo, "checkout", "-q", "main")

    # planning commit lives on the seed's history -- unrelated to the detached base.
    git_out(repo, "checkout", "-q", "-b", "planning-tmp", seed_sha)
    (repo / "planning.txt").write_text("planning artifact\n")
    git_out(repo, "add", ".")
    git_out(repo, "commit", "-q", "-m", "planning commit")
    planning_sha = git_out(repo, "rev-parse", "HEAD")
    git_out(repo, "checkout", "-q", "main")
    # #4827: merge the planning commit into "main" (target_branch) BEFORE
    # discarding "planning-tmp" -- in real usage the recorded
    # planning_commit_sha is always initially reachable from target_branch
    # (finalize-tasks commits it there directly); leaving it an orphaned
    # island branch here would misclassify it under the #4827 orphan
    # detector this fixture predates, defeating this test's actual base +
    # planning-commit composition assertions.
    git_out(repo, "merge", "-q", "--no-ff", "--no-edit", "planning-tmp")
    git_out(repo, "branch", "-D", "planning-tmp")

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
        git_out(repo, "worktree", "prune")

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
    def test_present_on_honored_no_dep_fresh_create(self, coord_mission_with_divergent_base: Path) -> None:
        result = _run_implement_for_real(coord_mission_with_divergent_base, base=EXPLICIT_BASE_BRANCH)

        assert result.exit_code == 0, result.output
        captured = result.output.splitlines()
        assert any(_SUCCESS_PREFIX in line and EXPLICIT_BASE_BRANCH in line for line in captured), (
            f"expected the success line in captured output: {captured!r}"
        )

    def test_absent_on_base_none(self, coord_mission_with_divergent_base: Path) -> None:
        result = _run_implement_for_real(coord_mission_with_divergent_base, base=None)

        # Positive control: the claim succeeded and printed its tracker, so the ABSENT assertion
        # below is not satisfied by an empty or failed run.
        assert result.exit_code == 0, result.output
        captured = result.output.splitlines()
        assert captured, "positive control failed: nothing was captured at all"
        assert not any(_SUCCESS_PREFIX in line for line in captured), (
            f"success line must not print when base=None: {captured!r}"
        )

    def test_absent_on_error_path(self, coord_mission_with_divergent_base: Path) -> None:
        from specify_cli.lanes.worktree_allocator import UnhonorableBaseError

        repo = coord_mission_with_divergent_base

        # First call (no base) creates the lane -- now a second call with an
        # explicit base hits the reuse fail-loud guard (FL1).
        first = _run_implement_for_real(repo, base=None)
        assert first.exit_code == 0, first.output
        # #3471: no commit between the claims -- the first claim's own
        # --no-auto-commit writes no longer block the second, so it reaches
        # the allocator's reuse refusal directly.

        result = _run_implement_for_real(repo, base=EXPLICIT_BASE_BRANCH)

        # The run fails on the reuse refusal itself, not on anything earlier.
        assert result.exit_code == 1, result.output
        refusal = UnhonorableBaseError(route="reuse", wp_id=WP_ID, base=EXPLICIT_BASE_BRANCH)
        assert str(refusal) in _flat(result.output)
        assert not any(_SUCCESS_PREFIX in line for line in result.output.splitlines()), (
            f"success line must not print on a fail-loud error path: {result.output!r}"
        )


# ---------------------------------------------------------------------------
# FR-007 -- planning-lane --base ignored, with warning, no allocation effect
# ---------------------------------------------------------------------------


def test_fr007_planning_lane_base_ignored_with_warning(tmp_path: Path) -> None:
    from specify_cli.lanes.compute import PLANNING_LANE_ID

    repo = init_repo(tmp_path / "repo", branch="main")
    mission_slug = "lane-base-honoring-planning"
    build_mission(
        repo, mission_slug, MISSION_ID,
        wps={"WP01": ("planning_artifact", [])},
        target="main",
        layout=((PLANNING_LANE_ID, ("WP01",), ()),),
    )
    result = _run_implement_for_real(repo, base="main", wp_id="WP01", mission_slug=mission_slug)

    assert result.exit_code == 0, result.output
    captured = result.output.splitlines()
    assert any("ignored" in line and "--base" in line for line in captured), (
        f"expected the FR-007 'ignored' warning: {captured!r}"
    )
    assert not any(_SUCCESS_PREFIX in line for line in captured)
    # No lane worktree was allocated for the planning lane.
    assert not (repo / ".worktrees" / f"{mission_slug}-{PLANNING_LANE_ID}").exists()


# ---------------------------------------------------------------------------
# NFR-004 -- orchestrator-api envelope carries the machine-readable error_code
# ---------------------------------------------------------------------------


def test_nfr004_orchestrator_envelope_carries_unhonorable_base_error_code(tmp_path: Path) -> None:
    """Defensive/synthetic (per plan.md): the orchestrator passes base=None
    (inert), so the raise is mock-injected to prove the envelope wiring."""
    from specify_cli.lanes.worktree_allocator import UnhonorableBaseError
    from specify_cli.orchestrator_api import _common, wp_lifecycle

    captured_envelopes: list[dict[str, object]] = []

    def _fake_allocate(**_kwargs: object) -> tuple[Path, str]:
        raise UnhonorableBaseError(route="reuse", wp_id="WP06", base="some-ref")

    with (
        patch("specify_cli.lanes.worktree_allocator.allocate_lane_worktree", side_effect=_fake_allocate),
        patch.object(_common, "_emit", side_effect=lambda env: captured_envelopes.append(env)),
        patch.object(
            wp_lifecycle, "_lane_assignment_or_legacy",
            return_value=(
                _make_manifest(mission_branch=f"kitty/mission-{MISSION_SLUG}"),
                _make_manifest(mission_branch=f"kitty/mission-{MISSION_SLUG}").lanes[0],
            ),
        ),
        pytest.raises(typer.Exit),
    ):
        wp_lifecycle._resolve_start_workspace(
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
