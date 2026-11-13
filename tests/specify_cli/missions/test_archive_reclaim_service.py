"""Branch-level tests for :mod:`specify_cli.missions.archive_reclaim` (#4041).

The end-to-end cells drive the real CLI against a real consolidation
(``tests/specify_cli/cli/commands/test_archive_reclaim.py``, nightly). These cover each refusal and
step branch of the service and the CLI rendering directly, with the git- and seam-facing
collaborators replaced at the module boundary.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from specify_cli.cli.commands import archive as archive_cli
from specify_cli.consolidation.git_probes import GitProbeError
from specify_cli.coordination.teardown import CoordTeardownKeptOnlyCopy, ProjectionTeardownAbort
from specify_cli.coordination.workspace import CoordinationWorkspace
from specify_cli.git.commit_helpers import SafeCommitHeadMismatch
from specify_cli.git.destructive_guard import DestructiveOpRefused
from specify_cli.missions import archive_reclaim as reclaim
from specify_cli.missions.archive_reclaim import ReclaimRefused, ReclaimReport

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_SLUG = "demo-01ABCDEF"
_BRANCH = "kitty/mission-demo-01ABCDEF"
_LANDED = "a" * 40
_LIVE = "b" * 40


def _feature_dir(tmp_path: Path, **meta: Any) -> Path:
    feature_dir = tmp_path / "kitty-specs" / _SLUG
    feature_dir.mkdir(parents=True)
    (feature_dir / "meta.json").write_text(json.dumps({"mission_id": "01ABCDEF" + "0" * 18, "mission_slug": _SLUG, **meta}), encoding="utf-8")
    return feature_dir


@pytest.fixture
def seams(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    """Every collaborator answers "archived, landed at the live tip, worktree present"; a test overrides one."""
    calls: dict[str, Any] = {"deleted": [], "cleared": [], "teardown": 0, "flattened": 0, "committed": 0}
    present = {"value": True}

    def teardown(*_args: object, **_kwargs: object) -> bool:
        calls["teardown"] += 1
        present["value"] = False
        return True

    def delete(_root: Path, branch: str, **kwargs: object) -> None:
        calls["deleted"].append((branch, kwargs))

    def flatten(_feature_dir: Path) -> dict[str, object]:
        calls["flattened"] += 1
        return {}

    def commit(**_kwargs: object) -> None:
        calls["committed"] += 1

    monkeypatch.setattr(reclaim, "primary_mission_dir", lambda _root, _slug: tmp_path / "kitty-specs" / _SLUG)
    monkeypatch.setattr(reclaim, "is_mission_archived", lambda _root, _mission_id: True)
    monkeypatch.setattr(reclaim, "is_mission_merged", lambda _dir: True)
    monkeypatch.setattr(reclaim, "commit_in_clone", lambda _root, _ref: True)
    monkeypatch.setattr(reclaim, "resolve_commit", lambda _root, _ref: _LIVE)
    monkeypatch.setattr(reclaim, "landed_coordination_tip", lambda _root, _branch: _LIVE)
    monkeypatch.setattr(reclaim, "is_ancestor_strict", lambda _root, _a, _b: False)
    monkeypatch.setattr(CoordinationWorkspace, "branch_name", staticmethod(lambda _slug, _mid8: _BRANCH))
    monkeypatch.setattr(CoordinationWorkspace, "is_present", staticmethod(lambda *_a: present["value"]))
    monkeypatch.setattr(reclaim, "teardown_coordination_topology", teardown)
    monkeypatch.setattr(reclaim, "guarded_branch_delete", delete)
    monkeypatch.setattr(reclaim, "clear_landed_coordination_tip", lambda _root, branch: calls["cleared"].append(branch) or True)
    monkeypatch.setattr(reclaim, "flatten_coordination_metadata", flatten)
    monkeypatch.setattr(reclaim, "commit_merge_bookkeeping", commit)
    monkeypatch.setattr(reclaim, "resolve_terminal_state", lambda _dir: "merged")
    monkeypatch.setattr(reclaim, "_preflight_marker_commit", lambda *_a, **_k: None, raising=False)
    calls["present"] = present
    return calls


def _coord_meta(tmp_path: Path, **extra: Any) -> Path:
    return _feature_dir(tmp_path, coordination_branch=_BRANCH, mid8="01ABCDEF", target_branch="main", **extra)


def _refusal(tmp_path: Path) -> ReclaimRefused:
    with pytest.raises(ReclaimRefused) as excinfo:
        reclaim.reclaim_archived_mission(tmp_path, _SLUG)
    return excinfo.value


def test_happy_path_runs_every_step_bound_to_the_live_tip(tmp_path: Path, seams: dict[str, Any]) -> None:
    _coord_meta(tmp_path)

    report = reclaim.reclaim_archived_mission(tmp_path, _SLUG)

    assert [step.outcome for step in report.steps] == ["removed", "deleted", "flattened and committed"]
    assert not report.nothing_left
    assert seams["deleted"] == [(_BRANCH, {"creation_base": None, "operator_intent": "landed", "expected_tip": _LIVE})]
    assert seams["cleared"] == [_BRANCH]
    assert seams["teardown"] == 1 and seams["flattened"] == 1 and seams["committed"] == 1


def test_a_live_tip_behind_the_landed_tip_is_proved(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)
    monkeypatch.setattr(reclaim, "landed_coordination_tip", lambda _root, _branch: _LANDED)
    monkeypatch.setattr(reclaim, "is_ancestor_strict", lambda _root, ancestor, descendant: (ancestor, descendant) == (_LIVE, _LANDED))

    reclaim.reclaim_archived_mission(tmp_path, _SLUG)

    assert seams["deleted"]


def test_partial_state_skips_the_done_steps(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)
    seams["present"]["value"] = False
    monkeypatch.setattr(reclaim, "commit_in_clone", lambda _root, _ref: False)

    report = reclaim.reclaim_archived_mission(tmp_path, _SLUG)

    assert [step.outcome for step in report.steps] == ["already gone", "already gone", "flattened and committed"]
    assert seams["teardown"] == 1, "the seam (and its ledger guard) runs even when the worktree is already gone"
    assert seams["deleted"] == [] and seams["cleared"] == [_BRANCH]


def test_not_archived_refuses(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)
    monkeypatch.setattr(reclaim, "is_mission_archived", lambda _root, _mission_id: False)

    assert _refusal(tmp_path).error_code == reclaim.RECLAIM_NOT_ARCHIVED
    assert seams["teardown"] == 0


def test_unreadable_meta_refuses(tmp_path: Path, seams: dict[str, Any]) -> None:
    (tmp_path / "kitty-specs" / _SLUG).mkdir(parents=True)

    assert _refusal(tmp_path).error_code == reclaim.RECLAIM_NO_COORDINATION


def test_never_coordinated_refuses(tmp_path: Path, seams: dict[str, Any]) -> None:
    _feature_dir(tmp_path, topology="single_branch")

    assert _refusal(tmp_path).error_code == reclaim.RECLAIM_NO_COORDINATION


def test_flattened_mission_has_nothing_left(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _feature_dir(tmp_path, flattened=True)
    monkeypatch.setattr(reclaim, "_meta_uncommitted", lambda _root, _dir: False)

    report = reclaim.reclaim_archived_mission(tmp_path, _SLUG)

    assert report.nothing_left and report.steps == ()


def test_an_uncommitted_flatten_is_committed(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _feature_dir(tmp_path, flattened=True)
    monkeypatch.setattr(reclaim, "_meta_uncommitted", lambda _root, _dir: True)

    report = reclaim.reclaim_archived_mission(tmp_path, _SLUG)

    assert not report.nothing_left and seams["committed"] == 1


def test_meta_uncommitted_fails_closed_outside_a_repository(tmp_path: Path) -> None:
    """#7598 fold (NIT-8): a git error must not read as "nothing uncommitted" ("Nothing left to reclaim")."""
    feature_dir = _feature_dir(tmp_path)

    with pytest.raises(ReclaimRefused) as excinfo:
        reclaim._meta_uncommitted(tmp_path, feature_dir)

    assert excinfo.value.error_code == reclaim.RECLAIM_MARKER_NOT_COMMITTED


def test_a_flattened_mission_whose_status_cannot_be_read_is_refused(tmp_path: Path, seams: dict[str, Any]) -> None:
    _feature_dir(tmp_path, flattened=True)

    assert _refusal(tmp_path).error_code == reclaim.RECLAIM_MARKER_NOT_COMMITTED


def test_marker_without_mid8_refuses(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _feature_dir(tmp_path, coordination_branch=_BRANCH)
    monkeypatch.setattr(reclaim, "recorded_mid8", lambda _meta: "")

    assert _refusal(tmp_path).error_code == reclaim.RECLAIM_NO_COORDINATION


def test_unreadable_branch_refuses(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)

    def broken(_root: Path, _ref: str) -> bool:
        raise GitProbeError("boom")

    monkeypatch.setattr(reclaim, "commit_in_clone", broken)

    assert _refusal(tmp_path).error_code == reclaim.RECLAIM_UNABSORBED


@pytest.mark.parametrize(("terminal", "expected"), [("merged", "nothing was changed"), ("canceled", "spec-kitty mission close --discard --mission")])
def test_unmerged_mission_refuses_with_the_right_remedy(
    tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch, terminal: str, expected: str
) -> None:
    _coord_meta(tmp_path)
    monkeypatch.setattr(reclaim, "is_mission_merged", lambda _dir: False)
    monkeypatch.setattr(reclaim, "resolve_terminal_state", lambda _dir: terminal)

    refused = _refusal(tmp_path)

    assert refused.error_code == reclaim.RECLAIM_UNABSORBED and "merged_at" in str(refused)
    assert expected in refused.remedy
    assert seams["teardown"] == 0 and seams["deleted"] == []


def test_no_recorded_landed_tip_refuses(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)
    monkeypatch.setattr(reclaim, "landed_coordination_tip", lambda _root, _branch: None)

    refused = _refusal(tmp_path)

    assert refused.error_code == reclaim.RECLAIM_UNABSORBED and "no recorded landed coordination tip" in str(refused)


_INSPECT = f"git log main..{_BRANCH}"


@pytest.mark.parametrize("cause", ["no_merged_at", "no_landed_tip"])
@pytest.mark.parametrize("terminal", ["merged", "canceled"])
def test_an_unproved_landing_names_the_inspection_command(
    tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch, cause: str, terminal: str
) -> None:
    """#7598 fold (MINOR-3): "nothing was changed" alone is no next step; name what to inspect, and when removal is safe."""
    _coord_meta(tmp_path)
    if cause == "no_merged_at":
        monkeypatch.setattr(reclaim, "is_mission_merged", lambda _dir: False)
    else:
        monkeypatch.setattr(reclaim, "landed_coordination_tip", lambda _root, _branch: None)
    monkeypatch.setattr(reclaim, "resolve_terminal_state", lambda _dir: terminal)

    refused = _refusal(tmp_path)

    assert _INSPECT in refused.remedy
    assert f"git branch -D {_BRANCH}" in refused.remedy and "only after" in refused.remedy
    assert ("spec-kitty mission close --discard --mission" in refused.remedy) is (terminal == "canceled")


def test_commits_after_the_landing_are_listed_and_capped(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)
    late = [f"{index:02d}" + "c" * 38 for index in range(25)]
    monkeypatch.setattr(reclaim, "landed_coordination_tip", lambda _root, _branch: _LANDED)
    monkeypatch.setattr(reclaim, "commits_in_range", lambda _root, _base, _tip: late)

    refused = _refusal(tmp_path)

    assert "25 commit(s)" in str(refused) and late[0][:12] in str(refused) and "and 5 more" in str(refused)
    assert late[24][:12] not in str(refused)


def test_an_unprovable_landing_refuses(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)

    def broken(_root: Path, _branch: str) -> str:
        raise GitProbeError("boom")

    monkeypatch.setattr(reclaim, "landed_coordination_tip", broken)

    assert "could not be proved" in str(_refusal(tmp_path))


def test_a_dirty_worktree_refusal_keeps_its_code(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)

    def dirty(*_args: object, **_kwargs: object) -> bool:
        raise CoordTeardownKeptOnlyCopy(worktree_path=tmp_path, kept_files=["x.md"], follow_up_command="spec-kitty archive reclaim demo")

    monkeypatch.setattr(reclaim, "teardown_coordination_topology", dirty)

    refused = _refusal(tmp_path)

    assert refused.error_code == CoordTeardownKeptOnlyCopy.error_code
    assert seams["deleted"] == []


def test_the_teardown_seam_runs_without_its_persist_leg(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """#7598 fold (NIT-4): consolidate already persisted a merged Mission's retrospective; reclaim never commits one."""
    _coord_meta(tmp_path)
    seen: dict[str, object] = {}

    def teardown(*_args: object, **kwargs: object) -> bool:
        seen.update(kwargs)
        seams["present"]["value"] = False
        return True

    monkeypatch.setattr(reclaim, "teardown_coordination_topology", teardown)

    reclaim.reclaim_archived_mission(tmp_path, _SLUG)

    assert seen.get("persist") is False


def test_an_unexpected_teardown_error_is_a_named_refusal(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """#7598 fold (NIT-4): any other seam failure is RECLAIM_WORKTREE_KEPT with its text, never a traceback."""
    _coord_meta(tmp_path)

    def broken(*_args: object, **_kwargs: object) -> bool:
        raise OSError("disk went away")

    monkeypatch.setattr(reclaim, "teardown_coordination_topology", broken)

    refused = _refusal(tmp_path)

    assert refused.error_code == reclaim.RECLAIM_WORKTREE_KEPT and "disk went away" in str(refused)
    assert seams["deleted"] == []


def test_a_worktree_the_seam_could_not_remove_refuses(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)
    monkeypatch.setattr(reclaim, "teardown_coordination_topology", lambda *_a, **_k: False)

    assert _refusal(tmp_path).error_code == reclaim.RECLAIM_WORKTREE_KEPT


def test_a_moved_branch_refuses_and_keeps_the_landed_ref(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)

    def moved(*_args: object, **_kwargs: object) -> None:
        raise DestructiveOpRefused(error_code="BRANCH_TIP_MOVED", remediation="re-run")

    monkeypatch.setattr(reclaim, "guarded_branch_delete", moved)

    assert _refusal(tmp_path).error_code == "BRANCH_TIP_MOVED"
    assert seams["cleared"] == []


def test_a_kept_tip_is_reported_under_the_ref_the_guard_names(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)
    monkeypatch.setattr(reclaim, "guarded_branch_delete", lambda *_a, **_k: _LIVE)
    monkeypatch.setattr(reclaim, "discarded_ref", lambda _root, branch, tip: f"refs/spec-kitty/discarded/{branch}@{tip[:12]}", raising=False)

    report = reclaim.reclaim_archived_mission(tmp_path, _SLUG)

    assert f"refs/spec-kitty/discarded/{_BRANCH}@{_LIVE[:12]}" in report.steps[1].detail


def test_an_unrepaired_ledger_refuses_before_the_branch_goes_even_without_a_worktree(
    tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review cycle 1, N1: the seam's ledger guard protects the branch whatever the step order."""
    _coord_meta(tmp_path)
    seams["present"]["value"] = False

    def unrepaired(*_args: object, **_kwargs: object) -> bool:
        raise ProjectionTeardownAbort(reason="ledger only on coordination", coord_ref=_BRANCH, error_code="COORDINATION_LEDGER_UNREPAIRED", remedy="repair")

    monkeypatch.setattr(reclaim, "teardown_coordination_topology", unrepaired)

    assert _refusal(tmp_path).error_code == "COORDINATION_LEDGER_UNREPAIRED"
    assert seams["deleted"] == []


def test_an_unreachable_commit_destination_refuses_before_any_change(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 1, F1."""
    _coord_meta(tmp_path)

    def off_target(*_args: object, **_kwargs: object) -> None:
        raise SafeCommitHeadMismatch(destination_ref="main", observed_head="side", worktree_root=tmp_path)

    monkeypatch.setattr(reclaim, "_preflight_marker_commit", off_target, raising=False)

    refused = _refusal(tmp_path)

    assert refused.error_code == reclaim.RECLAIM_NOT_ON_TARGET and "git checkout main" in refused.remedy
    assert seams["teardown"] == 0 and seams["deleted"] == [] and seams["flattened"] == 0


def test_a_failed_flatten_refuses_with_a_named_code(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """Review cycle 1, N2."""
    _coord_meta(tmp_path)

    def locked(_feature_dir: Path) -> dict[str, object]:
        raise TimeoutError("Mission write lock held")

    monkeypatch.setattr(reclaim, "flatten_coordination_metadata", locked)

    refused = _refusal(tmp_path)

    assert refused.error_code == reclaim.RECLAIM_MARKER_NOT_COMMITTED and "re-run" in refused.remedy.lower()


def test_a_failed_marker_commit_refuses(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    _coord_meta(tmp_path)

    def broken(**_kwargs: object) -> None:
        raise RuntimeError("protected")

    monkeypatch.setattr(reclaim, "commit_merge_bookkeeping", broken)

    assert _refusal(tmp_path).error_code == reclaim.RECLAIM_MARKER_NOT_COMMITTED


def test_holds_coordination_marker(tmp_path: Path, seams: dict[str, Any]) -> None:
    _coord_meta(tmp_path)

    assert reclaim.holds_coordination_marker(tmp_path, _SLUG) is True
    assert reclaim.reclaim_command(_SLUG) == f"spec-kitty archive reclaim {_SLUG}"


# -- CLI rendering ---------------------------------------------------------------------------


@pytest.fixture
def cli(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> CliRunner:
    feature_dir = _feature_dir(tmp_path)
    monkeypatch.setattr(archive_cli, "locate_project_root", lambda: tmp_path)
    monkeypatch.setattr(archive_cli, "candidate_feature_dir_for_mission", lambda _root, _mission: feature_dir)
    monkeypatch.setattr(archive_cli, "primary_mission_dir", lambda _root, _mission: feature_dir)
    return CliRunner()


def _report(nothing_left: bool) -> ReclaimReport:
    steps = () if nothing_left else (reclaim.ReclaimStep("coordination branch", "deleted", _BRANCH),)
    return ReclaimReport(mission_slug=_SLUG, steps=steps, nothing_left=nothing_left)


@pytest.mark.parametrize("nothing_left", [True, False])
def test_cli_renders_the_report_as_json(cli: CliRunner, monkeypatch: pytest.MonkeyPatch, nothing_left: bool) -> None:
    monkeypatch.setattr(archive_cli, "reclaim_archived_mission", lambda _root, _slug: _report(nothing_left))

    result = cli.invoke(archive_cli.app, ["reclaim", _SLUG, "--json"])

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["ok"] is True and payload["nothing_left"] is nothing_left


def test_cli_renders_a_refusal_as_json(cli: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(_root: Path, _slug: str) -> ReclaimReport:
        raise ReclaimRefused(reclaim.RECLAIM_UNABSORBED, "not landed", "keep it")

    monkeypatch.setattr(archive_cli, "reclaim_archived_mission", refuse)

    result = cli.invoke(archive_cli.app, ["reclaim", _SLUG, "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.output)
    assert payload["remedy"] == "keep it" and reclaim.RECLAIM_UNABSORBED in json.dumps(payload)


def test_cli_renders_steps_as_text(cli: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive_cli, "reclaim_archived_mission", lambda _root, _slug: _report(False))

    result = cli.invoke(archive_cli.app, ["reclaim", _SLUG])

    assert result.exit_code == 0 and "Coordination branch  deleted" in result.output


def test_cli_outside_a_project_exits_2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive_cli, "locate_project_root", lambda: None)

    result = CliRunner().invoke(archive_cli.app, ["reclaim", _SLUG])

    assert result.exit_code == 2


def test_cli_outside_a_project_exits_2_with_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive_cli, "locate_project_root", lambda: None)

    result = CliRunner().invoke(archive_cli.app, ["reclaim", _SLUG, "--json"])

    assert result.exit_code == 2 and "not_in_project" in result.output


@pytest.mark.parametrize("json_flag", [[], ["--json"]])
def test_cli_reports_an_unknown_mission(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, json_flag: list[str]) -> None:
    monkeypatch.setattr(archive_cli, "locate_project_root", lambda: tmp_path)
    monkeypatch.setattr(archive_cli, "primary_mission_dir", lambda _root, _mission: tmp_path / "absent")

    result = CliRunner().invoke(archive_cli.app, ["reclaim", _SLUG, *json_flag])

    assert result.exit_code == 2 and "not" in result.output.lower()


@pytest.mark.parametrize("json_flag", [[], ["--json"]])
def test_cli_reports_an_ambiguous_selector(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, json_flag: list[str]) -> None:
    from specify_cli.missions._read_path_resolver import MissionSelectorAmbiguous

    def ambiguous(_root: Path, mission: str) -> Path:
        raise MissionSelectorAmbiguous(handle=mission, candidates=["a", "b"])

    monkeypatch.setattr(archive_cli, "locate_project_root", lambda: tmp_path)
    monkeypatch.setattr(archive_cli, "primary_mission_dir", ambiguous)

    result = CliRunner().invoke(archive_cli.app, ["reclaim", "demo", *json_flag])

    assert result.exit_code == 1


@pytest.mark.parametrize("holds", [True, False])
def test_archive_create_points_at_reclaim_only_while_the_marker_remains(cli: CliRunner, monkeypatch: pytest.MonkeyPatch, holds: bool) -> None:
    from specify_cli.missions._archive import ArchivedMission, ArchiveOutcome

    record = ArchivedMission(
        mission_id="01ABCDEF" + "0" * 18, archived_by="t", archived_at="2026-11-12T00:00:00+00:00", reason="done", terminal_state_at_archive="merged"
    )
    monkeypatch.setattr(archive_cli, "archive_mission", lambda **_kwargs: ArchiveOutcome(record=record, cleared_deferrals=[]))
    monkeypatch.setattr(archive_cli, "holds_coordination_marker", lambda _root, _slug: holds)

    result = cli.invoke(archive_cli.app, ["create", _SLUG, "--by", "t", "--reason", "done"])

    assert result.exit_code == 0, result.output
    assert (f"spec-kitty archive reclaim {_SLUG}" in result.output) is holds


@pytest.mark.parametrize("holds", [True, False])
def test_archive_create_json_carries_the_reclaim_command_while_the_marker_remains(cli: CliRunner, monkeypatch: pytest.MonkeyPatch, holds: bool) -> None:
    """#7598 fold (NIT-9): the JSON record carries the reclaim hint the text output prints (null when none)."""
    from specify_cli.missions._archive import ArchivedMission, ArchiveOutcome

    record = ArchivedMission(
        mission_id="01ABCDEF" + "0" * 18, archived_by="t", archived_at="2026-11-12T00:00:00+00:00", reason="done", terminal_state_at_archive="merged"
    )
    monkeypatch.setattr(archive_cli, "archive_mission", lambda **_kwargs: ArchiveOutcome(record=record, cleared_deferrals=[]))
    monkeypatch.setattr(archive_cli, "holds_coordination_marker", lambda _root, _slug: holds)

    result = cli.invoke(archive_cli.app, ["create", _SLUG, "--by", "t", "--reason", "done", "--json"])

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["reclaim_command"] == (f"spec-kitty archive reclaim {_SLUG}" if holds else None)


def test_late_commits_are_named_as_unreachable_from_the_recorded_landing(tmp_path: Path, seams: dict[str, Any], monkeypatch: pytest.MonkeyPatch) -> None:
    """#7598 fold (NIT-9): a rewritten branch's commits are not "made after" the landing; say what is proved."""
    _coord_meta(tmp_path)
    monkeypatch.setattr(reclaim, "landed_coordination_tip", lambda _root, _branch: _LANDED)
    monkeypatch.setattr(reclaim, "commits_in_range", lambda _root, _base, _tip: ["c" * 40])

    text = str(_refusal(tmp_path))

    assert f"not reachable from the recorded landing ({_LANDED[:12]})" in text and "made after" not in text


def test_cli_renders_nothing_left_and_a_refusal_as_text(cli: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(archive_cli, "reclaim_archived_mission", lambda _root, _slug: _report(True))
    assert "Nothing left to reclaim" in cli.invoke(archive_cli.app, ["reclaim", _SLUG]).output

    def refuse(_root: Path, _slug: str) -> ReclaimReport:
        raise ReclaimRefused(reclaim.RECLAIM_NOT_ARCHIVED, "not archived [yet]", "archive it")

    monkeypatch.setattr(archive_cli, "reclaim_archived_mission", refuse)
    result = cli.invoke(archive_cli.app, ["reclaim", _SLUG])

    assert result.exit_code == 1
    assert "not archived [yet]" in result.output and f"Error code: {reclaim.RECLAIM_NOT_ARCHIVED}." in result.output


def test_preflight_validates_the_bookkeeping_destination(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    feature_dir = _coord_meta(tmp_path)
    seen: dict[str, Any] = {}
    monkeypatch.setattr(reclaim, "preflight_merge_bookkeeping", lambda **kwargs: seen.update(kwargs))

    reclaim._preflight_marker_commit(tmp_path, feature_dir, _SLUG)

    assert seen["branch"] == "main" and seen["mission_slug"] == _SLUG
    assert seen["paths"] == (feature_dir / "meta.json",) and seen["worktree_root"] == tmp_path


def test_any_other_commit_precondition_refuses_before_any_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.git.commit_helpers import SafeCommitError

    feature_dir = _coord_meta(tmp_path)

    def protected(*_args: object, **_kwargs: object) -> None:
        raise SafeCommitError("protected branch")

    monkeypatch.setattr(reclaim, "_preflight_marker_commit", protected)

    with pytest.raises(ReclaimRefused) as excinfo:
        reclaim._require_committable(tmp_path, feature_dir, _SLUG)

    assert excinfo.value.error_code == reclaim.RECLAIM_NOT_ON_TARGET and "nothing was changed" in str(excinfo.value)
