"""Regression: the backfill cutover guard must be invoking-checkout-aware.

Mission ``worktree-root-resolution-01M0B59R`` WP05 (FR-005; issue #3049).

The defect (#3049): invoked from a foreign lane worktree, ``verify_backfill``
canonicalizes ``feature_dir`` to the primary/coord checkout — the deliberate
C-003 write target — and then READS that same redirected path, so the cutover
guard passes regardless of which checkout invoked it (a false-green).

These tests build a REAL primary checkout plus a REAL linked lane worktree
(``git init`` / ``git worktree add`` subprocesses — no mocked git output,
mirroring the WP01 house pattern in ``tests/specify_cli/core/
test_checkout_identity.py``) and prove:

* the foreign lane invocation is now refused (fail-closed, naming the checkout),
  instead of passing merely by reading the redirected path; and
* the owner (primary) invocation is unchanged — no new refusal.

The write target itself is deliberately primary/coord and is NOT changed here
(C-003 / ``canonicalize_feature_dir`` "never ``Path.cwd``"): only the guard's
false-green is the defect.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.core.checkout_identity import Intent
from specify_cli.migration.backfill_runtime_state import verify_backfill
from specify_cli.migration.runtime_state_cutover import cutover_mission
from specify_cli.workspace import canonicalize_feature_dir

# Tier markers only: ``regression`` is applied per test to the two #3049 pins
# below (tests/regression/README.md), never module-wide.
pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

MISSION_SLUG = "demo-mission-01ABCDEF"
MISSION_ID = "01ABCDEFGHJKMNPQRSTVWXYZ00"


def _run_git(args: list[str], cwd: Path) -> None:
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )


def _init_repo(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    _run_git(["init"], cwd=path)
    _run_git(["config", "user.email", "test@example.com"], cwd=path)
    _run_git(["config", "user.name", "Test User"], cwd=path)
    (path / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    _run_git(["add", "README.md"], cwd=path)
    _run_git(["commit", "-m", "Initial commit"], cwd=path)
    _run_git(["branch", "-M", "main"], cwd=path)
    return path


@pytest.fixture
def primary(tmp_path: Path) -> Path:
    """A real primary git repo carrying a single, already-verifying mission.

    The mission has a ``mission_id`` + an (empty) event log and no legacy
    ``tasks/`` runtime, so ``verify_backfill`` legitimately returns ``ok`` when
    read from the checkout that OWNS it — the clean substrate against which the
    foreign-lane false-green stands out.
    """
    repo = _init_repo(tmp_path / "primary")
    mission = repo / "kitty-specs" / MISSION_SLUG
    mission.mkdir(parents=True)
    (mission / "meta.json").write_text(
        json.dumps({"mission_id": MISSION_ID, "mission_slug": MISSION_SLUG}),
        encoding="utf-8",
    )
    (mission / "status.events.jsonl").write_text("", encoding="utf-8")
    _run_git(["add", "-A"], cwd=repo)
    _run_git(["commit", "-m", "seed mission"], cwd=repo)
    return repo


@pytest.fixture
def lane_worktree(primary: Path, tmp_path: Path) -> Path:
    """A real linked worktree of ``primary`` (its ``.git`` is a pointer file)."""
    wt = tmp_path / "lane-a"
    _run_git(["worktree", "add", "-b", "lane-a", str(wt)], cwd=primary)
    return wt


def _primary_feature_dir(primary: Path) -> Path:
    return primary / "kitty-specs" / MISSION_SLUG


def _lane_feature_dir(lane_worktree: Path) -> Path:
    return lane_worktree / "kitty-specs" / MISSION_SLUG


@pytest.mark.regression
def test_foreign_lane_write_guard_refuses_false_green(primary: Path, lane_worktree: Path) -> None:
    """#3049: the foreign-lane cutover WRITE guard must fail closed on the redirect.

    RED on ``upstream/main``: the unfixed guard returns ``ok=True`` here because
    it reads the same redirected primary path it would write (the cutover flow
    threads ``Intent.WRITE`` — modelled directly here). GREEN after the fix: it
    fails closed and the message names the checkout it declined to act on.
    """
    lane_feature_dir = _lane_feature_dir(lane_worktree)
    primary_feature_dir = _primary_feature_dir(primary)

    # Precondition — this is exactly the false-green condition: canonicalization
    # redirects the lane read to the primary (the deliberate C-003 write target).
    assert canonicalize_feature_dir(lane_feature_dir) == primary_feature_dir
    assert canonicalize_feature_dir(lane_feature_dir) != lane_feature_dir

    result = verify_backfill(lane_feature_dir, intent=Intent.WRITE)

    assert result.ok is False
    assert result.mismatches
    joined = " ".join(result.mismatches)
    assert "does not own" in joined
    # The refusal names the canonical target checkout (the primary) verbatim —
    # the deliberate write target, which this WP leaves unchanged.
    assert str(primary.resolve()) in joined


@pytest.mark.regression
def test_foreign_lane_cutover_flow_no_longer_false_flips(primary: Path, lane_worktree: Path) -> None:
    """End-to-end: the real cutover flow (``cutover_mission``) refuses the lane.

    RED on ``upstream/main``: invoked with a lane-rooted ``feature_dir`` the
    cutover verify passes on the redirected read and the mission flips. GREEN
    after the fix: the WRITE-guarded verify fails closed, so ``cutover_mission``
    returns ``flipped=False`` — a lane invocation can no longer complete the
    cutover it does not own.
    """
    result = cutover_mission(_lane_feature_dir(lane_worktree))

    assert result.flipped is False
    assert result.verify is not None
    assert result.verify.ok is False


def test_owner_primary_write_guard_still_verifies(primary: Path) -> None:
    """The owner (primary) WRITE invocation is unchanged — no new refusal.

    GREEN before AND after the fix: the checkout that owns the mission verifies
    exactly as it did prior to the guard gaining identity awareness (INV, C-003).
    """
    result = verify_backfill(_primary_feature_dir(primary), intent=Intent.WRITE)

    assert result.ok is True
    assert result.mismatches == ()


def test_read_only_lane_verify_is_not_refused(primary: Path, lane_worktree: Path) -> None:
    """A bare read-only verify (``PRIMARY_READ``, the default) is never refused.

    The ``is_cut_over`` doctor reads the deliberate primary anchor from wherever
    it runs — including a worktree — and must keep working; only a WRITE-guarding
    verify gains the fail-closed refusal (WP01 INV-2).
    """
    result = verify_backfill(_lane_feature_dir(lane_worktree))

    assert result.ok is True
    assert result.mismatches == ()


def test_write_target_is_unchanged_by_the_guard(primary: Path, lane_worktree: Path) -> None:
    """Risk mitigation: the guard change never redirects the write target.

    The canonical target for a lane read stays the primary/coord mission dir
    (C-003) both before and after the refusal — the guard only refuses to
    *bless* the redirected read; it does not move where a write would land, and
    it writes nothing itself.
    """
    lane_feature_dir = _lane_feature_dir(lane_worktree)
    primary_feature_dir = _primary_feature_dir(primary)

    # The deliberate write target is still the primary mission dir (C-003) —
    # the guard refuses to *bless* the redirected read, it does not move the
    # target away from the primary.
    assert canonicalize_feature_dir(lane_feature_dir) == primary_feature_dir

    # The guard is read-only: the (refused) WRITE-guarding verify writes nothing
    # — the primary event log it would have blessed is untouched.
    verify_backfill(lane_feature_dir, intent=Intent.WRITE)
    assert (primary_feature_dir / "status.events.jsonl").read_text(encoding="utf-8") == ""
