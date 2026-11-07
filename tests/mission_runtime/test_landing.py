"""``mission_runtime.landing.mission_has_landed`` -- the one "has this Mission landed" reader (#7276)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from mission_runtime.landing import mission_has_landed

pytestmark = pytest.mark.fast


def _meta(mission_dir: Path, **fields: object) -> Path:
    mission_dir.mkdir(parents=True, exist_ok=True)
    meta = {"mission_id": "01KZZZZZZZZZZZZZZZZZZZZZZZ", "mission_slug": "demo", **fields}
    (mission_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return mission_dir


def test_missing_meta_has_not_landed(tmp_path: Path) -> None:
    assert mission_has_landed(tmp_path / "absent") is False


def test_meta_without_merge_marker_has_not_landed(tmp_path: Path) -> None:
    assert mission_has_landed(_meta(tmp_path / "demo")) is False


def test_merge_marker_means_landed(tmp_path: Path) -> None:
    assert mission_has_landed(_meta(tmp_path / "demo", merged_at="2026-11-01T12:00:00+00:00")) is True


def test_corrupt_meta_reads_as_not_landed(tmp_path: Path) -> None:
    mission_dir = tmp_path / "demo"
    mission_dir.mkdir()
    (mission_dir / "meta.json").write_text("{not json", encoding="utf-8")
    assert mission_has_landed(mission_dir) is False
