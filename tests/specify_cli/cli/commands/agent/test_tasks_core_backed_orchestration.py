"""WP07 (#2116) — core-backed orchestrator side-effect parity (T032).

The WP07 rewire thins ``map_requirements`` and ``status`` into thin orchestrators
over their WP04/WP05 pure cores (``plan_mapping`` / ``build_status_view``) and the
WP02 capability ports. This module injects the WP02 **Fake** ports (``ports=`` on
the extracted ``_do_map_requirements`` / ``_do_status`` orchestrators — the C-005
injection seam that never touches the Typer surface) and asserts the executed
side-effects match the pre-rewire behaviour:

``map_requirements``
    * the co-located canonicalizer fold (``primary_feature_dir_for_mission(
      _canonicalize_primary_read_handle(...))``) is resolved through the WP02
      ``FsReader.primary_anchor_dir`` port — its named consumer (T030 / WP02 Note A);
    * an auto-commit run routes the WP-file commit through the coord
      ``commit_artifact`` capability keyed ``WORK_PACKAGE_TASK`` with the WP file in
      the bundle, while a ``--no-auto-commit`` run leaves that seam untouched;
    * the production map_requirements coord router (``seam_coord_router(
      thread_target_branch=True, ...)``) threads the resolved ``target_branch``
      into ``commit_for_mission`` so the post-commit ff-advance still fires.

``status``
    * the ``--json`` leg assembles its envelope from the pure ``build_status_view``
      aggregation and serialises it through ``ports.render.json_envelope``;
    * the human leg draws every board section through ``ports.render.human``.

These are the Fake-port projections; they pin the routing without a real git
worktree. NFR-004 pure parity: no behaviour change is encoded here.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path
from unittest.mock import patch

import pytest

from mission_runtime import MissionArtifactKind
from specify_cli.agent_tasks_ports import MissionHandle, TasksPorts
from specify_cli.cli.commands.agent.tasks import (
    _do_map_requirements,
    _do_status,
    seam_coord_router,
)
from specify_cli.git.protection_policy import ProtectionPolicy
from specify_cli.status.models import Lane, StatusEvent
from tests._support.status_seed import seed_status_event
from tests.mocked_env import setup_mocked_env
from tests.specify_cli.cli.commands.agent.test_tasks_ports import (
    FakeCoordCommitRouter,
    FakeFsReader,
    FakeGitOps,
    FakeRender,
)

pytestmark = pytest.mark.fast

_MISSION = "core-backed-orchestration"


# ===========================================================================
# map_requirements — fold via primary_anchor_dir + commit via commit_artifact
# ===========================================================================


def _build_map_fixture(tmp_path: Path, mission_slug: str) -> Path:
    """Primary planning surface: meta + spec (FR ids) + one WP frontmatter."""
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": mission_slug, "mission_type": "software-dev"}),
        encoding="utf-8",
    )
    (feature_dir / "spec.md").write_text(
        "# Spec\n\n## Requirements\n\n- **FR-001**: first\n- **FR-002**: second\n",
        encoding="utf-8",
    )
    (tasks_dir / "WP01-test.md").write_text(
        textwrap.dedent(
            """\
            ---
            work_package_id: WP01
            title: Test WP01
            execution_mode: code_change
            ---
            # WP01
            """
        ),
        encoding="utf-8",
    )
    return feature_dir


def _map_fake_ports(anchor_dir: Path) -> tuple[TasksPorts, FakeFsReader, FakeCoordCommitRouter]:
    """A WP02 Fake bundle whose FsReader anchors on the REAL primary feature dir.

    ``primary_anchor_dir`` must return the on-disk dir carrying ``spec.md`` so the
    orchestrator's spec read succeeds; the ``commit_artifact`` capability records
    its calls on a separate log.
    """
    fs = FakeFsReader(anchor_dir=anchor_dir)
    coord = FakeCoordCommitRouter()
    return TasksPorts(fs=fs, coord=coord, git=FakeGitOps(), render=FakeRender()), fs, coord


def test_map_requirements_fold_routes_through_primary_anchor_dir(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """T030: the canonicalizer fold resolves via the ``FsReader.primary_anchor_dir``
    port (its named consumer), and a ``--no-auto-commit`` run never touches the
    coord ``commit_artifact`` seam."""
    feature_dir = _build_map_fixture(tmp_path, _MISSION)
    ports, fs, coord = _map_fake_ports(feature_dir)

    with setup_mocked_env(tmp_path, mission_slug=_MISSION, target_branch="wip-lane"):
        _do_map_requirements(
            wp="WP01",
            refs="FR-001",
            batch=None,
            replace=False,
            tracker_ref=None,
            mission=_MISSION,
            json_output=True,
            auto_commit=False,
            ports=ports,
        )

    # The spec-anchor read routed through the port (T030 / WP02 Note A).
    assert ("primary_anchor_dir", _MISSION) in fs.calls
    # No auto-commit => the primary WRITE capability is untouched.
    assert coord.artifact_calls == []

    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "success"
    assert payload["mapped"] == {"WP01": ["FR-001"]}
    # The WP frontmatter was written on disk (partial write happens before commit).
    assert "FR-001" in (feature_dir / "tasks" / "WP01-test.md").read_text(encoding="utf-8")


def test_map_requirements_auto_commit_routes_via_commit_artifact(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """T030: an auto-commit run routes the WP-file commit through the coord
    ``commit_artifact`` capability, keyed ``WORK_PACKAGE_TASK`` with the WP file."""
    feature_dir = _build_map_fixture(tmp_path, _MISSION)
    ports, _fs, coord = _map_fake_ports(feature_dir)

    # The protected-primary placement guard is orthogonal to the commit ROUTING
    # under test; neutralise it so the fixture's default primary branch does not
    # short-circuit the auto-commit leg.
    with setup_mocked_env(
        tmp_path,
        mission_slug=_MISSION,
        target_branch="wip-lane",
        extra_patches={"_protected_branch_status_commit_error": None},
    ):
        _do_map_requirements(
            wp="WP01",
            refs="FR-001",
            batch=None,
            replace=False,
            tracker_ref=None,
            mission=_MISSION,
            json_output=True,
            auto_commit=True,
            ports=ports,
        )

    assert len(coord.artifact_calls) == 1
    slug, paths, message, kind = coord.artifact_calls[0]
    assert slug == _MISSION
    assert kind == MissionArtifactKind.WORK_PACKAGE_TASK
    assert (feature_dir / "tasks" / "WP01-test.md").resolve() in paths
    assert message.startswith("chore: Map requirements for WP01")

    payload = json.loads(capsys.readouterr().out)
    assert payload["committed"] is True
    # Reconstructed commit_result envelope shape (#1891 / FR-013).
    assert payload["commit_result"]["destination_ref"] == "primary"


def test_map_req_coord_router_threads_target_branch() -> None:
    """T030: the production map_requirements coord router threads the resolved
    ``target_branch`` into ``commit_for_mission`` (the ff-advance parity), and
    re-resolves the symbol through THIS module so the ``@patch`` seam intercepts.

    (constructor-DI collapse: built via ``seam_coord_router(thread_target_branch=
    True, target_branch=...)`` rather than the deleted ``_MapReqCoordRouter``.)"""
    router = seam_coord_router(thread_target_branch=True, target_branch="wip-lane")
    handle = MissionHandle(repo_root=Path("/repo"), mission_slug=_MISSION)

    with patch(
        "specify_cli.cli.commands.agent.tasks.commit_for_mission"
    ) as mock_commit:
        mock_commit.return_value.status = "committed"
        mock_commit.return_value.placement_ref = "primary"
        mock_commit.return_value.commit_hash = "0" * 40
        mock_commit.return_value.diagnostic = None
        result = router.commit_artifact(
            handle,
            [Path("kitty-specs/m/tasks/WP01.md")],
            "chore: x",
            kind=MissionArtifactKind.WORK_PACKAGE_TASK,
            policy=ProtectionPolicy(protected_branches=frozenset(), operator_hatch_active=False),
        )

    assert result.status == "committed"
    assert mock_commit.call_args.kwargs["target_branch"] == "wip-lane"
    assert mock_commit.call_args.kwargs["kind"] == MissionArtifactKind.WORK_PACKAGE_TASK


# ===========================================================================
# status — build_status_view aggregation emitted through the Render port
# ===========================================================================


def _build_status_fixture(tmp_path: Path, mission_slug: str, lanes: dict[str, str]) -> Path:
    """Primary surface: meta + one WP per lane, each seeded into the event log."""
    (tmp_path / ".kittify").mkdir(exist_ok=True)
    feature_dir = tmp_path / "kitty-specs" / mission_slug
    tasks_dir = feature_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (feature_dir / "meta.json").write_text(
        json.dumps({"mission_slug": mission_slug, "mission_type": "software-dev"}),
        encoding="utf-8",
    )
    for wp_id, lane in lanes.items():
        (tasks_dir / f"{wp_id}-test.md").write_text(
            textwrap.dedent(
                f"""\
                ---
                work_package_id: {wp_id}
                title: Test {wp_id}
                execution_mode: code_change
                ---
                # {wp_id}
                """
            ),
            encoding="utf-8",
        )
        seed_status_event(
            feature_dir,
            StatusEvent(
                event_id=f"test-{wp_id}-{lane}",
                mission_slug=mission_slug,
                wp_id=wp_id,
                from_lane=Lane.PLANNED,
                to_lane=Lane(lane),
                at="2026-01-01T00:00:00+00:00",
                actor="test",
                force=True,
                execution_mode="worktree",
            ),
        )
    return feature_dir


def _status_fake_ports() -> tuple[TasksPorts, FakeRender]:
    render = FakeRender()
    return TasksPorts(
        fs=FakeFsReader(), coord=FakeCoordCommitRouter(), git=FakeGitOps(), render=render
    ), render


def test_status_json_emits_via_render_json_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T031: the ``--json`` leg serialises the ``build_status_view`` aggregation
    through ``ports.render.json_envelope`` (recorded on the Fake)."""
    _build_status_fixture(tmp_path, _MISSION, {"WP01": "approved", "WP02": "planned"})
    monkeypatch.chdir(tmp_path)
    ports, render = _status_fake_ports()

    with setup_mocked_env(tmp_path, workspace_resolution=FileNotFoundError):
        _do_status(mission=_MISSION, json_output=True, stale_threshold=10, ports=ports)

    # The JSON envelope was assembled and routed through the Render port exactly once.
    assert len(render.envelopes) == 1
    assert render.views == []  # JSON leg draws nothing on the human arm
    payload = render.envelopes[0]
    assert payload["total_wps"] == 2
    assert payload["by_lane"] == {Lane.APPROVED: 1, Lane.PLANNED: 1}
    assert payload["progress_semantics"]  # WP05 view carried into the envelope


def test_status_human_renders_board_via_render_human(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T031: the human leg draws every board section through ``ports.render.human``
    and never touches the JSON-envelope arm."""
    _build_status_fixture(tmp_path, _MISSION, {"WP01": "approved", "WP02": "planned"})
    monkeypatch.chdir(tmp_path)
    ports, render = _status_fake_ports()

    with setup_mocked_env(tmp_path, workspace_resolution=FileNotFoundError):
        _do_status(mission=_MISSION, json_output=False, stale_threshold=10, ports=ports)

    # The human leg rendered through the port; the JSON-envelope arm stayed unused.
    assert render.envelopes == []
    assert len(render.views) > 0
    # The kanban board table + the mission title panel are both among the views.
    rendered = "".join(type(v).__name__ for v in render.views)
    assert "Table" in rendered
    assert "Panel" in rendered
