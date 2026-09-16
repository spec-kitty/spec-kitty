"""Board regression: ``agent tasks status`` must read committed lanes for a
merged mission, not a stale coordination checkout (WP01 T001, #2947).

Mission next-committed-state-authority-01M1CA8W. Before the fix, the board's
lane rollup reads WP lanes from the (possibly stale) topology-resolved
``feature_dir`` — for a merged mission whose coordination worktree has not
been cleaned up, that surface still shows the pre-merge ``planned`` lanes even
though the PRIMARY checkout carries the committed ``accepted`` truth
(``tasks_status_cmd.py`` :193 already reads ``tasks/`` from PRIMARY; the lane
read did not, until this fix).

The fixture below builds TWO DISTINCT on-disk surfaces on purpose (a
single-dir fixture would not exercise the bug): a committed PRIMARY (accepted)
and a stale COORD checkout (still planned). An explicit assertion proves the
two surfaces diverge before asserting the board's committed-lane output.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest
import ulid
from typer.testing import CliRunner

from specify_cli.cli.commands.agent.tasks import app
from specify_cli.status.models import Lane, StatusEvent
from specify_cli.status.store import StoreError, append_event, read_events
from tests.mocked_env import setup_mocked_env

pytestmark = pytest.mark.fast

runner = CliRunner()

_SLUG = "committed-board-01KZCD"


def _write_wp_file(tasks_dir: Path, wp_id: str) -> None:
    (tasks_dir / f"{wp_id}-test.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Test {wp_id}\nexecution_mode: code_change\n---\n# {wp_id}\n",
        encoding="utf-8",
    )


def _seed_lane(feature_dir: Path, wp_id: str, *, from_lane: Lane, to_lane: Lane) -> None:
    append_event(
        feature_dir,
        StatusEvent(
            event_id=f"test-{feature_dir.name}-{wp_id}-{to_lane}",
            mission_slug=_SLUG,
            wp_id=wp_id,
            from_lane=from_lane,
            to_lane=to_lane,
            at="2026-01-01T00:00:00+00:00",
            actor="test",
            force=True,
            execution_mode="worktree",
        ),
    )


def _build_two_surface_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Build a committed PRIMARY (accepted) + a stale COORD checkout (planned)."""
    primary = tmp_path / "kitty-specs" / _SLUG
    tasks_dir = primary / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_wp_file(tasks_dir, "WP01")
    _write_wp_file(tasks_dir, "WP02")
    (primary / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _SLUG,
                "mission_id": "01KZCD00000000000000000AB",
                "mission_number": 99,
                "mission_type": "software-dev",
                "coordination_branch": f"kitty/mission-{_SLUG}",
            }
        ),
        encoding="utf-8",
    )
    _seed_lane(primary, "WP01", from_lane=Lane.IN_REVIEW, to_lane=Lane.APPROVED)
    _seed_lane(primary, "WP02", from_lane=Lane.APPROVED, to_lane=Lane.DONE)

    coord = tmp_path / ".worktrees" / f"{_SLUG}-coord" / "kitty-specs" / _SLUG
    coord.mkdir(parents=True)
    _seed_lane(coord, "WP01", from_lane=Lane.GENESIS, to_lane=Lane.PLANNED)
    _seed_lane(coord, "WP02", from_lane=Lane.GENESIS, to_lane=Lane.PLANNED)

    return primary, coord


@pytest.mark.regression
def test_status_board_reports_committed_lanes_for_merged_mission(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#2947: a merged mission's board must show committed (accepted) lanes,
    never the stale coordination checkout's pre-merge ``planned`` lanes."""
    primary, coord = _build_two_surface_fixture(tmp_path)

    # The two on-disk surfaces genuinely diverge -- proves the stale-coord leg
    # is under test, not a same-dir no-op (SHOULD-FIX-6).
    primary_events = read_events(primary)
    coord_events = read_events(coord)
    assert {e.to_lane for e in primary_events} == {Lane.APPROVED, Lane.DONE}
    assert {e.to_lane for e in coord_events} == {Lane.PLANNED}

    workspace = SimpleNamespace(execution_mode="code_change", resolution_kind="lane_workspace")
    monkeypatch.chdir(tmp_path)

    with (
        setup_mocked_env(tmp_path, mission_slug=_SLUG, workspace_resolution=workspace),
        # Simulate the real topology resolver landing on the still-present
        # (stale) coordination checkout -- exactly what a merged mission whose
        # coord worktree was never cleaned up produces (D1/D7: the resolver is
        # existence-gated and freshness-blind).
        patch(
            "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
            return_value=coord,
        ),
    ):
        result = runner.invoke(app, ["status", "--mission", _SLUG, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    lanes_by_id = {wp["id"]: wp["lane"] for wp in payload["work_packages"]}

    # Before the fix: {"WP01": "planned", "WP02": "planned"} (the stale coord
    # rollup). After the fix: the committed PRIMARY lanes.
    assert lanes_by_id == {"WP01": "approved", "WP02": "done"}
    assert payload["by_lane"].get("planned", 0) == 0


def _build_corrupt_primary_fixture(tmp_path: Path) -> tuple[Path, Path]:
    """Build a PRIMARY whose committed event log is corrupt + a valid COORD.

    The PRIMARY carries a genuinely-present but unparsable
    ``status.events.jsonl`` (``has_event_log`` is True — the file exists — so
    the committed-authority read does not take its "genuinely absent" ``None``
    early exit; it must read through to ``wp_ending`` ->
    ``read_event_stream``, which raises ``StoreError`` on the malformed
    line). The COORD checkout
    carries a normal, valid event log so the board's own fallback lane read
    (``_st_runtime_row``) has somewhere else to land -- isolating the
    regression to exactly the committed-authority read this fold guards.
    """
    primary = tmp_path / "kitty-specs" / _SLUG
    tasks_dir = primary / "tasks"
    tasks_dir.mkdir(parents=True)
    _write_wp_file(tasks_dir, "WP01")
    (primary / "meta.json").write_text(
        json.dumps(
            {
                "mission_slug": _SLUG,
                "mission_id": "01KZCD00000000000000000AB",
                "mission_number": 99,
                "mission_type": "software-dev",
                "coordination_branch": f"kitty/mission-{_SLUG}",
            }
        ),
        encoding="utf-8",
    )
    # Malformed JSONL line -- present on disk (has_event_log() == True) but
    # unparsable (StoreError on read), simulating a corrupted PRIMARY log.
    (primary / "status.events.jsonl").write_text(
        '{"event_id": "broken", "wp_id": "WP01", NOT_VALID_JSON\n',
        encoding="utf-8",
    )

    coord = tmp_path / ".worktrees" / f"{_SLUG}-coord" / "kitty-specs" / _SLUG
    coord.mkdir(parents=True)
    _seed_lane(coord, "WP01", from_lane=Lane.GENESIS, to_lane=Lane.PLANNED)

    return primary, coord


@pytest.mark.regression
def test_status_board_degrades_on_corrupt_primary_event_log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """PR-introduced regression: a corrupt PRIMARY ``status.events.jsonl``
    must not crash the board (``agent tasks status``).

    Before this fold, the committed-authority lane read (the per-WP
    ``committed_wp_lane`` reader the #3825 board used, since deleted with its
    last caller) -> ``wp_ending`` -> ``read_event_stream`` raised
    ``StoreError`` UNWRAPPED inside the board's
    per-WP row loop for a merged mission (``mission_number`` assigned) whose
    committed PRIMARY log is corrupt/malformed -- crashing the whole command.
    Before this PR (i.e. pre-committed-authority-read), the board degraded
    gracefully because it never read the committed surface at all. This test
    pins the degrade-not-crash contract: the board must still render, falling
    back to the row's own (coordination-aware) lane source.
    """
    primary, coord = _build_corrupt_primary_fixture(tmp_path)

    with pytest.raises(StoreError):
        read_events(primary)

    workspace = SimpleNamespace(execution_mode="code_change", resolution_kind="lane_workspace")
    monkeypatch.chdir(tmp_path)

    with (
        setup_mocked_env(tmp_path, mission_slug=_SLUG, workspace_resolution=workspace),
        patch(
            "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
            return_value=coord,
        ),
    ):
        result = runner.invoke(app, ["status", "--mission", _SLUG, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    lanes_by_id = {wp["id"]: wp["lane"] for wp in payload["work_packages"]}

    # Degraded: falls back to the coord-read lane instead of crashing.
    assert lanes_by_id == {"WP01": "planned"}


# ---------------------------------------------------------------------------
# #3829 item 3: the WHOLE row comes from one committed reduction — never a
# committed lane beside stale coordination companions.
# ---------------------------------------------------------------------------


def _seed_companions(feature_dir: Path, wp_id: str, *, agent: str, model: str, profile: str) -> None:
    """Seed a resolved-binding annotation on *feature_dir* for *wp_id*.

    The companion fields (``agent`` / ``resolved_model`` /
    ``resolved_agent_profile``) are event-sourced off-axis slots
    (:class:`~specify_cli.status.models.InnerStateChanged`), so a divergent
    pair of annotations on the two surfaces makes the mixed-authority
    regression observable end to end.
    """
    from specify_cli.status.models import InnerStateChanged, WPInnerStateDelta
    from specify_cli.status.store import append_annotations_atomic_verified

    append_annotations_atomic_verified(
        feature_dir,
        [
            InnerStateChanged(
                # Annotation event_ids are ULID-validated on read-back, so a
                # fresh ULID per (surface, WP) is minted here rather than the
                # readable slug the lane ``StatusEvent`` fixtures use.
                event_id=str(ulid.ULID()),
                wp_id=wp_id,
                at="2026-01-02T00:00:00+00:00",
                actor="test",
                delta=WPInnerStateDelta(agent=agent, model=model, agent_profile=profile, role="implementer"),
            )
        ],
    )


@pytest.mark.regression
def test_status_board_row_companions_come_from_the_committed_surface(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """#3829 item 3: for a merged mission on a not-yet-cleaned coordination
    checkout, the row's companion fields (``agent`` / ``resolved_model`` /
    ``resolved_agent_profile`` via ``reconstruct_wp_view``) must come from the
    SAME committed reduction the lane came from — never the stale
    coordination checkout's pre-merge companions beside the committed lane."""
    primary, coord = _build_two_surface_fixture(tmp_path)
    # Divergent companions: the committed surface records the merged
    # actuals; the stale coord checkout still shows its pre-merge pick-up.
    _seed_companions(primary, "WP01", agent="committed-agent", model="committed-model", profile="committed-profile")
    _seed_companions(coord, "WP01", agent="stale-agent", model="stale-model", profile="stale-profile")

    workspace = SimpleNamespace(execution_mode="code_change", resolution_kind="lane_workspace")
    monkeypatch.chdir(tmp_path)

    with (
        setup_mocked_env(tmp_path, mission_slug=_SLUG, workspace_resolution=workspace),
        patch(
            "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
            return_value=coord,
        ),
    ):
        result = runner.invoke(app, ["status", "--mission", _SLUG, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    row = {wp["id"]: wp for wp in payload["work_packages"]}["WP01"]

    # The whole row is committed-sourced: lane AND companions.
    assert row["lane"] == "approved"
    assert row["agent"] == "committed-agent"
    assert row["resolved_model"] == "committed-model"
    assert row["resolved_agent_profile"] == "committed-profile"


@pytest.mark.regression
def test_status_board_row_companions_still_follow_coord_surface_when_not_merged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The not-merged arm: with no committed authority (``mission_number``
    absent), the whole row — lane AND companions — still comes from the
    coordination read, byte-identical to the pre-#3829 board."""
    primary, coord = _build_two_surface_fixture(tmp_path)
    # Un-merge the PRIMARY meta: the coord surface becomes the row's one
    # authority again.
    meta = json.loads((primary / "meta.json").read_text(encoding="utf-8"))
    meta["mission_number"] = None
    (primary / "meta.json").write_text(json.dumps(meta), encoding="utf-8")
    _seed_companions(primary, "WP01", agent="committed-agent", model="committed-model", profile="committed-profile")
    _seed_companions(coord, "WP01", agent="stale-agent", model="stale-model", profile="stale-profile")

    workspace = SimpleNamespace(execution_mode="code_change", resolution_kind="lane_workspace")
    monkeypatch.chdir(tmp_path)

    with (
        setup_mocked_env(tmp_path, mission_slug=_SLUG, workspace_resolution=workspace),
        patch(
            "specify_cli.missions._read_path_resolver.resolve_handle_to_read_path",
            return_value=coord,
        ),
    ):
        result = runner.invoke(app, ["status", "--mission", _SLUG, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    row = {wp["id"]: wp for wp in payload["work_packages"]}["WP01"]

    # Whole row coordination-sourced: the in-flight mission's real state.
    assert row["lane"] == "planned"
    assert row["agent"] == "stale-agent"
    assert row["resolved_model"] == "stale-model"
    assert row["resolved_agent_profile"] == "stale-profile"
