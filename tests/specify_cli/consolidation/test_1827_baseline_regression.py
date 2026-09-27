"""Regression tests for #1827 — post-merge baseline ordering.

Issue #1827: `spec-kitty merge` completed the merge then errored
``baseline_merge_commit is missing from committed meta.json on main`` because
the validation ran *before* the tool wrote the field.  Re-running re-merged and
failed identically (circular, unrecoverable).

Debbie's live repro on HEAD (see research/live-repro.md §#1827) confirmed the
ordering is **structurally fixed**:

* ``_record_baseline_merge_commit`` writes the baseline into the working
  ``meta.json`` BEFORE the bookkeeping commit; the helper is idempotent
  (skips if already set).
* ``_assert_baseline_merge_commit_on_target`` reads the **recorded** value from
  the working ``meta.json`` via ``_recorded_baseline_from_working_meta``, not a
  freshly re-derived HEAD — so a resume/re-run after HEAD has advanced past the
  original baseline does not spuriously fail.

Disposition (FR-012 / D-3): verified-already-fixed.  These tests lock the
correct ordering as a regression guard.  No ``src/`` file is modified.

Tests
-----
T035 — full record→commit→assert + resume/re-run (passes on HEAD)
T036 — falsification guard: broken ordering raises the exact #1827 error
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.cli.commands.consolidate import (
    BaselineMergeCommitError,
    _assert_baseline_merge_commit_on_target,
    _record_baseline_merge_commit,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

# ---------------------------------------------------------------------------
# Topology-true constants (Debbie's repro shape: full 26-char ULID mission_id)
# ---------------------------------------------------------------------------

_MISSION_ID = "01KV8NPCDEBBIE1827REPRO000"
_MISSION_SLUG = "merge-baseline-repro-01kv8npc"
_TARGET_BRANCH = "main"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> str:
    """Run a git command rooted at *repo_root*; return stdout stripped."""
    result = subprocess.run(
        ["git", "-C", str(repo_root), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_meta(feature_dir: Path, *, extra: dict[str, object] | None = None) -> None:
    """Write a topology-true meta.json with a full 26-char ULID mission_id.

    ``baseline_merge_commit`` is intentionally absent on first write —
    that is the starting state #1827 described (the field must not exist until
    ``_record_baseline_merge_commit`` writes it).
    """
    feature_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "created_at": "2026-06-16T00:00:00+00:00",
        "friendly_name": "Merge Baseline Repro",
        "mission_id": _MISSION_ID,
        "mission_number": None,
        "mission_slug": _MISSION_SLUG,
        "mission_type": "software-dev",
        "slug": _MISSION_SLUG,
        "target_branch": _TARGET_BRANCH,
    }
    if extra:
        meta.update(extra)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _bootstrap_repo(tmp_path: Path) -> tuple[Path, Path, str]:
    """Create a real git repo with a modern mission on the target branch.

    Returns:
        (repo_root, feature_dir, initial_commit_sha)

    The initial commit carries ``kitty-specs/<slug>/meta.json`` WITHOUT
    ``baseline_merge_commit`` — the pre-merge state that triggers #1827 when
    the ordering is wrong.
    """
    repo_root = tmp_path
    _git(repo_root, "init", "-b", _TARGET_BRANCH)
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")

    feature_dir = repo_root / "kitty-specs" / _MISSION_SLUG
    _write_meta(feature_dir)

    _git(repo_root, "add", str(feature_dir / "meta.json"))
    _git(repo_root, "commit", "-m", "initial: modern mission (no baseline yet)")
    initial_sha = _git(repo_root, "rev-parse", "HEAD")

    return repo_root, feature_dir, initial_sha


# ---------------------------------------------------------------------------
# T035 — full record→commit→assert + resume/re-run regression test
# ---------------------------------------------------------------------------


def test_1827_full_sequence_passes_on_head(tmp_path: Path) -> None:
    """T035 — #1827 full record→commit→assert sequence passes on HEAD.

    Steps:
    1. _record_baseline_merge_commit — writes baseline into working meta.json.
    2. Bookkeeping commit — carries meta.json (with baseline) to target branch.
    3. _assert_baseline_merge_commit_on_target — reads committed value; MUST NOT raise.

    This is the correct ordering that HEAD implements; it locks the fix as a
    regression guard (FR-012, C-FR012, D-3).
    """
    repo_root, feature_dir, initial_sha = _bootstrap_repo(tmp_path)

    # Step 1: record baseline into working meta.json.
    meta_path = _record_baseline_merge_commit(
        feature_dir,
        initial_sha,
        mission_id=_MISSION_ID,
    )
    assert meta_path == feature_dir / "meta.json"
    working_meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert working_meta["baseline_merge_commit"] == initial_sha

    # Step 2: bookkeeping commit — carries the updated meta.json to the target branch.
    _git(repo_root, "add", str(feature_dir / "meta.json"))
    _git(repo_root, "commit", "-m", "merge: bookkeeping — record baseline_merge_commit")
    bookkeeping_sha = _git(repo_root, "rev-parse", "HEAD")

    # Step 3: assert — must NOT raise BaselineMergeCommitError.
    _assert_baseline_merge_commit_on_target(
        repo_root,
        _MISSION_SLUG,
        _TARGET_BRANCH,
        initial_sha,
        feature_dir=feature_dir,
        mission_id=_MISSION_ID,
    )

    assert bookkeeping_sha != initial_sha  # sanity: HEAD advanced


def test_1827_resume_rerun_idempotent_and_passes(tmp_path: Path) -> None:
    """T035 resume/re-run leg: HEAD advanced past baseline; record+assert still pass.

    After the first merge run:
    - working meta.json already carries ``baseline_merge_commit = initial_sha``.
    - HEAD has advanced past initial_sha (bookkeeping commit landed).

    On ``spec-kitty merge --resume`` the live HEAD is now ``bookkeeping_sha``,
    NOT ``initial_sha``.  The re-run must:
    a. Keep the ORIGINAL recorded baseline (not overwrite with the advanced HEAD).
    b. Pass the assert by reading the recorded value, not re-deriving HEAD.

    This is the circular-failure scenario from #1827 under the broken ordering.
    Under the FIXED ordering it passes because ``_record_baseline_merge_commit``
    is idempotent and ``_assert_baseline_merge_commit_on_target`` reads the
    recorded value from working meta.json.
    """
    repo_root, feature_dir, initial_sha = _bootstrap_repo(tmp_path)

    # --- First run: record + commit ---
    _record_baseline_merge_commit(feature_dir, initial_sha, mission_id=_MISSION_ID)
    _git(repo_root, "add", str(feature_dir / "meta.json"))
    _git(repo_root, "commit", "-m", "merge: bookkeeping — record baseline_merge_commit")
    bookkeeping_sha = _git(repo_root, "rev-parse", "HEAD")

    # Confirm HEAD advanced past the original baseline.
    assert bookkeeping_sha != initial_sha

    # --- Resume leg: re-run record with the ADVANCED head as input ---
    # The idempotent guard must keep initial_sha, not write bookkeeping_sha.
    result = _record_baseline_merge_commit(
        feature_dir,
        bookkeeping_sha,  # re-derived HEAD on resume — must be ignored
        mission_id=_MISSION_ID,
    )
    assert result is None, (
        "_record_baseline_merge_commit must return None when baseline already recorded "
        "(idempotency: do not overwrite with the advanced HEAD)"
    )

    # Confirm working meta still carries the ORIGINAL baseline, not the advanced HEAD.
    working_meta = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert working_meta["baseline_merge_commit"] == initial_sha, (
        "Idempotency violated: working meta.json must retain the original recorded "
        "baseline even after re-running with the advanced HEAD as input"
    )

    # Resume assert with the ADVANCED HEAD as expected_baseline — must NOT raise.
    # feature_dir supplies the recorded value, which overrides the live expected_baseline.
    _assert_baseline_merge_commit_on_target(
        repo_root,
        _MISSION_SLUG,
        _TARGET_BRANCH,
        bookkeeping_sha,  # re-derived live HEAD — must be overridden by recorded value
        feature_dir=feature_dir,
        mission_id=_MISSION_ID,
    )


# ---------------------------------------------------------------------------
# T036 — falsification guard: broken ordering raises the exact #1827 error
# ---------------------------------------------------------------------------


def test_1827_falsification_guard_broken_ordering_raises(tmp_path: Path) -> None:
    """T036 — broken ordering raises BaselineMergeCommitError with the #1827 message.

    Reproduces the exact failure mode from #1827:
    - meta.json is committed to the target branch WITHOUT ``baseline_merge_commit``
      (as if _record_baseline_merge_commit had not yet run, or run after the commit).
    - _assert_baseline_merge_commit_on_target runs BEFORE the bookkeeping commit
      that would carry the field to the target branch.

    Debbie's falsification harness confirmed this ordering produces the exact
    error string.  This test pins that behavior so future regressions are caught.
    """
    repo_root, feature_dir, initial_sha = _bootstrap_repo(tmp_path)

    # The broken ordering: assert BEFORE the bookkeeping commit lands the field.
    # At this point the committed meta.json on target does NOT carry
    # ``baseline_merge_commit`` — the initial commit never had it.
    #
    # We pass feature_dir=None to suppress the recorded-value path (simulates
    # the broken calling sequence where the record step ran but the commit did
    # not yet land on the target branch, so the committed copy is stale).
    with pytest.raises(BaselineMergeCommitError) as exc_info:
        _assert_baseline_merge_commit_on_target(
            repo_root,
            _MISSION_SLUG,
            _TARGET_BRANCH,
            initial_sha,
            feature_dir=None,  # no recorded value — forces use of committed copy
            mission_id=_MISSION_ID,
        )

    error_message = str(exc_info.value)
    assert "baseline_merge_commit is missing from committed" in error_message, (
        f"Exact #1827 error substring not found in: {error_message!r}"
    )
    assert "meta.json" in error_message, (
        f"Expected 'meta.json' in error message: {error_message!r}"
    )
    assert f"on {_TARGET_BRANCH}" in error_message, (
        f"Expected 'on {_TARGET_BRANCH}' in error message: {error_message!r}"
    )
