"""#5296 waiver seam: ``_root_checkout_is_target`` and ``_approved_dependency_lane_refs``."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from specify_cli.lanes.compute import PLANNING_LANE_ID
from specify_cli.lanes.implement_support import _approved_dependency_lane_refs, _root_checkout_is_target
from specify_cli.lanes.persistence import read_lanes_json
from specify_cli.status.models import Lane
from tests.specify_cli.cli.commands.agent.test_claim_ancestry_gate import (
    _MISSION_SLUG,
    _WP_DEP,
    _WP_SELF,
    _create_lane_a_branch,
    _feature_dir,
    _git,
    _init_repo,
    _seed_wp_lane,
    _write_meta_and_lanes,
)

pytestmark = [pytest.mark.fast, pytest.mark.git_repo]


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    _init_repo(root)
    _write_meta_and_lanes(root)
    lanes_path = _feature_dir(root) / "lanes.json"
    payload = json.loads(lanes_path.read_text())
    payload["lanes"][1]["lane_id"] = PLANNING_LANE_ID
    payload["planning_artifact_wps"] = [_WP_SELF]
    lanes_path.write_text(json.dumps(payload))
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "planning lane")
    _create_lane_a_branch(root)
    _seed_wp_lane(root, _WP_DEP, Lane.APPROVED)
    _git(root, "add", ".")
    _git(root, "commit", "-qm", "approved dependency")
    return root


def _refs(repo: Path, wp_id: str) -> list[tuple[str, str]]:
    manifest = read_lanes_json(_feature_dir(repo))
    assert manifest is not None
    lane = manifest.lane_for_wp(wp_id)
    assert lane is not None
    return _approved_dependency_lane_refs(repo, _MISSION_SLUG, _feature_dir(repo), lane, manifest)


def test_root_checkout_is_target_truth_table(repo: Path) -> None:
    manifest = read_lanes_json(_feature_dir(repo))
    assert manifest is not None and manifest.target_branch == "main"
    assert _root_checkout_is_target(repo, manifest) is True
    _git(repo, "checkout", "-q", "-b", "feat/other")
    assert _root_checkout_is_target(repo, manifest) is False
    _git(repo, "checkout", "-q", "--detach")
    assert _root_checkout_is_target(repo, manifest) is False


def test_root_checkout_is_target_false_outside_a_repo(tmp_path: Path, repo: Path) -> None:
    manifest = read_lanes_json(_feature_dir(repo))
    assert manifest is not None
    assert _root_checkout_is_target(tmp_path, manifest) is False


def test_planning_lane_on_target_requires_no_code_lane_refs(repo: Path) -> None:
    assert _refs(repo, _WP_SELF) == []


def test_planning_lane_off_target_keeps_code_lane_refs(repo: Path) -> None:
    _git(repo, "checkout", "-q", "-b", "feat/planning")
    refs = _refs(repo, _WP_SELF)
    assert [dep for dep, _branch in refs] == ["lane-a"]


def test_code_lane_keeps_refs_even_on_target(repo: Path) -> None:
    """A code lane depending on another code lane is never waived."""
    lanes_path = _feature_dir(repo) / "lanes.json"
    payload = json.loads(lanes_path.read_text())
    payload["lanes"][1]["lane_id"] = "lane-b"
    payload["planning_artifact_wps"] = []
    lanes_path.write_text(json.dumps(payload))
    _git(repo, "add", ".")
    _git(repo, "commit", "-qm", "code lane b")
    refs = _refs(repo, _WP_SELF)
    assert [dep for dep, _branch in refs] == ["lane-a"]
