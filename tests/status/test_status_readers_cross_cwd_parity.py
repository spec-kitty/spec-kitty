"""Every migrated status reader agrees, from every cwd, in every coordination state (WP06, SC-001).

Mission lane-worktree-model-hardening, FR-005, FR-043, SC-001; ADR
``2026-11-06-2-one-status-read-contract``. One ``lanes_with_coord`` Mission (WP04's matrix
builder, real git, nothing patched in the resolution path) whose coordination branch commits
three events ending ``in_progress``, while the repository root checkout and the registered lane
worktree both carry a stale ``planned`` copy (spec User Story 1, Independent Test).

Each reader is invoked through the entry its command uses (``CliRunner`` for the CLI readers,
the command's own read function for the internal ones) and its WP01 answer is compared with the
authority. Coordination states: ``present`` (materialized worktree), ``empty`` (worktree checked
out, Mission directory gone, the branch still holds the log: the post-fix EMPTY state) and
``absent`` (no worktree). Working directories: the repository root checkout, the lane checkout
and the coordination worktree (when one is checked out).

``events tail`` follows a file by byte offset, so on a ref-sourced surface (no file on disk) it
refuses with ``status_surface_on_ref`` instead of printing an empty history; that refusal is its
pinned cell value there (WP06 decision; the cursor source over a ref is ADR C-3's).

Commands whose readers live outside WP06's files (``agent tasks status``, ``next``, ``accept``,
``issue-verdict``) are migrated, and joined to this matrix, by WP07 and its follow-ups.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest
from typer.testing import CliRunner

from tests.status.test_status_read_matrix import (
    COORD_BRANCH,
    KITTY_SPECS,
    LANES_WITH_COORD,
    MATERIALIZED,
    SLUG,
    UNMATERIALIZED,
    MatrixMission,
    build_matrix_mission,
    git,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo]

AUTHORITY = "in_progress"
PRESENT = "present"
EMPTY_POST_FIX = "empty"
ABSENT = "absent"
CWD_ROOT = "root"
CWD_LANE = "lane"
CWD_COORD = "coord"
REFUSED_ON_REF = "refused:status_surface_on_ref"

_runner = CliRunner()


def build_mission(base: Path, coord_state: str) -> MatrixMission:
    """The parity Mission in *coord_state* (``present`` / ``empty`` / ``absent``)."""
    if coord_state == PRESENT:
        return build_matrix_mission(base, LANES_WITH_COORD, MATERIALIZED)
    mission = build_matrix_mission(base, LANES_WITH_COORD, UNMATERIALIZED)
    if coord_state == EMPTY_POST_FIX:
        coord_worktree = mission.repo / ".worktrees" / f"{SLUG}-coord"
        git(mission.repo, "worktree", "add", "-q", str(coord_worktree), COORD_BRANCH)
        shutil.rmtree(coord_worktree / KITTY_SPECS / SLUG)
        return MatrixMission(
            repo=mission.repo,
            topology=mission.topology,
            coord_state=coord_state,
            lane_worktree=mission.lane_worktree,
            coord_worktree=coord_worktree,
        )
    return mission


def cwd_root(mission: MatrixMission, cwd: str) -> Path:
    if cwd == CWD_LANE:
        assert mission.lane_worktree is not None
        return mission.lane_worktree
    if cwd == CWD_COORD:
        assert mission.coord_worktree is not None
        return mission.coord_worktree
    return mission.repo


def _first_json(output: str) -> dict[str, Any]:
    for line in output.splitlines():
        line = line.strip()
        if line.startswith("{"):
            parsed: dict[str, Any] = json.loads(line)
            return parsed
    raise AssertionError(f"no JSON object in output:\n{output}")


# ---------------------------------------------------------------------------
# Readers: each returns WP01's lane as the command reports it
# ---------------------------------------------------------------------------


def _mission_status_claim(root: Path) -> str:
    from specify_cli.status.aggregate import MissionStatus

    return str(MissionStatus.load(root, SLUG).claim("WP01").current_lane)


def _agent_status_materialize(root: Path) -> str:
    from specify_cli.cli.commands.agent.status import app

    result = _runner.invoke(app, ["materialize", "--mission", SLUG, "--json"])
    assert result.exit_code == 0, result.output
    return str(_first_json(result.output)["work_packages"]["WP01"]["lane"])


def _retrospect_completion_check(root: Path) -> str:
    from specify_cli.cli.commands.retrospect import _check_mission_completed

    open_wps = _check_mission_completed(cast(Any, SimpleNamespace(mission_slug=SLUG)), root)
    lanes = {entry["wp_id"]: entry["lane"] for entry in open_wps}
    return lanes.get("WP01", "<no open WP01>")


def _agent_retrospect_events(root: Path) -> str:
    from specify_cli.cli.commands.agent_retrospect import _canonical_status_events

    events = _canonical_status_events(root, SLUG, root / KITTY_SPECS / SLUG)
    return str(events[-1].to_lane) if events else "<empty history>"


def _implement_claim_preflight(root: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    from specify_cli.cli.commands import implement_phases

    seen: dict[str, Any] = {}

    def _capture(wp_id: str, _deps: list[str], work_packages: dict[str, Any]) -> None:
        seen.update(work_packages)

    monkeypatch.setattr(implement_phases.dependency_graph, "ensure_wp_claim_preconditions", _capture)
    monkeypatch.setattr(implement_phases.workspace_context, "resolve_mission_target_branch", lambda *_a, **_k: "main")
    ctx = implement_phases.ImplementContext(
        repo_root=root,
        auto_commit=False,
        mission_slug=SLUG,
        mission_dir=root / KITTY_SPECS / SLUG,
        wp_file=root / KITTY_SPECS / SLUG / "tasks" / "WP01.md",
        declared_deps=[],
    )
    implement_phases.claim_preflight(ctx, "WP01")
    return str(seen.get("WP01", {}).get("lane", "<unseeded>"))


def _finalize_execution_has_begun(root: Path) -> str:
    from specify_cli.cli.commands.agent.mission_finalize_planning_pin import _execution_has_begun

    # The finalize gate reports a boolean; the authority (in_progress) means "begun".
    return AUTHORITY if _execution_has_begun(root, SLUG) else "<not begun>"


def _events_tail(root: Path) -> str:
    from specify_cli.cli.commands.events import app

    result = _runner.invoke(app, ["tail", "--mission", SLUG, "--once", "--json"])
    if result.exit_code != 0:
        payload = _first_json(result.output)
        return f"refused:{payload.get('error')}"
    lanes = [json.loads(line)["to_lane"] for line in result.output.splitlines() if line.strip().startswith("{")]
    return lanes[-1] if lanes else "<empty history>"


READERS: dict[str, Callable[..., str]] = {
    "MissionStatus.claim": _mission_status_claim,
    "agent status materialize": _agent_status_materialize,
    "retrospect": _retrospect_completion_check,
    "agent retrospect": _agent_retrospect_events,
    "implement claim_preflight": _implement_claim_preflight,
    "finalize-tasks execution gate": _finalize_execution_has_begun,
    "events tail": _events_tail,
}

CELLS: list[tuple[str, str]] = [
    (PRESENT, CWD_ROOT),
    (PRESENT, CWD_LANE),
    (PRESENT, CWD_COORD),
    (EMPTY_POST_FIX, CWD_ROOT),
    (EMPTY_POST_FIX, CWD_LANE),
    (EMPTY_POST_FIX, CWD_COORD),
    (ABSENT, CWD_ROOT),
    (ABSENT, CWD_LANE),
]


def expected(reader: str, coord_state: str) -> str:
    if reader == "events tail" and coord_state != PRESENT:
        return REFUSED_ON_REF
    return AUTHORITY


def _observe(reader: str, root: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    fn = READERS[reader]
    try:
        if reader == "implement claim_preflight":
            return fn(root, monkeypatch)
        return fn(root)
    except Exception as exc:  # a reader that raises is a divergent cell, named by its type
        return f"!{type(exc).__name__}"


def test_status_readers_agree_across_cwd_and_coord_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """SC-001: 0 divergent cells across (coordination state x cwd x reader)."""
    missions = {state: build_mission(tmp_path / state, state) for state in (PRESENT, EMPTY_POST_FIX, ABSENT)}
    divergent: list[str] = []
    matrix_lines: list[str] = []
    for coord_state, cwd in CELLS:
        mission = missions[coord_state]
        root = cwd_root(mission, cwd)
        for reader in READERS:
            with monkeypatch.context() as patch:
                patch.chdir(root)
                observed = _observe(reader, root, patch)
            want = expected(reader, coord_state)
            mark = "ok" if observed == want else "DIVERGENT"
            matrix_lines.append(f"{coord_state:8} {cwd:6} {reader:30} {observed:40} want={want} {mark}")
            if observed != want:
                divergent.append(f"{coord_state}/{cwd}/{reader}")

    assert not divergent, "divergent cells:\n" + "\n".join(matrix_lines)


# ---------------------------------------------------------------------------
# N4 (WP05 review): an unreadable coordination ref never reads as an empty history
# ---------------------------------------------------------------------------


def _break_coordination_ref(mission: MatrixMission) -> None:
    """Point the coordination branch at a blob: the branch exists, its tree cannot be read."""
    blob = subprocess.run(
        ["git", "-C", str(mission.repo), "hash-object", "-w", "--stdin"],
        input="not a commit\n",
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()
    git(mission.repo, "update-ref", f"refs/heads/{COORD_BRANCH}", blob)


@pytest.mark.parametrize(
    "reader",
    ["MissionStatus.claim", "retrospect", "agent retrospect", "implement claim_preflight", "finalize-tasks execution gate"],
)
def test_unreadable_coordination_ref_fails_closed_for_every_reader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reader: str) -> None:
    """N4: a migrated reader refuses an unreadable coordination ref; it never answers from no history."""
    mission = build_mission(tmp_path, ABSENT)
    _break_coordination_ref(mission)
    monkeypatch.chdir(mission.repo)

    observed = _observe(reader, mission.repo, monkeypatch)

    assert observed == "!StatusSurfaceRefUnreadable"


@pytest.mark.parametrize("reader", ["MissionStatus.claim", "retrospect", "agent retrospect", "implement claim_preflight", "finalize-tasks execution gate"])
def test_empty_coordination_worktree_reads_the_committed_history(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, reader: str) -> None:
    """N4: a post-fix EMPTY coordination worktree reads the branch's three events, not an empty history."""
    mission = build_mission(tmp_path, EMPTY_POST_FIX)
    monkeypatch.chdir(mission.repo)

    assert _observe(reader, mission.repo, monkeypatch) == AUTHORITY


def test_retrospective_gate_reads_retrospective_events_from_the_coordination_ref(tmp_path: Path) -> None:
    """The retrospective gate reads ``retrospective.*`` events from the declared source (a ref here)."""
    from specify_cli.retrospective.gate import _read_status_log_retrospective_events

    mission = build_matrix_mission(tmp_path, LANES_WITH_COORD, MATERIALIZED)
    line = json.dumps({"event_name": "retrospective.completed", "mission_id": "m", "at": "2026-11-06T00:03:00+00:00"})
    events_file = mission.coord_mission_dir / "status.events.jsonl"
    events_file.write_text(events_file.read_text(encoding="utf-8") + line + "\n", encoding="utf-8")
    assert mission.coord_worktree is not None
    git(mission.coord_worktree, "add", "-A")
    git(mission.coord_worktree, "commit", "-q", "-m", "retrospective event")
    git(mission.repo, "worktree", "remove", "-f", str(mission.coord_worktree))

    events = _read_status_log_retrospective_events(feature_dir=mission.root_mission_dir, repo_root=mission.repo)

    assert [event["event_name"] for event in events] == ["retrospective.completed"]
