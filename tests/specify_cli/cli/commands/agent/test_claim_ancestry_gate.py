"""T013 (#3281/FR-007/C-005/C-WP03) — the POST-materialize claim-ancestry gate.

Focused unit coverage for
``specify_cli.lanes.implement_support.check_claim_ancestry`` and
``resolve_claim_ancestry_gate`` — the shared predicate all three claim sites
(the CLI seam in ``workflow.py``, and ``orchestrator_api/commands.py``'s
``start_implementation`` + ``transition``) call through.

Two things this module proves, both real-git (no mocking of git plumbing —
the predicate's own subprocess calls run against a genuine repo):

1. **Ancestry refusal**: a dependent lane's worktree that has NOT yet merged
   an approved dependency lane's tip fails the bare predicate.
2. **No-deadlock regression (the C-005 hazard this WP closes)**: the
   SELF-HEAL-COUPLED gate (``resolve_claim_ancestry_gate``) does NOT stay
   refused — it re-enters the idempotent self-heal, which merges the
   approved dependency's tip, and the recheck passes. A pre-materialize (or
   self-heal-decoupled) design would refuse this FOREVER, which is exactly
   the deadlock the post-plan adversarial squad flagged (#3281 C-005).

A third scenario pins the deadlock-avoidance mechanism precisely: a
dependency lane that is NOT yet approved is OMITTED from the ancestry
requirement entirely (not merged, not required) — the PRE-materialize
dependency-status gate is what blocks an unapproved dependency; this
predicate never re-litigates that at the post-materialize seam.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from ulid import ULID

from specify_cli.lanes.branch_naming import lane_branch_name
from specify_cli.lanes.implement_support import (
    AncestryCheckResult,
    check_claim_ancestry,
    resolve_claim_ancestry_gate,
)
from specify_cli.lanes.worktree_allocator import ORPHANED_PIN_RECOVERY_HINT
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]

_MISSION_SLUG = "ancestry-gate-01KZZDANCESTRY"
_MISSION_ID = "01KZZDANCESTRY000000000000"
_WP_DEP = "WP01"  # lane-a, the dependency
_WP_SELF = "WP02"  # lane-b, the dependent claim under test


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True)
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _git(repo, "config", "commit.gpgsign", "false")
    (repo / "seed.txt").write_text("seed\n", encoding="utf-8")
    _git(repo, "add", "seed.txt")
    _git(repo, "commit", "-q", "-m", "seed")


def _feature_dir(repo: Path) -> Path:
    return repo / "kitty-specs" / _MISSION_SLUG


def _write_meta_and_lanes(repo: Path) -> None:
    """Write a LEGACY (no ``coordination_branch``) mission: the PRIMARY
    planning dir and the STATUS dir coincide (``kitty-specs/<slug>/``), which
    keeps this fixture to one directory instead of a full coord-topology
    setup (that shape is exercised elsewhere, e.g.
    ``tests/integration/test_wp_integrity_p0_repro.py``).
    """
    feature_dir = _feature_dir(repo)
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "mid8": _MISSION_ID[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-08-26T00:00:00+00:00",
                "friendly_name": "ancestry gate test",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lanes_payload = {
        "version": 1,
        "mission_slug": _MISSION_SLUG,
        "mission_id": _MISSION_ID,
        "mission_branch": f"kitty/mission-{_MISSION_SLUG}",
        "target_branch": "main",
        "lanes": [
            {
                "lane_id": "lane-a",
                "wp_ids": [_WP_DEP],
                "write_scope": ["src/**"],
                "predicted_surfaces": ["core"],
                "depends_on_lanes": [],
                "parallel_group": 0,
            },
            {
                "lane_id": "lane-b",
                "wp_ids": [_WP_SELF],
                "write_scope": ["src/**"],
                "predicted_surfaces": ["core"],
                "depends_on_lanes": ["lane-a"],
                "parallel_group": 1,
            },
        ],
        "computed_at": "2026-08-26T00:00:00+00:00",
        "computed_from": "test",
        "planning_artifact_wps": [],
        "planning_commit_sha": None,
    }
    (feature_dir / "lanes.json").write_text(json.dumps(lanes_payload, indent=2), encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "chore: planning artifacts")


def _write_meta_and_lanes_with_pin(repo: Path, planning_commit_sha: str | None) -> None:
    """Same fixture shape as :func:`_write_meta_and_lanes`, but with a
    caller-supplied ``planning_commit_sha`` on the manifest -- used to drive
    the orphaned-pin diagnostic path in
    ``implement_support._planning_commit_missing_diagnostic``.
    """
    feature_dir = _feature_dir(repo)
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_id": _MISSION_ID,
                "mission_slug": _MISSION_SLUG,
                "mid8": _MISSION_ID[:8].lower(),
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-08-26T00:00:00+00:00",
                "friendly_name": "ancestry gate test",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    lanes_payload = {
        "version": 1,
        "mission_slug": _MISSION_SLUG,
        "mission_id": _MISSION_ID,
        "mission_branch": f"kitty/mission-{_MISSION_SLUG}",
        "target_branch": "main",
        "lanes": [
            {
                "lane_id": "lane-a",
                "wp_ids": [_WP_DEP],
                "write_scope": ["src/**"],
                "predicted_surfaces": ["core"],
                "depends_on_lanes": [],
                "parallel_group": 0,
            },
        ],
        "computed_at": "2026-08-26T00:00:00+00:00",
        "computed_from": "test",
        "planning_artifact_wps": [],
        "planning_commit_sha": planning_commit_sha,
    }
    (feature_dir / "lanes.json").write_text(json.dumps(lanes_payload, indent=2), encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "chore: planning artifacts (orphan-pin fixture)")


def _seed_wp_lane(repo: Path, wp_id: str, lane: Lane) -> None:
    """Append ONE raw StatusEvent moving *wp_id* straight to *lane*.

    Bypasses ``emit_status_transition``'s FSM validation (and its
    sync-daemon side effects) deliberately -- ``reduce()`` is a pure fold
    over the event log; this writes directly through the same
    ``append_event`` production entry point ``emit_status_transition`` itself
    calls, exercising the REAL reader (``read_events`` + ``reduce``) the
    predicate under test consumes.
    """
    event = StatusEvent(
        event_id=str(ULID()),
        mission_slug=_MISSION_SLUG,
        wp_id=wp_id,
        from_lane=Lane.PLANNED,
        to_lane=lane,
        at="2026-08-26T00:00:00+00:00",
        actor="test",
        force=False,
        execution_mode="worktree",
        mission_id=_MISSION_ID,
    )
    append_event(_feature_dir(repo), event)


def _create_lane_a_branch(repo: Path) -> str:
    """Create ``lane-a``'s branch off main with a distinguishing commit."""
    branch = lane_branch_name(_MISSION_SLUG, "lane-a")
    _git(repo, "branch", branch, "main")
    _git(repo, "checkout", "-q", branch)
    (repo / "lane_a_output.txt").write_text("lane-a code\n", encoding="utf-8")
    _git(repo, "add", "lane_a_output.txt")
    _git(repo, "commit", "-q", "-m", "lane-a: write output")
    tip = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    return tip


def _create_lane_b_worktree(repo: Path) -> Path:
    """Create ``lane-b``'s worktree off ``main`` -- WITHOUT lane-a's tip."""
    branch = lane_branch_name(_MISSION_SLUG, "lane-b")
    worktree = repo / ".worktrees" / f"{_MISSION_SLUG}-lane-b"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-b", branch, str(worktree), "main")
    return worktree


def test_ancestry_refusal_when_approved_dep_tip_not_merged(tmp_path: Path) -> None:
    """FR-007: the bare predicate refuses when an APPROVED dependency lane's
    tip is not (yet) a git ancestor of the claimant's workspace HEAD.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_meta_and_lanes(repo)
    lane_a_tip = _create_lane_a_branch(repo)
    lane_b_worktree = _create_lane_b_worktree(repo)

    # lane-a's sole WP is APPROVED -- its tip becomes a hard ancestry
    # requirement for lane-b.
    _seed_wp_lane(repo, _WP_DEP, Lane.APPROVED)

    status_dir = _feature_dir(repo)
    result = check_claim_ancestry(repo, _MISSION_SLUG, status_dir, _WP_SELF, lane_b_worktree)

    assert isinstance(result, AncestryCheckResult)
    assert result.ok is False
    assert any("lane-a" in ref for ref in result.missing_refs), result.missing_refs
    # The dependency tip is genuinely NOT an ancestor yet (fixture sanity).
    not_ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", lane_a_tip, "HEAD"],
        cwd=str(lane_b_worktree),
    )
    assert not_ancestor.returncode != 0


def test_approved_dependency_does_not_deadlock_self_heal_establishes_ancestry(
    tmp_path: Path,
) -> None:
    """C-005 no-deadlock regression: ``resolve_claim_ancestry_gate`` (the
    SELF-HEAL-COUPLED gate every claim site actually calls) does NOT stay
    refused when the dependency is genuinely approved -- it re-enters the
    idempotent self-heal, which merges the approved tip, and the recheck
    passes. A pre-materialize (or self-heal-decoupled) ancestry design would
    refuse this claim FOREVER; that is exactly the #3281 C-005 deadlock
    hazard the post-plan adversarial squad flagged and this WP closes.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_meta_and_lanes(repo)
    _create_lane_a_branch(repo)
    lane_b_worktree = _create_lane_b_worktree(repo)

    _seed_wp_lane(repo, _WP_DEP, Lane.APPROVED)

    status_dir = _feature_dir(repo)

    # Sanity: the bare (non-self-heal) predicate is refused first.
    bare = check_claim_ancestry(repo, _MISSION_SLUG, status_dir, _WP_SELF, lane_b_worktree)
    assert bare.ok is False

    # The self-heal-coupled gate re-enters allocate_lane_worktree's reuse-path
    # self-heal (merges lane-a's approved tip into lane-b) and rechecks.
    healed = resolve_claim_ancestry_gate(repo, _MISSION_SLUG, status_dir, _WP_SELF, lane_b_worktree)
    assert healed.ok is True, f"approved dependency lane-a must not deadlock the claim: {healed.missing_refs}"

    # Observable: lane-a's tip really did land in lane-b's worktree.
    assert (lane_b_worktree / "lane_a_output.txt").exists()


def test_non_approved_dependency_is_omitted_not_required(tmp_path: Path) -> None:
    """A dependency lane still IN PROGRESS (not approved/done) is not an
    ancestry requirement at all -- the PRE-materialize dependency-status gate
    is what blocks an unapproved dependency; this predicate must not
    re-litigate that here (it would otherwise permanently refuse a claim
    whose real dependency gate already correctly allowed it through, e.g. a
    ``force`` override or a lane with unrelated in-flight siblings).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)
    _write_meta_and_lanes(repo)
    _create_lane_a_branch(repo)
    lane_b_worktree = _create_lane_b_worktree(repo)

    # lane-a's WP is still in flight -- NOT approved/done.
    _seed_wp_lane(repo, _WP_DEP, Lane.IN_PROGRESS)

    status_dir = _feature_dir(repo)
    result = check_claim_ancestry(repo, _MISSION_SLUG, status_dir, _WP_SELF, lane_b_worktree)

    assert result.ok is True, f"a non-approved dependency lane must be omitted, not required: {result.missing_refs}"


def test_legacy_non_lane_wp_is_a_no_op(tmp_path: Path) -> None:
    """A WP with no ``lanes.json`` (or no lane assignment) has nothing to
    check -- ``ok=True`` unconditionally (legacy/non-lane missions keep
    working unchanged, mirrors ``allocate_lane_worktree``'s own legacy path).
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    result = check_claim_ancestry(repo, "no-such-mission", repo, "WP99", repo)

    assert result.ok is True
    assert result.missing_refs == ()


def test_orphaned_planning_commit_produces_orphan_diagnostic(tmp_path: Path) -> None:
    """#4827 pre-PR squad finding [MEDIUM]: no test asserted
    ``implement_support._planning_commit_missing_diagnostic``'s
    orphan-specific wording, reached only through
    ``check_claim_ancestry`` when ``classify_recorded_pin`` returns
    ``PinClass.ORPHANED`` for the recorded ``planning_commit_sha``.

    A recorded pin whose commit OBJECT is still present but is no longer an
    ancestor of the target-branch tip (the mid-mission rebase/rewrite shape)
    must produce the "is orphaned against the target-branch tip; run ... to
    re-point it" recovery wording -- distinct from the bare
    "recorded planning commit <sha>" wording a merely-not-yet-merged
    (still-reachable) pin gets.
    """
    repo = tmp_path / "repo"
    _init_repo(repo)

    # Orphaned pin: commit object present in the object store, but no longer
    # reachable from main's tip. Committed on a throwaway branch, its sha
    # captured, then the branch deleted -- the loose object survives (no gc
    # runs in this fixture), so `git cat-file -e` still finds it while
    # `git merge-base --is-ancestor` correctly reports "not an ancestor".
    _git(repo, "checkout", "-q", "-b", "throwaway")
    (repo / "orphan.txt").write_text("orphan\n", encoding="utf-8")
    _git(repo, "add", "orphan.txt")
    _git(repo, "commit", "-q", "-m", "orphan candidate")
    orphaned_sha = _git(repo, "rev-parse", "HEAD")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "branch", "-D", "throwaway")

    _write_meta_and_lanes_with_pin(repo, orphaned_sha)

    branch = lane_branch_name(_MISSION_SLUG, "lane-a")
    worktree = repo / ".worktrees" / f"{_MISSION_SLUG}-lane-a"
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-b", branch, str(worktree), "main")

    status_dir = _feature_dir(repo)
    result = check_claim_ancestry(repo, _MISSION_SLUG, status_dir, _WP_DEP, worktree)

    assert result.ok is False
    assert len(result.missing_refs) == 1, result.missing_refs
    diagnostic = result.missing_refs[0]
    assert orphaned_sha in diagnostic
    assert "is orphaned against the target-branch tip" in diagnostic
    assert ORPHANED_PIN_RECOVERY_HINT in diagnostic

    # Contrast: a healthy (still-reachable) pin never gets this wording --
    # locks the "distinct from the healthy/dep-lane paths" contract.
    healthy_sha = _git(repo, "rev-parse", "main")
    lanes_path = _feature_dir(repo) / "lanes.json"
    payload = json.loads(lanes_path.read_text(encoding="utf-8"))
    payload["planning_commit_sha"] = healthy_sha
    lanes_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    _git(repo, "add", "kitty-specs")
    _git(repo, "commit", "-q", "-m", "chore: healthy pin")

    healthy_result = check_claim_ancestry(repo, _MISSION_SLUG, status_dir, _WP_DEP, worktree)
    assert healthy_result.ok is True, healthy_result.missing_refs
