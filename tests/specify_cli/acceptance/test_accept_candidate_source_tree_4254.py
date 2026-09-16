"""#4254: acceptance checks source paths against the tree being accepted.

Strict acceptance validated mission-declared BUILD paths (``tests/``,
``docs/``) against the canonical primary checkout, which is evaluated *before*
the approved lane's source is integrated. A lane that introduces the first
``tests/`` and ``docs/`` therefore could not be accepted even though those
exact reviewed files exist in its own worktree — observed in
spec-kitty-alerts and spec-kitty-kuma during the SaaS #1713 source handoff,
where WP01 was independently approved and acceptance still reported
``tests/ (not found)``.

The fix lets a build path additionally be satisfied by the candidate source
tree, and these tests pin the four regression checks the issue names:

1. new ``tests/``/``docs/`` on one approved lane succeed;
2. a path missing from the actual candidate still fails;
3. an unapproved lane cannot satisfy a path;
4. mission artifacts (``contracts/``) stay on the primary planning surface —
   a lane worktree can never satisfy one.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from specify_cli.mission import get_mission_for_feature
from specify_cli.validators.paths import validate_mission_paths

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SLUG = "candidate-source-tree-01M2AGNS"
_MISSION_ID = "01M2AGNSZAP70V8DVJZ8XN0M3T"


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo_root, check=True, capture_output=True)


@pytest.fixture
def mission_repo(tmp_path: Path) -> tuple[Path, Path]:
    """A repo whose PRIMARY checkout has ``src/`` but no ``tests/``/``docs/``.

    That is the reported shape: the reviewed lane introduces those two
    directories, so before integration they exist only in its worktree.
    """
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    _git(repo_root, "init", "-q", ".")
    _git(repo_root, "config", "user.email", "test@test.com")
    _git(repo_root, "config", "user.name", "Test")
    _git(repo_root, "branch", "-M", "main")

    (repo_root / ".kittify").mkdir()
    (repo_root / "src").mkdir()
    (repo_root / "src" / ".gitkeep").write_text("")

    feature_dir = repo_root / "kitty-specs" / _SLUG
    (feature_dir / "tasks").mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "slug": _SLUG,
                "mission_slug": _SLUG,
                "mission_id": _MISSION_ID,
                "mid8": _MISSION_ID[:8],
                "friendly_name": "Candidate source tree",
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-01-01T00:00:00Z",
            },
            indent=2,
        )
        + "\n"
    )
    for name in ("spec.md", "plan.md", "tasks.md"):
        (feature_dir / name).write_text(f"# {name}\nDone.\n")

    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-qm", "init")
    return repo_root, feature_dir


def _lane_worktree(repo_root: Path, *, with_dirs: tuple[str, ...]) -> Path:
    """A lane worktree carrying the reviewed source directories."""
    from specify_cli.lanes.branch_naming import worktree_path

    lane_root = worktree_path(repo_root, _SLUG, mission_id=_MISSION_ID, lane_id="lane-a")
    lane_root.mkdir(parents=True)
    for name in with_dirs:
        (lane_root / name).mkdir()
        (lane_root / name / "reviewed.md").write_text("reviewed source\n")
    return lane_root


def _validate(repo_root: Path, feature_dir: Path, roots: tuple[Path, ...]):
    mission = get_mission_for_feature(feature_dir)
    return validate_mission_paths(
        mission,
        repo_root,
        feature_dir=feature_dir,
        candidate_source_roots=roots,
    )


def test_build_paths_only_in_the_approved_lane_satisfy_acceptance(
    mission_repo: tuple[Path, Path],
) -> None:
    """Regression check 1: the reported blocker — reviewed source that exists
    only on the lane no longer reads as missing."""
    repo_root, feature_dir = mission_repo
    lane_root = _lane_worktree(repo_root, with_dirs=("tests", "docs"))

    without = _validate(repo_root, feature_dir, ())
    assert any(p.startswith("tests") for p in without.missing_paths), "fixture invalid: the primary checkout must lack tests/, or there is nothing to observe"

    result = _validate(repo_root, feature_dir, (lane_root,))

    assert not [p for p in result.missing_paths if p.startswith(("tests", "docs"))], (
        f"#4254: reviewed source on the approved lane still read as missing: {result.missing_paths}"
    )
    # The evidence says WHERE it was found, so a reader can tell "already
    # integrated" from "present in the approved lane".
    assert str(lane_root) in set(result.satisfied_by.values())


def test_a_path_missing_from_the_candidate_still_fails(
    mission_repo: tuple[Path, Path],
) -> None:
    """Regression check 2: this widens where a path may live, not whether it must exist."""
    repo_root, feature_dir = mission_repo
    lane_root = _lane_worktree(repo_root, with_dirs=("tests",))  # no docs/ anywhere

    result = _validate(repo_root, feature_dir, (lane_root,))

    assert any(p.startswith("docs") for p in result.missing_paths), "a directory absent from both the primary checkout and the candidate must still fail"


def test_an_unapproved_lane_cannot_satisfy_a_path(
    mission_repo: tuple[Path, Path],
) -> None:
    """Regression check 3: only trees the caller vouches for are consulted.

    The acceptance caller passes approved lanes only; a worktree that is not
    among them — an unapproved lane, or any other checkout on disk — is not
    consulted even when it contains the directory.
    """
    repo_root, feature_dir = mission_repo
    _lane_worktree(repo_root, with_dirs=("tests", "docs"))

    result = _validate(repo_root, feature_dir, ())

    assert any(p.startswith("tests") for p in result.missing_paths), "#4254: a lane the caller did not vouch for satisfied a declared path"


def test_mission_artifacts_are_never_satisfied_by_a_lane_worktree(
    mission_repo: tuple[Path, Path],
) -> None:
    """Regression check 4: planning ownership is unchanged.

    ``contracts/`` is a mission artifact: it belongs on the primary planning
    surface. A lane worktree carrying one must not satisfy it, or acceptance
    would stop requiring planning artifacts where they actually live.
    """
    repo_root, feature_dir = mission_repo
    lane_root = _lane_worktree(repo_root, with_dirs=("tests", "docs", "contracts"))

    result = _validate(repo_root, feature_dir, (lane_root,))

    assert any("contracts" in p for p in result.missing_paths), "#4254: a lane worktree satisfied a mission artifact that belongs on the primary surface"
    assert not any("contracts" in key for key in result.satisfied_by)


# ---------------------------------------------------------------------------
# The approved-lane gate itself: which trees acceptance vouches for.
# ---------------------------------------------------------------------------


def _lanes_json(feature_dir: Path, *, wp_ids: tuple[str, ...]) -> None:
    (feature_dir / "lanes.json").write_text(
        json.dumps(
            {
                "version": 1,
                "mission_slug": _SLUG,
                "mission_id": _MISSION_ID,
                "mission_branch": f"kitty/mission-{_SLUG}",
                "target_branch": "main",
                "lanes": [{"lane_id": "lane-a", "wp_ids": list(wp_ids), "depends_on": []}],
                "computed_at": "2026-01-01T00:00:00Z",
                "computed_from": "dependency_graph+ownership",
            },
            indent=2,
        )
        + "\n"
    )


def test_only_a_fully_approved_lane_is_offered_as_a_candidate(
    mission_repo: tuple[Path, Path],
) -> None:
    """The caller-side gate: approved lanes are vouched for, others are not.

    This is what makes "an unapproved lane cannot satisfy a path" true in
    production rather than only in the validator's own contract.
    """
    from specify_cli.acceptance import _approved_lane_source_roots

    repo_root, feature_dir = mission_repo
    lane_root = _lane_worktree(repo_root, with_dirs=("tests", "docs"))
    _lanes_json(feature_dir, wp_ids=("WP01",))

    approved = _approved_lane_source_roots(repo_root, feature_dir, {"approved": ["WP01"], "done": []})
    assert approved == (lane_root,)

    # The same lane, with its work package still in review, is not offered.
    in_review = _approved_lane_source_roots(repo_root, feature_dir, {"approved": [], "in_review": ["WP01"]})
    assert in_review == ()


def test_a_lane_with_an_unapproved_work_package_is_not_offered(
    mission_repo: tuple[Path, Path],
) -> None:
    """Partial approval is not approval: one un-approved WP disqualifies the lane."""
    from specify_cli.acceptance import _approved_lane_source_roots

    repo_root, feature_dir = mission_repo
    _lane_worktree(repo_root, with_dirs=("tests", "docs"))
    _lanes_json(feature_dir, wp_ids=("WP01", "WP02"))

    roots = _approved_lane_source_roots(repo_root, feature_dir, {"approved": ["WP01"], "done": []})
    assert roots == ()


def test_a_missing_lanes_manifest_offers_nothing(
    mission_repo: tuple[Path, Path],
) -> None:
    """No topology, no guessing: the check behaves exactly as it did before."""
    from specify_cli.acceptance import _approved_lane_source_roots

    repo_root, feature_dir = mission_repo
    _lane_worktree(repo_root, with_dirs=("tests", "docs"))

    assert _approved_lane_source_roots(repo_root, feature_dir, {"approved": ["WP01"]}) == ()


# ---------------------------------------------------------------------------
# End-to-end wiring proof: the real ``collect_feature_summary`` entry point,
# not the validator or the gate helper each already tested in isolation.
# ---------------------------------------------------------------------------


def _wp_task_file(feature_dir: Path, *, wp_id: str = "WP01") -> None:
    """A minimal WP task file so ``_iter_work_packages`` finds ``wp_id``."""
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}-sample.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Sample\nagent: claude\nassignee: claude\nshell_pid: '1'\n---\n\n# WP\n",
        encoding="utf-8",
    )


def _approve_wp(feature_dir: Path, *, wp_id: str = "WP01") -> None:
    """Write a real, event-sourced ``approved`` transition for ``wp_id``.

    Uses the canonical ``append_event`` writer (mirrors
    ``test_populate_criteria_from_review_evidence.py``) so
    ``collect_feature_summary``'s own status read -- not a hand-built
    snapshot -- puts the WP's lane into ``approved``.
    """
    from specify_cli.status import Lane, ReviewResult, StatusEvent
    from specify_cli.status._unsafe import append_event

    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"evt-{wp_id}-approved",
            mission_slug=_SLUG,
            wp_id=wp_id,
            from_lane=Lane.IN_REVIEW,
            to_lane=Lane.APPROVED,
            at="2026-01-01T00:00:00+00:00",
            actor="reviewer-renata",
            force=False,
            execution_mode="worktree",
            review_result=ReviewResult(
                reviewer="reviewer-renata",
                verdict="approved",
                reference=f"review-cycle://{_SLUG}/{wp_id}/1",
            ),
        ),
    )


def test_collect_feature_summary_reports_approved_lane_build_path_as_satisfied(
    mission_repo: tuple[Path, Path],
) -> None:
    """The #4254 wiring seam, proved end-to-end through the real accept
    entry point -- not the validator (``validate_mission_paths``) or the
    caller-side gate helper (``_approved_lane_source_roots``) each of the
    other tests in this file already exercises in isolation.

    ``collect_feature_summary`` (``acceptance/__init__.py``) threads
    ``candidate_source_roots=_approved_lane_source_roots(...)`` into
    ``evaluate_path_conventions``. Every other test here calls
    ``validate_mission_paths``/``_approved_lane_source_roots`` directly, so
    if that ``candidate_source_roots=`` argument were ever dropped from the
    real call site, every one of them would still pass while the production
    fix silently reverted -- this is the one test that would go red.
    """
    from specify_cli.acceptance import collect_feature_summary

    repo_root, feature_dir = mission_repo
    _lane_worktree(repo_root, with_dirs=("tests", "docs"))
    _lanes_json(feature_dir, wp_ids=("WP01",))
    _wp_task_file(feature_dir)
    _approve_wp(feature_dir)

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False)

    rendered_violations = "\n".join(summary.path_violations)
    assert "tests" not in rendered_violations, (
        "#4254: acceptance still reported the approved lane's reviewed tests/ "
        f"as missing through the real collect_feature_summary entry point: {summary.path_violations!r}"
    )
    assert "docs" not in rendered_violations, (
        "#4254: acceptance still reported the approved lane's reviewed docs/ "
        f"as missing through the real collect_feature_summary entry point: {summary.path_violations!r}"
    )
