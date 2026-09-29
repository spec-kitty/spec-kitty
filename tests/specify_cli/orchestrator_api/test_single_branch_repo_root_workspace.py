"""Orchestrator-api repo-root lane workspace for single_branch (#5100 B5).

The orchestrator's hand-built ``lane_branch`` must agree with the canonical
resolver (``meta.mission_branch`` for a stored single_branch mission, else
``target_branch``), and the start path must run the
same WRITE_CHECKOUT_* refusals as ``implement`` so sequential execution cannot
be bypassed.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest
import typer

from specify_cli.lanes.persistence import write_lanes_json, read_lanes_json
from specify_cli.orchestrator_api import commands as oc
from tests.specify_cli.cli.commands.test_single_branch_implement_refusals import (
    _build_mission,
    _git,
    _init_repo,
)
from tests.utils import _seed_canonical_wp_state

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

_MINTED = "kitty/mission-orch-protected-01ORCHPR"


@pytest.fixture()
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repo"
    _init_repo(root)
    monkeypatch.chdir(root)
    monkeypatch.setenv("SPECIFY_REPO_ROOT", str(root))
    return root


def _mint(repo: Path, slug: str) -> None:
    """Mint the mission branch the way ``mission create`` does: meta.json (the
    authority) AND the lanes.json copy record it."""
    feature_dir = repo / "kitty-specs" / slug
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    write_lanes_json(feature_dir, dataclasses.replace(manifest, mission_branch=_MINTED))
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["mission_branch"] = _MINTED
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "mint")
    _git(repo, "checkout", "-q", "-b", _MINTED)


def test_protected_target_start_reports_minted_branch(repo: Path) -> None:
    slug = "orch-protected"
    _build_mission(repo, slug, "01ORCHPR000000000000000001")
    _mint(repo, slug)

    ws = oc._resolve_start_workspace("start-implementation", repo, slug, repo / "kitty-specs" / slug, "WP01")

    assert ws.lane_branch == _MINTED


def test_protected_target_read_only_resolver_reports_minted_branch(repo: Path) -> None:
    slug = "orch-protected"
    _build_mission(repo, slug, "01ORCHPR000000000000000001")
    _mint(repo, slug)

    ws = oc._resolve_existing_workspace(repo, slug, "WP01")

    assert ws.lane_branch == _MINTED


def test_landed_mission_start_ignores_stale_lanes_json_mission_branch(repo: Path) -> None:
    """A protected landing clears ``meta.mission_branch`` but leaves the lanes.json
    copy naming the deleted branch; both orchestrator resolvers follow meta.json."""
    slug = "orch-landed"
    _build_mission(repo, slug, "01ORCHLD000000000000000001")
    _mint(repo, slug)
    _git(repo, "checkout", "-q", "trunk")
    meta_path = repo / "kitty-specs" / slug / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    del meta["mission_branch"]
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "landed")

    started = oc._resolve_start_workspace("start-implementation", repo, slug, repo / "kitty-specs" / slug, "WP01")
    existing = oc._resolve_existing_workspace(repo, slug, "WP01")

    assert started.lane_branch == "trunk"
    assert existing.lane_branch == "trunk"


def test_unprotected_start_reports_target_branch(repo: Path) -> None:
    slug = "orch-unprotected"
    _build_mission(repo, slug, "01ORCHUN000000000000000001")

    ws = oc._resolve_start_workspace("start-implementation", repo, slug, repo / "kitty-specs" / slug, "WP01")

    assert ws.lane_branch == "trunk"


def test_occupied_single_branch_checkout_is_refused_on_orchestrator_path(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    other = "orch-occupant"
    _build_mission(repo, other, "01ORCHOC000000000000000001")
    _seed_canonical_wp_state(repo, other, "WP01", "in_progress", actor="claude", assignee="Owner", shell_pid="1234", timestamp="2026-09-28T00:45:00Z")
    slug = "orch-claimant"
    _build_mission(repo, slug, "01ORCHCL000000000000000001")

    with pytest.raises(typer.Exit):
        oc._resolve_start_workspace("start-implementation", repo, slug, repo / "kitty-specs" / slug, "WP01")

    assert "WRITE_CHECKOUT_OCCUPIED" in capsys.readouterr().out


def test_wrong_branch_single_branch_checkout_is_refused_on_orchestrator_path(repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    slug = "orch-wrongbranch"
    _build_mission(repo, slug, "01ORCHWB000000000000000001")
    _mint(repo, slug)
    _git(repo, "checkout", "-q", "trunk")

    with pytest.raises(typer.Exit):
        oc._resolve_start_workspace("start-implementation", repo, slug, repo / "kitty-specs" / slug, "WP01")

    assert "WRITE_CHECKOUT_WRONG_BRANCH" in capsys.readouterr().out


def _build_lanes_planning_mission(repo: Path, slug: str, mission_id: str) -> None:
    """A ``lanes`` (NOT single_branch) mission whose planning_artifact WP runs in the
    repo root and whose ``lanes.json`` carries a ``kitty/mission-...`` branch."""
    _build_mission(repo, slug, mission_id, topology="lanes", wp_kind="planning_artifact")
    _mint(repo, slug)
    _git(repo, "checkout", "-q", "trunk")


def test_lanes_topology_planning_wp_start_reports_target_branch(repo: Path) -> None:
    slug = "orch-lanes-plan"
    _build_lanes_planning_mission(repo, slug, "01ORCHLP000000000000000001")

    ws = oc._resolve_start_workspace("start-implementation", repo, slug, repo / "kitty-specs" / slug, "WP01")

    assert ws.lane_branch == "trunk"


def test_lanes_topology_planning_wp_read_only_resolver_reports_target_branch(repo: Path) -> None:
    slug = "orch-lanes-plan"
    _build_lanes_planning_mission(repo, slug, "01ORCHLP000000000000000001")

    ws = oc._resolve_existing_workspace(repo, slug, "WP01")

    assert ws.lane_branch == "trunk"
