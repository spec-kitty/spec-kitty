"""#7792: ``finalize-tasks`` commits its own writes in the coordination worktree.

A default Mission settled to ``lanes_with_coord`` keeps its PRIMARY-partition planning
artifacts (``tasks.md``, ``lanes.json``, ``tasks/WP*.md``) in the coordination worktree
until it lands. ``finalize-tasks`` used to probe those candidates for pending changes in
the repository root checkout, where the nested ``.worktrees/<slug>-coord/`` checkout is
invisible, so a re-finalize after adding a WP reported ``commit_created: false`` and left
its own writes dirty. Every test drives the real ``finalize-tasks`` command.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from specify_cli.cli.commands.agent.mission_finalize_commit import _CommitOutcome
from tests.specify_cli.cli.commands.agent.test_finalize_topology_settlement import (
    REPO_ROOT,
    THREE_LANES,
    DefaultMission,
    git,
    make_default_mission,
    run_finalize,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]


@pytest.fixture(autouse=True)
def _quiet_status_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    import specify_cli.status.emit as emit_module

    monkeypatch.chdir(REPO_ROOT)
    monkeypatch.setattr(emit_module, "_status_fan_out", lambda *a, **k: None)


def _settled_lanes_with_coord(tmp_path: Path) -> DefaultMission:
    mission = make_default_mission(tmp_path, THREE_LANES)
    code, payload = run_finalize(mission)
    assert code == 0, payload
    decision = payload["topology_decision"]
    assert isinstance(decision, dict) and decision["settled_topology"] == "lanes_with_coord"
    return mission


def _add_wp(mission_dir: Path, wp_id: str, owned: str) -> None:
    (mission_dir / "tasks" / f"{wp_id}-work.md").write_text(
        f"---\nwork_package_id: {wp_id}\ntitle: Work {wp_id}\ndependencies: []\nrequirement_refs: [FR-001]\nsubtasks: []\n"
        f"owned_files: [{owned}]\nauthoritative_surface: {owned}\nexecution_mode: code_change\n"
        f"create_intent:\n  - {owned}\n---\n\n# {wp_id}\n",
        encoding="utf-8",
    )
    tasks_md = mission_dir / "tasks.md"
    tasks_md.write_text(tasks_md.read_text(encoding="utf-8") + f"## {wp_id}\n\nNo dependencies.\n\n", encoding="utf-8")


def test_refinalize_commits_new_wp_in_coordination_worktree(tmp_path: Path) -> None:
    mission = _settled_lanes_with_coord(tmp_path)
    coord_root = mission.coord_mission_dir.parents[1]
    assert git(coord_root, "status", "--porcelain") == ""
    _add_wp(mission.coord_mission_dir, "WP04", "src/four.py")

    code, payload = run_finalize(mission)

    assert code == 0, payload
    assert payload["commit_created"] is True, payload
    assert git(coord_root, "status", "--porcelain") == ""
    lanes = git(mission.root, "show", f"{mission.topic}:kitty-specs/{mission.slug}/lanes.json")
    assert "WP04" in lanes


def test_candidate_probe_sees_dirt_in_nested_coordination_worktree(tmp_path: Path) -> None:
    """Unit: the candidate probe reads the coordination worktree, not the repository root checkout."""
    from specify_cli.cli.commands.agent import mission_finalize as mf

    mission = _settled_lanes_with_coord(tmp_path)
    planning_dir = mission.coord_mission_dir
    coord_root = planning_dir.parents[1]
    assert mf._planning_checkout_root(planning_dir, mission.root, mission.slug, owned=None) == coord_root
    tasks_md = planning_dir / "tasks.md"
    tasks_md.write_text(tasks_md.read_text(encoding="utf-8") + "\nedit\n", encoding="utf-8")

    candidates = mf._resolve_finalize_commit_candidates(planning_dir, planning_dir / "tasks", mission.root, planning_dir / "lanes.json", mission_slug=mission.slug)

    assert candidates.has_relevant_changes is True
    assert candidates.checkouts[tasks_md] == coord_root


def test_planning_checkout_root_falls_back_for_a_foreign_directory(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission_finalize as mf

    mission = _settled_lanes_with_coord(tmp_path)
    foreign = tmp_path / "elsewhere"
    foreign.mkdir()
    assert mf._planning_checkout_root(foreign, mission.root, mission.slug, owned=None) == mission.root


def test_uncommitted_writes_ignore_files_the_run_did_not_write(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission_finalize as mf

    mission = _settled_lanes_with_coord(tmp_path)
    coord_root = mission.coord_mission_dir.parents[1]
    tasks_md = mission.coord_mission_dir / "tasks.md"
    tasks_md.write_text("dirty\n", encoding="utf-8")
    ledger = mf.FinalizeWriteLedger()
    assert mf._uncommitted_finalize_writes({tasks_md: coord_root}, None) == []
    assert mf._uncommitted_finalize_writes({tasks_md: coord_root}, ledger) == []
    ledger.record(tasks_md, b"dirty\n")
    assert mf._uncommitted_finalize_writes({tasks_md: coord_root}, ledger) == [tasks_md]


def test_refinalize_refuses_when_its_own_writes_stay_uncommitted(tmp_path: Path) -> None:
    """Postcondition: a probe that misses finalize's own writes fails loud, never "unchanged"."""
    from specify_cli.cli.commands.agent import mission_finalize as mf

    mission = _settled_lanes_with_coord(tmp_path)
    _add_wp(mission.coord_mission_dir, "WP04", "src/four.py")
    real = mf._resolve_finalize_commit_candidates

    def _blind(
        planning_dir: Path, tasks_dir: Path, repo_root: Path, lanes_path: Path | None, *, mission_slug: str, owned: object = None
    ) -> mf._FinalizeCommitCandidates:
        assert owned is None
        found = real(planning_dir, tasks_dir, repo_root, lanes_path, mission_slug=mission_slug)
        return mf._FinalizeCommitCandidates(
            files_to_commit=found.files_to_commit,
            files_to_commit_rel=found.files_to_commit_rel,
            has_relevant_changes=False,
            checkouts=found.checkouts,
        )

    with patch.object(mf, "_resolve_finalize_commit_candidates", _blind):
        code, payload = run_finalize(mission)

    assert code == 1, payload
    assert payload["error_code"] == "FINALIZE_WRITES_UNCOMMITTED"
    uncommitted = payload["uncommitted_files"]
    assert isinstance(uncommitted, list)
    assert any(str(name).endswith("lanes.json") for name in uncommitted)
    assert "No commit landed" in str(payload["error"])


def _outcome(tmp_path: Path, *, surface_refusal: bool, commit_created: bool) -> tuple[_CommitOutcome, Path]:
    from specify_cli.cli.commands.agent import mission_finalize as mf

    root = tmp_path / "repo-postcondition"
    root.mkdir()
    git(root, "init", "-q")
    dirty = root / "tasks.md"
    dirty.write_text("x\n", encoding="utf-8")
    return mf._CommitOutcome(commit_created=commit_created, surface_refusal=surface_refusal, candidate_checkouts={dirty: root}), dirty


def test_postcondition_defers_to_a_surface_refusal(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission_finalize as mf

    outcome, dirty = _outcome(tmp_path, surface_refusal=True, commit_created=True)
    ledger, ledger_token, observer_token = mf.begin_write_ledger()
    try:
        ledger.record(dirty, b"x\n")
        mf._refuse_uncommitted_finalize_writes(outcome, json_output=True)  # no raise
    finally:
        mf.end_write_ledger(ledger_token, observer_token)


def test_postcondition_trusts_a_reported_commit(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission_finalize as mf

    outcome, dirty = _outcome(tmp_path, surface_refusal=False, commit_created=True)
    ledger, ledger_token, observer_token = mf.begin_write_ledger()
    try:
        ledger.record(dirty, b"x\n")
        mf._refuse_uncommitted_finalize_writes(outcome, json_output=True)  # no raise
    finally:
        mf.end_write_ledger(ledger_token, observer_token)


def test_postcondition_refuses_in_text_mode_when_nothing_landed(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    import typer

    from specify_cli.cli.commands.agent import mission_finalize as mf

    outcome, dirty = _outcome(tmp_path, surface_refusal=False, commit_created=False)
    ledger, ledger_token, observer_token = mf.begin_write_ledger()
    try:
        ledger.record(dirty, b"x\n")
        with pytest.raises(typer.Exit):
            mf._refuse_uncommitted_finalize_writes(outcome, json_output=False)
    finally:
        mf.end_write_ledger(ledger_token, observer_token)
    out = capsys.readouterr().out
    assert "FINALIZE_WRITES_UNCOMMITTED" in out and "No commit landed" in out


def test_postcondition_checks_writes_behind_an_unchanged_surface_after_a_commit(tmp_path: Path) -> None:
    """A committed PRIMARY group beside an unchanged coordination group: its dirty writes still refuse."""
    import typer

    from specify_cli.cli.commands.agent import mission_finalize as mf

    outcome, dirty = _outcome(tmp_path, surface_refusal=False, commit_created=True)
    outcome.commit_surfaces = [{"surface": "primary", "status": "committed"}, {"surface": "coordination", "status": "unchanged"}]
    ledger, ledger_token, observer_token = mf.begin_write_ledger()
    try:
        ledger.record(dirty, b"x\n")
        with patch.object(mf, "_emit_json") as emit, pytest.raises(typer.Exit):
            mf._refuse_uncommitted_finalize_writes(outcome, json_output=True)
    finally:
        mf.end_write_ledger(ledger_token, observer_token)
    payload = emit.call_args.args[0]
    assert payload["error_code"] == "FINALIZE_WRITES_UNCOMMITTED"
    assert "A commit landed and is kept" in payload["error"]


def test_postcondition_trusts_every_surface_committed(tmp_path: Path) -> None:
    from specify_cli.cli.commands.agent import mission_finalize as mf

    outcome, dirty = _outcome(tmp_path, surface_refusal=False, commit_created=True)
    outcome.commit_surfaces = [{"surface": "primary", "status": "committed"}, {"surface": "coordination", "status": "committed"}]
    ledger, ledger_token, observer_token = mf.begin_write_ledger()
    try:
        ledger.record(dirty, b"x\n")
        mf._refuse_uncommitted_finalize_writes(outcome, json_output=True)  # no raise
    finally:
        mf.end_write_ledger(ledger_token, observer_token)


def test_planning_checkout_root_resolves_a_symlinked_spelling(tmp_path: Path) -> None:
    """A planning dir spelled through a symbolic link still finds the coordination worktree."""
    from specify_cli.cli.commands.agent import mission_finalize as mf

    mission = _settled_lanes_with_coord(tmp_path)
    link = tmp_path / "linked"
    link.symlink_to(mission.root, target_is_directory=True)
    linked_planning = link / mission.coord_mission_dir.relative_to(mission.root)

    root = mf._planning_checkout_root(linked_planning, mission.root, mission.slug, owned=None)

    assert root == link / mission.coord_mission_dir.parents[1].relative_to(mission.root)
    assert linked_planning.is_relative_to(root)
    tasks_md = linked_planning / "tasks.md"
    tasks_md.write_text(tasks_md.read_text(encoding="utf-8") + "\nedit\n", encoding="utf-8")
    candidates = mf._resolve_finalize_commit_candidates(
        linked_planning, linked_planning / "tasks", mission.root, linked_planning / "lanes.json", mission_slug=mission.slug
    )
    assert candidates.has_relevant_changes is True


def test_settlement_commits_its_meta_restamp_in_the_coordination_worktree(tmp_path: Path) -> None:
    mission = _settled_lanes_with_coord(tmp_path)
    coord_root = mission.coord_mission_dir.parents[1]
    assert git(coord_root, "status", "--porcelain") == ""
    meta = git(mission.root, "show", f"{mission.topic}:kitty-specs/{mission.slug}/meta.json")
    assert '"coordination_branch"' in meta and '"lanes_with_coord"' in meta


def _meta_repo(tmp_path: Path, committed: dict[str, object], current: dict[str, object]) -> Path:
    import json

    root = tmp_path / "meta-repo"
    root.mkdir()
    git(root, "init", "-q")
    meta = root / "meta.json"
    meta.write_text(json.dumps(committed), encoding="utf-8")
    git(root, "add", "meta.json")
    git(root, "-c", "user.email=t@example.com", "-c", "user.name=t", "commit", "-qm", "meta")
    meta.write_text(json.dumps(current), encoding="utf-8")
    return meta


_PROVISIONAL: dict[str, object] = {"slug": "s", "topology": "single_branch", "topology_settled": False}
_SETTLED: dict[str, object] = {
    "topology": "lanes_with_coord",
    "coordination_branch": "b",
    "topology_settled": True,
    "topology_decision": {"rule": "x"},
}


@pytest.mark.parametrize(
    ("committed", "current", "expected"),
    [
        (_PROVISIONAL, {**_PROVISIONAL, **_SETTLED}, True),
        (_PROVISIONAL, {**_PROVISIONAL, "topology": "lanes_with_coord"}, False),
        (_PROVISIONAL, {**_PROVISIONAL, "topology": "lanes_with_coord", "coordination_branch": "b"}, False),
        (_PROVISIONAL, {**_PROVISIONAL, **_SETTLED, "vcs": "git"}, False),
        ({**_PROVISIONAL, **_SETTLED}, {**_PROVISIONAL, **_SETTLED, "topology": "lanes"}, False),
    ],
    ids=[
        "settlement_delta",
        "topology_alone",
        "topology_and_coordination_branch_without_decision",
        "settlement_plus_foreign_field",
        "decision_already_at_head",
    ],
)
def test_meta_settlement_delta_attribution(tmp_path: Path, committed: dict[str, object], current: dict[str, object], expected: bool) -> None:
    from specify_cli.cli.commands.agent import mission_finalize as mf

    meta = _meta_repo(tmp_path, committed, current)
    assert mf._meta_json_delta_is_finalize_attributable(meta, meta.parent) is expected
