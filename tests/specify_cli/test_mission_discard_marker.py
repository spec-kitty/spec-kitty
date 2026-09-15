"""``mission close --discard`` marks a mission instead of deleting it (#704).

The reporter asked for the spec directory to be removed on discard. It cannot
be: the discard leg persists a ``runtime_abandoned`` retrospective into
``kitty-specs/<slug>/`` first (persist-before-destroy, FR-005), and
``iter_mission_instance_dirs`` discovers mission records from exactly that
directory (FR-013). Deleting it would throw away the abandonment record the
command had just written.

These tests pin the marker that replaces the deletion, and the tolerance the
discard path needs around it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.core.paths import MissionMetaReadError
from specify_cli.mission_metadata import load_meta_strict, record_discard, write_meta

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_MISSION_ID = "01KVRJ6PQ7XB2M9K4D8N3FZ0YT"
_MID8 = _MISSION_ID[:8]
_MISSION_SLUG = f"discardable-mission-{_MID8}"


def _seed_mission(tmp_path: Path, **overrides: Any) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    meta: dict[str, Any] = {
        "mission_id": _MISSION_ID,
        "slug": _MISSION_SLUG,
        "mission_slug": _MISSION_SLUG,
        "created_at": "2026-09-01T00:00:00+00:00",
    }
    meta.update(overrides)
    write_meta(feature_dir, meta, validate=False)
    return feature_dir


def test_record_discard_stamps_the_marker(tmp_path: Path) -> None:
    feature_dir = _seed_mission(tmp_path)

    record_discard(feature_dir)

    assert load_meta_strict(feature_dir)["discarded_at"]


def test_record_discard_preserves_the_rest_of_meta(tmp_path: Path) -> None:
    # The marker is additive: nothing that identifies the mission may be lost,
    # or the retrospective reducer stops resolving the record it just wrote.
    feature_dir = _seed_mission(tmp_path, coordination_branch="mission/coord")

    record_discard(feature_dir)

    meta = load_meta_strict(feature_dir)
    assert meta["mission_id"] == _MISSION_ID
    assert meta["slug"] == _MISSION_SLUG
    assert meta["coordination_branch"] == "mission/coord"


def test_record_discard_is_idempotent(tmp_path: Path) -> None:
    feature_dir = _seed_mission(tmp_path)

    record_discard(feature_dir)
    first = load_meta_strict(feature_dir)["discarded_at"]
    record_discard(feature_dir)
    second = load_meta_strict(feature_dir)["discarded_at"]

    assert first and second
    assert second >= first


def test_record_discard_on_a_missing_meta_raises_for_the_caller_to_absorb(
    tmp_path: Path,
) -> None:
    # A legacy mission has no meta.json. record_discard fails closed; the
    # tolerance lives at the discard call site, which suppresses it so an
    # otherwise-successful discard is not turned into a failure.
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)

    with pytest.raises(FileNotFoundError):
        record_discard(feature_dir)


def test_record_discard_marks_a_mission_with_an_incomplete_meta(tmp_path: Path) -> None:
    # The write skips validation on purpose: an abandoned mission is the likely
    # holder of a half-filled meta.json, and refusing the marker there would
    # leave exactly those missions listed on the dashboard.
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"slug": _MISSION_SLUG}), encoding="utf-8")

    record_discard(feature_dir)

    raw = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert raw["discarded_at"]


def test_discard_marker_survives_a_meta_reload(tmp_path: Path) -> None:
    # meta.json is committed by the discard path's bookkeeping leg, so the
    # marker has to be plain JSON a later process can read back.
    feature_dir = _seed_mission(tmp_path)

    record_discard(feature_dir)

    raw = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert isinstance(raw["discarded_at"], str)


def test_mark_mission_discarded_is_a_noop_on_a_legacy_mission(tmp_path: Path) -> None:
    # The discard call site absorbs the failure: a legacy mission with no
    # meta.json must not turn an otherwise-successful discard into an error.
    from specify_cli.cli.commands.mission_type import _mark_mission_discarded

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)

    _mark_mission_discarded(feature_dir)

    assert not (feature_dir / "meta.json").exists()


def test_mark_mission_discarded_stamps_a_normal_mission(tmp_path: Path) -> None:
    from specify_cli.cli.commands.mission_type import _mark_mission_discarded

    feature_dir = _seed_mission(tmp_path)

    _mark_mission_discarded(feature_dir)

    assert load_meta_strict(feature_dir)["discarded_at"]


def test_record_discard_on_a_corrupt_meta_raises_the_typed_read_error(
    tmp_path: Path,
) -> None:
    # Pins the real taxonomy: a corrupt meta.json fails closed through
    # _require_meta as the typed MissionMetaReadError, never a raw
    # ValueError. The discard call site's suppress set has to match this
    # exactly, or a real corrupt-meta failure escapes uncaught.
    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text("{ not valid json", encoding="utf-8")

    with pytest.raises(MissionMetaReadError):
        record_discard(feature_dir)


def test_mark_mission_discarded_is_a_noop_on_a_corrupt_meta(tmp_path: Path) -> None:
    # The discard call site absorbs MissionMetaReadError too, not just
    # FileNotFoundError: an abandoned mission is exactly the one likely to
    # hold a degraded meta.json, and the discard has already torn down
    # branches/worktrees by this point -- crashing over a cosmetic marker
    # is the wrong trade.
    from specify_cli.cli.commands.mission_type import _mark_mission_discarded

    feature_dir = tmp_path / "kitty-specs" / _MISSION_SLUG
    feature_dir.mkdir(parents=True)
    corrupt = "{ not valid json"
    (feature_dir / "meta.json").write_text(corrupt, encoding="utf-8")

    _mark_mission_discarded(feature_dir)

    assert (feature_dir / "meta.json").read_text(encoding="utf-8") == corrupt
