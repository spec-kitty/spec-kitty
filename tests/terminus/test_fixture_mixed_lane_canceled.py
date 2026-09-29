"""WP01 (mixed-lane-authorship-soundness-01M3M7Y0) — fixture behaviour, FR-008.

Correct the recorded fixture limitation. Grounding on 2026-09-28 found that
``build_coord_mission_mixed_lane`` already consolidates under the default
strategy and survives post-build lane-ref and coordination-worktree-content
mutations; the "coordination branch ... is unmaterialized" abort occurs only
when the coordination WORKTREE DIRECTORY itself goes missing. This file pins
both observed behaviours with real ``spec-kitty`` CLI runs (no ``_run_git`` /
subprocess mocking), and adds a fixture-hygiene unit check for the new
``_event``/``_cancel_event`` ``policy_metadata`` keyword (T002).

Do NOT write the #5046 mixed-lane-authorship assertions here (they belong to
WP02+) — this file only pins the FIXTURE's own documented behaviour.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tests.terminus.conftest import (
    CoordMission,
    PlantedChange,
    _event,
    build_coord_mission_mixed_lane_canceled,
)
from tests.terminus.conftest import _git as git
from tests.terminus.conftest import (
    reached_reconciliation_verdict,
    run_terminus,
)

_DEFAULT_CANCELED_CHANGES = (PlantedChange("src/pkg/wp02_canceled.py", "def wp02_canceled() -> str:\n    return 'leaked'\n"),)


def _collapse(text: str) -> str:
    """Collapse whitespace to single spaces so a rich-console line wrap still matches."""
    return " ".join(text.split())


def _plant_extra_lane_commit_via_cas_update_ref(mission: CoordMission, lane_branch: str) -> str:
    """Plant one extra real commit on *lane_branch* using plumbing (``git
    commit-tree`` + a 3-arg CAS ``git update-ref``), mirroring the production
    ``update-ref <ref> <new_sha> <expected_old_sha>`` contract
    (``git/ref_advance.py``) rather than a porcelain ``git commit``. Runs
    AFTER the coordination worktree has already been resolved, to pin FR-008's
    "post-build lane mutation still consolidates" claim.

    Returns the new commit SHA.
    """
    repo = mission.repo
    old_sha = mission.rev(lane_branch)

    git(repo, "checkout", "-q", lane_branch)
    extra_file = repo / "src" / "pkg" / "wp02_post_build.py"
    extra_file.parent.mkdir(parents=True, exist_ok=True)
    extra_file.write_text("# planted after CoordinationWorkspace.resolve\n", encoding="utf-8")
    git(repo, "add", str(extra_file.relative_to(repo)))
    tree = git(repo, "write-tree").stdout.strip()
    new_sha = git(repo, "commit-tree", tree, "-p", old_sha, "-m", "chore: post-build lane commit (CAS update-ref)").stdout.strip()
    # Discard the staged-but-uncommitted working-tree state; the blob/tree/
    # commit objects the two calls above wrote already live in the object
    # database and are unaffected by resetting the working tree back.
    git(repo, "reset", "--hard", old_sha)
    git(repo, "checkout", "-q", mission.target_branch)

    git(repo, "update-ref", f"refs/heads/{lane_branch}", new_sha, old_sha)
    return new_sha


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.regression
def test_post_build_lane_update_ref_still_consolidates(tmp_path: Path) -> None:
    """FR-008(a): a post-build lane ``update-ref`` still reaches the
    reconciliation verdict under the default strategy — it does NOT abort
    with "unmaterialized".

    Today (the #5046 bug, still open at WP01) this exits 0 with
    "squash content attribution verified" even though the lane's own
    survivor commit is the only approved content and the extra post-build
    commit is unattributed. This test intentionally asserts only that the
    run REACHED a reconciliation verdict, not which one, so it stays valid
    once WP05 closes the #5046 gap and the verdict flips.
    """
    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=_DEFAULT_CANCELED_CHANGES, mid8="01M5047A")
    lane_branch = mission.lane_branch("WP01")

    _plant_extra_lane_commit_via_cas_update_ref(mission, lane_branch)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    flat = _collapse(result.stdout + "\n" + result.stderr).lower()
    assert "unmaterialized" not in flat, f"a post-build lane update-ref must not trip the unmaterialized-coordination abort:\n{result.stdout}\n{result.stderr}"
    assert reached_reconciliation_verdict(result), (
        f"expected the run to reach a reconciliation verdict (PASS/FAIL/REFUSE), "
        f"got exit {result.returncode} with no verdict line:\n{result.stdout}\n{result.stderr}"
    )


@pytest.mark.integration
@pytest.mark.git_repo
@pytest.mark.regression
def test_missing_coord_worktree_dir_is_the_unmaterialized_trigger(tmp_path: Path) -> None:
    """FR-008(b): the REAL "unmaterialized" trigger is the coordination
    worktree DIRECTORY going missing — not a lane-branch or coordination-
    worktree-content mutation (see the first test in this file).
    """
    from specify_cli.coordination.workspace import CoordinationWorkspace

    mission = build_coord_mission_mixed_lane_canceled(tmp_path, canceled_changes=_DEFAULT_CANCELED_CHANGES, mid8="01M5047B")
    coord_worktree = CoordinationWorkspace.worktree_path(mission.repo, mission.slug, mission.mid8)
    assert coord_worktree.exists(), "the coordination worktree must be materialized by the builder"

    git(mission.repo, "worktree", "remove", "--force", str(coord_worktree))
    assert not coord_worktree.exists()

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes"])

    assert result.returncode != 0, f"a missing coordination worktree directory must abort, got exit 0:\n{result.stdout}\n{result.stderr}"
    flat = _collapse(result.stdout + "\n" + result.stderr).lower()
    assert "unmaterialized" in flat, f"expected the 'is unmaterialized' abort naming the coordination branch, got:\n{result.stdout}\n{result.stderr}"


@pytest.mark.unit
@pytest.mark.fast
def test_event_policy_metadata_round_trips_through_read_events(tmp_path: Path) -> None:
    """T002 fixture-hygiene validation: ``_event(..., policy_metadata=...)``
    round-trips byte-faithfully through ``specify_cli.status.read_events`` —
    no subprocess, no real git repo, pure JSONL I/O.
    """
    from specify_cli.status import read_events

    slug = "terminus-roundtrip"
    feature_dir = tmp_path / "kitty-specs" / slug
    feature_dir.mkdir(parents=True)
    mission = CoordMission(
        repo=tmp_path,
        home=tmp_path,
        feature_dir=feature_dir,
        slug=slug,
        mission_id="01M00000000000000000000000",
        mid8="01M00000",
        coord_branch=f"kitty/mission-{slug}-01M00000",
        target_branch="main",
    )
    stamped_metadata: dict[str, object] = {"lane_head": "a" * 40}

    event = _event(mission, "WP02", "claimed", "in_progress", policy_metadata=stamped_metadata)
    assert event["policy_metadata"] == stamped_metadata

    (feature_dir / "status.events.jsonl").write_text(json.dumps(event, sort_keys=True) + "\n", encoding="utf-8")

    events = read_events(feature_dir)

    assert len(events) == 1
    assert events[0].policy_metadata == stamped_metadata


def test_event_omits_policy_metadata_key_when_not_passed() -> None:
    """T002: existing call sites (no ``policy_metadata`` argument) stay
    byte-identical — the key is added ONLY when a caller passes one.
    """
    mission = CoordMission(
        repo=Path("/nonexistent"),
        home=Path("/nonexistent"),
        feature_dir=Path("/nonexistent/kitty-specs/terminus-no-metadata"),
        slug="terminus-no-metadata",
        mission_id="01M00000000000000000000001",
        mid8="01M00001",
        coord_branch="kitty/mission-terminus-no-metadata-01M00001",
        target_branch="main",
    )

    event = _event(mission, "WP01", "planned", "claimed")

    assert "policy_metadata" not in event
