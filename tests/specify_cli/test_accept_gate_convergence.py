"""Convergence regression test for the accept gate (WP06 / T029).

Running ``spec-kitty accept`` (or the core ``collect_feature_summary`` function)
twice in the same mission state must produce the same pass/fail verdict on both
runs and must not accumulate new dirty-tree entries on the second run.

Before the fix, ``_check_lane_gates`` wrote ``acceptance-matrix.json`` during
the first run.  The second run then saw that file as a dirty-tree change,
causing a false "dirty tree" failure — a non-convergent result.  The fix:

1. The accept pipeline's own writes (``acceptance-matrix.json`` + ``status.json``)
   are excluded from the git-dirty gate — via
   ``specify_cli.acceptance._is_accept_pipeline_own_write`` (IC-07g retired the
   former ``ACCEPT_OWNED_PATHS`` filename frozenset onto the shared
   ``mission_runtime.kind_for_mission_file`` owner classifier) — so accept-owned
   artifacts do not count as unexpected dirt.
2. ``mutate_matrix`` is gated on ``not no_commit`` so ``--no-commit`` mode is
   truly read-only.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from kernel.clock import now_utc_iso
from specify_cli.acceptance import collect_feature_summary
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event

pytestmark = [pytest.mark.non_sandbox, pytest.mark.git_repo]

_FEATURE_SLUG = "099-convergence-test"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True)


def _create_minimal_feature(tmp_path: Path) -> tuple[Path, Path]:
    """Set up a minimal but complete mission suitable for acceptance testing.

    Returns (repo_root, feature_dir).
    """
    repo_root = tmp_path
    _git(repo_root, "init")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")

    feature_dir = repo_root / "kitty-specs" / _FEATURE_SLUG
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)

    # meta.json — no lanes.json so matrix checks are skipped (simplest path)
    meta: dict[str, object] = {
        "mission_number": "099",
        "slug": _FEATURE_SLUG,
        "mission_slug": _FEATURE_SLUG,
        "friendly_name": "Convergence Test",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-01-01T00:00:00Z",
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta, indent=2) + "\n")

    # Required planning artifacts
    for fname in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / fname).write_text(f"# {fname}\nDone.\n")

    # WP file with all required frontmatter fields
    wp_content = (
        "---\n"
        'work_package_id: "WP01"\n'
        'title: "Test WP"\n'
        'lane: "done"\n'
        'assignee: "test-agent"\n'
        'agent: "test-agent"\n'
        'shell_pid: "12345"\n'
        "---\n"
        "# WP01\nDone.\n"
    )
    (tasks_dir / "WP01-test.md").write_text(wp_content)

    # Status event log — WP01 forced straight to done
    from ulid import ULID

    now = now_utc_iso()
    event = StatusEvent(
        event_id=str(ULID()),
        mission_slug=_FEATURE_SLUG,
        wp_id="WP01",
        from_lane=Lane.PLANNED,
        to_lane=Lane.DONE,
        at=now,
        actor="test-agent",
        force=True,
        execution_mode="direct_repo",
        reason="Test setup: skip to done",
    )
    seed_status_event(feature_dir, event)

    # Pre-materialize status.json so it is part of the committed state and the
    # second run does not see it as an unexpected dirty artifact.
    from specify_cli.status.reducer import materialize

    materialize(feature_dir)

    # Initial commit — clean tree
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "init")

    return repo_root, feature_dir


def _dirty_paths(repo_root: Path) -> list[str]:
    """Return porcelain dirty lines from git status."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), "status", "--porcelain"],
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line.strip()]


def test_accept_gate_convergence_two_runs_produce_same_verdict(tmp_path: Path) -> None:
    """Two consecutive collect_feature_summary calls must agree on pass/fail.

    Before the fix, the second call would see accept-owned files written by the
    first call (acceptance-matrix.json, status.json) as dirty-tree changes and
    return a different (failing) summary even though mission state was unchanged.
    """
    repo_root, _feature_dir = _create_minimal_feature(tmp_path)

    # First run
    summary1 = collect_feature_summary(
        repo_root,
        _FEATURE_SLUG,
        strict_metadata=False,
        mutate_matrix=True,
    )

    # Second run — same state, must produce same verdict
    summary2 = collect_feature_summary(
        repo_root,
        _FEATURE_SLUG,
        strict_metadata=False,
        mutate_matrix=True,
    )

    assert summary1.ok == summary2.ok, (
        f"First run ok={summary1.ok}, second run ok={summary2.ok}. "
        f"Run 1 git_dirty={summary1.git_dirty}, activity={summary1.activity_issues}. "
        f"Run 2 git_dirty={summary2.git_dirty}, activity={summary2.activity_issues}."
    )


def test_accept_gate_second_run_no_unexpected_dirty_files(tmp_path: Path) -> None:
    """After two accept runs, no unexpected dirty files should remain.

    Accept-owned artifacts (acceptance-matrix.json, status.json) are written by
    the pipeline and must not appear as unexpected dirt on the second run's
    git-dirty gate.
    """
    repo_root, _feature_dir = _create_minimal_feature(tmp_path)

    dirty_before = _dirty_paths(repo_root)

    # Run accept twice
    collect_feature_summary(
        repo_root,
        _FEATURE_SLUG,
        strict_metadata=False,
        mutate_matrix=True,
    )
    collect_feature_summary(
        repo_root,
        _FEATURE_SLUG,
        strict_metadata=False,
        mutate_matrix=True,
    )

    dirty_after = _dirty_paths(repo_root)

    # The working tree may have accept-owned artifacts written (expected), but
    # the second summary's git_dirty gate must not flag them — verified above by
    # the convergence test.  Here we check the raw porcelain count does not
    # include files outside the accept-owned set. ``ACCEPT_OWNED_PATHS`` was
    # retired (IC-07g); this basename pair is the test's own oracle, not an
    # import of production exemption state.
    accept_owned_basenames = ("acceptance-matrix.json", "status.json")

    unexpected_dirty = [
        line
        for line in dirty_after
        if line not in dirty_before
        and not any(line.endswith(owned) for owned in accept_owned_basenames)
    ]
    assert unexpected_dirty == [], (
        f"Unexpected dirty files after two accept runs: {unexpected_dirty}"
    )


def test_accept_dirty_gate_keeps_unrelated_status_json_dirty(tmp_path: Path) -> None:
    """Only the current mission's accept-owned status files are filtered."""
    repo_root, _feature_dir = _create_minimal_feature(tmp_path)

    other_status = repo_root / "kitty-specs" / "other-mission" / "status.json"
    other_status.parent.mkdir(parents=True)
    other_status.write_text('{"lane": "planned"}\n', encoding="utf-8")
    _git(repo_root, "add", "kitty-specs/other-mission/status.json")
    _git(repo_root, "commit", "-m", "seed unrelated status")

    other_status.write_text('{"lane": "locally-edited"}\n', encoding="utf-8")

    summary = collect_feature_summary(
        repo_root,
        _FEATURE_SLUG,
        strict_metadata=False,
        mutate_matrix=True,
    )

    assert any("kitty-specs/other-mission/status.json" in line for line in summary.git_dirty)
    assert summary.ok is False
