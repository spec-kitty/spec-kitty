"""The durable auto-rebase record (FR-005, NFR-002, ``contracts/auto-rebase-record.md``).

Every merge the stale-lane auto-rebase makes on a lane leaves
``refs/spec-kitty/auto-rebase/<lane-branch>/<merge-sha> -> <merge-sha>``. These tests pin:

* the writer (``attempt_auto_rebase``) records clean and auto-resolved merges, with the exact SHA,
  and records nothing when it halts or has nothing to merge;
* a record that cannot be written halts the auto-rebase and undoes the merge, lane-tip ref included;
* the reader answers only for that exact SHA under that lane, is not fooled by a commit message or
  by the tool's parent shape, and raises (never answers) when git cannot be read;
* lane cleanup deletes a lane's records exactly when it deletes the lane branch.

The writer tests read refs with plain git, so they do not depend on the module under test.
Real repositories; the process probe is injected.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from specify_cli.lanes.auto_rebase import AutoRebaseReport, attempt_auto_rebase
from specify_cli.lanes.models import ExecutionLane

pytestmark = pytest.mark.git_repo

_PREFIX = "refs/spec-kitty/auto-rebase/"
_LANE_TIP_PREFIX = "refs/spec-kitty/lane-tip/"
_MISSION = "kitty/mission-x-01ABCDEF"
_LANE = "kitty/mission-x-01ABCDEF-lane-a"
_OTHER_LANE = "kitty/mission-x-01ABCDEF-lane-b"


# --- helpers -----------------------------------------------------------------------------------


def _git(cwd: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=False)
    assert result.returncode == 0, f"git {' '.join(args)}: {result.stderr}"
    return result.stdout.strip()


def _commit(cwd: Path, name: str, content: str, message: str | None = None) -> str:
    (cwd / name).write_text(content, encoding="utf-8")
    _git(cwd, "add", name)
    _git(cwd, "commit", "-q", "-m", message or f"edit {name}")
    return _git(cwd, "rev-parse", "HEAD")


def _refs_under(repo: Path, prefix: str) -> list[str]:
    listing = _git(repo, "for-each-ref", "--format=%(refname)", prefix)
    return [line for line in listing.splitlines() if line]


def _parents(repo: Path, sha: str) -> list[str]:
    return _git(repo, "rev-list", "--parents", "-n1", sha).split()[1:]


def _ref_value(repo: Path, ref: str) -> str | None:
    result = subprocess.run(["git", "rev-parse", "--verify", "--quiet", ref], cwd=repo, capture_output=True, text=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def _pyproject(deps: list[str]) -> str:
    return '[project]\nname = "demo"\ndependencies = [\n' + "".join(f'  "{dep}",\n' for dep in deps) + "]\n"


def _lane() -> ExecutionLane:
    return ExecutionLane(
        lane_id="lane-a",
        wp_ids=("WP01",),
        write_scope=("lane.py",),
        predicted_surfaces=(),
        depends_on_lanes=(),
        parallel_group=0,
    )


def _init_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q", "-b", "main")
    for key, value in (("user.email", "t@example.invalid"), ("user.name", "T"), ("commit.gpgsign", "false")):
        _git(root, "config", key, value)
    (root / ".gitignore").write_text(".worktrees/\n", encoding="utf-8")
    (root / "pyproject.toml").write_text(_pyproject(["alpha", "bravo"]), encoding="utf-8")
    (root / "shared.py").write_text("value = 0\n", encoding="utf-8")
    _git(root, "add", ".gitignore", "pyproject.toml", "shared.py")
    _git(root, "commit", "-q", "-m", "seed")
    _git(root, "branch", _MISSION)
    return root


def _lane_worktree(root: Path, branch: str = _LANE, start: str = "main") -> Path:
    worktree = root / ".worktrees" / branch.replace("/", "_")
    worktree.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "worktree", "add", "-q", "-b", branch, str(worktree), start)
    return worktree


def _advance_mission(root: Path, name: str, content: str) -> str:
    _git(root, "checkout", "-q", _MISSION)
    sha = _commit(root, name, content, f"mission: {name}")
    _git(root, "checkout", "-q", "main")
    return sha


def _clean_shape(tmp_path: Path) -> tuple[Path, Path]:
    """The Mission branch and the lane edit different files: the merge is clean."""
    root = _init_repo(tmp_path)
    worktree = _lane_worktree(root)
    _commit(worktree, "lane.py", "y = 2\n", "lane work")
    _advance_mission(root, "other.py", "z = 3\n")
    return root, worktree


def _auto_resolved_shape(tmp_path: Path) -> tuple[Path, Path]:
    """Both add a dependency to ``pyproject.toml``: the merge conflicts and the additive rule resolves it."""
    root = _init_repo(tmp_path)
    worktree = _lane_worktree(root)
    _commit(worktree, "pyproject.toml", _pyproject(["alpha", "bravo", "delta"]), "lane: add delta")
    _advance_mission(root, "pyproject.toml", _pyproject(["alpha", "bravo", "charlie"]))
    return root, worktree


def _manual_shape(tmp_path: Path) -> tuple[Path, Path]:
    """Two different edits of the same line in a ``.py`` file: a Manual conflict halts."""
    root = _init_repo(tmp_path)
    worktree = _lane_worktree(root)
    _commit(worktree, "shared.py", "value = 1\n", "lane: value 1")
    _advance_mission(root, "shared.py", "value = 2\n")
    return root, worktree


_SHAPES = {"clean": _clean_shape, "auto_resolved": _auto_resolved_shape}


def _rebase(root: Path, worktree: Path) -> AutoRebaseReport:
    return attempt_auto_rebase(lane=_lane(), branch=_LANE, mission_branch=_MISSION, repo_root=root, worktree_path=worktree)


# --- T006: the writer --------------------------------------------------------------------------


def _assert_recorded_tool_merge(root: Path, worktree: Path, before: str, mission_before: str) -> str:
    head = _git(worktree, "rev-parse", "HEAD")
    assert _parents(root, head) == [before, mission_before]
    assert _ref_value(root, f"{_PREFIX}{_LANE}/{head}") == head
    assert _refs_under(root, _PREFIX) == [f"{_PREFIX}{_LANE}/{head}"]
    return head


def test_clean_auto_rebase_records_the_merge(tmp_path: Path) -> None:
    root, worktree = _clean_shape(tmp_path)
    before, mission_before = _git(worktree, "rev-parse", "HEAD"), _git(root, "rev-parse", _MISSION)
    report = _rebase(root, worktree)
    assert report.succeeded, report.halt_reason
    assert not report.classifications, "fixture invalid: the merge must have been clean"
    _assert_recorded_tool_merge(root, worktree, before, mission_before)


def test_auto_resolved_auto_rebase_records_the_merge(tmp_path: Path) -> None:
    root, worktree = _auto_resolved_shape(tmp_path)
    before, mission_before = _git(worktree, "rev-parse", "HEAD"), _git(root, "rev-parse", _MISSION)
    report = _rebase(root, worktree)
    assert report.succeeded, report.halt_reason
    assert report.classifications, "fixture invalid: the merge must have been auto-resolved"
    _assert_recorded_tool_merge(root, worktree, before, mission_before)


@pytest.mark.parametrize("shape", ["clean", "auto_resolved"])
def test_report_names_the_merge_sha(tmp_path: Path, shape: str) -> None:
    root, worktree = _SHAPES[shape](tmp_path)
    report = _rebase(root, worktree)
    assert report.merge_sha == _git(worktree, "rev-parse", "HEAD")


def test_halted_report_names_no_merge(tmp_path: Path) -> None:
    root, worktree = _manual_shape(tmp_path)
    report = _rebase(root, worktree)
    assert report.succeeded is False
    assert report.merge_sha is None


def test_halted_auto_rebase_records_nothing(tmp_path: Path) -> None:
    """Control (green before FR-005): a Manual conflict halts and no record exists."""
    root, worktree = _manual_shape(tmp_path)
    before = _git(worktree, "rev-parse", "HEAD")
    report = _rebase(root, worktree)
    assert report.succeeded is False
    assert _git(worktree, "rev-parse", "HEAD") == before
    assert _refs_under(root, _PREFIX) == []


def test_already_up_to_date_records_nothing(tmp_path: Path) -> None:
    """Control (green before FR-005): the lane already contains the Mission tip; no merge, no record."""
    root = _init_repo(tmp_path)
    _advance_mission(root, "other.py", "z = 3\n")
    worktree = _lane_worktree(root, start=_MISSION)
    before = _commit(worktree, "lane.py", "y = 2\n", "lane work")
    report = _rebase(root, worktree)
    assert report.succeeded, report.halt_reason
    assert _git(worktree, "rev-parse", "HEAD") == before
    assert _refs_under(root, _PREFIX) == []


@pytest.mark.parametrize("shape", ["clean", "auto_resolved"])
def test_record_write_failure_halts_and_leaves_no_unrecorded_merge(tmp_path: Path, shape: str, monkeypatch: pytest.MonkeyPatch) -> None:
    root, worktree = _SHAPES[shape](tmp_path)
    before = _git(worktree, "rev-parse", "HEAD")
    _git(root, "update-ref", f"{_LANE_TIP_PREFIX}{_LANE}", before)

    def _refuse(repo_root: Path, lane_branch: str, merge_sha: str) -> bool:
        # What the POSIX post-commit recorder hook does on the merge commit: the tip ref names it.
        _git(repo_root, "update-ref", f"{_LANE_TIP_PREFIX}{lane_branch}", merge_sha)
        return False

    monkeypatch.setattr("specify_cli.lanes.auto_rebase_record.record", _refuse)

    report = _rebase(root, worktree)

    assert report.succeeded is False
    assert report.halt_reason is not None and "auto-rebase record could not be written" in report.halt_reason
    assert "the merge was undone" in report.halt_reason
    assert report.merge_sha is None
    assert _git(worktree, "rev-parse", "HEAD") == before
    assert _git(worktree, "status", "--porcelain") == ""
    assert _refs_under(root, _PREFIX) == []
    assert _ref_value(root, f"{_LANE_TIP_PREFIX}{_LANE}") == before


def test_two_auto_rebases_of_one_lane_leave_two_records(tmp_path: Path) -> None:
    root, worktree = _clean_shape(tmp_path)
    first = _rebase(root, worktree)
    _advance_mission(root, "later.py", "w = 4\n")
    second = _rebase(root, worktree)

    assert first.succeeded and second.succeeded
    assert first.merge_sha and second.merge_sha and first.merge_sha != second.merge_sha
    expected = sorted(f"{_PREFIX}{_LANE}/{sha}" for sha in (first.merge_sha, second.merge_sha))
    assert sorted(_refs_under(root, _PREFIX)) == expected
    for sha in (first.merge_sha, second.merge_sha):
        assert _ref_value(root, f"{_PREFIX}{_LANE}/{sha}") == sha


# --- T006: the reader --------------------------------------------------------------------------


def test_is_recorded_only_for_the_exact_sha_and_lane(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase_record

    root, worktree = _clean_shape(tmp_path)
    report = _rebase(root, worktree)
    merge = report.merge_sha
    assert merge is not None
    other_sha = _git(root, "rev-parse", "main")

    assert auto_rebase_record.is_recorded(root, _LANE, merge) is True
    assert auto_rebase_record.is_recorded(root, _OTHER_LANE, merge) is False
    assert auto_rebase_record.is_recorded(root, _LANE, other_sha) is False
    assert auto_rebase_record.recorded_merges(root, _LANE) == frozenset({merge})
    assert auto_rebase_record.recorded_merges(root, _OTHER_LANE) == frozenset()


def test_forged_message_merge_is_not_recorded(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase_record

    root, worktree = _clean_shape(tmp_path)
    forged = "auto-rebase(lane=lane-a): 0 conflicts resolved by classifier rules []"
    _git(worktree, "merge", "-q", "--no-ff", "-m", forged, _MISSION)
    head = _git(worktree, "rev-parse", "HEAD")

    assert auto_rebase_record.is_recorded(root, _LANE, head) is False


def test_hand_merge_of_the_mission_branch_is_not_recorded(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase_record

    root, worktree = _clean_shape(tmp_path)
    before = _git(worktree, "rev-parse", "HEAD")
    mission_before = _git(root, "rev-parse", _MISSION)
    _git(worktree, "merge", "-q", "--no-ff", "--no-edit", _MISSION)
    head = _git(worktree, "rev-parse", "HEAD")

    assert _parents(root, head) == [before, mission_before], "fixture invalid: the hand merge must have the tool's parent shape"
    assert auto_rebase_record.is_recorded(root, _LANE, head) is False


def test_is_recorded_raises_on_git_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes import auto_rebase_record

    nowhere = tmp_path / "not-a-repo"
    nowhere.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    with pytest.raises(auto_rebase_record.AutoRebaseRecordError):
        auto_rebase_record.is_recorded(nowhere, _LANE, "a" * 40)
    with pytest.raises(auto_rebase_record.AutoRebaseRecordError):
        auto_rebase_record.recorded_merges(nowhere, _LANE)


def test_is_recorded_raises_on_a_record_naming_another_commit(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase_record

    root = _init_repo(tmp_path)
    main = _git(root, "rev-parse", "main")
    other = "b" * 40
    _git(root, "update-ref", f"{_PREFIX}{_LANE}/{other}", main)
    with pytest.raises(auto_rebase_record.AutoRebaseRecordError):
        auto_rebase_record.is_recorded(root, _LANE, other)


def test_record_is_idempotent_and_delete_is_a_no_op_when_absent(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase_record

    root = _init_repo(tmp_path)
    sha = _git(root, "rev-parse", "main")
    assert auto_rebase_record.record(root, _LANE, sha) is True
    assert auto_rebase_record.record(root, _LANE, sha) is True
    assert auto_rebase_record._record_ref(_LANE, sha) == f"{_PREFIX}{_LANE}/{sha}"
    assert auto_rebase_record.delete(root, _LANE, sha) is True
    assert auto_rebase_record.delete(root, _LANE, sha) is True
    assert _refs_under(root, _PREFIX) == []


def test_record_fails_when_the_ref_holds_another_value(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase_record

    root = _init_repo(tmp_path)
    sha = _git(root, "rev-parse", "main")
    seed_parent = _commit(root, "extra.py", "e = 1\n")
    _git(root, "update-ref", f"{_PREFIX}{_LANE}/{sha}", seed_parent)
    assert auto_rebase_record.record(root, _LANE, sha) is False


@pytest.mark.parametrize(("branch", "sha"), [("", "a" * 40), (_LANE, "abc"), (_LANE, "A" * 40), (_LANE, "g" * 40)])
def test_invalid_inputs_raise_before_any_git_call(tmp_path: Path, branch: str, sha: str) -> None:
    from specify_cli.lanes import auto_rebase_record

    for call in (auto_rebase_record.record, auto_rebase_record.is_recorded, auto_rebase_record.delete):
        with pytest.raises(ValueError, match="an auto-rebase record needs"):
            call(tmp_path, branch, sha)


def test_recorded_merges_ignores_a_nested_lane_s_records(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase_record

    root = _init_repo(tmp_path)
    sha = _git(root, "rev-parse", "main")
    assert auto_rebase_record.record(root, f"{_LANE}/nested", sha)
    assert auto_rebase_record.recorded_merges(root, _LANE) == frozenset()
    assert auto_rebase_record.recorded_merges(root, f"{_LANE}/nested") == frozenset({sha})


# --- T009: lane cleanup ------------------------------------------------------------------------


def _idle(_paths: object):  # the process probe: nothing stands in any worktree
    from specify_cli.workspace.process_probe import ProcessProbeResult

    return ProcessProbeResult(available=True)


def _two_lanes_with_records(tmp_path: Path) -> tuple[Path, list[str]]:
    """lane-a and lane-b at ``main``; lane-a holds two records, lane-b one."""
    from specify_cli.lanes import auto_rebase_record

    root = _init_repo(tmp_path)
    seed = _git(root, "rev-parse", "main")
    second = _commit(root, "more.py", "m = 1\n")
    for branch in (_LANE, _OTHER_LANE):
        _git(root, "branch", branch, "main")
    assert auto_rebase_record.record(root, _LANE, seed) and auto_rebase_record.record(root, _LANE, second)
    assert auto_rebase_record.record(root, _OTHER_LANE, second)
    return root, [seed, second]


def _main_today(root: Path):
    from specify_cli.consolidation.lane_cleanup import MainTodayRemover
    from specify_cli.coordination.coherence import NothingIsResidue

    return MainTodayRemover(root, context=NothingIsResidue(), probe=_idle)


def _branch_item(branch: str = _LANE, expected_tip: str | None = None):
    from specify_cli.consolidation.lane_cleanup import LaneCleanupItem

    return LaneCleanupItem(lane_id="lane-a", worktree=None, branch=branch, expected_tip=expected_tip)


def test_cleanup_removes_the_lane_s_records(tmp_path: Path) -> None:
    from specify_cli.consolidation.lane_cleanup import LaneCleanupOutcome

    root, (_seed, second) = _two_lanes_with_records(tmp_path)

    result = _main_today(root).remove(_branch_item(), landing=None)

    assert result.outcome is LaneCleanupOutcome.REMOVED, result
    assert _refs_under(root, f"{_PREFIX}{_LANE}/") == []
    assert _refs_under(root, _PREFIX) == [f"{_PREFIX}{_OTHER_LANE}/{second}"]


def test_guarded_cleanup_removes_the_lane_s_records(tmp_path: Path) -> None:
    from specify_cli.consolidation.lane_cleanup import GuardedLaneRemover, LaneCleanupItem, LaneCleanupOutcome, LocalTargetAtPass
    from specify_cli.coordination.coherence import NothingIsResidue

    root, worktree = _clean_shape(tmp_path)
    report = _rebase(root, worktree)
    assert report.succeeded and report.merge_sha
    assert _refs_under(root, _PREFIX) == [f"{_PREFIX}{_LANE}/{report.merge_sha}"]
    _git(root, "checkout", "-q", _MISSION)
    _git(root, "merge", "-q", "--no-ff", "-m", "consolidate lane-a", _LANE)
    _git(root, "checkout", "-q", "main")
    _git(root, "merge", "-q", "--no-ff", "-m", "land mission", _MISSION)
    landing = LocalTargetAtPass(target_ref="main", passed_sha=_git(root, "rev-parse", "main"))
    item = LaneCleanupItem(lane_id="lane-a", worktree=worktree, branch=_LANE, expected_tip=report.merge_sha)

    result = GuardedLaneRemover(root, context=NothingIsResidue(), probe=_idle).remove(item, landing=landing)

    assert result.outcome is LaneCleanupOutcome.REMOVED, result
    assert _git(root, "branch", "--list", _LANE) == ""
    assert _refs_under(root, _PREFIX) == []


def test_a_kept_lane_keeps_its_records(tmp_path: Path) -> None:
    from specify_cli.consolidation.lane_cleanup import LaneCleanupOutcome

    root, _shas = _two_lanes_with_records(tmp_path)
    _git(root, "checkout", "-q", _LANE)
    _commit(root, "unlanded.py", "u = 1\n")
    _git(root, "checkout", "-q", "main")
    before = _refs_under(root, _PREFIX)

    result = _main_today(root).remove(_branch_item(), landing=None)

    assert result.outcome is LaneCleanupOutcome.KEPT and result.code == "BRANCH_HAS_UNIQUE_COMMITS"
    assert _refs_under(root, _PREFIX) == before


def test_a_missing_branch_keeps_its_records(tmp_path: Path) -> None:
    from specify_cli.consolidation.lane_cleanup import LaneCleanupOutcome

    root, _shas = _two_lanes_with_records(tmp_path)
    _git(root, "branch", "-D", _LANE)
    before = _refs_under(root, _PREFIX)

    result = _main_today(root).remove(_branch_item(), landing=None)

    assert result.outcome is LaneCleanupOutcome.REMOVED
    assert _refs_under(root, _PREFIX) == before, "FR-034 parity: the records stay with a branch cleanup did not delete"


def test_cleanup_logs_records_it_could_not_list_or_delete(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    from specify_cli.consolidation import lane_cleanup
    from specify_cli.lanes import auto_rebase_record

    def _unlistable(_root: Path, _branch: str) -> tuple[str, ...]:
        raise auto_rebase_record.AutoRebaseRecordError("listing failed")

    caplog.set_level("DEBUG", logger=lane_cleanup.__name__)
    monkeypatch.setattr(auto_rebase_record, "delete_for_lane", _unlistable)
    lane_cleanup._clear_lane_records(tmp_path, _LANE)
    monkeypatch.setattr(auto_rebase_record, "delete_for_lane", lambda _root, _branch: (f"{_PREFIX}{_LANE}/{'c' * 40}",))
    lane_cleanup._clear_lane_records(tmp_path, _LANE)

    assert "could not be listed: listing failed" in caplog.text
    assert f"{_PREFIX}{_LANE}/{'c' * 40}" in caplog.text


# --- writer failure branches -------------------------------------------------------------------


def test_unreadable_pre_merge_tips_are_a_halt_reason(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes.auto_rebase import _PreMergeTips, _read_pre_merge_tips

    root, worktree = _clean_shape(tmp_path)
    tips = _read_pre_merge_tips(worktree, _MISSION)
    assert tips == _PreMergeTips(_git(worktree, "rev-parse", "HEAD"), _git(root, "rev-parse", _MISSION))
    missing = _read_pre_merge_tips(worktree, "kitty/no-such-branch")
    assert isinstance(missing, str) and missing.startswith("could not read the tip of kitty/no-such-branch")
    nowhere = tmp_path / "not-a-repo"
    nowhere.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    unreadable = _read_pre_merge_tips(nowhere, _MISSION)
    assert isinstance(unreadable, str) and unreadable.startswith("could not read the lane tip")


def test_a_refused_undo_leaves_the_merge_and_says_so(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.git.destructive_guard import DestructiveOpRefused
    from specify_cli.lanes import auto_rebase

    root, worktree = _clean_shape(tmp_path)
    before = _git(worktree, "rev-parse", "HEAD")

    def _refuse_reset(*_args: object, **_kwargs: object) -> None:
        raise DestructiveOpRefused(error_code="MERGE_UNSAFE_WORKTREE_DIRTY", current_branch=_LANE, remediation="commit it first")

    monkeypatch.setattr("specify_cli.lanes.auto_rebase_record.record", lambda *_args: False)
    monkeypatch.setattr(auto_rebase, "guarded_reset_hard", _refuse_reset)

    report = _rebase(root, worktree)

    head = _git(worktree, "rev-parse", "HEAD")
    assert report.succeeded is False and head != before
    assert report.halt_reason is not None
    assert f"merge {head[:12]} was left on the lane unrecorded" in report.halt_reason
    assert "commit it first" in report.halt_reason and "hand merge" in report.halt_reason
    assert _refs_under(root, _PREFIX) == []


def test_a_head_that_is_not_the_tool_merge_is_not_recorded(tmp_path: Path) -> None:
    from specify_cli.coordination.coherence import NothingIsResidue
    from specify_cli.lanes.auto_rebase import AutoRebaseReport as Report
    from specify_cli.lanes.auto_rebase import _PreMergeTips, _record_tool_merge

    root, worktree = _clean_shape(tmp_path)
    before = _git(worktree, "rev-parse", "HEAD")
    _commit(worktree, "late.py", "w = 4\n")  # a plain commit, not a merge of the Mission branch
    tips = _PreMergeTips(before=before, mission_before=_git(root, "rev-parse", _MISSION))

    outcome = _record_tool_merge(NothingIsResidue(), worktree, root, "lane-a", _LANE, tips, [], _git(worktree, "rev-parse", "HEAD^{tree}"))

    assert isinstance(outcome, Report) and outcome.succeeded is False
    assert outcome.halt_reason is not None and "left on the lane unrecorded" in outcome.halt_reason
    assert _refs_under(root, _PREFIX) == []


def test_an_unreadable_head_is_not_recorded(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.coordination.coherence import NothingIsResidue
    from specify_cli.lanes.auto_rebase import AutoRebaseReport as Report
    from specify_cli.lanes.auto_rebase import _PreMergeTips, _record_tool_merge

    nowhere = tmp_path / "not-a-repo"
    nowhere.mkdir()
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path))
    outcome = _record_tool_merge(NothingIsResidue(), nowhere, nowhere, "lane-a", _LANE, _PreMergeTips("a" * 40, "b" * 40), [], "c" * 40)
    assert isinstance(outcome, Report) and outcome.halt_reason is not None
    assert "could not read the lane tip after the auto-rebase merge" in outcome.halt_reason


def test_attempt_halts_without_merging_when_a_pre_merge_tip_is_unreadable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes import auto_rebase

    root, worktree = _clean_shape(tmp_path)
    before = _git(worktree, "rev-parse", "HEAD")
    monkeypatch.setattr(auto_rebase, "_read_pre_merge_tips", lambda *_args: "could not read the lane tip before the auto-rebase merge: boom")

    report = _rebase(root, worktree)

    assert report.succeeded is False and report.halt_reason == "could not read the lane tip before the auto-rebase merge: boom"
    assert _git(worktree, "rev-parse", "HEAD") == before
    assert _git(worktree, "status", "--porcelain") == ""


# --- the record is bound to the tree the tool staged (review cycle 1, must-fix 2) --------------


def _install_staging_pre_commit_hook(root: Path) -> None:
    """A repository ``pre-commit`` hook that stages a file of its own into every commit."""
    hooks = root / ".git" / "custom-hooks"
    hooks.mkdir()
    hook = hooks / "pre-commit"
    hook.write_text("#!/bin/sh\necho injected > injected-by-hook.txt\ngit add injected-by-hook.txt\n", encoding="utf-8")
    hook.chmod(0o755)
    _git(root, "config", "core.hooksPath", str(hooks))


@pytest.mark.parametrize("shape", ["clean", "auto_resolved"])
def test_a_hook_altered_merge_tree_is_undone_and_not_recorded(tmp_path: Path, shape: str) -> None:
    root, worktree = _SHAPES[shape](tmp_path)
    before = _git(worktree, "rev-parse", "HEAD")
    _install_staging_pre_commit_hook(root)

    report = _rebase(root, worktree)

    assert report.succeeded is False
    assert report.halt_reason is not None and "pre-commit hook" in report.halt_reason
    assert "the merge was undone" in report.halt_reason
    assert report.merge_sha is None
    assert _git(worktree, "rev-parse", "HEAD") == before
    assert not (worktree / "injected-by-hook.txt").exists()
    assert _refs_under(root, _PREFIX) == []


@pytest.mark.parametrize("shape", ["clean", "auto_resolved"])
def test_an_unreadable_staged_tree_aborts_the_merge_before_any_commit(tmp_path: Path, shape: str, monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.lanes import auto_rebase

    root, worktree = _SHAPES[shape](tmp_path)
    before = _git(worktree, "rev-parse", "HEAD")
    monkeypatch.setattr(auto_rebase, "_staged_tree", lambda _worktree: None)

    report = _rebase(root, worktree)

    assert report.succeeded is False
    assert report.halt_reason is not None and report.halt_reason.startswith("could not read the staged merge tree")
    assert _git(worktree, "rev-parse", "HEAD") == before
    assert _refs_under(root, _PREFIX) == []


# --- one-read helpers (#5604, the #7689 spawn ceiling) ---------------------------------------


def test_head_commit_reads_id_tree_and_parents_in_one_raw_read(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase

    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t.co")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    base = _commit(repo, "a.txt", "a\n")
    _git(repo, "checkout", "-q", "-b", "side")
    side = _commit(repo, "b.txt", "b\n")
    _git(repo, "checkout", "-q", "main")
    main = _commit(repo, "c.txt", "c\n")
    _git(repo, "merge", "-q", "--no-edit", "side")
    head = _git(repo, "rev-parse", "HEAD")
    _git(repo, "config", "log.showSignature", "true")  # porcelain would print here; plumbing does not
    assert auto_rebase._head_commit(repo) == (head, _git(repo, "rev-parse", "HEAD^{tree}"), (main, side))
    assert base != head


def test_head_commit_of_an_unborn_branch_is_unreadable(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase

    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    assert auto_rebase._head_commit(repo) == ("", "", ())


def test_pre_merge_tips_are_read_together_and_a_missing_one_halts(tmp_path: Path) -> None:
    from specify_cli.lanes import auto_rebase

    repo = tmp_path / "r"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "t@t.co")
    _git(repo, "config", "user.name", "T")
    _git(repo, "config", "commit.gpgsign", "false")
    tip = _commit(repo, "a.txt", "a\n")
    _git(repo, "branch", "mission")
    assert auto_rebase._read_pre_merge_tips(repo, "mission") == auto_rebase._PreMergeTips(before=tip, mission_before=tip)
    halted = auto_rebase._read_pre_merge_tips(repo, "nope")
    assert isinstance(halted, str) and halted.startswith("could not read the tip of nope before the auto-rebase merge")
