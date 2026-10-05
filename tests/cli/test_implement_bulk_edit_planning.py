"""Regression tests for implement bulk-edit planning preflight."""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from specify_cli.cli.commands.implement import implement
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _bypass_charter_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """These unit tests do not stage a charter; bypass the preflight gate.

    Without this, ``spec-kitty implement`` returns ``Error: charter_source
    missing`` before the bulk-edit planning code under test runs.
    """
    from specify_cli.charter_runtime.preflight.result import CharterPreflightResult

    result = CharterPreflightResult(passed=True, checks=[])
    monkeypatch.setattr(
        "specify_cli.charter_runtime.preflight.hook.run_preflight_or_abort",
        lambda *_args, **_kwargs: result,
    )


def _write_meta(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": feature_dir.name,
                "slug": feature_dir.name,
                "friendly_name": feature_dir.name,
                "mission_type": "software-dev",
                "target_branch": "main",
                "created_at": "2026-05-21T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )


def _write_lanes(feature_dir: Path) -> None:
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug=feature_dir.name,
            mission_id=f"mission-{feature_dir.name}",
            mission_branch=f"kitty/mission-{feature_dir.name}",
            target_branch="main",
            lanes=[
                ExecutionLane(
                    lane_id="lane-a",
                    wp_ids=("WP01",),
                    write_scope=("src/**",),
                    predicted_surfaces=("runtime",),
                    depends_on_lanes=(),
                    parallel_group=0,
                )
            ],
            computed_at="2026-05-21T00:00:00Z",
            computed_from="test",
        ),
    )


def _build_feature(tmp_path: Path, *, owned_file: str) -> Path:
    mission_slug = "bulk-planning-demo"
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_meta(feature_dir)
    _write_lanes(feature_dir)
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n"
        "This mission will bulk edit rename across the codebase and replace everywhere.\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-plan.md").write_text(
        "---\n"
        "work_package_id: WP01\n"
        "title: Plan edit\n"
        "dependencies: []\n"
        "execution_mode: code_change\n"
        "owned_files:\n"
        f"  - {owned_file}\n"
        "authoritative_surface: src/example/\n"
        "---\n"
        "# WP01\n",
        encoding="utf-8",
    )
    # Seed WP01 out of the non-display 'genesis' state into 'planned' (as
    # finalize-tasks does) so implement's start-implementation composite
    # (planned -> claimed -> in_progress) is legal.
    seed_event = {
        "actor": "seed",
        "at": "2026-05-31T00:00:00+00:00",
        "event_id": "01HXYZ0123456789ABCDEFGS01",
        "evidence": None,
        "execution_mode": "worktree",
        "force": False,
        "from_lane": "genesis",
        "mission_slug": mission_slug,
        "reason": "seed",
        "review_ref": None,
        "to_lane": "planned",
        "wp_id": "WP01",
    }
    (feature_dir / "status.events.jsonl").write_text(
        json.dumps(seed_event, sort_keys=True) + "\n", encoding="utf-8"
    )
    return feature_dir


def _workspace(feature_dir: Path) -> MagicMock:
    return MagicMock(
        workspace_path=feature_dir.parent.parent / ".worktrees" / f"{feature_dir.name}-lane-a",
        branch_name=f"kitty/mission-{feature_dir.name}-lane-a",
        lane_id="lane-a",
        mission_branch=f"kitty/mission-{feature_dir.name}",
        is_reuse=False,
    )


@contextmanager
def _patched_implement(tmp_path: Path, feature_dir: Path):
    with (
        patch("specify_cli.cli.commands.implement.find_repo_root", return_value=tmp_path),
        patch(
            "specify_cli.cli.commands.implement_phases.detect_feature_context",
            return_value=(None, feature_dir.name),
        ),
        patch(
            "specify_cli.workspace.context.resolve_mission_target_branch",
            return_value="main",
        ),
        patch("specify_cli.cli.commands.implement_planning_commit._ensure_planning_artifacts_committed_git"),
        patch("specify_cli.cli.commands.implement_phases._ensure_vcs_in_meta", return_value=MagicMock(value="git")),
        patch("specify_cli.cli.commands.implement_phases.create_lane_workspace", return_value=_workspace(feature_dir)) as create_workspace,
    ):
        yield create_workspace


def test_occurrence_map_planning_wp_does_not_require_acknowledgement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    feature_dir = _build_feature(tmp_path, owned_file="occurrence_map.yaml")

    with _patched_implement(tmp_path, feature_dir) as create_workspace:
        implement("WP01", mission=feature_dir.name, recover=False, auto_commit=False)

    output = capsys.readouterr().out
    assert "Bulk Edit Inference Informational" in output
    assert "Bulk Edit Inference Warning" not in output
    create_workspace.assert_called_once()


def test_active_rewrite_wp_still_requires_acknowledgement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    feature_dir = _build_feature(tmp_path, owned_file="src/runtime/**")

    with (
        _patched_implement(tmp_path, feature_dir) as create_workspace,
        pytest.raises(typer.Exit) as exc_info,
    ):
        implement("WP01", mission=feature_dir.name, recover=False, auto_commit=False)

    assert exc_info.value.exit_code == 1
    output = capsys.readouterr().out
    assert "Bulk Edit Inference Warning" in output
    assert "--acknowledge-not-bulk-edit" in output
    create_workspace.assert_not_called()


def test_non_utf8_spec_without_bulk_edit_signal_does_not_block_implement(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    feature_dir = _build_feature(tmp_path, owned_file="src/runtime/**")
    (feature_dir / "spec.md").write_bytes(
        b"\xff\xfe# Spec\n\nRegular feature work with no occurrence-sensitive wording.\n"
    )

    with _patched_implement(tmp_path, feature_dir) as create_workspace:
        implement("WP01", mission=feature_dir.name, recover=False, auto_commit=False)

    output = capsys.readouterr().out
    assert "Bulk Edit Inference Warning" not in output
    create_workspace.assert_called_once()
