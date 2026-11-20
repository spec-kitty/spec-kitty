"""An orchestrator-claimed Mission, and one with a WP canceled before any claim, reach acceptance (#5781, #5818).

Drives the real ``orchestrator-api accept-mission`` command and ``collect_feature_summary``
(the readiness function ``spec-kitty accept`` calls) on a real git Mission. Each event row is
written in the shape its verb writes on disk, as captured from the end-to-end reproductions of
#5781 and #5818:

* WP01 is claimed the way ``orchestrator-api start-implementation`` recorded it before #5781:
  the orchestrator ``--policy`` as the claim's ``policy_metadata``, with no ``agent`` key. It is
  then reviewed and approved by an independent actor.
* WP02 is canceled straight from ``planned``: by host ``move-task`` without ``--agent`` (actor
  ``user``), with ``--agent`` (a stamped ``agent`` annotation), or by ``orchestrator-api
  transition --to canceled`` (a structured ``orch`` actor). Each carries the operator's note.

Before #5781 the strict readiness gate demanded the snapshot ``agent`` slot, filled only by a
claim sidecar, so every one of these refused, and the repair it printed (``--to <current lane>``)
was illegal. Before #5818 ``accept-mission`` counted every WP outside ``approved``/``done`` as
incomplete, provenance or not.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.acceptance import collect_feature_summary
from specify_cli.acceptance.matrix import write_acceptance_matrix
from specify_cli.orchestrator_api.commands import app
from specify_cli.status.emit import emit_inner_state_changed, emit_status_transition
from specify_cli.status.models import ReviewResult, TransitionRequest, WPInnerStateDelta
from tests.integration.coord_topology_fixture import CoordTopologyContext, coord_topology_mission
from tests.lane_test_utils import derive_mission_id, write_single_lane_manifest
from tests.orchestrator_api.test_issue_4934_accept_mission_readiness import _passing_matrix
from tests.specify_cli.test_acceptance_regressions import _create_test_feature
from tests.status.conftest import seed_wp_to_planned

# Re-exported so pytest discovers the coordination-topology fixture in this directory.
__all__ = ["coord_topology_mission"]

pytestmark = [pytest.mark.git_repo, pytest.mark.integration]

runner = CliRunner()

_SLUG = "issue-5781-accept-readiness"

#: The ``--policy`` an orchestrator passes, as ``start-implementation`` stored it before #5781.
_ORCHESTRATOR_POLICY: dict[str, Any] = {
    "orchestrator_id": "qa",
    "orchestrator_version": "1.0.0",
    "agent_family": "claude",
    "approval_mode": "auto",
    "sandbox_mode": "none",
    "network_mode": "none",
    "dangerous_flags": [],
    "tool_restrictions": None,
}


def _git(repo_root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo_root), *args], check=True, capture_output=True)


def _emit(feature_dir: Path, wp_id: str, to_lane: str, actor: object, **kwargs: Any) -> None:
    emit_status_transition(TransitionRequest(feature_dir=feature_dir, mission_slug=_SLUG, wp_id=wp_id, to_lane=to_lane, actor=actor, **kwargs))


def _api_claimed_and_independently_approved(feature_dir: Path) -> None:
    """WP01 as an orchestrator drives it: an API claim without an ``agent`` sidecar, then review."""
    seed_wp_to_planned(feature_dir, "WP01", slug=_SLUG)
    _emit(feature_dir, "WP01", "claimed", "claude", policy_metadata=dict(_ORCHESTRATOR_POLICY))
    _emit(feature_dir, "WP01", "in_progress", "claude", workspace_context="worktree:lane-a", policy_metadata=dict(_ORCHESTRATOR_POLICY))
    _emit(feature_dir, "WP01", "for_review", "claude", implementation_evidence_present=True)
    _emit(feature_dir, "WP01", "in_review", "codex")
    _emit(
        feature_dir,
        "WP01",
        "approved",
        "codex",
        review_result=ReviewResult(reviewer="codex", verdict="approved", reference="review-5781"),
    )


def _cancel_wp02(feature_dir: Path, variant: str) -> None:
    seed_wp_to_planned(feature_dir, "WP02", slug=_SLUG)
    if variant == "host_without_agent":
        _emit(feature_dir, "WP02", "canceled", {"tool": "user", "role": "implementer", "profile": None, "model": None}, reason="descoped", reason_source="operator")
    elif variant == "host_with_agent":
        _emit(
            feature_dir, "WP02", "canceled", {"tool": "claude", "role": "implementer", "profile": None, "model": None}, reason="descoped", reason_source="operator"
        )
        emit_inner_state_changed(feature_dir, "WP02", WPInnerStateDelta(agent="claude", note="descoped"), actor="claude", mission_slug=_SLUG)
    elif variant == "api":
        _emit(
            feature_dir,
            "WP02",
            "canceled",
            {"tool": "orch", "role": "implementer", "profile": None, "model": None},
            reason="descoped",
            policy_metadata=dict(_ORCHESTRATOR_POLICY),
        )
    elif variant == "synthetic":
        # ``move-task --to canceled --force`` with no ``--note``: the default reason, marked synthetic.
        _emit(feature_dir, "WP02", "canceled", "orch", force=True, reason="Force move to canceled", reason_source="synthetic")
    else:  # pragma: no cover - parametrization guard
        raise AssertionError(variant)


def _seed_mission(tmp_path: Path, *, wp02_cancel: str | None) -> tuple[Path, Path]:
    repo_root, feature_dir = _create_test_feature(tmp_path, _SLUG, omit_status_events=True)
    _git(repo_root, "branch", "-M", "main")
    mission_id = derive_mission_id(_SLUG)
    meta_path = feature_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta.update(mission_id=mission_id, mid8=mission_id[:8])
    meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    wp_ids: tuple[str, ...] = ("WP01",)
    if wp02_cancel is not None:
        (feature_dir / "tasks" / "WP02-descoped.md").write_text('---\nwork_package_id: "WP02"\ntitle: "Descoped WP"\nsubtasks: []\n---\n# WP02\n', encoding="utf-8")
        wp_ids = ("WP01", "WP02")

    _api_claimed_and_independently_approved(feature_dir)
    if wp02_cancel is not None:
        _cancel_wp02(feature_dir, wp02_cancel)

    write_single_lane_manifest(feature_dir, wp_ids=wp_ids, target_branch="main", mission_id=mission_id)
    write_acceptance_matrix(feature_dir, _passing_matrix(_SLUG))
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "seed the orchestrator-driven Mission")
    _seed_wp01_lane_implementation(repo_root, feature_dir)
    return repo_root, feature_dir


def _seed_wp01_lane_implementation(repo_root: Path, feature_dir: Path) -> None:
    """WP01's lane branch with its owned, committed change (#6715 evidence)."""
    from specify_cli.lanes.compute import lane_created_branch
    from specify_cli.lanes.persistence import read_lanes_json
    from tests.lane_test_utils import create_lane_branches
    from tests.terminus.conftest import declare_owned_files

    declare_owned_files(feature_dir, ["WP01"])
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "declare WP01's owned files")
    manifest = read_lanes_json(feature_dir)
    assert manifest is not None
    create_lane_branches(repo_root, manifest)
    branch = lane_created_branch(manifest, manifest.lanes[0].lane_id)
    _git(repo_root, "checkout", "-q", branch)
    (repo_root / "src" / "wp01.py").write_text("VALUE = 1\n", encoding="utf-8")
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-m", "feat(WP01): implement")
    _git(repo_root, "checkout", "-q", manifest.target_branch)


def _accept_mission(repo_root: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    monkeypatch.setattr("specify_cli.orchestrator_api._common._get_main_repo_root", lambda: repo_root)
    result = runner.invoke(app, ["accept-mission", "--mission", _SLUG, "--actor", "orch"], catch_exceptions=False)
    payload: dict[str, Any] = json.loads(result.output)
    return payload


def _missing_agent(issues: list[str]) -> list[str]:
    return [issue for issue in issues if "missing agent" in issue]


def test_an_api_claimed_mission_passes_the_strict_readiness_gate(tmp_path: Path) -> None:
    repo_root, _feature_dir = _seed_mission(tmp_path, wp02_cancel=None)

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False)

    assert _missing_agent(summary.metadata_issues) == []


def test_accept_mission_accepts_an_api_claimed_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, _feature_dir = _seed_mission(tmp_path, wp02_cancel=None)

    payload = _accept_mission(repo_root, monkeypatch)

    assert payload["success"] is True, payload
    assert payload["data"]["accepted"] is True


@pytest.mark.parametrize("variant", ["host_without_agent", "host_with_agent", "api"])
def test_a_wp_canceled_before_any_claim_needs_no_implementer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, variant: str) -> None:
    repo_root, _feature_dir = _seed_mission(tmp_path, wp02_cancel=variant)

    summary = collect_feature_summary(repo_root, _SLUG, strict_metadata=True, mutate_matrix=False)
    assert _missing_agent(summary.metadata_issues) == []
    assert [entry["wp_id"] for entry in summary.canceled_wps] == ["WP02"]

    payload = _accept_mission(repo_root, monkeypatch)
    assert payload["success"] is True, payload


def test_a_synthetic_cancellation_is_still_incomplete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repo_root, _feature_dir = _seed_mission(tmp_path, wp02_cancel="synthetic")

    payload = _accept_mission(repo_root, monkeypatch)

    assert payload["success"] is False
    assert payload["error_code"] == "MISSION_NOT_READY"
    assert payload["data"]["incomplete_wps"] == ["WP02"]


# ---------------------------------------------------------------------------
# Coordination topology: the gate reads the implementer from the coord status surface
# ---------------------------------------------------------------------------


def _event_row(n: int, slug: str, from_lane: str, to_lane: str, actor: object, **extra: Any) -> str:
    row: dict[str, Any] = {
        "event_id": f"01M5781C00RD000000000000{n:02d}",
        "mission_slug": slug,
        "wp_id": "WP01",
        "from_lane": from_lane,
        "to_lane": to_lane,
        "at": f"2026-11-20T00:00:{n:02d}+00:00",
        "actor": actor,
        "force": False,
        "execution_mode": "worktree",
        **extra,
    }
    return json.dumps(row) + "\n"


def test_an_api_claimed_wp_on_the_coordination_surface_passes_the_strict_gate(
    coord_topology_mission: CoordTopologyContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    ctx = coord_topology_mission
    review = {"reviewer": "codex", "verdict": "approved", "reference": "review-5781"}
    # The structured actors orchestrator-api writes (#6400), exactly as on disk in the #5781 reproduction.
    claude = {"tool": "claude", "role": "implementer", "profile": None, "model": None}
    codex = {"tool": "codex", "role": "reviewer", "profile": None, "model": None}
    ctx.status_events_path.write_text(
        "".join(
            [
                _event_row(1, ctx.slug, "genesis", "planned", "finalize-tasks"),
                _event_row(2, ctx.slug, "planned", "claimed", claude, policy_metadata=dict(_ORCHESTRATOR_POLICY)),
                _event_row(3, ctx.slug, "claimed", "in_progress", claude, policy_metadata=dict(_ORCHESTRATOR_POLICY)),
                _event_row(4, ctx.slug, "in_progress", "for_review", claude),
                _event_row(5, ctx.slug, "for_review", "in_review", codex),
                _event_row(6, ctx.slug, "in_review", "approved", codex, review_result=review),
            ]
        ),
        encoding="utf-8",
    )

    summary = collect_feature_summary(ctx.repo, ctx.slug, strict_metadata=True, mutate_matrix=False)

    assert _missing_agent(summary.metadata_issues) == []
    wp01 = next(state for state in summary.work_packages if state.work_package_id == "WP01")
    assert wp01.lane == "approved"

    # accept-mission on the same coordination surface: WP01 is not incomplete, and the strict
    # readiness verdict holds no metadata issue. (This fixture carries no planning artifacts or
    # acceptance matrix, so the verdict still refuses on those, which this test does not judge.)
    monkeypatch.setattr("specify_cli.orchestrator_api._common._get_main_repo_root", lambda: ctx.repo)
    result = runner.invoke(app, ["accept-mission", "--mission", ctx.slug, "--actor", "orch"], catch_exceptions=False)
    payload: dict[str, Any] = json.loads(result.output)
    assert "incomplete_wps" not in payload["data"], payload
    assert "outstanding" in payload["data"], payload
    assert "metadata" not in payload["data"]["outstanding"], payload["data"]["outstanding"]
