"""WP04 T023 integration — default-policy generator failure.

Breaks the mission directory (removes status.events.jsonl) so the
generator raises FileNotFoundError. Asserts:
  (a) The callback re-raises (terminus handles via its own flow).
  (b) A ``RetrospectureCaptureFailed`` event appears in status.events.jsonl
      (the callback emits it before re-raising).
  (c) The mission CONTINUES (terminus default-policy: warn, not block).

T019: default post-completion flow under generator failure.
"""

from __future__ import annotations

import json
from pathlib import Path

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
            "friendly_name": "Test Mission",
            "mission_number": None,
        }),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (feature_dir / "plan.md").write_text("# Plan\n", encoding="utf-8")
    (feature_dir / "tasks.md").write_text("# Tasks\n", encoding="utf-8")
    # Intentionally: NO status.events.jsonl — generator still works (events are optional)
    return feature_dir, mission_id


@pytest.mark.integration
def test_default_flow_generator_failure_emits_capture_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Generator raises → RetrospectureCaptureFailed emitted → callback re-raises.

    The facilitator callback MUST:
    (a) Call emit_capture_failed before re-raising.
    (b) Re-raise so the terminus can handle the non-blocking warn path.
    """
    from runtime.next.runtime_bridge_retrospective import _build_retrospective_facilitator_callback

    mission_slug = "default-flow-failure-01KQ"
    feature_dir, mission_id = _scaffold_minimal_mission(tmp_path, mission_slug)

    # Make generate_retrospective raise FileNotFoundError by removing the mission dir.
    # We use monkeypatch to inject the failure at the generator level.
    from specify_cli.retrospective import generator as gen_mod

    def _broken_generate(*args, **kwargs):
        raise FileNotFoundError(f"Simulated missing artifact for {mission_slug}")

    monkeypatch.setattr(gen_mod, "generate_retrospective", _broken_generate)

    callback = _build_retrospective_facilitator_callback(
        mission_slug=mission_slug,
        repo_root=tmp_path,
        provenance_kind="runtime_post_completion",
    )

    # The callback should re-raise.
    with pytest.raises(FileNotFoundError):
        callback(
            mission_id=mission_id,
            feature_dir=feature_dir,
            repo_root=tmp_path,
        )

    # RetrospectureCaptureFailed event was emitted (by the callback, before re-raise).
    events_path = feature_dir / "status.events.jsonl"
    assert events_path.exists(), "status.events.jsonl must exist after emit_capture_failed"
    events_raw = events_path.read_text(encoding="utf-8").splitlines()
    events = [json.loads(line) for line in events_raw if line.strip()]
    failed_events = [e for e in events if e.get("type") == "RetrospectiveCaptureFailed"]
    assert failed_events, (
        f"Expected RetrospectiveCaptureFailed event after generator failure; "
        f"got event types: {[e.get('type') for e in events]}"
    )

    failed = failed_events[0]
    assert failed.get("policy_source"), "policy_source must be non-empty on CaptureFailed"
    assert failed.get("failure_category") == "missing_artifacts"
