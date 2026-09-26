"""Seam test for ``specify_cli.merge.bookkeeping_projection`` (mission #2057, WP09).

Covers the security-sensitive path-trust assertions (trusted AND rejected
branches) and the surviving coord→target projection helpers. The
final-bookkeeping snapshot/restore compensator that used to live in this module
was RETIRED by the lifecycle-gate-execution-context mission (WP09 / T048 / TAO-3):
the merge executor now enrols its bytes with the SINGLE owner compensator in
``coordination.atomic_write``, so the compensator round-trip / trust tests below
re-point onto that owner surface (same byte-identical semantics). The
re-export-identity and one-way-import guards live in the consolidated
``tests/merge/test_merge_compat_surface.py``.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.coordination import atomic_write as aw
from specify_cli.core.constants import KITTY_SPECS_DIR
from specify_cli.merge import bookkeeping_projection as bp
from specify_cli.merge.git_probes import GitProbeError, driver_replay_expected_bytes

pytestmark = pytest.mark.fast


def test_restore_generated_artifact_snapshots_signature_stable() -> None:
    """TAO-3: the ONE owner compensator restores from a single dict positional arg."""
    import inspect

    sig = inspect.signature(aw.restore_generated_artifact_snapshots)
    params = list(sig.parameters)
    assert params[0] == "snapshots"


# --- _validate_mission_slug_path_segment ------------------------------------


def test_validate_mission_slug_accepts_safe_segment() -> None:
    assert bp._validate_mission_slug_path_segment("my-mission-01ABC") == "my-mission-01ABC"


def test_validate_mission_slug_rejects_traversal() -> None:
    with pytest.raises(ValueError):
        bp._validate_mission_slug_path_segment("../escape")


# --- snapshot capture / restore round-trip ----------------------------------


def _repo_with_spec(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    (repo / KITTY_SPECS_DIR / "m").mkdir(parents=True)
    return repo


def test_capture_and_restore_round_trip(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    events = repo / KITTY_SPECS_DIR / "m" / "status.events.jsonl"
    events.write_text("ORIGINAL\n", encoding="utf-8")

    roots = [repo / KITTY_SPECS_DIR]
    snapshots = aw.capture_generated_artifact_snapshots(events, trusted_roots=roots)
    # Mutate, then restore through the single owner compensator.
    events.write_text("MUTATED\n", encoding="utf-8")
    aw.restore_generated_artifact_snapshots(snapshots)
    assert events.read_text(encoding="utf-8") == "ORIGINAL\n"


def test_capture_restore_recreates_deleted_file(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    events = repo / KITTY_SPECS_DIR / "m" / "status.events.jsonl"
    # Absent at capture time -> snapshot is None -> restore must remove it.
    roots = [repo / KITTY_SPECS_DIR]
    snapshots = aw.capture_generated_artifact_snapshots(events, trusted_roots=roots)
    events.write_text("CREATED-AFTER-CAPTURE\n", encoding="utf-8")
    aw.restore_generated_artifact_snapshots(snapshots)
    assert not events.exists()


# --- path-trust: trusted + rejected branches (owner containment) -------------


def test_snapshot_trust_accepts_kitty_specs(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    candidate = repo / KITTY_SPECS_DIR / "m" / "status.json"
    snapshots = aw.capture_generated_artifact_snapshots(
        candidate, trusted_roots=[repo / KITTY_SPECS_DIR]
    )
    assert candidate.resolve(strict=False) in snapshots


def test_snapshot_trust_rejects_outside_path(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    outside = tmp_path / "elsewhere" / "evil.json"
    with pytest.raises(ValueError):
        aw.capture_generated_artifact_snapshots(
            outside, trusted_roots=[repo / KITTY_SPECS_DIR]
        )


def test_status_surface_trust_accepts_kitty_specs(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    surface = repo / KITTY_SPECS_DIR / "m"
    with patch.object(bp, "get_main_repo_root", lambda _r: repo):
        trusted = bp._assert_status_surface_path_is_trusted(repo_root=repo, status_feature_dir=surface)
    assert trusted == surface.resolve()


def test_status_surface_trust_rejects_topology_mismatch(tmp_path: Path) -> None:
    """A worktrees-shaped segment that resolves outside the worktrees root is rejected."""
    repo = _repo_with_spec(tmp_path)
    # A path under kitty-specs but named like a worktrees path is a mismatch.
    bogus = repo / "not-real-root" / "x"
    with (
        patch.object(bp, "get_main_repo_root", lambda _r: repo),
        pytest.raises(ValueError, match="Untrusted status surface path"),
    ):
        bp._assert_status_surface_path_is_trusted(repo_root=repo, status_feature_dir=bogus)


def test_status_surface_file_trust_rejects_bad_filename(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    surface = repo / KITTY_SPECS_DIR / "m"
    with (
        patch.object(bp, "get_main_repo_root", lambda _r: repo),
        pytest.raises(ValueError, match="Refusing untrusted status filename"),
    ):
        bp._assert_status_surface_file_path_is_trusted(
            repo_root=repo, status_feature_dir=surface, filename="evil.txt"
        )


# --- _target_branch_still_at_baseline ---------------------------------------


def test_target_branch_still_at_baseline(tmp_path: Path) -> None:
    assert bp._target_branch_still_at_baseline(tmp_path, "main", "") is False
    assert bp._target_branch_still_at_baseline(tmp_path, "main", "HEAD~1") is False
    with patch.object(bp, "run_command", return_value=(0, "abc123", "")):
        assert bp._target_branch_still_at_baseline(tmp_path, "main", "abc123") is True
        assert bp._target_branch_still_at_baseline(tmp_path, "main", "deadbeef") is False
    with patch.object(bp, "run_command", return_value=(1, "", "err")):
        assert bp._target_branch_still_at_baseline(tmp_path, "main", "abc123") is False


# --- _project_status_bookkeeping_to_target (non-worktree fast path) ----------


def test_project_returns_target_paths_when_not_worktree(tmp_path: Path) -> None:
    repo = _repo_with_spec(tmp_path)
    surface = repo / KITTY_SPECS_DIR / "m"
    with patch.object(bp, "get_main_repo_root", lambda _r: repo):
        events, status = bp._project_status_bookkeeping_to_target(
            main_repo=repo, mission_slug="m", status_feature_dir=surface
        )
    assert events.name == "status.events.jsonl"
    assert status.name == "status.json"


# --- driver-replay attribution probe (#5038, terminus-projection-driver-replay) --
#
# Real, on-disk git repos throughout (no git-layer mocking): the probe shells out
# to ``git show``/``git check-attr`` and invokes the ACTUAL registered
# ``cli.commands.merge_driver`` implementations, so a mock would prove nothing
# about whether the replay genuinely matches what a real squash would do.


def _driver_git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True)


def _driver_rev(repo: Path, ref: str) -> str:
    return _driver_git(repo, "rev-parse", ref).stdout.strip()


def _init_driver_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "driver-repo"
    repo.mkdir()
    _driver_git(repo, "init", "-q", "-b", "main")
    _driver_git(repo, "config", "user.email", "t@example.com")
    _driver_git(repo, "config", "user.name", "Test")
    _driver_git(repo, "config", "commit.gpgsign", "false")
    (repo / "README.md").write_text("seed\n", encoding="utf-8")
    _driver_git(repo, "add", "-A")
    _driver_git(repo, "commit", "-q", "-m", "seed")
    return repo


def _commit_trace(repo: Path, trace_rel: str, body: str, msg: str) -> None:
    path = repo / trace_rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    _driver_git(repo, "add", "-A")
    _driver_git(repo, "commit", "-q", "-m", msg)


@pytest.mark.git_repo
def test_driver_replay_pass_on_lossless_union(tmp_path: Path) -> None:
    """FR-001: a diverged, driver-governed path PASSes when the landed blob IS
    the registered driver's own replayed output (a legitimate lossless union)."""
    repo = _init_driver_repo(tmp_path)
    trace_rel = "kitty-specs/m/traces/WP01.md"
    _commit_trace(repo, trace_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")

    _commit_trace(repo, trace_rel, "baseline\ntarget edit\n", "target update")
    pre_squash_target = _driver_rev(repo, "main")

    _driver_git(repo, "branch", "coord", checkpoint)
    _driver_git(repo, "checkout", "-q", "coord")
    _commit_trace(repo, trace_rel, "baseline\ncoord edit\n", "coord update")
    _driver_git(repo, "checkout", "-q", "main")

    expected = driver_replay_expected_bytes(
        repo, trace_rel, base_ref=checkpoint, ours_ref=pre_squash_target, theirs_ref="coord"
    )
    landed_path = repo / trace_rel
    landed_path.write_bytes(expected)
    _driver_git(repo, "add", "-A")
    _driver_git(repo, "commit", "-q", "-m", "landed the driver's real output")

    assert bp.projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(trace_rel,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash_target,
    )


@pytest.mark.git_repo
def test_driver_replay_refuses_on_dropped_content(tmp_path: Path) -> None:
    """FR-002 / INV-FLOOR-1: REFUSE when the landed blob is NOT the driver's
    replayed output -- here the target's own edit is silently dropped."""
    repo = _init_driver_repo(tmp_path)
    trace_rel = "kitty-specs/m/traces/WP01.md"
    _commit_trace(repo, trace_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")

    _commit_trace(repo, trace_rel, "baseline\ntarget edit\n", "target update")
    pre_squash_target = _driver_rev(repo, "main")

    _driver_git(repo, "branch", "coord", checkpoint)
    _driver_git(repo, "checkout", "-q", "coord")
    _commit_trace(repo, trace_rel, "baseline\ncoord edit\n", "coord update")
    _driver_git(repo, "checkout", "-q", "main")

    # Genuinely-lossy landing: coord bytes verbatim, dropping the target edit --
    # NOT what the union driver would ever produce.
    _commit_trace(repo, trace_rel, "baseline\ncoord edit\n", "genuinely-lossy landing")

    assert not bp.projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(trace_rel,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash_target,
    )


@pytest.mark.git_repo
def test_driver_replay_refuses_when_no_registered_driver(tmp_path: Path) -> None:
    """FR-003 / INV-FLOOR-2: a diverged path with NO registered merge driver
    REFUSEs fail-closed rather than passing vacuously."""
    repo = _init_driver_repo(tmp_path)
    notes_rel = "kitty-specs/m/notes/some-note.md"  # not in _MERGE_DRIVERS' patterns
    _commit_trace(repo, notes_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")

    _commit_trace(repo, notes_rel, "baseline\ntarget edit\n", "target update")
    pre_squash_target = _driver_rev(repo, "main")

    _driver_git(repo, "branch", "coord", checkpoint)
    _driver_git(repo, "checkout", "-q", "coord")
    _commit_trace(repo, notes_rel, "baseline\ncoord edit\n", "coord update")
    _driver_git(repo, "checkout", "-q", "main")

    # Whatever a real, driver-less squash would land here, the proof cannot
    # evaluate it (no registered driver to replay) -- REFUSE, never PASS.
    _commit_trace(repo, notes_rel, "baseline\ntarget edit\ncoord edit\n", "auto-merged landing")

    assert not bp.projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(notes_rel,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash_target,
    )


@pytest.mark.git_repo
def test_driver_replay_probe_raises_on_missing_blob(tmp_path: Path) -> None:
    """FR-003: the probe itself REFUSEs fail-closed (raises ``GitProbeError``)
    when the ``theirs`` blob cannot be read at the given ref."""
    repo = _init_driver_repo(tmp_path)
    seed_sha = _driver_rev(repo, "main")  # the file does not exist yet here
    trace_rel = "kitty-specs/m/traces/WP01.md"
    _commit_trace(repo, trace_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")
    _commit_trace(repo, trace_rel, "baseline\ntarget edit\n", "target update")
    pre_squash_target = _driver_rev(repo, "main")

    with pytest.raises(GitProbeError):
        # ``seed_sha`` predates the file's existence -- absent as ``theirs``.
        driver_replay_expected_bytes(
            repo, trace_rel, base_ref=checkpoint, ours_ref=pre_squash_target, theirs_ref=seed_sha
        )


@pytest.mark.git_repo
def test_driver_replay_preserves_non_diverged_pass(tmp_path: Path) -> None:
    """FR-004 / INV-NO-REGRESSION: a path the target never touched after the
    checkpoint keeps PASSing via the original byte-equality proof -- no driver
    lookup needed at all (proven with a path that has none registered)."""
    repo = _init_driver_repo(tmp_path)
    notes_rel = "kitty-specs/m/notes/some-note.md"
    _commit_trace(repo, notes_rel, "baseline\n", "checkpoint")
    checkpoint = _driver_rev(repo, "main")
    # Target never diverges: its pre-squash tip IS the checkpoint.
    pre_squash_target = checkpoint

    _driver_git(repo, "branch", "coord", checkpoint)
    _driver_git(repo, "checkout", "-q", "coord")
    _commit_trace(repo, notes_rel, "baseline\ncoord-only addition\n", "coord update")
    _driver_git(repo, "checkout", "-q", "main")

    # The coord content lands verbatim (no divergence to reconcile).
    _commit_trace(repo, notes_rel, "baseline\ncoord-only addition\n", "project coord content")

    assert bp.projected_content_matches_target(
        main_repo=repo,
        coord_ref="coord",
        target_ref="main",
        projected_paths=(notes_rel,),
        checkpoint_sha=checkpoint,
        pre_squash_target_ref=pre_squash_target,
    )
