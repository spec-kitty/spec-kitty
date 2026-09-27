"""Unit tests for the lifecycle-phase reader (WP03, T008/T013).

Mission ``post-merge-write-authoring-finish-01KYRRM5`` (FR-001, D2, C-003).

:func:`mission_runtime.lifecycle_phase.resolve_lifecycle_phase` derives a
mission's :class:`~mission_runtime.lifecycle_phase.LifecyclePhase` from
durable signals alone (``baseline_merge_commit`` + Target Ref branch
existence + terminal-completion evidence). These tests build REAL git repos
(never mocked) through the actual merge-time bookkeeping entry point
(:func:`specify_cli.consolidation.baseline.record_baseline_merge_commit`) so the
fixtures are the same shape ``spec-kitty merge`` produces, mirroring the
WP02 red-pin fixtures (``tests/regression/test_issue_3033_post_consolidation_
write.py``).

Also covers the D1 squash-robust content-presence predicate
(:func:`~mission_runtime.lifecycle_phase.content_present_at_primary_tip`),
including the exit-1-vs-exit-128 distinction (renata B1).
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from mission_runtime.lifecycle_phase import (
    LifecyclePhase,
    LifecyclePhaseProbeError,
    content_present_at_primary_tip,
    resolve_lifecycle_phase,
)
from specify_cli.mission_metadata import load_meta, write_meta
from specify_cli.consolidation.baseline import record_baseline_merge_commit

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]


# ---------------------------------------------------------------------------
# Real-git plumbing helpers (mirrors tests/regression/test_issue_3033_*)
# ---------------------------------------------------------------------------


def _run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), check=True, capture_output=True, text=True)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return _run(["git", "-C", str(repo), *args], cwd=repo)


def _init_git_repo(repo: Path) -> str:
    """Real ``git init`` on ``main``. Returns the initial commit SHA."""
    repo.mkdir(parents=True, exist_ok=True)
    _run(["git", "init", "-qb", "main", str(repo)], cwd=repo)
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / ".kittify").mkdir()
    (repo / ".kittify" / "config.json").write_text("{}\n", encoding="utf-8")
    (repo / "README.md").write_text("# repo\n", encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "init")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def _write_meta(
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    mid8: str,
    target_branch: str,
) -> None:
    meta: dict[str, object] = {
        "mission_slug": mission_slug,
        "mission_id": mission_id,
        "mid8": mid8,
        "mission_number": None,
        "mission_type": "software-dev",
        "target_branch": target_branch,
        "topology": "single_branch",
        "friendly_name": "Lifecycle phase reader fixture",
    }
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _done_event(mission_slug: str, wp_id: str) -> dict[str, object]:
    return {
        "actor": "reviewer-renata",
        "at": "2026-07-30T12:00:00+00:00",
        "event_id": f"01HXYZLIFEPHASE00000{wp_id}",
        "evidence": None,
        "execution_mode": "worktree",
        "feature_slug": mission_slug,
        "force": False,
        "from_lane": "approved",
        "reason": None,
        "review_ref": None,
        "to_lane": "done",
        "wp_id": wp_id,
    }


def _build_mission(
    repo: Path, *, mid8: str, slug_base: str
) -> tuple[str, Path, str]:
    """Scaffold a mission with its own Target Ref (branch), pre-consolidation.

    Returns ``(mission_slug, feature_dir, target_branch)``.
    """
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"{slug_base}-{mid8}"
    target_branch = f"kitty/mission-{mission_slug}"

    _git(repo, "checkout", "-q", "-b", target_branch)
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=target_branch,
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): mission scaffold")
    return mission_slug, feature_dir, target_branch


def _consolidate_e1(
    repo: Path,
    feature_dir: Path,
    *,
    mission_slug: str,
    mission_id: str,
    baseline_commit: str,
    mission_number: int | None,
) -> None:
    """Bake ``baseline_merge_commit`` (+ optionally ``mission_number``) via
    the REAL merge-bookkeeping entry point, then commit — the durable E1
    signal a genuine ``spec-kitty merge`` consolidation produces."""
    record_baseline_merge_commit(feature_dir, baseline_commit, mission_id=mission_id)
    if mission_number is not None:
        meta = load_meta(feature_dir)
        assert meta is not None
        meta["mission_number"] = mission_number
        write_meta(feature_dir, meta, validate=False)
    _git(repo, "add", ".")
    _git(
        repo,
        "commit",
        "-m",
        f"chore({mission_slug}): record baseline_merge_commit (E1 consolidation)",
    )


def _publish_e2(repo: Path, target_branch: str) -> None:
    """Publish-to-trunk: real merge into ``main`` + Target Ref deletion."""
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", target_branch, "-m", f"Merge {target_branch}")
    _git(repo, "branch", "-D", target_branch)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    _init_git_repo(r)
    return r


# ---------------------------------------------------------------------------
# The three phases (T013)
# ---------------------------------------------------------------------------


def test_pre_consolidation_when_baseline_absent(repo: Path) -> None:
    """No ``baseline_merge_commit`` -> PRE_CONSOLIDATION (the safe default)."""
    mission_slug, _feature_dir, _target = _build_mission(
        repo, mid8="01KYS1AA", slug_base="widget-catalog"
    )

    phase = resolve_lifecycle_phase(mission_slug, repo)

    assert phase is LifecyclePhase.PRE_CONSOLIDATION


def test_consolidated_when_baseline_present_and_target_ref_exists(repo: Path) -> None:
    """``baseline_merge_commit`` present AND the Target Ref still exists -> E1."""
    init_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    mid8 = "01KYS1BB"
    mission_id = f"{mid8}0000000000000000"
    mission_slug, feature_dir, _target = _build_mission(
        repo, mid8=mid8, slug_base="widget-catalog"
    )
    _consolidate_e1(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=init_sha,
        mission_number=None,
    )

    phase = resolve_lifecycle_phase(mission_slug, repo)

    assert phase is LifecyclePhase.CONSOLIDATED


def test_published_when_target_ref_deleted_and_mission_number_assigned(
    repo: Path,
) -> None:
    """E2: baseline present, Target Ref gone, ``mission_number`` assigned."""
    init_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    mid8 = "01KYS1CC"
    mission_id = f"{mid8}0000000000000000"
    mission_slug, feature_dir, target_branch = _build_mission(
        repo, mid8=mid8, slug_base="widget-catalog"
    )
    _consolidate_e1(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=init_sha,
        mission_number=214,
    )
    _publish_e2(repo, target_branch)

    phase = resolve_lifecycle_phase(mission_slug, repo)

    assert phase is LifecyclePhase.PUBLISHED


def test_published_when_target_ref_deleted_and_all_wps_done(repo: Path) -> None:
    """E2 via the OTHER terminal-completion signal: no ``mission_number``, but
    every WP in the status event log is ``done`` (D2's second disjunct)."""
    init_sha = _git(repo, "rev-parse", "HEAD").stdout.strip()
    mid8 = "01KYS1DD"
    mission_id = f"{mid8}0000000000000000"
    mission_slug, feature_dir, target_branch = _build_mission(
        repo, mid8=mid8, slug_base="widget-catalog"
    )
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(_done_event(mission_slug, "WP01"), sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): WP01 done")
    _consolidate_e1(
        repo,
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        baseline_commit=init_sha,
        mission_number=None,  # deliberately unset — pin the OTHER signal
    )
    _publish_e2(repo, target_branch)

    phase = resolve_lifecycle_phase(mission_slug, repo)

    assert phase is LifecyclePhase.PUBLISHED


# ---------------------------------------------------------------------------
# C-003: never-created vs deleted Target Ref (the disambiguation)
# ---------------------------------------------------------------------------


def test_c003_target_ref_absent_without_terminal_completion_is_pre_consolidation(
    repo: Path,
) -> None:
    """The ambiguous case C-003 exists to resolve: ``baseline_merge_commit``
    present (synthetic — a malformed/legacy state) but the Target Ref was
    NEVER created (absent for a reason OTHER than publish) AND no
    terminal-completion evidence exists. Must NOT be misread as E2 — the
    safe default is PRE_CONSOLIDATION (data-model.md "Invariants")."""
    mid8 = "01KYS1EE"
    mission_id = f"{mid8}0000000000000000"
    mission_slug = f"widget-catalog-{mid8}"
    # Deliberately a Target Ref name that was NEVER created as a branch —
    # the never-created leg of the C-003 ambiguity (contrast with the E2
    # tests above, where the branch existed and was later deleted).
    never_created_target = f"kitty/mission-{mission_slug}"
    feature_dir = repo / "kitty-specs" / mission_slug
    _write_meta(
        feature_dir,
        mission_slug=mission_slug,
        mission_id=mission_id,
        mid8=mid8,
        target_branch=never_created_target,
    )
    # A synthetic baseline_merge_commit with NO mission_number and NO status
    # event log at all — no terminal-completion evidence of any kind.
    meta = load_meta(feature_dir) or {}
    meta["baseline_merge_commit"] = _git(repo, "rev-parse", "HEAD").stdout.strip()
    write_meta(feature_dir, meta, validate=False)
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", f"chore({mission_slug}): synthetic never-created fixture")

    assert not (repo / ".git" / "refs" / "heads" / never_created_target.split("/")[-1]).exists()

    phase = resolve_lifecycle_phase(mission_slug, repo)

    assert phase is LifecyclePhase.PRE_CONSOLIDATION


# ---------------------------------------------------------------------------
# D1 content-presence predicate (renata B1)
# ---------------------------------------------------------------------------


def test_content_present_at_primary_tip_true_when_content_committed(repo: Path) -> None:
    mid8 = "01KYS1FF"
    mission_slug, _feature_dir, _target = _build_mission(
        repo, mid8=mid8, slug_base="widget-catalog"
    )
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--no-ff", f"kitty/mission-{mission_slug}")

    assert content_present_at_primary_tip(mission_slug, repo) is True


def test_content_present_at_primary_tip_false_when_content_absent(repo: Path) -> None:
    """A mission that was never merged to the Primary Branch: absent, not an error."""
    mid8 = "01KYS1GG"
    mission_slug, _feature_dir, _target = _build_mission(
        repo, mid8=mid8, slug_base="widget-catalog"
    )
    _git(repo, "checkout", "-q", "main")  # main never received the mission's commit

    assert content_present_at_primary_tip(mission_slug, repo) is False


def test_content_present_at_primary_tip_raises_on_broken_probe(repo: Path) -> None:
    """A genuinely broken probe (exit 128, not exit 1) must raise LOUDLY, never
    be silently read as "content absent" (renata B1 — mirrors write_seam.py's
    "unrelated bug must still raise" discipline)."""
    # An empty-history repo has no commit on any branch, so ``git cat-file -e
    # main:...`` fails with "fatal: Not a valid object name main" (exit 128,
    # a bad-revision failure) rather than the documented exit-1 "path
    # missing at a valid rev" signal.
    empty_repo = repo.parent / "empty_repo"
    empty_repo.mkdir()
    _run(["git", "init", "-qb", "main", str(empty_repo)], cwd=empty_repo)
    mission_slug = "widget-catalog-01KYS1HH"

    with pytest.raises(LifecyclePhaseProbeError):
        content_present_at_primary_tip(mission_slug, empty_repo)
