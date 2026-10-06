"""WP04 T023 integration — enabled: false opt-out.

When policy.enabled is False, the facilitator callback returns None
immediately without writing any record or emitting any event.

T019: enabled=false → no events, no record, mission completes silently.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

import ulid as _ulid_mod
from ruamel.yaml import YAML


def _scaffold_minimal_mission(tmp_path: Path, mission_slug: str) -> tuple[Path, str]:
    """Create a minimal mission directory."""
    mission_id = str(_ulid_mod.ULID())
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({
            "mission_id": mission_id,
            "mission_slug": mission_slug,
            "mission_type": "software-dev",
        }),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    return feature_dir, mission_id


def _write_disabled_config(tmp_path: Path) -> None:
    """Write .kittify/config.yaml with enabled: false."""
    kittify = tmp_path / ".kittify"
    kittify.mkdir(parents=True, exist_ok=True)
    yaml = YAML()
    config = {"retrospective": {"enabled": False}}
    with (kittify / "config.yaml").open("w", encoding="utf-8") as fh:
        yaml.dump(config, fh)


@pytest.mark.integration
def test_opt_out_no_events_no_record(tmp_path: Path) -> None:
    """enabled=false → callback returns None, no events, no record."""
    from runtime.next.runtime_bridge_retrospective import _build_retrospective_facilitator_callback

    _write_disabled_config(tmp_path)

    mission_slug = "opt-out-test-01KQ"
    feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)

    callback = _build_retrospective_facilitator_callback(
        mission_slug=mission_slug,
        repo_root=tmp_path,
        provenance_kind="runtime_post_completion",
    )

    result = callback(
        mission_id=mission_id,
        feature_dir=feature_dir,
        repo_root=tmp_path,
    )

    # No record should have been written.
    canonical = feature_dir / "retrospective.yaml"
    assert not canonical.exists(), (
        f"No record should be written when policy.enabled=False; found {canonical}"
    )

    # No retrospective lifecycle events should have been appended.
    events_path = feature_dir / "status.events.jsonl"
    if events_path.exists():
        events = [
            json.loads(line)
            for line in events_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        retro_events = [
            e for e in events
            if e.get("type", "").startswith("Retrospective")
        ]
        assert not retro_events, (
            f"No retrospective events should be emitted when policy.enabled=False; "
            f"found: {retro_events}"
        )

    # Callback returns None as no-op sentinel.
    assert result is None, (
        f"Callback must return None (no-op) when policy.enabled=False; got {result!r}"
    )
