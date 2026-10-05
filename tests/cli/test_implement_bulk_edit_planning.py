"""Regression tests for implement bulk-edit planning preflight.

Each test calls the bulk-edit phase (``implement_phases.run_bulk_edit_gate``) directly with a real
mission directory and asserts its verdict (raise or proceed) and its console output; nothing in the
implement command family is patched. The CLI smoke for this family is the characterization
refusal (``test_unacknowledged_bulk_edit_inference_is_refused_and_the_flag_lets_it_through``).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import typer

from specify_cli.cli.commands import implement_phases
from specify_cli.cli.commands.implement_phases import ImplementContext
from specify_cli.cli.console import console
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import write_lanes_json

pytestmark = pytest.mark.fast


@pytest.fixture(autouse=True)
def _wide_console(monkeypatch: pytest.MonkeyPatch) -> None:
    """Render the panels without wrapping so phrases compare whole."""
    monkeypatch.setenv("COLUMNS", "240")


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


def _context(tmp_path: Path, feature_dir: Path) -> ImplementContext:
    wp_file = feature_dir / "tasks" / "WP01-plan.md"
    return ImplementContext(tmp_path, False, feature_dir.name, feature_dir, wp_file, [])


def _run_gate(ctx: ImplementContext) -> str:
    """Run the bulk-edit phase the way ``implement`` does (no acknowledgement); return its output."""
    with console.capture() as capture:
        implement_phases.run_bulk_edit_gate(ctx, "WP01", acknowledge_not_bulk_edit=False)
    return capture.get()


def test_occurrence_map_planning_wp_does_not_require_acknowledgement(tmp_path: Path) -> None:
    feature_dir = _build_feature(tmp_path, owned_file="occurrence_map.yaml")

    # The phase returns (the claim proceeds to allocation) instead of raising.
    output = _run_gate(_context(tmp_path, feature_dir))

    assert "Bulk Edit Inference Informational" in output
    assert "Bulk Edit Inference Warning" not in output


def test_active_rewrite_wp_still_requires_acknowledgement(tmp_path: Path) -> None:
    feature_dir = _build_feature(tmp_path, owned_file="src/runtime/**")

    with console.capture() as capture, pytest.raises(typer.Exit) as exc_info:
        implement_phases.run_bulk_edit_gate(_context(tmp_path, feature_dir), "WP01", acknowledge_not_bulk_edit=False)

    assert exc_info.value.exit_code == 1
    output = capture.get()
    assert "Bulk Edit Inference Warning" in output
    assert "--acknowledge-not-bulk-edit" in output


def test_non_utf8_spec_without_bulk_edit_signal_does_not_block_implement(tmp_path: Path) -> None:
    feature_dir = _build_feature(tmp_path, owned_file="src/runtime/**")
    (feature_dir / "spec.md").write_bytes(
        b"\xff\xfe# Spec\n\nRegular feature work with no occurrence-sensitive wording.\n"
    )

    # The phase returns (the claim proceeds to allocation) instead of raising.
    output = _run_gate(_context(tmp_path, feature_dir))

    assert "Bulk Edit Inference Warning" not in output
