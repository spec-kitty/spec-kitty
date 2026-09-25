"""WP02 / T011: command-level acceptable-ending behavior for canceled WPs.

Drives the CANONICAL flow — the cancellation whose provenance is under test is
produced through the real ``move-task`` command (Typer ``CliRunner``), never a
hand-edited ``canceled`` event — then runs the real acceptance authority
(``collect_feature_summary`` / ``perform_acceptance``) and asserts:

* approved + canceled(**operator** provenance, via ``--note``) → accept eligible;
  the canceled WP is reported under ``canceled_wps`` (NFR-003 pinned shape,
  validated against ``contracts/accept-canceled-wps.schema.json``) and is NOT a
  blocker (FR-001/FR-002).
* canceled(**synthetic** provenance, via ``--force`` with no note) → a structured
  blocker naming the WP and "operator-authored cancellation provenance required"
  (FR-003); the WP is ABSENT from ``canceled_wps``.
* a WP still in a non-terminal lane blocks acceptance (FR-006).

Only pre-cancel lane states are seeded via the event store (a standard fixture
convenience, mirroring ``test_cancellation_provenance``); the cancellation — the
behavior under test — always goes through the canonical command surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

import jsonschema
import pytest
from typer.testing import CliRunner

from specify_cli.acceptance import collect_feature_summary, perform_acceptance
from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import append_event
from tests.lane_test_utils import write_single_lane_manifest
from tests.mocked_env import setup_mocked_env

pytestmark = [pytest.mark.integration, pytest.mark.fast]

runner = CliRunner()

_TARGET_BRANCH = "main"


def _canceled_wps_schema() -> dict[str, Any]:
    """Load the pinned ``canceled_wps`` contract schema (single source of truth)."""
    repo_root = Path(__file__).resolve().parents[2]
    matches = sorted(repo_root.glob("kitty-specs/**/contracts/accept-canceled-wps.schema.json"))
    assert matches, "accept-canceled-wps.schema.json contract not found under kitty-specs/"
    return json.loads(matches[0].read_text(encoding="utf-8"))


def _minimal_meta(mission_slug: str) -> dict[str, Any]:
    return {
        "mission_number": mission_slug.split("-")[0],
        "slug": mission_slug,
        "mission_slug": mission_slug,
        "friendly_name": "Acceptable Ending Test",
        "mission_type": "software-dev",
        "target_branch": _TARGET_BRANCH,
        "created_at": "2026-08-28T00:00:00+00:00",
    }


def _write_wp_file(tasks_dir: Path, wp_id: str) -> None:
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (tasks_dir / f"{wp_id}.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\n"
        f"execution_mode: code_change\nagent: testbot\n"
        f"subtasks: []\n"
        f"owned_files:\n  - src/{wp_id.lower()}/**\n"
        f"authoritative_surface: src/{wp_id.lower()}/\n---\n\n# {wp_id}\n\n## Activity Log\n",
        encoding="utf-8",
    )


def _scaffold_mission(tmp_path: Path, mission_slug: str, wp_ids: list[str]) -> Path:
    """Create a flat mission dir with meta + required artifacts + WP task files."""
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".kittify").mkdir(exist_ok=True)

    (feature_dir / "meta.json").write_text(
        json.dumps(_minimal_meta(mission_slug), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    for artifact in ("spec.md", "plan.md", "tasks.md"):
        # A single CHECKED row keeps the unchecked-tasks gate silent regardless
        # of the FR-009 normalization, so the assertions isolate the acceptable-
        # ending behavior under test.
        (feature_dir / artifact).write_text(f"# {artifact}\n\n- [x] done\n", encoding="utf-8")

    for wp_id in wp_ids:
        _write_wp_file(feature_dir / "tasks", wp_id)

    # #4891: accept fails closed when lanes.json is absent. A planning-lane
    # manifest keeps the (irrelevant here) acceptance-matrix gate a no-op
    # while satisfying the now-unconditional lanes gate; target_branch matches
    # the mocked "main" branch _collect() uses throughout this module.
    write_single_lane_manifest(
        feature_dir,
        wp_ids=tuple(wp_ids),
        lane_id="lane-planning",
        target_branch=_TARGET_BRANCH,
    )

    return feature_dir


def _seed_lane(feature_dir: Path, mission_slug: str, wp_id: str, lane: str) -> None:
    """Seed a WP's pre-cancel lane directly in the event store (fixture only)."""
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"seed-{wp_id}-{lane}",
            mission_slug=mission_slug,
            wp_id=wp_id,
            from_lane=Lane.PLANNED,
            to_lane=Lane(lane),
            at="2026-08-28T00:00:00+00:00",
            actor="seed",
            force=True,
            execution_mode="worktree",
            reason=f"seed to {lane}",
        ),
    )


def _cancel_via_move_task(tmp_path: Path, mission_slug: str, wp_id: str, *, note: str | None) -> None:
    """Cancel ``wp_id`` through the canonical ``move-task`` command surface."""
    args = ["move-task", wp_id, "--to", "canceled", "--mission", mission_slug, "--no-auto-commit"]
    if note is None:
        args.append("--force")
    else:
        args.extend(["--note", note])
    with setup_mocked_env(tmp_path, mission_slug=mission_slug, workspace_resolution=FileNotFoundError):
        result = runner.invoke(app, args, catch_exceptions=False)
    assert result.exit_code == 0, f"move-task failed:\n{result.output}"


def _collect(tmp_path: Path, mission_slug: str) -> Any:
    with patch("specify_cli.acceptance.run_git") as mock_git, patch("specify_cli.acceptance.git_status_lines", return_value=[]):
        mock_git.return_value.stdout = f"{_TARGET_BRANCH}\n"
        return collect_feature_summary(tmp_path, mission_slug, strict_metadata=False)


def test_approved_plus_operator_cancel_is_eligible_and_reported(tmp_path: Path) -> None:
    mission_slug = "099-acceptable-operator"
    feature_dir = _scaffold_mission(tmp_path, mission_slug, ["WP01", "WP02"])
    _seed_lane(feature_dir, mission_slug, "WP01", "approved")
    _seed_lane(feature_dir, mission_slug, "WP02", "in_progress")

    note = "replan: WP02 scope removed; capturing the operator rationale"
    _cancel_via_move_task(tmp_path, mission_slug, "WP02", note=note)

    summary = _collect(tmp_path, mission_slug)

    # The canceled-with-operator-provenance WP is an acceptable ending.
    assert summary.all_done is True, f"lanes={summary.lanes} activity={summary.activity_issues}"
    assert summary.ok is True, f"outstanding={summary.outstanding()}"

    # Reported separately under canceled_wps, NOT as a blocker (FR-002).
    assert [entry["wp_id"] for entry in summary.canceled_wps] == ["WP02"]
    assert summary.canceled_wps[0]["reason"] == note
    assert "lane_blockers" not in summary.outstanding()

    # NFR-003: the canceled_wps field validates against the pinned schema.
    jsonschema.validate({"canceled_wps": summary.canceled_wps}, _canceled_wps_schema())

    # And accept --json (the result payload) carries the same top-level field.
    result = perform_acceptance(summary, mode="local", actor="tester", auto_commit=False)
    payload = result.to_dict()
    jsonschema.validate({"canceled_wps": payload["canceled_wps"]}, _canceled_wps_schema())
    assert payload["canceled_wps"] == summary.canceled_wps


def test_synthetic_cancel_blocks_and_absent_from_canceled_wps(tmp_path: Path) -> None:
    mission_slug = "099-acceptable-synthetic"
    feature_dir = _scaffold_mission(tmp_path, mission_slug, ["WP01", "WP02"])
    _seed_lane(feature_dir, mission_slug, "WP01", "approved")
    _seed_lane(feature_dir, mission_slug, "WP02", "in_progress")

    # Bare force-cancel with no operator note → synthetic provenance.
    _cancel_via_move_task(tmp_path, mission_slug, "WP02", note=None)

    summary = _collect(tmp_path, mission_slug)

    assert summary.ok is False
    assert summary.canceled_wps == []

    outstanding = summary.outstanding()
    assert "lane_blockers" in outstanding
    blocker = next(item for item in outstanding["lane_blockers"] if "WP02" in item)
    assert "canonical lane is 'canceled'" in blocker
    assert "operator-authored cancellation provenance required" in blocker


def test_non_terminal_wp_still_blocks(tmp_path: Path) -> None:
    mission_slug = "099-acceptable-nonterminal"
    feature_dir = _scaffold_mission(tmp_path, mission_slug, ["WP01", "WP02"])
    _seed_lane(feature_dir, mission_slug, "WP01", "approved")
    _seed_lane(feature_dir, mission_slug, "WP02", "in_progress")

    summary = _collect(tmp_path, mission_slug)

    assert summary.all_done is False
    assert summary.ok is False
    assert summary.canceled_wps == []
    # FR-006: an in_progress WP is a genuine "not done" blocker.
    assert "WP02" in summary.outstanding().get("not_done", [])
