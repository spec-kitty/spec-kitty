"""T006/T009: A declared-but-never-created coord branch must not be classified healthy coord.

FR-002 / #2250.

Binding constraint C-001: ``classify_topology`` and ``read_topology`` remain
pure — no I/O inside; their behaviour is unchanged by WP02.

T006 RED-first:
  (a) A mission whose ``meta.json`` declares a ``coordination_branch`` that was
      never created in git must NOT be backfilled as healthy ``coord``
      (backfill must skip, not write).
  (b) ``resolve_status_surface_with_anchor`` raises ``CoordinationBranchDeleted``
      for that same mission, and ``CoordinationBranchDeleted.next_step`` leads
      with "flatten" before "doctor".

T009 Purity guards:
  ``classify_topology`` and ``read_topology`` produce identical outputs for
  identical inputs and perform no git/subprocess calls.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import MissionTopology, classify_topology
from specify_cli.coordination.surface_resolver import (
    CoordinationBranchDeleted,
    resolve_status_surface_with_anchor,
)
from specify_cli.migration.backfill_topology import (
    backfill_mission_topology,
    read_topology,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True)


def _make_git_repo(path: Path) -> Path:
    """Initialise a minimal git repo with an empty initial commit."""
    path.mkdir(parents=True, exist_ok=True)
    _git("init", "-b", "main", cwd=path)
    _git("config", "user.name", "Test", cwd=path)
    _git("config", "user.email", "test@example.com", cwd=path)
    _git("commit", "--allow-empty", "-m", "init", cwd=path)
    return path


def _write_meta(feature_dir: Path, meta: dict[str, object]) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2) + "\n", encoding="utf-8"
    )


# ---------------------------------------------------------------------------
# T006(a) — backfill WRITE path must not persist healthy coord for a
# declared-but-never-created coordination branch (#2250)
# ---------------------------------------------------------------------------


def test_backfill_skips_never_created_coord_branch(tmp_path: Path) -> None:
    """T006(a): backfill must NOT write topology='coord' when the declared
    coordination_branch does not exist in git.

    Pre-fix: ``backfill_mission_topology`` calls ``_derive_topology``
    (pure — C-001 preserved) which returns COORD because ``coordination_branch``
    is non-None.  Without the git-existence check it then writes ``topology:
    coord`` — a false-healthy classification.

    Post-fix: after deriving COORD the write path probes git via the
    canonical ``_coord_branch_exists`` seam (lazy import, C-001 preserved); an
    absent branch causes a "skip" return so meta.json is left untouched.
    """
    repo = _make_git_repo(tmp_path / "repo")
    # The coord branch "kitty/mission-my-mission-01ABC123" was declared but
    # never created in the git repo.
    slug = "my-mission-01ABC123"
    feature_dir = repo / "kitty-specs" / slug
    _write_meta(
        feature_dir,
        {
            "coordination_branch": "kitty/mission-my-mission-01ABC123",
            # No "topology" key — un-backfilled, to exercise the backfill path.
        },
    )
    meta_before = (feature_dir / "meta.json").read_bytes()

    result = backfill_mission_topology(feature_dir)

    # Action must NOT be "wrote" (a false-healthy COORD would be "wrote").
    assert result.action == "skip", (
        f"Expected action='skip' for a never-created coord branch, got {result.action!r}. "
        "backfill_mission_topology must not persist topology='coord' when the "
        "declared coordination_branch does not exist in git (#2250)."
    )
    assert result.topology != MissionTopology.COORD.value, (
        "backfill must not report topology='coord' for a never-created branch."
    )
    # meta.json must be byte-identical — no write occurred.
    assert (feature_dir / "meta.json").read_bytes() == meta_before, (
        "meta.json must not be mutated when backfill skips."
    )


# ---------------------------------------------------------------------------
# T006(b) — surface resolver remediation must lead with "flatten"
# for a never-created (or deleted) coordination branch (#2250)
# ---------------------------------------------------------------------------


def test_resolver_remediation_leads_with_flatten(tmp_path: Path) -> None:
    """T006(b): ``CoordinationBranchDeleted.next_step`` must lead with 'flatten'
    before 'doctor' for a mission whose declared coordination_branch does not
    exist in git.

    Pre-fix: ``next_step`` leads with 'Run `spec-kitty doctor workspaces --fix`'
    and mentions flatten only as an afterthought.

    Post-fix: flatten is the FIRST recovery action in ``next_step``.
    """
    repo = _make_git_repo(tmp_path / "repo")
    slug = "my-mission"
    feature_dir = repo / "kitty-specs" / slug
    _write_meta(
        feature_dir,
        {
            "mid8": "01ABC123",
            "coordination_branch": "kitty/mission-my-mission-01ABC123",
        },
    )

    with pytest.raises(CoordinationBranchDeleted) as exc_info:
        resolve_status_surface_with_anchor(repo, slug)

    next_step: str = exc_info.value.next_step
    lower = next_step.lower()
    flatten_pos = lower.find("flatten")
    doctor_pos = lower.find("doctor")
    assert flatten_pos >= 0, f"next_step must mention 'flatten'. Got: {next_step!r}"
    assert doctor_pos >= 0, f"next_step must mention 'doctor'. Got: {next_step!r}"
    assert flatten_pos < doctor_pos, (
        "next_step must lead with 'flatten' BEFORE 'doctor'. "
        f"flatten at {flatten_pos}, doctor at {doctor_pos}. "
        f"Full next_step: {next_step!r}"
    )


# ---------------------------------------------------------------------------
# T009 — C-001 purity guards: classify_topology and read_topology are pure
# (no git/subprocess calls, same inputs → same outputs)
# ---------------------------------------------------------------------------


def test_classify_topology_pure_no_subprocess(tmp_path: Path) -> None:
    """T009(a): ``classify_topology`` must never call subprocess.run.

    C-001: this is the pure 2×2 mapper — it takes ``(coordination_branch,
    has_lanes)`` and returns a MissionTopology cell with no I/O.  Any git probe
    added here would silently reclassify missions for all 6 consumers (the
    cross-lane behavioral shift the WP02 C-001 constraint prohibits).
    """
    with patch("subprocess.run") as mock_run:
        r1 = classify_topology("kitty/mission-test-01XXXXX1", has_lanes=False)
        r2 = classify_topology("kitty/mission-test-01XXXXX1", has_lanes=True)
        r3 = classify_topology(None, has_lanes=False)
        r4 = classify_topology(None, has_lanes=True)
        mock_run.assert_not_called()

    assert r1 is MissionTopology.COORD
    assert r2 is MissionTopology.LANES_WITH_COORD
    assert r3 is MissionTopology.SINGLE_BRANCH
    assert r4 is MissionTopology.LANES


def test_read_topology_pure_no_subprocess(tmp_path: Path) -> None:
    """T009(b): ``read_topology`` must never call subprocess.run.

    C-001 / #1814 read-only contract: ``read_topology`` reads ``meta.json``
    purely from disk and derives the topology without any git probe.  A git
    call here would break the finalize ``--validate-only`` / accept-readiness
    transactional-read contract AND silently affect the Lane B consumers
    (``runtime_bridge``, ``resolution``, ``status_transition``).
    """
    feature_dir = tmp_path / "mission-pure"
    feature_dir.mkdir(parents=True)

    # Case 1: stored topology present — must return it with NO write and NO git.
    _write_meta(
        feature_dir,
        {"coordination_branch": "kitty/test-branch", "topology": "coord"},
    )
    with patch("subprocess.run") as mock_run:
        result = read_topology(feature_dir)
        mock_run.assert_not_called()
    assert result is MissionTopology.COORD

    # Case 2: no stored topology — derives without git call.
    _write_meta(feature_dir, {"coordination_branch": "kitty/test-branch"})
    with patch("subprocess.run") as mock_run:
        result = read_topology(feature_dir)
        mock_run.assert_not_called()
    assert result is MissionTopology.COORD

    # Case 3: un-backfilled coord-less mission — derives LANES without git
    # (#5100 FR-013 / #2602: never a derived ``single_branch`` at runtime).
    _write_meta(feature_dir, {})
    with patch("subprocess.run") as mock_run:
        result = read_topology(feature_dir)
        mock_run.assert_not_called()
    assert result is MissionTopology.LANES
