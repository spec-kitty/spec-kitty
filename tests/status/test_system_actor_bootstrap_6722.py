"""The bootstrap seed records the structured system actor (#6722, FR-002).

``finalize-tasks`` seeds ``genesis -> planned`` for every uninitialised work package.
Since #6722 that event carries ``{"tool": "finalize-tasks", "role": "system",
"profile": null, "model": null}`` instead of the bare string, and the reduced snapshot's
``actor`` slot still reads the bare tool.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.status.bootstrap import bootstrap_canonical_state
from specify_cli.status.models import StatusEvent, actor_identity_str
from specify_cli.status.store import read_events

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_SYSTEM_BOOTSTRAP_ACTOR = {"tool": "finalize-tasks", "role": "system", "profile": None, "model": None}


def _write_wp_file(tasks_dir: Path, wp_id: str) -> Path:
    wp_file = tasks_dir / f"{wp_id}.md"
    wp_file.write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Test WP\n---\n\n# Test WP\n",
        encoding="utf-8",
    )
    return wp_file


@pytest.fixture(autouse=True)
def _disable_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    """These tests assert local state seeding, not SaaS sync behaviour."""
    import specify_cli.status.emit as emit_module

    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *args, **kwargs: None)


def test_bootstrap_seed_keeps_its_lane_payload_and_identity(tmp_path: Path) -> None:
    """Only the actor changes: the lane edge, force flag and reason stay as they were."""
    feature_dir = tmp_path / "kitty-specs" / "060-test-feature"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_wp_file(tasks_dir, "WP01")

    bootstrap_canonical_state(feature_dir, "060-test-feature")

    (event,) = read_events(feature_dir)
    assert isinstance(event, StatusEvent)
    assert str(event.from_lane) == "genesis"
    assert str(event.to_lane) == "planned"
    assert event.force is False
    assert event.reason == "canonical bootstrap"
    # The display identity every board and guard reads is unchanged.
    assert actor_identity_str(event.actor) == "finalize-tasks"


def test_bootstrap_seed_snapshot_actor_slot_reads_the_tool(tmp_path: Path) -> None:
    feature_dir = tmp_path / "kitty-specs" / "060-test-feature"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_wp_file(tasks_dir, "WP01")

    bootstrap_canonical_state(feature_dir, "060-test-feature")

    snapshot = json.loads((feature_dir / "status.json").read_text(encoding="utf-8"))
    assert snapshot["work_packages"]["WP01"]["actor"] == "finalize-tasks"
    assert snapshot["summary"]["planned"] == 1


def test_a_preexisting_string_seed_row_is_untouched(tmp_path: Path) -> None:
    """An already-initialised WP is never re-seeded, so its old string row survives (#6722 C-003)."""
    feature_dir = tmp_path / "kitty-specs" / "060-test-feature"
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_wp_file(tasks_dir, "WP01")
    legacy = {
        "event_id": "01LEGACYSEED00000000000001",
        "mission_slug": "060-test-feature",
        "wp_id": "WP01",
        "from_lane": "genesis",
        "to_lane": "planned",
        "at": "2026-01-01T00:00:00+00:00",
        "actor": "finalize-tasks",
        "force": False,
        "execution_mode": "worktree",
        "reason": "canonical bootstrap",
    }
    (feature_dir / "status.events.jsonl").write_text(json.dumps(legacy, sort_keys=True) + "\n", encoding="utf-8")

    result = bootstrap_canonical_state(feature_dir, "060-test-feature")

    assert result.newly_seeded == 0
    (event,) = read_events(feature_dir)
    assert event.actor == "finalize-tasks"
    assert actor_identity_str(event.actor) == actor_identity_str(_SYSTEM_BOOTSTRAP_ACTOR)
