"""``restamp_topic_branch_as_coordination`` (S7 #7282, T078): the topic branch becomes the coordination branch."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from specify_cli.mission_metadata import restamp_topic_branch_as_coordination

pytestmark = pytest.mark.fast

_TOPIC = "kitty/mission-demo-01ABCDEF"
_DECISION = {"rule": "lanes_with_coord", "wp_count": 5, "code_lane_count": 3, "from": "single_branch", "to": "lanes_with_coord"}


def _feature_dir(tmp_path: Path, **extra: Any) -> Path:
    feature_dir = tmp_path / "kitty-specs" / "demo-01ABCDEF"
    feature_dir.mkdir(parents=True)
    meta: dict[str, Any] = {
        "mission_id": "01ABCDEF000000000000000000",
        "mission_slug": "demo-01ABCDEF",
        "slug": "demo-01ABCDEF",
        "friendly_name": "demo",
        "mission_type": "software-dev",
        "target_branch": "main",
        "created_at": "2026-11-06T00:00:00+00:00",
        "topology": "single_branch",
        "topology_source": "default",
        "topology_settled": False,
        "mission_branch": _TOPIC,
        **extra,
    }
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    return feature_dir


def _read(feature_dir: Path) -> dict[str, Any]:
    data = json.loads((feature_dir / "meta.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def test_promotes_the_topic_branch_in_one_write(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)

    prior = restamp_topic_branch_as_coordination(feature_dir, topology_decision=_DECISION)

    meta = _read(feature_dir)
    assert meta["coordination_branch"] == _TOPIC
    assert meta["mission_branch"] == _TOPIC
    assert meta["topology"] == "lanes_with_coord"
    assert meta["topology_settled"] is True
    assert meta["topology_decision"] == _DECISION
    assert prior == {"coordination_branch": None, "topology": "single_branch", "topology_settled": False, "topology_decision": None}


def test_refuses_without_a_mission_branch(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path)
    meta = _read(feature_dir)
    del meta["mission_branch"]
    (feature_dir / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    before = (feature_dir / "meta.json").read_bytes()

    with pytest.raises(ValueError, match="no mission_branch"):
        restamp_topic_branch_as_coordination(feature_dir, topology_decision=_DECISION)

    assert (feature_dir / "meta.json").read_bytes() == before


def test_refuses_a_different_coordination_branch(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path, coordination_branch="kitty/other")

    with pytest.raises(ValueError, match="is not the topic branch"):
        restamp_topic_branch_as_coordination(feature_dir, topology_decision=_DECISION)


def test_decision_is_write_once(tmp_path: Path) -> None:
    feature_dir = _feature_dir(tmp_path, topology_decision={"rule": "wp_count_le_2"})

    with pytest.raises(ValueError, match="write-once"):
        restamp_topic_branch_as_coordination(feature_dir, topology_decision=_DECISION)
