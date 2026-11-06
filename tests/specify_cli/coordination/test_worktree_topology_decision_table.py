"""#1889 decision-table tests for the surface resolver (WP03, FR-008).

Pins rows R1/R2/R2'/R3/R4 of the declared-but-not-materialized coord topology
table (data-model.md §3). R3 (declared + worktree absent + branch DELETED) must
fail closed with a distinct, loud, structured error — never a fallback to the
primary surface. R3 composes with the #1848 status-transition carve-out: a
deleted coord branch carrying unmerged status is data loss, surfaced loudly.

R2' (declared + coord root materialized-but-EMPTY) was updated by mission
01KVN754 / WP04 to **Option B**: it no longer hard-fails — it resolves the
PRIMARY checkout. ADR 2026-11-06-2 (Mission lane-worktree-model-hardening WP05)
replaced its loud WARNING with the read door's declared pre-seed fallback.
coord-EMPTY = declared primary fallback; coord-DELETED = hard-fail. The two
fail-closed states stay distinct.
"""
from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    resolve_status_surface,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )


def _init_repo(repo_root: Path) -> None:
    repo_root.mkdir(parents=True, exist_ok=True)
    _git(repo_root, "init", "-q")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")
    (repo_root / "README.md").write_text("seed\n", encoding="utf-8")
    _git(repo_root, "add", "README.md")
    _git(repo_root, "commit", "-q", "-m", "seed")


def _write_meta(feature_dir: Path, **fields: object) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(json.dumps(fields), encoding="utf-8")


_MID8 = "01KTDVHZ"
_MISSION = "my-mission"
_COORD_BRANCH = f"kitty/mission-{_MISSION}-{_MID8}"


def _seed_primary_meta(
    repo_root: Path,
    *,
    coordination_branch: str | None,
    topology: str | None = None,
) -> Path:
    feature_dir = repo_root / "kitty-specs" / _MISSION
    fields: dict[str, object] = {"mission_id": "01KTDVHZKGCHCW6HQ4V577PNES"}
    if coordination_branch is not None:
        fields["coordination_branch"] = coordination_branch
    if topology is not None:
        fields["topology"] = topology
    _write_meta(feature_dir, **fields)
    return feature_dir


# ---------------------------------------------------------------------------
# R4 — undeclared → PRIMARY
# ---------------------------------------------------------------------------


def test_r4_undeclared_resolves_primary(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    feature_dir = _seed_primary_meta(repo_root, coordination_branch=None)

    result = resolve_status_surface(repo_root, _MISSION)
    assert result == feature_dir / "status.events.jsonl"


# ---------------------------------------------------------------------------
# R2 — declared + branch exists + worktree absent → compose-once, no raise
# ---------------------------------------------------------------------------


def test_r2_declared_branch_exists_worktree_absent_composes(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    # The coord branch exists in git, but no coord worktree has been added.
    _git(repo_root, "branch", _COORD_BRANCH)
    _seed_primary_meta(repo_root, coordination_branch=_COORD_BRANCH)

    result = resolve_status_surface(repo_root, _MISSION)
    expected = (
        repo_root
        / ".worktrees"
        / f"{_MISSION}-{_MID8}-coord"
        / "kitty-specs"
        / f"{_MISSION}-{_MID8}"
        / "status.events.jsonl"
    )
    assert result == expected


# ---------------------------------------------------------------------------
# R2' — declared + materialized root, mission dir absent (coord-EMPTY) →
# Option B: PRIMARY fallback + loud warning (mission 01KVN754 / WP04; ADR
# 2026-06-19-1 amended). The historical hard-fail here was the routine-workaround
# trap; coord-empty now resolves primary loudly so liveness is preserved and the
# staleness risk is observable. (coord-DELETED stays hard-fail — R3 below.)
# ---------------------------------------------------------------------------


def test_r2prime_materialized_root_missing_dir_declares_pre_seed_fallback(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """R2' after ADR 2026-11-06-2 (Mission lane-worktree-model-hardening WP05).

    The coordination branch holds no log for the Mission yet (pre-seed), so the read door
    declares the write-checkout fallback on the surface (``fallback_reason``) instead of the
    former loud log WARNING; the legacy projection still resolves the PRIMARY log.
    """
    from specify_cli.status.read_surface import StatusReadSource, resolve_status_read

    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    _git(repo_root, "branch", _COORD_BRANCH)
    feature_dir = _seed_primary_meta(
        repo_root, coordination_branch=_COORD_BRANCH, topology="lanes_with_coord"
    )
    # Coord worktree root exists but lacks the mission dir.
    coord_root = repo_root / ".worktrees" / f"{_MISSION}-{_MID8}-coord"
    coord_root.mkdir(parents=True)

    surface = resolve_status_read(repo_root, _MISSION)
    with caplog.at_level(logging.WARNING, logger="specify_cli.coordination.surface_resolver"):
        result = resolve_status_surface(repo_root, _MISSION)

    # Option B kept: resolve the PRIMARY surface, do not hard-fail.
    assert result == feature_dir / "status.events.jsonl"
    # The fallback is declared on the surface, not logged (FR-004).
    assert surface.source is StatusReadSource.WRITE_CHECKOUT
    assert surface.fallback_reason and "pre-seed" in surface.fallback_reason
    assert not [r for r in caplog.records if r.levelno == logging.WARNING]


# ---------------------------------------------------------------------------
# R3 — declared + branch DELETED + worktree absent → distinct loud error
# ---------------------------------------------------------------------------


def test_r3_declared_branch_deleted_raises_distinct_error(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    # Branch is declared in meta but NEVER created (deleted/absent in git).
    _seed_primary_meta(repo_root, coordination_branch=_COORD_BRANCH)

    with pytest.raises(CoordinationBranchDeleted) as excinfo:
        resolve_status_surface(repo_root, _MISSION)

    err = excinfo.value
    assert err.error_code == "COORDINATION_BRANCH_DELETED"
    assert _COORD_BRANCH in str(err)
    # Actionable next_step — never a silent primary fallback.
    assert err.next_step
    assert "repair" in err.next_step or "coordination_branch" in err.next_step


def test_r3_never_falls_back_to_primary(tmp_path: Path) -> None:
    """The primary mission dir EXISTS and would resolve happily — but a deleted
    coord branch must still fail loud, never silently degrade to primary."""
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    _seed_primary_meta(repo_root, coordination_branch=_COORD_BRANCH)

    with pytest.raises(CoordinationBranchDeleted):
        resolve_status_surface(repo_root, _MISSION)


def test_r3_distinct_from_r2prime(tmp_path: Path) -> None:
    """R3 (branch DELETED) hard-fails CoordinationBranchDeleted — data loss; R2'
    (branch exists, coord root materialized-but-empty) resolves PRIMARY loudly
    (Option B, mission 01KVN754). The two coord fail-closed states are distinct:
    deleted = hard-fail, empty = loud primary fallback."""
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    feature_dir = _seed_primary_meta(repo_root, coordination_branch=_COORD_BRANCH)

    # R3: branch absent → hard-fail (never a silent OR loud primary fallback).
    with pytest.raises(CoordinationBranchDeleted):
        resolve_status_surface(repo_root, _MISSION)

    # Now create the branch + materialized-but-empty root → R2' (coord-empty).
    _git(repo_root, "branch", _COORD_BRANCH)
    coord_root = repo_root / ".worktrees" / f"{_MISSION}-{_MID8}-coord"
    coord_root.mkdir(parents=True)
    # R2' no longer raises — Option B resolves the primary surface.
    result = resolve_status_surface(repo_root, _MISSION)
    assert result == feature_dir / "status.events.jsonl"


# ---------------------------------------------------------------------------
# R1 — declared + materialized worktree + branch exists → COORDINATION surface
# ---------------------------------------------------------------------------


def test_r1_declared_materialized_resolves_coord_surface(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    _init_repo(repo_root)
    coord_root = repo_root / ".worktrees" / f"{_MISSION}-{_MID8}-coord"
    subprocess.run(
        [
            "git", "-C", str(repo_root), "worktree", "add", "-q",
            "-b", _COORD_BRANCH, str(coord_root),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    coord_feature_dir = coord_root / "kitty-specs" / f"{_MISSION}-{_MID8}"
    _write_meta(
        coord_feature_dir,
        mission_id="01KTDVHZKGCHCW6HQ4V577PNES",
        coordination_branch=_COORD_BRANCH,
    )
    _seed_primary_meta(repo_root, coordination_branch=_COORD_BRANCH)

    result = resolve_status_surface(repo_root, _MISSION)
    assert result == coord_feature_dir / "status.events.jsonl"
