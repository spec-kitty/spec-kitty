"""Guards against the lanes-subsystem consumers regressing onto the forbidden
identity/legacy/HEAD naming probe (C-004) or an untyped invalid-identity
crash (FR-006/FR-007/FR-011).

Each fixture here builds a *divergent shape* directly with
:func:`allocate_lane_worktree`, tailored to this module's per-test needs
(single-lane worktree config, a missing-``lanes.json`` scenario, a decoy
branch, a detached HEAD) rather than the fuller WP-status-seeded shapes
``tests/merge/_divergent_shapes.py`` builds for the reconciliation-claim
tests. Shared bits stay private to this file.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.branch_naming import BranchIdentityUnresolved, InvalidMissionIdentity
from specify_cli.lanes.lifecycle_sync import (
    LaneAutoRebaseSyncError,
    sync_lane_after_coordination_commit,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json
from specify_cli.lanes.recovery import _resolve_mission_branch
from specify_cli.lanes.worktree_allocator import allocate_lane_worktree

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _run(cmd: list[str], cwd: Path, *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check)


def _write_task_file(feature_dir: Path, wp_id: str = "WP01") -> None:
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (feature_dir / "tasks" / f"{wp_id}-test.md").write_text(f"---\nwork_package_id: {wp_id}\n---\n# {wp_id}\n", encoding="utf-8")


def _init_repo(tmp_path: Path, mission_slug: str, *, mission_id: str | None) -> tuple[Path, Path, LanesManifest]:
    """A tmp git repo with a real allocator-created lane (a divergent shape).

    Returns ``(repo_root, feature_dir, manifest)``. The manifest's ``mission_id``
    is whatever the caller supplies (``None``, a short literal, or a full
    ULID-shaped literal) — never derived by calling the naming code, so a
    decoy or invalid value is under the test's full control.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    _run(["git", "init", "-b", "main", str(repo)], tmp_path)
    _run(["git", "config", "user.email", "test@spec-kitty"], repo)
    _run(["git", "config", "user.name", "test"], repo)
    _run(["git", "config", "commit.gpgsign", "false"], repo)

    feature_dir = repo / "kitty-specs" / mission_slug
    _write_task_file(feature_dir)
    (repo / "src").mkdir()
    (repo / "src" / "shared.txt").write_text("base\n", encoding="utf-8")
    _run(["git", "add", "."], repo)
    _run(["git", "commit", "-m", "seed mission"], repo)

    lane = ExecutionLane(
        lane_id="lane-a",
        wp_ids=("WP01",),
        write_scope=("src/**", "kitty-specs/**"),
        predicted_surfaces=("test",),
        depends_on_lanes=(),
        parallel_group=0,
    )
    manifest = LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=[lane],
        computed_at="2026-09-26T00:00:00Z",
        computed_from="test",
    )
    write_lanes_json(feature_dir, manifest)
    _run(["git", "add", "kitty-specs"], repo)
    _run(["git", "commit", "-m", "compute lanes"], repo)

    # The write authority: creates the REAL worktree + branch (always the
    # legacy ``kitty/mission-{slug}-{lane}`` form -- predict_lane_worktree
    # hardcodes ``mission_id=None`` regardless of the manifest's mission_id).
    allocate_lane_worktree(repo, mission_slug, "WP01", manifest)
    for key, value in (("user.email", "test@spec-kitty"), ("user.name", "test")):
        _run(["git", "config", key, value], repo / ".worktrees" / f"{mission_slug}-lane-a")

    return repo, feature_dir, manifest


def _created_branch(mission_slug: str) -> str:
    return f"kitty/mission-{mission_slug}-lane-a"


def _created_worktree(repo: Path, mission_slug: str) -> Path:
    return repo / ".worktrees" / f"{mission_slug}-lane-a"


def test_decoy_identity_branch_is_never_attached(tmp_path: Path) -> None:
    """FR-007: the identity-form probe must not win over the created branch.

    Guards against ``_resolve_lane_branch`` trying the identity-form
    candidate FIRST. A decoy branch at that literal name exists (created
    directly by ``git branch``, never by calling the naming code with an
    identity); the probe must not pick it and attach the WRONG branch to
    the recreated worktree.
    """
    mission_slug = "divergent-decoy"
    mission_id = "01ABCDEFGHJKMNPQRSTVWXYZ01"  # 26 chars, valid mid8-length ULID shape
    repo, _feature_dir, manifest = _init_repo(tmp_path, mission_slug, mission_id=mission_id)
    created_branch = _created_branch(mission_slug)
    worktree = _created_worktree(repo, mission_slug)

    # Literal decoy string -- the identity-form name a probe would guess,
    # never produced by calling lane_branch_name/branch_naming with an identity.
    decoy_branch = f"kitty/mission-{mission_slug}-01ABCDEF-lane-a"
    _run(["git", "branch", decoy_branch, "main"], repo)

    _run(["git", "worktree", "remove", str(worktree), "--force"], repo)

    report = sync_lane_after_coordination_commit(
        repo_root=repo,
        mission_slug=mission_slug,
        wp_id="WP01",
        coordination_branch=manifest.mission_branch,
    )
    assert report is not None and report.succeeded

    actual_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], worktree).stdout.strip()
    assert actual_branch == created_branch, (
        f"FR-007: sync attached a probed identity-form decoy ({actual_branch!r}) instead of the allocator-created branch ({created_branch!r})"
    )


def test_no_head_fallback_raises_naming_created_branch(tmp_path: Path) -> None:
    """FR-007: no third naming strategy -- HEAD is never read to resolve the
    lane branch.

    The lane worktree is detached (its created branch is then deleted, which
    only ``git`` allows once nothing has it checked out) and its content
    conflicts with the coordination branch. Guards against a resolver whose
    candidates are both absent falling back to
    ``git rev-parse --abbrev-ref HEAD`` inside the (detached) worktree and
    returning the placeholder ``"HEAD"`` rather than the real created branch
    name -- the "third naming strategy" FR-007 retires.
    """
    mission_slug = "divergent-detached"
    repo, _feature_dir, manifest = _init_repo(tmp_path, mission_slug, mission_id=None)
    created_branch = _created_branch(mission_slug)
    worktree = _created_worktree(repo, mission_slug)

    # Conflicting lane-side edit, committed on the still-named created branch.
    (worktree / "src" / "shared.txt").write_text("lane-version\n", encoding="utf-8")
    _run(["git", "add", "src/shared.txt"], worktree)
    _run(["git", "commit", "-m", "lane edit"], worktree)

    # Detach, then delete the created branch (git refuses to delete a branch
    # that is still checked out anywhere).
    _run(["git", "checkout", "--detach", "HEAD"], worktree)
    _run(["git", "branch", "-D", created_branch], repo)

    # Conflicting coordination-side edit to the SAME line.
    _run(["git", "switch", manifest.mission_branch], repo)
    (repo / "src" / "shared.txt").write_text("coord-version\n", encoding="utf-8")
    _run(["git", "add", "src/shared.txt"], repo)
    _run(["git", "commit", "-m", "coord edit"], repo)
    _run(["git", "switch", "main"], repo)

    with pytest.raises(LaneAutoRebaseSyncError) as exc_info:
        sync_lane_after_coordination_commit(
            repo_root=repo,
            mission_slug=mission_slug,
            wp_id="WP01",
            coordination_branch=manifest.mission_branch,
        )

    assert exc_info.value.lane_branch == created_branch, (
        f"FR-007: the refusal must name the allocator-created branch, never a HEAD-derived placeholder; got {exc_info.value.lane_branch!r}"
    )


def test_invalid_short_identity_never_crashes_lifecycle_sync(tmp_path: Path) -> None:
    """FR-011 edge case (lifecycle_sync leg): an identity shorter than 8
    characters recorded in ``lanes.json`` must never raise a raw
    ``ValueError`` out of the sync entry point, and the allocator-created
    branch is still the one attached.
    """
    mission_slug = "divergent-shortid"
    repo, _feature_dir, manifest = _init_repo(tmp_path, mission_slug, mission_id="abc")
    created_branch = _created_branch(mission_slug)
    worktree = _created_worktree(repo, mission_slug)

    report = sync_lane_after_coordination_commit(
        repo_root=repo,
        mission_slug=mission_slug,
        wp_id="WP01",
        coordination_branch=manifest.mission_branch,
    )
    assert report is not None and report.succeeded

    actual_branch = _run(["git", "rev-parse", "--abbrev-ref", "HEAD"], worktree).stdout.strip()
    assert actual_branch == created_branch


# ---------------------------------------------------------------------------
# Acceptance lane source roots on a divergent shape.
# ---------------------------------------------------------------------------


def test_acceptance_finds_divergent_shape_lane_root(tmp_path: Path) -> None:
    """FR-006/#4254: acceptance's approved-lane candidate roots must resolve
    the CREATED worktree, not an identity-form path that was never
    materialized.

    Guards against ``_approved_lane_source_roots`` passing
    ``mission_id=manifest.mission_id`` into ``worktree_path``, which for a
    divergent (mismatched-mid8 / legacy) shape looks in a directory the
    allocator never created and silently finds nothing.
    """
    from specify_cli.acceptance import _approved_lane_source_roots

    mission_slug = "divergent-acceptance"
    mission_id = "01ABCDEFGHJKMNPQRSTVWXYZ01"
    repo, feature_dir, _manifest = _init_repo(tmp_path, mission_slug, mission_id=mission_id)
    worktree = _created_worktree(repo, mission_slug)

    roots = _approved_lane_source_roots(repo, feature_dir, {"approved": ["WP01"], "done": []})

    assert roots == (worktree,), f"FR-006: acceptance did not find the divergent shape's created lane root; expected {(worktree,)!r}, got {roots!r}"


# ---------------------------------------------------------------------------
# recovery's ``_resolve_mission_branch`` typed refusal.
# ---------------------------------------------------------------------------


def test_resolve_mission_branch_raises_typed_error_on_invalid_identity(tmp_path: Path) -> None:
    """FR-011: an invalid (<8 char) ``mission_id`` in ``meta.json`` must
    raise :class:`BranchIdentityUnresolved`, never a raw ``ValueError``.

    Guards against ``_resolve_mission_branch`` catching only
    ``BranchIdentityUnresolved`` around ``mission_branch_name_required`` --
    a raw ``ValueError`` from ``_mid8`` for a short identity must never
    propagate uncaught (it is now the typed ``InvalidMissionIdentity``
    subclass, raised at the source).
    """
    mission_slug = "divergent-recovery-shortid"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": "abc", "mission_slug": mission_slug}), encoding="utf-8")
    # No lanes.json: _find_mission_branch returns "" and the composer path runs.

    with pytest.raises(BranchIdentityUnresolved) as exc_info:
        _resolve_mission_branch(feature_dir, mission_slug)

    err = exc_info.value
    assert isinstance(err, InvalidMissionIdentity)
    assert err.error_code == "INVALID_MISSION_IDENTITY"
    assert err.invalid_mission_id == "abc"
    assert str(feature_dir / "meta.json") in err.next_step
    assert "mission_id is absent and the slug" not in str(err)


def test_resolve_mission_branch_absent_identity_names_meta_path(tmp_path: Path) -> None:
    """An absent ``mission_id`` on a modern slug stays the base
    :class:`BranchIdentityUnresolved` (not the invalid-identity subclass),
    with the meta.json location appended to its backfill remedy."""
    mission_slug = "divergent-recovery-noid"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_slug": mission_slug}), encoding="utf-8")

    with pytest.raises(BranchIdentityUnresolved) as exc_info:
        _resolve_mission_branch(feature_dir, mission_slug)

    err = exc_info.value
    assert not isinstance(err, InvalidMissionIdentity)
    assert "backfill-identity" in err.next_step
    assert str(feature_dir / "meta.json") in err.next_step


def test_resolve_mission_branch_recorded_branch_wins_even_with_invalid_identity(
    tmp_path: Path,
) -> None:
    """A recorded ``lanes.json`` mission_branch wins before the identity is
    ever consulted -- even when that identity is invalid."""
    mission_slug = "divergent-recovery-recorded"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": "abc", "mission_slug": mission_slug}), encoding="utf-8")
    manifest = LanesManifest(
        version=1,
        mission_slug=mission_slug,
        mission_id="abc",
        mission_branch=f"kitty/mission-{mission_slug}",
        target_branch="main",
        lanes=[],
        computed_at="2026-09-26T00:00:00Z",
        computed_from="test",
    )
    write_lanes_json(feature_dir, manifest)

    assert _resolve_mission_branch(feature_dir, mission_slug) == manifest.mission_branch
