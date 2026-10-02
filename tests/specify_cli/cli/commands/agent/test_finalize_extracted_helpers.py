"""WP15 (coord-artifact-single-home-01M3V4BE) T004: focused tests for the
helpers extracted out of ``finalize_tasks`` / ``_commit_planning_pin_refresh_locked``
(mission_finalize.py) and ``_ft_apply_writes`` (tasks_finalize.py) as this WP's
tidy-first first commit.

Each helper is driven directly (not through the full ``finalize_tasks`` CLI
pipeline) per the WP's own validation note: "New tests drive each helper
directly: ... the pin-refresh guard raising on changed bytes, and the
status-emission helper writing to the dir it was given."
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import typer

from mission_runtime import MissionArtifactKind, MissionTopology
from specify_cli.cli.commands.agent.mission_finalize import (
    _guard_lanes_bytes_unchanged_before_commit,
    _planning_changed_since_pin,
)
from specify_cli.cli.commands.agent.tasks_finalize import _ft_emit_status_events

pytestmark = [pytest.mark.unit, pytest.mark.fast]


def _git_stdout(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(repo), capture_output=True, text=True, check=True)
    return result.stdout.strip()


# ---------------------------------------------------------------------------
# _guard_lanes_bytes_unchanged_before_commit (mission_finalize.py)
# ---------------------------------------------------------------------------


def test_guard_lanes_bytes_unchanged_before_commit_passes_when_bytes_match(tmp_path: Path) -> None:
    """The guard is a no-op (never raises) when the on-disk bytes still match."""
    lanes_path = tmp_path / "lanes.json"
    content = b'{"planning_commit_sha": "abc123"}'
    lanes_path.write_bytes(content)

    _guard_lanes_bytes_unchanged_before_commit(lanes_path, content)  # must not raise


def test_guard_lanes_bytes_unchanged_before_commit_raises_on_concurrent_write(tmp_path: Path) -> None:
    """A concurrent writer between the read and the commit attempt is caught (CAS)."""
    lanes_path = tmp_path / "lanes.json"
    lanes_path.write_bytes(b'{"planning_commit_sha": "concurrent-writer-sha"}')
    expected_bytes = b'{"planning_commit_sha": "abc123"}'

    with pytest.raises(RuntimeError, match="lanes.json changed before the conditional commit"):
        _guard_lanes_bytes_unchanged_before_commit(lanes_path, expected_bytes)


def test_guard_lanes_bytes_unchanged_before_commit_mutation_sensitive(tmp_path: Path) -> None:
    """Removing the guard's comparison would silently accept concurrent content.

    Proves the guard is the thing doing the work (not an incidental side
    effect of some other check) by exercising both a matching and a
    non-matching case against the SAME file, varying only the expected bytes.
    """
    lanes_path = tmp_path / "lanes.json"
    lanes_path.write_bytes(b"original")
    _guard_lanes_bytes_unchanged_before_commit(lanes_path, b"original")
    with pytest.raises(RuntimeError):
        _guard_lanes_bytes_unchanged_before_commit(lanes_path, b"different")


# ---------------------------------------------------------------------------
# _planning_changed_since_pin (mission_finalize.py, T083)
# ---------------------------------------------------------------------------


def _git(repo_root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=str(repo_root), capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _git_init(repo_root: Path) -> None:
    _git(repo_root, "init", "-q", "-b", "main")
    _git(repo_root, "config", "user.email", "test@example.com")
    _git(repo_root, "config", "user.name", "Test")


def _commit_all(repo_root: Path, message: str) -> str:
    _git(repo_root, "add", "-A")
    _git(repo_root, "commit", "-q", "-m", message)
    return _git(repo_root, "rev-parse", "HEAD")


def test_planning_changed_since_pin_false_when_endpoints_missing(tmp_path: Path) -> None:
    assert _planning_changed_since_pin(tmp_path, "061-feature", None, "deadbeef") is False
    assert _planning_changed_since_pin(tmp_path, "061-feature", "deadbeef", None) is False


def test_planning_changed_since_pin_false_when_endpoints_equal(tmp_path: Path) -> None:
    assert _planning_changed_since_pin(tmp_path, "061-feature", "deadbeef", "deadbeef") is False


def test_planning_changed_since_pin_true_for_a_primary_kind_change(tmp_path: Path) -> None:
    """A real ``spec.md`` edit under the mission dir is detected as PRIMARY change."""
    mission_dir = tmp_path / "kitty-specs" / "061-feature"
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text("# spec v1\n", encoding="utf-8")
    _git_init(tmp_path)
    recorded = _commit_all(tmp_path, "v1")

    (mission_dir / "spec.md").write_text("# spec v2\n", encoding="utf-8")
    tip = _commit_all(tmp_path, "v2")

    assert _planning_changed_since_pin(tmp_path, "061-feature", recorded, tip) is True


def test_planning_changed_since_pin_excludes_lanes_json(tmp_path: Path) -> None:
    """A lanes.json-only change (finalize's own pin write) never counts as a planning change."""
    mission_dir = tmp_path / "kitty-specs" / "061-feature"
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    (mission_dir / "lanes.json").write_text('{"planning_commit_sha": "x"}', encoding="utf-8")
    _git_init(tmp_path)
    recorded = _commit_all(tmp_path, "v1")

    (mission_dir / "lanes.json").write_text('{"planning_commit_sha": "y"}', encoding="utf-8")
    tip = _commit_all(tmp_path, "lanes-only change")

    assert _planning_changed_since_pin(tmp_path, "061-feature", recorded, tip) is False


def test_planning_changed_since_pin_excludes_other_mission(tmp_path: Path) -> None:
    """A change under a DIFFERENT mission's directory never counts."""
    this_mission = tmp_path / "kitty-specs" / "061-feature"
    this_mission.mkdir(parents=True)
    (this_mission / "spec.md").write_text("# spec\n", encoding="utf-8")
    other_mission = tmp_path / "kitty-specs" / "062-other"
    other_mission.mkdir(parents=True)
    (other_mission / "spec.md").write_text("# other spec\n", encoding="utf-8")
    _git_init(tmp_path)
    recorded = _commit_all(tmp_path, "v1")

    (other_mission / "spec.md").write_text("# other spec v2\n", encoding="utf-8")
    tip = _commit_all(tmp_path, "unrelated mission change")

    assert _planning_changed_since_pin(tmp_path, "061-feature", recorded, tip) is False


def test_planning_changed_since_pin_false_when_recorded_object_absent(tmp_path: Path) -> None:
    """A FOREIGN (absent) recorded SHA degrades to False -- the diff cannot run at all."""
    mission_dir = tmp_path / "kitty-specs" / "061-feature"
    mission_dir.mkdir(parents=True)
    (mission_dir / "spec.md").write_text("# spec\n", encoding="utf-8")
    _git_init(tmp_path)
    tip = _commit_all(tmp_path, "v1")

    foreign_sha = "0" * 40
    assert _planning_changed_since_pin(tmp_path, "061-feature", foreign_sha, tip) is False


# ---------------------------------------------------------------------------
# _ft_emit_status_events (tasks_finalize.py, T080)
# ---------------------------------------------------------------------------


def test_ft_emit_status_events_validate_only_never_calls_write_dir(tmp_path: Path) -> None:
    """B2 (cycle 2, HIGH/NFR-002): ``--validate-only`` must never call ``write_dir``
    (which can materialize + seed + commit a never-seeded coordination surface) --
    and bootstraps from PRIMARY, never a coord-resolved path.
    """
    from specify_cli.cli.commands.agent.tasks_finalize import _FinalizeState

    feature_dir = tmp_path / "kitty-specs" / "061-feature"
    st = _FinalizeState(mission="061-feature", json_output=True, validate_only=True)
    st.main_repo_root = tmp_path
    st.mission_slug = "061-feature"
    st.primary_feature_dir = feature_dir

    mock_seam = MagicMock()
    bootstrap_mock = MagicMock(return_value=SimpleNamespace(total_wps=0, already_initialized=0, newly_seeded=0, skipped=0, wp_details=[]))
    finalize_lanes = MagicMock()

    with (
        patch("specify_cli.cli.commands.agent.tasks_finalize.placement_seam", return_value=mock_seam) as seam_mock,
        patch("specify_cli.cli.commands.agent.tasks_finalize._tasks_bootstrap_canonical_state", bootstrap_mock),
    ):
        _ft_emit_status_events(st, finalize_lanes=finalize_lanes)

    seam_mock.assert_not_called()
    mock_seam.write_dir.assert_not_called()
    bootstrap_mock.assert_called_once_with(feature_dir, "061-feature", dry_run=True)
    assert st.feature_dir == feature_dir
    # validate_only=True: the lanes-write callback must never run (NFR-002).
    finalize_lanes.assert_not_called()


def test_ft_emit_status_events_runs_finalize_lanes_when_not_validate_only(tmp_path: Path) -> None:
    """Not validate-only: the coordination surface IS established (write_dir runs),
    but the SCAN/bootstrap ``feature_dir`` stays PRIMARY (B1, cycle 2, HIGH
    regression) -- never the established coord path, which carries no ``tasks/``.
    """
    from specify_cli.cli.commands.agent.tasks_finalize import _FinalizeState

    feature_dir = tmp_path / "kitty-specs" / "061-feature"
    coord_dir = tmp_path / ".worktrees" / "coord" / "kitty-specs" / "061-feature"
    st = _FinalizeState(mission="061-feature", json_output=True, validate_only=False)
    st.main_repo_root = tmp_path
    st.mission_slug = "061-feature"
    st.primary_feature_dir = feature_dir

    mock_seam = MagicMock()
    mock_seam.write_dir.return_value = SimpleNamespace(path=coord_dir)
    bootstrap_mock = MagicMock(return_value=SimpleNamespace(total_wps=0, already_initialized=0, newly_seeded=0, skipped=0, wp_details=[]))
    finalize_lanes = MagicMock()

    with (
        patch("specify_cli.cli.commands.agent.tasks_finalize.placement_seam", return_value=mock_seam) as seam_mock,
        patch("specify_cli.cli.commands.agent.tasks_finalize._tasks_bootstrap_canonical_state", bootstrap_mock),
    ):
        _ft_emit_status_events(st, finalize_lanes=finalize_lanes)

    seam_mock.assert_called_once_with(tmp_path, "061-feature")
    mock_seam.write_dir.assert_called_once_with(MissionArtifactKind.STATUS_STATE)
    finalize_lanes.assert_called_once()
    # B1: bootstrap must scan/read PRIMARY, never the coord dir write_dir returned.
    bootstrap_mock.assert_called_once_with(feature_dir, "061-feature", dry_run=False)
    assert st.feature_dir == feature_dir


# ---------------------------------------------------------------------------
# B1/B2 (cycle 2, HIGH): unmocked coordination-routed reproductions driving
# the REAL ``agent tasks finalize-tasks`` entry point (``_do_finalize_tasks``).
# ---------------------------------------------------------------------------


def _write_legacy_finalize_fixture(coord: object) -> None:
    """Minimal tasks.md + two dependency-free WP files under the PRIMARY Mission dir."""
    mission_dir = coord.root_mission_dir  # type: ignore[attr-defined]
    tasks_dir = mission_dir / "tasks"
    tasks_dir.mkdir(parents=True, exist_ok=True)
    (mission_dir / "tasks.md").write_text(
        "# Tasks\n\n## WP01\n\nNo dependencies.\n\n## WP02\n\nNo dependencies.\n",
        encoding="utf-8",
    )
    for wp_id in ("WP01", "WP02"):
        (tasks_dir / f"{wp_id}-fixture.md").write_text(
            f'---\nwork_package_id: "{wp_id}"\ntitle: "Fixture {wp_id}"\ndependencies: []\n---\n\n# {wp_id}\n',
            encoding="utf-8",
        )


def _run_do_finalize_tasks(monkeypatch: pytest.MonkeyPatch, coord: object, *, validate_only: bool) -> dict[str, object]:
    """Drive the REAL ``_do_finalize_tasks`` entry point and return its JSON payload."""
    import contextlib
    import io

    from specify_cli.cli.commands.agent.tasks_finalize import _do_finalize_tasks

    monkeypatch.chdir(coord.repo_root)  # type: ignore[attr-defined]
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.suppress(typer.Exit):
        _do_finalize_tasks(coord.mission_dir_name, True, validate_only)  # type: ignore[attr-defined]
    output = buf.getvalue()
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            payload: dict[str, object] = json.loads(line)
            return payload
    raise AssertionError(f"no JSON payload emitted: {output!r}")


@pytest.mark.parametrize("topology", [MissionTopology.COORD, MissionTopology.LANES_WITH_COORD])
@pytest.mark.parametrize(
    "shape",
    ["empty", "unmaterialized", "materialized"],
)
def test_do_finalize_tasks_seeds_wps_on_every_coordination_shape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, topology: MissionTopology, shape: str) -> None:
    """B1 (cycle 2, HIGH regression): ``agent tasks finalize-tasks`` must seed
    every WP's canonical status and report the real ``mission_type`` on
    EVERY coordination surface shape -- EMPTY, UNMATERIALIZED, and
    MATERIALIZED (the last already broken at the lane base; WP15 fixes it
    too, see B1 in the review).
    """
    from tests._factories.coord_mission import make_coord_mission, make_prefix_coord_mission

    if shape == "empty":
        coord = make_prefix_coord_mission(tmp_path, topology, worktree="empty")
    elif shape == "unmaterialized":
        coord = make_prefix_coord_mission(tmp_path, topology, worktree="absent")
    else:
        coord = make_coord_mission(tmp_path, topology, materialized=True, slug="materialized")
    _write_legacy_finalize_fixture(coord)

    payload = _run_do_finalize_tasks(monkeypatch, coord, validate_only=False)

    assert payload.get("result") == "success", f"finalize-tasks must succeed; payload={payload}"
    bootstrap = payload.get("bootstrap")
    assert isinstance(bootstrap, dict)
    assert bootstrap.get("newly_seeded") == 2, f"both WPs must be seeded (shape={shape}); bootstrap={bootstrap}"
    assert bootstrap.get("total_wps") == 2, f"both WPs must be discovered from PRIMARY (shape={shape}); bootstrap={bootstrap}"
    assert payload.get("mission_type") == "software-dev", f"mission_type must come from the real identity payload; payload={payload}"


@pytest.mark.parametrize("shape", ["empty", "unmaterialized"])
def test_do_finalize_tasks_validate_only_never_mutates_coordination_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, shape: str) -> None:
    """B2 (cycle 2, HIGH regression, NFR-002): ``--validate-only`` must leave the
    coordination branch tip, the worktree's existence, and the coordination
    Mission dir completely unchanged.
    """
    from tests._factories.coord_mission import make_prefix_coord_mission

    coord = make_prefix_coord_mission(tmp_path, MissionTopology.COORD, worktree="empty" if shape == "empty" else "absent")
    _write_legacy_finalize_fixture(coord)

    before_tip = _git_stdout(coord.repo_root, "rev-parse", coord.coordination_branch)
    worktree_existed_before = coord.coord_worktree_path.exists()
    coord_dir_existed_before = coord.coord_mission_dir.exists()

    payload = _run_do_finalize_tasks(monkeypatch, coord, validate_only=True)
    assert payload.get("result") == "validation_passed", f"payload={payload}"

    after_tip = _git_stdout(coord.repo_root, "rev-parse", coord.coordination_branch)
    assert after_tip == before_tip, "validate-only must never advance the coordination branch tip"
    assert coord.coord_worktree_path.exists() == worktree_existed_before, "validate-only must never materialize the coordination worktree"
    assert coord.coord_mission_dir.exists() == coord_dir_existed_before, "validate-only must never seed the coordination Mission dir"
