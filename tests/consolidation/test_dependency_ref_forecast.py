"""Forecast parity for the declared dependency ref (#6771).

The issue's other half: ``--dry-run`` exited 0 on a mission whose real
``--strategy merge`` run refused, because the forecast terminated before
reconciliation ran. These tests pin that the forecast now builds the same claim and
runs the same closed-world window scan, so a refusal is predictable before any ref
moves — and that the declaration that resolves it passes the forecast too.

Red-first on ``main``: ``--dependency-ref`` is not a flag, and ``--dry-run`` exits 0
on the undeclared repro.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from tests.terminus.conftest import (
    build_coord_mission,
    restamp_approvals_at_lane_tips,
    run_terminus,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

DEP_BRANCH = "dep-branch"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _plant_dependency_branch(mission: object, tmp_path: Path) -> str:
    """An external branch cut from the repo root, merged --no-ff into WP02's lane.

    Review then approves the merged tree (``restamp_approvals_at_lane_tips``) — the
    shape a restack onto a newer dependency head has.
    """
    repo: Path = mission.repo  # type: ignore[attr-defined]
    lane_branch = mission.lane_branch("WP02")  # type: ignore[attr-defined]
    root = _git(repo, "rev-list", "--max-parents=0", "HEAD")
    _git(repo, "branch", DEP_BRANCH, root)
    dep_wt = tmp_path / "dep-wt"
    _git(repo, "worktree", "add", dep_wt.as_posix(), DEP_BRANCH)
    for idx in range(2):
        target = dep_wt / "src" / "dep" / f"mod{idx}.py"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f"DEP = {idx}\n", encoding="utf-8")
        _git(dep_wt, "add", "-A")
        _git(dep_wt, "commit", "-qm", f"feat(dep): mod{idx}")
    _git(repo, "worktree", "remove", dep_wt.as_posix())

    lane_wt = tmp_path / "lane-wt"
    _git(repo, "worktree", "add", lane_wt.as_posix(), lane_branch)
    _git(lane_wt, "merge", "-q", "--no-ff", "--no-edit", DEP_BRANCH)
    _git(repo, "worktree", "remove", lane_wt.as_posix())
    restamp_approvals_at_lane_tips(mission)  # type: ignore[arg-type]
    return _git(repo, "rev-parse", DEP_BRANCH)


def _dry_run(mission: object, *extra: str) -> subprocess.CompletedProcess[str]:
    return run_terminus(
        mission,  # type: ignore[arg-type]
        ["consolidate", "--mission", mission.slug, "--strategy", "merge", "--dry-run", *extra],  # type: ignore[attr-defined]
    )


def test_forecast_refuses_the_undeclared_dependency_merge(tmp_path: Path) -> None:
    """The pre-fix defect: dry-run 0, real run 1. The forecast must refuse instead."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771F")
    dep_tip = _plant_dependency_branch(mission, tmp_path)

    result = _dry_run(mission)

    assert result.returncode != 0, f"--dry-run must predict the closed-world refusal, exited 0:\n{result.stdout[-2000:]}"
    assert dep_tip[:10] in result.stdout, "the forecast must name the dependency commit the real run reports"
    assert "un-attributable" in result.stdout
    assert "--dependency-ref" in result.stdout, "the forecast must name the declaration that resolves it"


def test_forecast_passes_once_the_dependency_is_declared(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771G")
    _plant_dependency_branch(mission, tmp_path)

    result = _dry_run(mission, "--dependency-ref", DEP_BRANCH)

    assert result.returncode == 0, result.stdout[-2000:]
    assert "would FAIL" not in result.stdout, "a declared dependency must not be reported as a would-be refusal"


def test_forecast_refuses_an_unresolvable_declaration(tmp_path: Path) -> None:
    """A mis-declaration must refuse on the forecast too — never a green preview."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771H")
    _plant_dependency_branch(mission, tmp_path)

    result = _dry_run(mission, "--dependency-ref", "no-such-ref")

    assert result.returncode != 0
    assert "no-such-ref" in result.stdout


def test_forecast_json_reports_the_refusal_with_a_stable_code(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771J")
    _plant_dependency_branch(mission, tmp_path)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--strategy", "merge", "--dry-run", "--json"])

    assert result.returncode != 0
    payload = json.loads(result.stdout.strip().splitlines()[-1])
    assert payload["error_code"] == "UNATTRIBUTABLE_CONTENT_FORECAST"
    assert "un-attributable" in payload["error"]


def _record_declaration(mission: object, *refs: str, pins: dict[str, str] | None = None) -> None:
    """Write the transaction record an interrupted run of ``consolidate --dependency-ref`` leaves behind."""
    from specify_cli.consolidation.state import ConsolidationState, save_state

    state = ConsolidationState(
        mission_id=mission.mission_id,  # type: ignore[attr-defined]
        mission_slug=mission.slug,  # type: ignore[attr-defined]
        target_branch=mission.target_branch,  # type: ignore[attr-defined]
        wp_order=["WP01", "WP02"],
        dependency_refs=list(refs),
        dependency_ref_pins=pins or {},
    )
    save_state(state, mission.repo)  # type: ignore[attr-defined]


def test_forecast_unions_the_recorded_declaration_with_the_command_line(tmp_path: Path) -> None:
    """``--dry-run`` previews the run a re-run would make, which reads the recorded declaration."""
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771R")
    _plant_dependency_branch(mission, tmp_path)
    assert _dry_run(mission).returncode != 0, "control: undeclared and unrecorded, the forecast refuses"
    _record_declaration(mission, DEP_BRANCH)

    result = _dry_run(mission)

    assert result.returncode == 0, result.stdout[-2000:]
    # A command-line set that differs from the recorded one is the refusal the real run gives, not a green preview.
    differing = _dry_run(mission, "--dependency-ref", "other-ref")
    assert differing.returncode != 0
    assert "Error code: DEPENDENCY_REF_SET_CHANGED." in " ".join(differing.stdout.split())


def test_forecast_refuses_a_recorded_ref_that_moved_since_it_was_pinned(tmp_path: Path) -> None:
    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771S")
    dep_tip = _plant_dependency_branch(mission, tmp_path)
    root = _git(mission.repo, "rev-list", "--max-parents=0", "HEAD")  # type: ignore[attr-defined]
    _record_declaration(mission, DEP_BRANCH, pins={DEP_BRANCH: root})

    result = _dry_run(mission)

    assert result.returncode != 0
    assert "Error code: DEPENDENCY_REF_MOVED." in result.stdout
    assert root[:10] in result.stdout and dep_tip[:10] in result.stdout


def test_resume_with_a_different_declared_set_is_refused_and_keeps_the_record(tmp_path: Path) -> None:
    """The record is the audit trail of what the interrupted run exempted: a different set never replaces it."""
    from specify_cli.consolidation.state import load_state

    mission = build_coord_mission(tmp_path, wps=("WP01", "WP02"), mid8="01M6771T")
    _plant_dependency_branch(mission, tmp_path)
    _record_declaration(mission, DEP_BRANCH)

    result = run_terminus(mission, ["consolidate", "--mission", mission.slug, "--yes", "--strategy", "merge", "--resume", "--dependency-ref", "other-ref"])

    assert result.returncode != 0
    assert "Error code: DEPENDENCY_REF_SET_CHANGED." in result.stdout
    assert "consolidate --abort" in result.stdout
    recorded = load_state(mission.repo, mission.mission_id)
    assert recorded is not None and recorded.dependency_refs == [DEP_BRANCH]


def test_declaration_round_trips_through_the_transaction_record() -> None:
    """A resume re-derives the same claim: the declaration and its pins are recorded, and a malformed entry fails closed."""
    from specify_cli.consolidation.state import ConsolidationState

    base = {"mission_id": "m", "mission_slug": "s", "target_branch": "main", "wp_order": []}
    state = ConsolidationState(
        mission_id="m", mission_slug="s", target_branch="main", wp_order=["WP01"], dependency_refs=["dep-branch"], dependency_ref_pins={"dep-branch": "a" * 40}
    )
    loaded = ConsolidationState.from_dict(state.to_dict())
    assert loaded.dependency_refs == ["dep-branch"]
    assert loaded.dependency_ref_pins == {"dep-branch": "a" * 40}
    # A hand-edited / corrupt entry loads as "declared nothing" / "pinned nothing" (fail closed: no exemption).
    malformed = {**base, "dependency_refs": "dep", "dependency_ref_pins": ["dep"]}
    assert ConsolidationState.from_dict(malformed).dependency_refs == []
    assert ConsolidationState.from_dict(malformed).dependency_ref_pins == {}
    # Back-compat: a record written before pins existed holds names only; its refs load UNPINNED
    # and are pinned by the next claim build (first use).
    legacy = ConsolidationState.from_dict({**base, "dependency_refs": ["dep-branch"]})
    assert legacy.dependency_refs == ["dep-branch"] and legacy.dependency_ref_pins == {}
    assert ConsolidationState.from_dict(base).dependency_refs == []
