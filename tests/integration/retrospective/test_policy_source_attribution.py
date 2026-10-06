"""WP04 T023 integration — policy_source attribution on every emitted event.

Asserts that every emitted retrospective lifecycle event carries a non-empty
``policy_source`` field matching the resolver's output.

T021: every emitted retrospective event has non-empty policy_source.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

pytestmark = [pytest.mark.integration]

import ulid as _ulid_mod


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
            "friendly_name": "Attribution Test Mission",
            "mission_number": None,
        }),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | Attribution | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nlane: done\ndependencies: []\n"
        "requirement_refs: [FR-001]\ntitle: WP01 Attribution Test\n---\n# WP01\n",
        encoding="utf-8",
    )

    events_path = feature_dir / "status.events.jsonl"
    events_path.write_text(
        json.dumps({
            "actor": "test",
            "at": "2026-01-01T00:00:00+00:00",
            "event_id": str(_ulid_mod.ULID()),
            "evidence": None,
            "execution_mode": "worktree",
            "feature_slug": mission_slug,
            "force": False,
            "from_lane": "planned",
            "reason": None,
            "review_ref": None,
            "to_lane": "done",
            "wp_id": "WP01",
        }) + "\n",
        encoding="utf-8",
    )
    return feature_dir, mission_id


def _read_retro_events(feature_dir: Path) -> list[dict[str, Any]]:
    """Read all retrospective lifecycle events from status.events.jsonl."""
    events_path = feature_dir / "status.events.jsonl"
    if not events_path.exists():
        return []
    events = [
        json.loads(line)
        for line in events_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [
        e for e in events
        if e.get("type", "").startswith("Retrospective")
    ]


@pytest.mark.integration
def test_captured_event_has_non_empty_policy_source_defaults_only(tmp_path: Path) -> None:
    """No charter, no config → all policy_source leaf values are '<default>'."""
    from runtime.next.runtime_bridge_retrospective import _build_retrospective_facilitator_callback

    mission_slug = "attribution-defaults-01KQ"
    feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)

    callback = _build_retrospective_facilitator_callback(
        mission_slug=mission_slug,
        repo_root=tmp_path,
        provenance_kind="runtime_post_completion",
    )

    callback(
        mission_id=mission_id,
        feature_dir=feature_dir,
        repo_root=tmp_path,
    )

    retro_events = _read_retro_events(feature_dir)
    assert retro_events, "Expected at least one retrospective event"

    for event in retro_events:
        event_type = event.get("type")
        ps = event.get("policy_source")
        assert ps, (
            f"policy_source must be non-empty on {event_type}; got: {ps!r}"
        )
        # When no charter or config is present, all leaf keys should be '<default>'.
        for key, value in ps.items():
            assert value == "<default>", (
                f"Expected '<default>' for policy_source[{key!r}] with no config; "
                f"got {value!r} on event {event_type}"
            )


@pytest.mark.integration
def test_all_retro_events_have_policy_source_after_callback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every RetroX event emitted by the callback has a non-empty policy_source.

    Triggers both captured AND capture_failed by running two scenarios and
    checking all emitted events.
    """
    from runtime.next.runtime_bridge_retrospective import _build_retrospective_facilitator_callback
    from specify_cli.retrospective import generator as gen_mod

    # --- Scenario 1: Healthy (produces RetrospectiveCaptured) ---
    mission_slug_a = "attribution-healthy-01KQ"
    feature_dir_a, mission_id_a = _scaffold_minimal_mission(tmp_path, mission_slug_a)

    callback_a = _build_retrospective_facilitator_callback(
        mission_slug=mission_slug_a,
        repo_root=tmp_path,
        provenance_kind="runtime_post_completion",
    )
    callback_a(
        mission_id=mission_id_a,
        feature_dir=feature_dir_a,
        repo_root=tmp_path,
    )

    # --- Scenario 2: Generator failure (produces RetrospectiveCaptureFailed) ---
    mission_slug_b = "attribution-failed-01KQ"
    feature_dir_b, mission_id_b = _scaffold_minimal_mission(tmp_path, mission_slug_b)

    def _broken_generate(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(gen_mod, "generate_retrospective", _broken_generate)

    callback_b = _build_retrospective_facilitator_callback(
        mission_slug=mission_slug_b,
        repo_root=tmp_path,
        provenance_kind="runtime_post_completion",
    )
    with pytest.raises(RuntimeError):
        callback_b(
            mission_id=mission_id_b,
            feature_dir=feature_dir_b,
            repo_root=tmp_path,
        )

    # Assert every emitted retrospective event has policy_source.
    for feature_dir, label in [(feature_dir_a, "healthy"), (feature_dir_b, "failed")]:
        retro_events = _read_retro_events(feature_dir)
        for event in retro_events:
            ps = event.get("policy_source")
            assert ps, (
                f"[{label}] policy_source empty on {event.get('type')}; event: {event}"
            )
