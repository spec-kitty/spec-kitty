"""Regression tests for dossier-snapshot self-blocking transitions (#845).

Mission: ``charter-e2e-827-followups-01KQAJA0``
Contract: ``contracts/dossier-snapshot-ownership.md`` (D1, D2, D3)

Locks in the EXCLUDE ownership policy (FR-009/FR-010/FR-011, C-006):

- The snapshot writer at ``src/specify_cli/dossier/snapshot.py`` continues to
  write ``<feature_dir>/.kittify/dossiers/<mission_slug>/snapshot-latest.json``
  with a plain file write — no staging, no commit, no special-case branch
  interaction.
- The dirty-state preflight backing ``agent tasks move-task`` (and its peer
  ``_validate_ready_for_review`` helper) explicitly filters that path before
  computing the blocking set, so the snapshot can never self-block a
  transition.
- Real, unrelated dirty state (e.g. a user-edited source file) STILL blocks,
  with guidance that names the offending file but NOT the snapshot.

The control test (D3) is the load-bearing assertion: without it the fix could
mask a regression where genuine drift silently slips past the gate.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from kernel.git import GitPath, StatusEntry
from specify_cli.cli.commands.agent.tasks import (
    _filter_runtime_state_paths,
    _validate_ready_for_review,
)
from specify_cli.dossier.snapshot import save_snapshot
from specify_cli.dossier.models import MissionDossierSnapshot
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.preflight import is_dossier_snapshot
from specify_cli.status.store import append_event
from tests.lane_test_utils import (
    lane_branch_name,
    lane_worktree_path,
    write_single_lane_manifest,
)

pytestmark = pytest.mark.git_repo


# ---------------------------------------------------------------------------
# Unit-level coverage for the helper itself
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "candidate",
    [
        ".kittify/dossiers/my-mission/snapshot-latest.json",
        "kitty-specs/charter-e2e/.kittify/dossiers/charter-e2e/snapshot-latest.json",
        "/abs/path/repo/.kittify/dossiers/foo/snapshot-latest.json",
        "nested/path/.kittify/dossiers/foo/snapshot-latest.json",
    ],
)
def test_is_dossier_snapshot_matches_documented_paths(candidate: str) -> None:
    """D1 — the canonical snapshot paths are recognised by the helper."""
    assert is_dossier_snapshot(candidate) is True
    assert is_dossier_snapshot(Path(candidate)) is True


@pytest.mark.parametrize(
    "candidate",
    [
        "src/specify_cli/cli/commands/agent/tasks.py",
        "kitty-specs/foo/spec.md",
        ".kittify/config.yaml",
        ".kittify/dossiers/my-mission/manifest.json",  # different filename
        "snapshot-latest.json",                          # bare filename
        "tests/integration/test_thing.py",
    ],
)
def test_is_dossier_snapshot_rejects_unrelated_paths(candidate: str) -> None:
    """D3 — paths outside the snapshot glob must NOT classify as snapshots."""
    assert is_dossier_snapshot(candidate) is False


def test_is_dossier_snapshot_filter_strips_only_snapshots() -> None:
    """Filtering with ``is_dossier_snapshot`` removes snapshots and preserves everything else."""
    paths = [
        "src/foo.py",
        ".kittify/dossiers/foo/snapshot-latest.json",
        "kitty-specs/x/.kittify/dossiers/x/snapshot-latest.json",
        "README.md",
    ]
    assert [p for p in paths if not is_dossier_snapshot(p)] == ["src/foo.py", "README.md"]


def test_filter_runtime_state_paths_drops_dossier_snapshot() -> None:
    """The shared porcelain filter must drop dossier snapshots (belt-and-suspenders)."""
    entries = (
        StatusEntry(xy=" M", path=GitPath.parse("src/foo.py")),
        StatusEntry(xy="??", path=GitPath.parse("kitty-specs/x/.kittify/dossiers/x/snapshot-latest.json")),
        StatusEntry(xy=" M", path=GitPath.parse("README.md")),
    )
    filtered = {str(entry.path) for entry in _filter_runtime_state_paths(entries)}
    assert filtered == {"src/foo.py", "README.md"}


# ---------------------------------------------------------------------------
# Integration fixture: minimal git repo + software-dev mission + worktree
# ---------------------------------------------------------------------------


@pytest.fixture
def snapshot_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    """Create a git repo with a software-dev mission and a clean lane worktree.

    Returns:
        (repo_root, worktree_path, mission_slug)
    """
    repo = tmp_path / "repo"
    repo.mkdir()

    # Initialise git repo on `main`.
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True, capture_output=True)

    # Mirror the project's own gitignore policy for dossier snapshots (D1):
    # without this, the porcelain output below would include the snapshot
    # write as untracked noise — but D1 is supposed to silence it via
    # ``.gitignore`` in the common case. The explicit filter (D2) is what
    # we exercise in the assertions below.
    (repo / ".gitignore").write_text(
        "\n".join(
            [
                ".kittify/dossiers/*/snapshot-latest.json",
                "kitty-specs/*/.kittify/dossiers/*/snapshot-latest.json",
                "",
            ]
        ),
        encoding="utf-8",
    )

    # ``.kittify`` marker so the project is recognised as spec-kitty managed.
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.yaml").write_text("# Config\n")

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, check=True, capture_output=True)

    mission_slug = "test-dossier-self-block"
    feature_dir = repo / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    write_single_lane_manifest(feature_dir, wp_ids=("WP01",))

    # WP task file (planning artifact).
    task_file = tasks_dir / "WP01-test-dossier.md"
    task_file.write_text(
        "---\nwork_package_id: WP01\ntitle: Test Dossier\nagent: test\nshell_pid: ''\n---\n\n# WP01\n",
        encoding="utf-8",
    )

    # Seed status events: planned -> in_progress.
    for lane_val in ("planned", "in_progress"):
        append_event(
            feature_dir,
            StatusEvent(
                event_id=f"seed-WP01-{lane_val}",
                mission_slug=mission_slug,
                wp_id="WP01",
                from_lane=Lane.PLANNED,
                to_lane=Lane(lane_val),
                at="2025-01-01T00:00:00+00:00",
                actor="test-fixture",
                force=True,
                execution_mode="worktree",
            ),
        )

    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Add mission and task"], cwd=repo, check=True, capture_output=True)

    # Create the lane worktree with one implementation commit.
    worktree_dir = lane_worktree_path(repo, mission_slug)
    subprocess.run(
        ["git", "worktree", "add", "-b", lane_branch_name(mission_slug), str(worktree_dir), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (worktree_dir / "implementation.py").write_text("# Implementation\n")
    subprocess.run(["git", "add", "."], cwd=worktree_dir, check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "feat(WP01): implement"], cwd=worktree_dir, check=True, capture_output=True
    )

    return repo, worktree_dir, mission_slug


def _make_minimal_snapshot(mission_slug: str) -> MissionDossierSnapshot:
    """Build a minimal valid :class:`MissionDossierSnapshot` for tests."""
    from kernel.clock import now_utc

    return MissionDossierSnapshot(
        mission_slug=mission_slug,
        total_artifacts=0,
        required_artifacts=0,
        required_present=0,
        required_missing=0,
        optional_artifacts=0,
        optional_present=0,
        completeness_status="unknown",
        parity_hash_sha256="0" * 64,
        parity_hash_components=[],
        artifact_summaries=[],
        computed_at=now_utc(),
    )


# ---------------------------------------------------------------------------
# Test 1 (D2 — green path): clean worktree + snapshot write -> move-task OK
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev")
def test_snapshot_write_does_not_block_move_task(
    _mock_mission: Mock,
    snapshot_repo: tuple[Path, Path, str],
) -> None:
    """A bare snapshot write on a clean worktree must NOT block the transition.

    GIVEN a clean worktree on a mission with no other dirty state
    WHEN ``save_snapshot`` writes ``snapshot-latest.json``
    AND the next call is ``_validate_ready_for_review`` (the preflight
    backing ``agent tasks move-task --to for_review``)
    THEN the call succeeds (no DirtyWorktreeError-style block)
    AND the snapshot file is left in place (not deleted, not auto-committed).
    """
    repo_root, worktree, mission_slug = snapshot_repo
    feature_dir = repo_root / "kitty-specs" / mission_slug

    # The writer is intentionally unchanged — invoke it as the runtime would.
    snapshot = _make_minimal_snapshot(mission_slug)
    save_snapshot(snapshot, feature_dir)

    snapshot_path = feature_dir / ".kittify" / "dossiers" / mission_slug / "snapshot-latest.json"
    assert snapshot_path.exists(), "save_snapshot must create the snapshot file"

    # No other dirty state. Preflight must pass.
    is_valid, guidance = _validate_ready_for_review(
        repo_root=worktree,
        mission_slug=mission_slug,
        wp_id="WP01",
        force=False,
    )

    assert is_valid is True, f"Snapshot write self-blocked transition. Guidance: {guidance}"
    assert guidance == []

    # The writer must not have deleted the file or auto-committed it.
    assert snapshot_path.exists(), "Snapshot must remain on disk"
    log_result = subprocess.run(
        ["git", "log", "--all", "--oneline", "--", str(snapshot_path.relative_to(repo_root))],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert log_result.stdout.strip() == "", "Snapshot must not be auto-committed"


# ---------------------------------------------------------------------------
# Test 2 (D3 — control case): real dirty state still blocks AND names file
# ---------------------------------------------------------------------------


@patch("specify_cli.cli.commands.agent.tasks.get_mission_type", return_value="software-dev")
def test_unrelated_dirty_state_still_blocks_and_names_offender(
    _mock_mission: Mock,
    snapshot_repo: tuple[Path, Path, str],
) -> None:
    """Unrelated dirty state must STILL block; guidance names that file, not the snapshot.

    GIVEN a worktree where ``snapshot-latest.json`` was just written
    AND an unrelated source file in the worktree has uncommitted edits
    WHEN ``_validate_ready_for_review`` runs
    THEN it fails with a dirty-state error
    AND the guidance names the unrelated file
    AND the guidance does NOT name the snapshot.
    """
    repo_root, worktree, mission_slug = snapshot_repo
    feature_dir = repo_root / "kitty-specs" / mission_slug

    # Write the snapshot (the would-be self-block).
    save_snapshot(_make_minimal_snapshot(mission_slug), feature_dir)

    # Introduce a real, unrelated dirty source file in the worktree.
    offending_name = "uncommitted_source.py"
    (worktree / offending_name).write_text("# uncommitted source code\n")

    is_valid, guidance = _validate_ready_for_review(
        repo_root=worktree,
        mission_slug=mission_slug,
        wp_id="WP01",
        force=False,
    )

    assert is_valid is False, "Unrelated dirty state must still block the transition"

    guidance_text = "\n".join(guidance)
    assert offending_name in guidance_text, (
        "Guidance must name the unrelated dirty file. "
        f"Guidance was: {guidance_text!r}"
    )
    assert "snapshot-latest.json" not in guidance_text, (
        "Guidance must NOT name the dossier snapshot — the EXCLUDE policy is "
        f"compromised. Guidance was: {guidance_text!r}"
    )
