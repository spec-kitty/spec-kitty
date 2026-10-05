"""Seam unit tests for the lane-selection decisions in ``lanes/implement_support.py`` (WP07).

Covers the execution-lane lookup, the origin-preferred base-ref resolution (#4969), the
effective-base decision (planning-lane ignore, unresolved base) and the VCS-lock decision.
Real tiny git repos for the ref resolution; ``tmp_path`` mission dirs for the rest.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from specify_cli.core.paths import MissionMetaReadError
from specify_cli.lanes import implement_support
from specify_cli.lanes.implement_support import (
    BaseRefUnresolved,
    MissionMetaMissing,
    ensure_vcs_locked,
    resolve_base_ref,
    resolve_effective_base,
    resolve_execution_lane,
)
from specify_cli.lanes.models import ExecutionLane, LanesManifest
from specify_cli.lanes.persistence import MissingLanesError, write_lanes_json

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_PLANNING = cast(Any, SimpleNamespace(lane_id="lane-planning"))
_CODE_LANE = cast(Any, SimpleNamespace(lane_id="lane-a"))


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout.strip()


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
    _git(repo, "config", "user.email", "t@example.com")
    _git(repo, "config", "user.name", "Test")
    _commit(repo, "seed")


def _commit(repo: Path, name: str) -> str:
    (repo / f"{name}.txt").write_text(name, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


def _manifest(feature_dir: Path) -> None:
    feature_dir.mkdir(parents=True, exist_ok=True)
    lane = ExecutionLane(lane_id="lane-a", wp_ids=("WP01",), write_scope=(), predicted_surfaces=(), depends_on_lanes=(), parallel_group=0)
    write_lanes_json(
        feature_dir,
        LanesManifest(
            version=1,
            mission_slug="m",
            mission_id=None,
            mission_branch="kitty/mission-m",
            target_branch="main",
            lanes=[lane],
            computed_at="2026-01-01T00:00:00+00:00",
            computed_from="test",
        ),
    )


# ---- resolve_execution_lane -------------------------------------------------------------------


def test_execution_lane_repo_root_planning_workspace_returns_none_pair(tmp_path: Path) -> None:
    assert resolve_execution_lane(_PLANNING, tmp_path, "WP01") == (None, None)


def test_execution_lane_returns_manifest_and_lane(tmp_path: Path) -> None:
    _manifest(tmp_path)
    manifest, lane = resolve_execution_lane(_CODE_LANE, tmp_path, "WP01")
    assert manifest is not None
    assert lane is not None
    assert lane.lane_id == "lane-a"


def test_execution_lane_unassigned_wp_raises_value_error_with_exact_text(tmp_path: Path) -> None:
    _manifest(tmp_path)
    with pytest.raises(ValueError, match=r"^WP99 is not assigned to any lane in lanes\.json$"):
        resolve_execution_lane(_CODE_LANE, tmp_path, "WP99")


def test_execution_lane_missing_manifest_raises_missing_lanes_error(tmp_path: Path) -> None:
    with pytest.raises(MissingLanesError):
        resolve_execution_lane(_CODE_LANE, tmp_path, "WP01")


# ---- resolve_base_ref (#4969 origin-preferred) -------------------------------------------------


def test_base_ref_unresolvable_returns_none(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    assert resolve_base_ref(tmp_path, "no-such-ref") is None


def test_base_ref_local_only_is_kept(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    sha = _git(tmp_path, "rev-parse", "main")
    assert resolve_base_ref(tmp_path, "main") == ("main", sha)


def _with_origin(tmp_path: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin"
    clone = tmp_path / "clone"
    _init_repo(origin)
    subprocess.run(["git", "clone", "-q", str(origin), str(clone)], check=True)
    _git(clone, "config", "user.email", "t@example.com")
    _git(clone, "config", "user.name", "Test")
    return origin, clone


def test_base_ref_prefers_origin_when_local_is_behind(tmp_path: Path) -> None:
    origin, clone = _with_origin(tmp_path)
    new_sha = _commit(origin, "advance")
    _git(clone, "fetch", "-q", "origin")
    assert resolve_base_ref(clone, "main") == ("origin/main", new_sha)


def test_base_ref_prefers_origin_when_local_is_absent(tmp_path: Path) -> None:
    origin, clone = _with_origin(tmp_path)
    _git(origin, "branch", "teammate-lane")
    _git(clone, "fetch", "-q", "origin")
    assert resolve_base_ref(clone, "teammate-lane") == ("origin/teammate-lane", _git(origin, "rev-parse", "teammate-lane"))


def test_base_ref_keeps_local_when_ahead_of_origin(tmp_path: Path) -> None:
    _origin, clone = _with_origin(tmp_path)
    ahead = _commit(clone, "local-only")
    assert resolve_base_ref(clone, "main") == ("main", ahead)


# ---- resolve_effective_base --------------------------------------------------------------------


def test_effective_base_none_when_flag_absent(tmp_path: Path) -> None:
    assert resolve_effective_base(tmp_path, None, _CODE_LANE) == (None, False)


def test_effective_base_ignored_on_planning_lane(tmp_path: Path) -> None:
    assert resolve_effective_base(tmp_path, "main", _PLANNING) == (None, True)


def test_effective_base_returns_effective_ref_name(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    assert resolve_effective_base(tmp_path, "main", _CODE_LANE) == ("main", False)


def test_effective_base_unresolvable_raises_typed_error(tmp_path: Path) -> None:
    _init_repo(tmp_path)
    with pytest.raises(BaseRefUnresolved) as excinfo:
        resolve_effective_base(tmp_path, "nonexistent", _CODE_LANE)
    assert excinfo.value.base_ref == "nonexistent"
    assert excinfo.value.error_code == "BASE_REF_UNRESOLVED"


# ---- ensure_vcs_locked -------------------------------------------------------------------------


def _meta(feature_dir: Path, payload: dict[str, object]) -> Path:
    feature_dir.mkdir(parents=True, exist_ok=True)
    path = feature_dir / "meta.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_vcs_lock_writes_once_then_is_a_no_op(tmp_path: Path) -> None:
    meta_path = _meta(
        tmp_path,
        {
            "mission_slug": "m",
            "slug": "m",
            "friendly_name": "M",
            "mission_type": "software-dev",
            "target_branch": "main",
            "created_at": "2026-01-01T00:00:00+00:00",
        },
    )
    assert ensure_vcs_locked(tmp_path) is True
    locked = json.loads(meta_path.read_text(encoding="utf-8"))
    assert locked["vcs"] == "git"
    assert "vcs_locked_at" in locked
    before = meta_path.read_text(encoding="utf-8")
    assert ensure_vcs_locked(tmp_path) is False
    assert meta_path.read_text(encoding="utf-8") == before


def test_vcs_lock_missing_meta_raises_typed_error(tmp_path: Path) -> None:
    with pytest.raises(MissionMetaMissing) as excinfo:
        ensure_vcs_locked(tmp_path)
    assert excinfo.value.feature_dir == tmp_path
    assert not (tmp_path / "meta.json").exists()


def test_vcs_lock_invalid_meta_raises_read_error_and_writes_nothing(tmp_path: Path) -> None:
    tmp_path.mkdir(exist_ok=True)
    (tmp_path / "meta.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(MissionMetaReadError):
        ensure_vcs_locked(tmp_path)
    assert (tmp_path / "meta.json").read_text(encoding="utf-8") == "{not json"


def test_seam_names_are_public() -> None:
    for name in ("resolve_base_ref", "resolve_effective_base", "resolve_execution_lane", "ensure_vcs_locked", "refuse_repo_root_checkout_if_unavailable"):
        assert callable(getattr(implement_support, name))
