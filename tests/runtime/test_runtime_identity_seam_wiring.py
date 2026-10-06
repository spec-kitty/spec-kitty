"""Patch-point regression guards for the identity trio.

``runtime_bridge_identity`` owns ``_primary_runtime_feature_dir``,
``_resolve_coordination_branch`` and ``_resolve_mission_ulid``. The two
resolvers call ``_primary_runtime_feature_dir`` directly, so a test that
replaces it patches ``runtime_bridge_identity._primary_runtime_feature_dir``
and steers both. The bridge defines none of the three; it calls them on the
seam (``tests/runtime/test_bridge_no_compat_delegates.py`` pins that).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from runtime.next import runtime_bridge_identity as identity

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def test_resolve_coordination_branch_reads_meta_through_the_seams_primary_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Patching ``runtime_bridge_identity._primary_runtime_feature_dir`` steers
    ``_resolve_coordination_branch`` (its meta read anchors on that function)."""
    feature_dir = tmp_path / "kitty-specs" / "my-mission-01KWDABC"
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"coordination_branch": "kitty/mission-my-mission-01KWDABC-lane-a"}),
        encoding="utf-8",
    )
    calls: list[str] = []

    def _spy(repo_root: Path, mission_slug: str) -> Path:
        calls.append("primary")
        return feature_dir

    monkeypatch.setattr(identity, "_primary_runtime_feature_dir", _spy)

    branch = identity._resolve_coordination_branch("my-mission-01KWDABC", tmp_path)

    assert calls == ["primary"]
    assert branch == "kitty/mission-my-mission-01KWDABC-lane-a"


def test_resolve_mission_ulid_reads_meta_through_the_seams_primary_dir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Same owner patch point, for ``_resolve_mission_ulid``."""
    feature_dir = tmp_path / "kitty-specs" / "my-mission-01KWDABC"
    feature_dir.mkdir(parents=True)
    ulid = "01KWDABC1234567890ABCDEFGH"
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": ulid}), encoding="utf-8")
    calls: list[str] = []

    def _spy(repo_root: Path, mission_slug: str) -> Path:
        calls.append("primary")
        return feature_dir

    monkeypatch.setattr(identity, "_primary_runtime_feature_dir", _spy)

    result = identity._resolve_mission_ulid("my-mission-01KWDABC", tmp_path)

    assert result == ulid
    assert calls == ["primary"]
