"""Unit coverage for WP01 change_mode normalization plumbing.

Covers the report-surface field (``MissionRepairResult.meta_actions``, T003) and
the canonicalizer wiring (``_canonicalize_meta`` records ``normalized_change_mode``
conditionally, T004) at the smallest testable seams — no git repo required.

Tactic references:
- ``tdd-red-green-refactor``: focused unit tests for the new field/branch.
- ``function-over-form-testing``: assert observable serialization/action output.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.migration.mission_state import (
    MissionRepairResult,
    _canonicalize_meta,
)

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _write_meta(mission_dir: Path, *, change_mode: object | None = None) -> None:
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta: dict[str, object] = {
        "slug": mission_dir.name,
        "mission_slug": mission_dir.name,
        "friendly_name": mission_dir.name,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-07-03T10:00:00+00:00",
        "mission_id": "01KWNP7Q8R9TVWXY2Z3A4B5C00",
    }
    if change_mode is not None:
        meta["change_mode"] = change_mode
    (mission_dir / "meta.json").write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")


# ── T003: MissionRepairResult.meta_actions serialization ────────────────────


def test_mission_repair_result_defaults_meta_actions_empty() -> None:
    result = MissionRepairResult(
        mission_slug="demo",
        mission_id=None,
        status="unchanged",
    )
    assert result.meta_actions == []
    assert result.to_dict()["meta_actions"] == []


def test_mission_repair_result_serializes_meta_actions() -> None:
    result = MissionRepairResult(
        mission_slug="demo",
        mission_id="01KWNP7Q8R9TVWXY2Z3A4B5C00",
        status="updated",
        meta_actions=["normalized_change_mode:regular"],
    )
    payload = result.to_dict()
    assert payload["meta_actions"] == ["normalized_change_mode:regular"]
    # A round-trip through JSON preserves the field (manifest fidelity).
    assert json.loads(json.dumps(payload))["meta_actions"] == ["normalized_change_mode:regular"]


# ── T004: _canonicalize_meta records normalized_change_mode:{old} conditionally ─


def test_canonicalize_meta_records_action_for_legacy_change_mode(tmp_path: Path) -> None:
    mission = tmp_path / "legacy-mission"
    _write_meta(mission, change_mode="regular")

    meta, actions = _canonicalize_meta(mission, [])

    assert "change_mode" not in meta
    assert "normalized_change_mode:regular" in actions


def test_canonicalize_meta_no_action_when_change_mode_absent(tmp_path: Path) -> None:
    mission = tmp_path / "ordinary-mission"
    _write_meta(mission, change_mode=None)

    meta, actions = _canonicalize_meta(mission, [])

    assert "change_mode" not in meta
    assert not any(action.startswith("normalized_change_mode") for action in actions)


def test_canonicalize_meta_preserves_bulk_edit(tmp_path: Path) -> None:
    mission = tmp_path / "bulk-edit-mission"
    _write_meta(mission, change_mode="bulk_edit")

    meta, actions = _canonicalize_meta(mission, [])

    assert meta["change_mode"] == "bulk_edit"
    assert not any(action.startswith("normalized_change_mode") for action in actions)


@pytest.mark.parametrize(
    ("change_mode", "expected_action"),
    [
        ("regular", "normalized_change_mode:regular"),
        (42, "normalized_change_mode:42"),
    ],
)
def test_canonicalize_meta_records_dropped_value_faithfully(tmp_path: Path, change_mode: object, expected_action: str) -> None:
    """The recorded action names WHICH value was dropped (fidelity, #4780)."""
    mission = tmp_path / "legacy-mission"
    _write_meta(mission, change_mode=change_mode)

    meta, actions = _canonicalize_meta(mission, [])

    assert "change_mode" not in meta
    assert expected_action in actions


def test_canonicalize_meta_records_dropped_null_change_mode(tmp_path: Path) -> None:
    """A present-but-JSON-null ``change_mode`` is distinct from absence: the
    dropped value is faithfully captured as the string ``"None"`` (fidelity,
    #4780) -- ``_write_meta``'s ``change_mode=None`` default means "omit the
    key" (see ``test_canonicalize_meta_no_action_when_change_mode_absent``), so
    this test writes the JSON directly to get an explicit ``null`` on disk.
    """
    mission = tmp_path / "legacy-mission"
    mission.mkdir(parents=True, exist_ok=True)
    meta_payload = {
        "slug": mission.name,
        "mission_slug": mission.name,
        "friendly_name": mission.name,
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-07-03T10:00:00+00:00",
        "mission_id": "01KWNP7Q8R9TVWXY2Z3A4B5C00",
        "change_mode": None,
    }
    (mission / "meta.json").write_text(json.dumps(meta_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    meta, actions = _canonicalize_meta(mission, [])

    assert "change_mode" not in meta
    assert "normalized_change_mode:None" in actions
