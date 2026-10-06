"""WP04 T023 integration — default-policy healthy flow.

Scaffolds a minimal mission in tmp_path, invokes
``_build_retrospective_facilitator_callback`` and calls it directly,
then asserts:
  (a) A generator record is written to disk.
  (b) A ``RetrospectiveCaptured`` event appears in status.events.jsonl.
  (c) The event has a non-empty ``policy_source``.

T019: default post-completion flow under healthy conditions.
T021: policy_source attribution on every emitted event.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.integration]

import ulid as _ulid_mod



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _scaffold_minimal_mission(tmp_path: Path, mission_slug: str) -> tuple[Path, str]:
    """Create a minimal mission directory under tmp_path/kitty-specs/."""
    mission_id = str(_ulid_mod.ULID())
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    feature_dir.mkdir(parents=True)

    (feature_dir / "meta.json").write_text(
        json.dumps({
            "mission_id": mission_id,
            "mission_slug": mission_slug,
            "mission_type": "software-dev",
            "friendly_name": "Test Mission",
            "mission_number": None,
        }),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Functional Requirements\n\n"
        "| ID | Requirement | Acceptance Criteria | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| FR-001 | First requirement | Covered by WP01. | proposed |\n",
        encoding="utf-8",
    )
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir()
    (tasks_dir / "WP01.md").write_text(
        "---\nwork_package_id: WP01\nlane: done\ndependencies: []\n"
        "requirement_refs: [FR-001]\ntitle: WP01 Test\n---\n# WP01\n",
        encoding="utf-8",
    )

    # Bootstrap a WP done event in status.events.jsonl so generator can read it.
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


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_default_flow_healthy_writes_record_and_emits_captured(tmp_path: Path) -> None:
    """Default flow: healthy mission → record on disk + RetrospectiveCaptured event."""
    from runtime.next.runtime_bridge_retrospective import _build_retrospective_facilitator_callback

    mission_slug = "default-flow-healthy-01KQ"
    feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)

    # Build and invoke the facilitator callback.
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

    # (a) A record was returned (truthy sentinel).
    assert result is not None, "Callback must return the generated record"

    # (b) Record written to canonical disk path.
    canonical = feature_dir / "retrospective.yaml"
    assert canonical.exists(), f"Expected record at {canonical}"

    # (c) RetrospectiveCaptured event in status.events.jsonl.
    events_raw = (feature_dir / "status.events.jsonl").read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in events_raw if line.strip()]
    captured_events = [e for e in events if e.get("type") == "RetrospectiveCaptured"]
    assert captured_events, "Expected at least one RetrospectiveCaptured event"

    captured = captured_events[0]

    # (d) policy_source is non-empty (T021).
    assert captured.get("policy_source"), (
        f"policy_source must be non-empty on RetrospectiveCaptured; got: {captured.get('policy_source')!r}"
    )

    # (e) provenance_kind matches what we passed.
    assert captured.get("provenance_kind") == "runtime_post_completion"
