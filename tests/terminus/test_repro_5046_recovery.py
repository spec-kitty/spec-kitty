"""Red-first real-CLI reproductions of the #5046 post-acceptance landing blockers.

Mission ``mixed-lane-authorship-soundness-01M3M7Y0`` (spec.md FR-011).

**FR-011 — migration-synthesized events never affect attribution.** The first
``spec-kitty consolidate`` of a mixed lane that FAILs (unsuperseded canceled
content) runs the birth-cutover backfill, which appends
``migration:backfill_runtime_state`` seed events (``planned -> claimed``, no
``lane_head`` stamp) for every WP AFTER the cancel. Before the fix those
seeds re-opened a work window that never closes, so every later run REFUSEd
``open_window`` — the printed FAIL recovery ("revert through a surviving WP,
re-run") could never succeed.

Every test drives the REAL ``spec-kitty consolidate`` CLI
(:func:`tests.terminus.conftest.run_terminus`) against a real on-disk
coordination mission; the surviving WP's rework goes through the production
transactional status shell (the same door ``test_repro_5046_production_path.py``
uses), never a hand-written stamp.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.coordination.status_transition import emit_status_transition_transactional
from specify_cli.status.models import ReviewResult, StatusEvent, TransitionRequest
from tests.terminus.conftest import (
    CoordMission,
    PlantedChange,
    blob_present_at,
    build_coord_mission_mixed_lane_canceled,
    run_terminus,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.regression]

_LEAKED_PATH = "src/pkg/wp02_new.py"
_WP01_PATH = "src/pkg/wp01.py"
_FAIL_HEADER = "Reconciliation FAILED"
_REFUSE_HEADER = "Reconciliation refused (fail-closed)"
_OPEN_WINDOW = "never closed"


def _collapse(text: str) -> str:
    """Whitespace collapse + backtick strip (same normalisation as ``test_repro_5046.py``)."""
    return " ".join(text.replace("`", "").split())


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)


def _consolidate(mission: CoordMission, *extra: str) -> tuple[int, str]:
    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", *extra])
    return result.returncode, _collapse(result.stdout + "\n" + result.stderr)


def _transition(
    mission: CoordMission,
    wp_id: str,
    to_lane: str,
    *,
    force: bool = False,
    reason: str | None = None,
    subtasks_complete: bool | None = None,
    review_result: ReviewResult | None = None,
) -> StatusEvent:
    """One transition through the production coord-topology transactional shell."""
    request = TransitionRequest(
        feature_dir=mission.feature_dir,
        mission_slug=mission.slug,
        wp_id=wp_id,
        to_lane=to_lane,
        actor="landing-recovery-test",
        repo_root=mission.repo,
        force=force,
        reason=reason,
        subtasks_complete=subtasks_complete,
        review_result=review_result,
    )
    return emit_status_transition_transactional(request)


def _ensure_wp01_subtasks_roster(mission: CoordMission) -> None:
    """The live ``in_progress -> for_review`` guard needs a ``subtasks:`` key (see the production-path test)."""
    wp01_file = mission.feature_dir / "tasks" / "WP01-work.md"
    wp01_file.write_text(
        "---\nwork_package_id: WP01\ntitle: WP01 work\nagent: implementer-ivan\nsubtasks: []\n---\n# WP01\n",
        encoding="utf-8",
    )
    _git(mission.repo, "add", str(wp01_file.relative_to(mission.repo)))
    _git(mission.repo, "commit", "-qm", "wp01: add empty subtasks roster for the live rework gate")


def _build_failing_mixed_lane(tmp_path: Path, mid8: str) -> CoordMission:
    """Stamped mixed lane: WP01 approved, WP02 added an unsuperseded file, then canceled."""
    return build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange(_LEAKED_PATH, "def wp02_new() -> str:\n    return 'wp02 leaked'\n")],
        survivor_before=[PlantedChange(_WP01_PATH, "def wp01() -> str:\n    return 'ok'\n")],
        stamp_attribution=True,
        mid8=mid8,
    )


def _supersede_through_wp01_rework(mission: CoordMission) -> None:
    """WP01 (recorded ``done`` by the first, failed run's bookkeeping) is reopened and
    reworked through the production shell: its rework deletes WP02's leaked file."""
    lane_branch = mission.lane_branches["WP01"]
    _transition(mission, "WP01", "in_progress", force=True, reason="rework: remove canceled WP02's leftover file")
    _git(mission.repo, "checkout", "-q", lane_branch)
    _git(mission.repo, "rm", "-q", _LEAKED_PATH)
    _git(mission.repo, "commit", "-qm", "wp01 rework removes canceled wp02's file")
    _git(mission.repo, "checkout", "-q", mission.target_branch)
    _transition(mission, "WP01", "for_review", subtasks_complete=True)
    _transition(mission, "WP01", "in_review")
    _transition(
        mission,
        "WP01",
        "approved",
        review_result=ReviewResult(reviewer="landing-recovery-test", verdict="approved", reference="review-wp01-recovery"),
    )


def test_rerun_after_fail_fails_again_not_open_window_refuse(tmp_path: Path) -> None:
    """FR-011 (i): a re-run with no change must report the SAME FAIL — the backfill
    seed events the first run appended must not turn it into an ``open_window`` REFUSE."""
    mission = _build_failing_mixed_lane(tmp_path, "01M5046T")
    pre_sha = mission.rev(mission.target_branch)

    first_rc, first = _consolidate(mission)
    assert first_rc != 0 and _FAIL_HEADER in first, f"first run must FAIL on WP02's leaked file:\n{first}"
    assert mission.rev(mission.target_branch) == pre_sha

    second_rc, second = _consolidate(mission)
    assert second_rc != 0, f"re-run with no change must not exit 0:\n{second}"
    assert _OPEN_WINDOW not in second, f"migration seed events must not re-open a work window (FR-011):\n{second}"
    assert _FAIL_HEADER in second, f"re-run must repeat the FAIL verdict:\n{second}"
    assert f"'{_LEAKED_PATH}'" in second
    assert mission.rev(mission.target_branch) == pre_sha


def test_supersede_after_fail_then_rerun_passes(tmp_path: Path) -> None:
    """FR-011 (ii): the FAIL's own recovery (revert through a surviving WP's governed
    work, re-run) must succeed — exit 0, and the canceled file is not on the target."""
    mission = _build_failing_mixed_lane(tmp_path, "01M5046U")
    _ensure_wp01_subtasks_roster(mission)

    first_rc, first = _consolidate(mission)
    assert first_rc != 0 and _FAIL_HEADER in first, f"first run must FAIL on WP02's leaked file:\n{first}"

    _supersede_through_wp01_rework(mission)

    rc, out = _consolidate(mission)
    assert rc == 0, f"after a superseding WP01 rework the re-run must consolidate cleanly:\n{out}"
    assert blob_present_at(mission.repo, mission.target_branch, _LEAKED_PATH) is False
    assert blob_present_at(mission.repo, mission.target_branch, _WP01_PATH) is True


# --------------------------------------------------------------------------- #
# FR-012 — operator-attested override for an unresolvable (legacy) mixed lane
# --------------------------------------------------------------------------- #

_ATTEST_FLAG = "--attest-canceled-superseded"
_ATTEST_REASON = "checked by hand: WP01 rework deleted WP02's file"


def _attestation_records(mission: CoordMission) -> list[dict[str, object]]:
    """Every attestation record in any copy of the mission's status event log."""
    import json

    records: list[dict[str, object]] = []
    for log in mission.repo.rglob("status.events.jsonl"):
        if ".git" in log.parts:
            continue
        for line in log.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if (event.get("policy_metadata") or {}).get("attestation") == "canceled_superseded":
                records.append(event)
    return records


def test_unstamped_mixed_lane_refuses_naming_the_override_then_attestation_passes(tmp_path: Path) -> None:
    """FR-012: a legacy (unstamped) mixed lane REFUSEs ``no_stamp`` forever — the
    REFUSE must name the override; with the attestation consolidation exits 0 and
    the event log carries the operator-provenance record (actor, reason)."""
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange(_LEAKED_PATH, "def wp02_new() -> str:\n    return 'wp02'\n")],
        survivor_after=[PlantedChange(_LEAKED_PATH, None)],
        stamp_attribution=False,
        mid8="01M5046W",
    )
    pre_sha = mission.rev(mission.target_branch)

    rc, out = _consolidate(mission)
    assert rc != 0, f"an unstamped mixed lane must refuse:\n{out}"
    assert _REFUSE_HEADER in out and "no commit attribution" in out, out
    assert f"{_ATTEST_FLAG} WP02" in out, f"the REFUSE must name the override flag for WP02:\n{out}"
    assert mission.rev(mission.target_branch) == pre_sha
    assert _attestation_records(mission) == []

    rc, out = _consolidate(mission, _ATTEST_FLAG, "WP02", "--attest-reason", _ATTEST_REASON)
    assert rc == 0, f"an attested legacy mixed lane must consolidate:\n{out}"
    assert blob_present_at(mission.repo, mission.target_branch, _LEAKED_PATH) is False

    records = _attestation_records(mission)
    assert records, "the attestation must be recorded in the status event log"
    record = records[0]
    assert record["wp_id"] == "WP02"
    assert record["from_lane"] == record["to_lane"] == "canceled"
    assert record["reason_source"] == "operator"
    assert record["force"] is True
    assert str(record["actor"]).strip()
    assert _ATTEST_REASON in str(record["reason"])
    assert record["at"]


def test_attestation_for_a_wp_that_is_not_canceled_is_rejected(tmp_path: Path) -> None:
    """FR-012: the flag applies only to a canceled WP — nothing is recorded otherwise."""
    mission = build_coord_mission_mixed_lane_canceled(
        tmp_path,
        canceled_changes=[PlantedChange(_LEAKED_PATH, "X = 1\n")],
        survivor_after=[PlantedChange(_LEAKED_PATH, None)],
        stamp_attribution=False,
        mid8="01M5046X",
    )
    rc, out = _consolidate(mission, _ATTEST_FLAG, "WP01", "--attest-reason", "not canceled")
    assert rc != 0
    assert "not canceled: WP01" in out, out
    assert _attestation_records(mission) == []


def test_attestation_without_reason_is_rejected_before_any_work(tmp_path: Path) -> None:
    mission = _build_failing_mixed_lane(tmp_path, "01M5046Y")
    pre_sha = mission.rev(mission.target_branch)
    rc, out = _consolidate(mission, _ATTEST_FLAG, "WP02")
    assert rc == 2, out
    assert "--attest-reason" in out
    assert mission.rev(mission.target_branch) == pre_sha


def test_dry_run_says_the_attestation_flags_are_not_applied(tmp_path: Path) -> None:
    """Review MINOR: --dry-run must not silently drop the attestation flags."""
    mission = _build_failing_mixed_lane(tmp_path, "01M5046Z")
    rc, out = _consolidate(mission, "--dry-run", _ATTEST_FLAG, "WP02", "--attest-reason", "checked")
    assert rc == 0, out
    assert "--attest-canceled-superseded is not applied with --dry-run" in out, out
    assert _attestation_records(mission) == []
