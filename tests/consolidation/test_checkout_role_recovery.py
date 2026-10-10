"""The behind-own-HEAD lag seam covers every worktree a consolidation advances (#5613).

Upstream (#5571 / #5605) proves and recovers a lag for the repository root and the
coordination worktree (``tests/consolidation/test_resume_coord_lag.py``). These tests
cover what #5613 adds on the same seam:

* a mission worktree and a lane worktree are lag candidates, each proven against its
  own branch's entry in the pre-mutation snapshot (``pre_mutation_refs``);
* a ``--resume`` preflight inspects every worktree on the mission branch up front;
* guidance for a lagging or lock-blocked checkout never keeps the generic "Commit" line;
* a lag that carries an operator edit gets runnable save-the-edit-first advice, and
  running the printed commands keeps both the edit and the lane files.

Real git repositories throughout: the ancestry and diff probes must run for real.
Fixture shape: ``base`` on ``main``; a linked worktree on ``branch``; ``branch`` is
advanced to add ``lane.py`` with ``update-ref`` while the worktree keeps ``base``'s tree.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NamedTuple
from unittest.mock import patch

import pytest
import typer

from kernel.git_topology import GitTopologyUnavailableError
from specify_cli.consolidation import entry_preflight
from specify_cli.consolidation import preflight as pf
from specify_cli.consolidation import resume_recovery
from specify_cli.consolidation.state import ConsolidationState, save_state
from specify_cli.git import ref_advance
from specify_cli.git.destructive_guard import MERGE_UNSAFE_PRIMARY_DIRTY, MERGE_UNSAFE_WORKTREE_DIRTY, DestructiveOpRefused
from tests.consolidation.executor_family import patch_executor_family

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_MISSION_ID = "01M5613UNITLAGTESTMISSION1"
_MISSION_BRANCH = "kitty/mission-m"
_LANE_BRANCH = "kitty/mission-m-lane-a"
_COMMIT_ADVICE = "Commit, stash, or revert"
_DO_NOT_RECORD = "Do NOT stage or record"
#: Any advice to "Commit" (capitalised, as the stock remedy spells it).
_ADVISES_COMMIT = re.compile(r"\bCommit\b")

BRANCHES = pytest.mark.parametrize("branch, label", [(_MISSION_BRANCH, "mission worktree"), (_LANE_BRANCH, "lane worktree")])


class _Lag(NamedTuple):
    repo: Path
    worktree: Path
    branch: str
    base: str
    advanced: str


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout.strip()


def _build_lag(tmp_path: Path, branch: str = _MISSION_BRANCH) -> _Lag:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    _git(repo, "add", "alpha.txt")
    _git(repo, "commit", "-qm", "base")
    base = _git(repo, "rev-parse", "HEAD")
    worktree = tmp_path / "wt"
    _git(repo, "worktree", "add", "-q", "-b", branch, str(worktree), base)
    (worktree / "lane.py").write_text("lane\n", encoding="utf-8")
    _git(worktree, "add", "lane.py")
    _git(worktree, "commit", "-qm", "lane work")
    advanced = _git(worktree, "rev-parse", "HEAD")
    # Interrupted window: ref at ``advanced``, worktree/index still ``base``'s tree.
    _git(worktree, "reset", "-q", "--hard", base)
    _git(repo, "update-ref", f"refs/heads/{branch}", advanced, base)
    return _Lag(repo=repo, worktree=worktree, branch=branch, base=base, advanced=advanced)


def _state(refs: dict[str, str]) -> ConsolidationState:
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug="m", target_branch="main", wp_order=["WP01"])
    state.pre_mutation_refs = refs
    return state


def _persist_state(lag: _Lag, refs: dict[str, str]) -> None:
    save_state(_state(refs), lag.repo)


def _no_lanes() -> Any:
    return SimpleNamespace(target_branch="main", mission_branch=_MISSION_BRANCH, lanes=[])


def _refusal(path: Path, code: str = MERGE_UNSAFE_WORKTREE_DIRTY) -> DestructiveOpRefused:
    return DestructiveOpRefused(
        error_code=code,
        remediation=f"{_COMMIT_ADVICE} the local changes in {path}, then resume.",
        worktree_path=path,
        dirty_entries=["D  lane.py"],
    )


def _recover(lag: _Lag) -> bool:
    return resume_recovery._recover_behind_head_primary_on_resume(_refusal(lag.worktree), lag.repo, _MISSION_ID, mission_branch=_MISSION_BRANCH)


def _report(lag: _Lag, capsys: pytest.CaptureFixture[str], *, base_sha: str | None) -> str:
    resume_recovery._report_pre_mutation_refusal(_refusal(lag.worktree), lag.repo, mission_branch=_MISSION_BRANCH, base_sha=base_sha)
    return capsys.readouterr().out


def _flat(text: str) -> str:
    return " ".join(text.split())


def _advised_commands(lines: list[str]) -> list[str]:
    """The shell commands the advice tells the operator to run, in order, exactly as given."""
    return ["git " + line.split(": git ", 1)[1] for line in lines if ": git " in line]


# --- which checkout a refusal names --------------------------------------------------------


@BRANCHES
def test_a_refused_worktree_maps_to_the_branch_it_has_checked_out(tmp_path: Path, branch: str, label: str) -> None:
    lag = _build_lag(tmp_path, branch)

    checkout = resume_recovery._lag_checkout_for_refusal(_refusal(lag.worktree), lag.repo, None, mission_branch=_MISSION_BRANCH)

    assert checkout == resume_recovery._LagCheckout(lag.worktree, coordination=False, branch=branch, lane=branch != _MISSION_BRANCH)
    assert checkout is not None and checkout.label == label and not checkout.is_root
    assert checkout.lane_branch(_MISSION_BRANCH) == branch


def test_the_root_and_the_coordination_worktree_classify_on_the_mission_branch(tmp_path: Path) -> None:
    root = resume_recovery._LagCheckout(tmp_path, coordination=False)
    coordination = resume_recovery._LagCheckout(tmp_path, coordination=True)

    assert root.is_root and not coordination.is_root
    assert root.lane_branch(_MISSION_BRANCH) == coordination.lane_branch(_MISSION_BRANCH) == _MISSION_BRANCH


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"coordination": True, "lane": True}, id="coordination-and-lane"),
        pytest.param({"coordination": True, "branch": _MISSION_BRANCH}, id="coordination-with-a-branch"),
        pytest.param({"coordination": False, "lane": True}, id="lane-without-a-branch"),
    ],
)
def test_a_checkout_cannot_claim_two_roles(tmp_path: Path, kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="anchored on"):
        resume_recovery._LagCheckout(tmp_path, **kwargs)


def test_a_worktree_with_no_branch_checked_out_is_no_candidate(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _git(lag.worktree, "checkout", "-q", "--detach")

    assert pf.checked_out_branch(lag.worktree) is None
    assert pf.checked_out_branch(tmp_path / "gone") is None
    assert resume_recovery._lag_checkout_for_refusal(_refusal(lag.worktree), lag.repo, None, mission_branch=_MISSION_BRANCH) is None
    assert resume_recovery._lag_checkout_for_refusal(_refusal(tmp_path / "gone"), lag.repo, None, mission_branch=_MISSION_BRANCH) is None


def test_checked_out_branch_names_the_branch(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)

    assert pf.checked_out_branch(lag.worktree) == _MISSION_BRANCH
    assert pf.checked_out_branch(lag.repo) == "main"


def test_each_checkout_is_anchored_on_its_own_persisted_tip(tmp_path: Path) -> None:
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug="m", target_branch="main", wp_order=["WP01"])
    state.pre_mutation_target_sha = "T" * 40
    state.pre_mutation_coord_sha = "C" * 40
    state.pre_mutation_refs = {_MISSION_BRANCH: "M" * 40}

    assert resume_recovery._LagCheckout(tmp_path, coordination=False, branch=_MISSION_BRANCH).base_sha(state) == "M" * 40
    assert resume_recovery._LagCheckout(tmp_path, coordination=False, branch=_LANE_BRANCH, lane=True).base_sha(state) is None, "not in the snapshot"
    assert resume_recovery._LagCheckout(tmp_path, coordination=False, branch=_MISSION_BRANCH).base_sha(None) is None


# --- in-place recovery on --resume ---------------------------------------------------------


@BRANCHES
def test_resume_refreshes_a_pure_lag_in_place(tmp_path: Path, branch: str, label: str) -> None:
    lag = _build_lag(tmp_path, branch)
    _persist_state(lag, {branch: lag.base})

    assert _recover(lag) is True

    assert (lag.worktree / "lane.py").read_text(encoding="utf-8") == "lane\n"
    assert _git(lag.worktree, "status", "--porcelain") == ""


@pytest.mark.parametrize("refs", [{}, {"some/other-branch": "0" * 40}])
def test_a_branch_absent_from_the_snapshot_is_never_reset(tmp_path: Path, refs: dict[str, str]) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, refs)

    assert _recover(lag) is False

    assert not (lag.worktree / "lane.py").exists()


def test_a_fresh_merge_never_refreshes_a_dirty_mission_worktree(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)  # no persisted state: not a --resume

    assert _recover(lag) is False

    assert not (lag.worktree / "lane.py").exists()


@BRANCHES
def test_a_genuine_edit_on_top_of_the_lag_is_never_reset(tmp_path: Path, branch: str, label: str) -> None:
    lag = _build_lag(tmp_path, branch)
    _persist_state(lag, {branch: lag.base})
    (lag.worktree / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    assert _recover(lag) is False

    assert (lag.worktree / "alpha.txt").read_text(encoding="utf-8") == "genuine edit\n"
    assert not (lag.worktree / "lane.py").exists()


def test_a_blocking_index_lock_is_not_recovered(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, {lag.branch: lag.base})
    Path(_git(lag.worktree, "rev-parse", "--path-format=absolute", "--git-path", "index.lock")).write_text("", encoding="utf-8")

    assert _recover(lag) is False

    assert not (lag.worktree / "lane.py").exists()


# --- the printed refusal -------------------------------------------------------------------


@BRANCHES
def test_a_pure_lag_prints_reset_guidance_and_no_commit_advice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, branch: str, label: str
) -> None:
    monkeypatch.setenv("COLUMNS", "4000")
    lag = _build_lag(tmp_path, branch)

    out = _flat(_report(lag, capsys, base_sha=lag.base))

    assert "Resume recovery guidance" in out and _DO_NOT_RECORD in out
    assert f"git -C {lag.worktree} reset --hard HEAD" in out
    assert "MERGE_UNSAFE_WORKTREE_DIRTY" in out and "D lane.py" in out, "the refusal still names its code and the dirty entries"
    assert not _ADVISES_COMMIT.search(out), out


@pytest.mark.parametrize("code, path_of", [(MERGE_UNSAFE_PRIMARY_DIRTY, "repo"), (MERGE_UNSAFE_WORKTREE_DIRTY, "worktree")])
def test_a_leftover_index_lock_names_the_lock_and_never_advises_commit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, code: str, path_of: str
) -> None:
    monkeypatch.setenv("COLUMNS", "4000")
    lag = _build_lag(tmp_path)
    checkout: Path = getattr(lag, path_of)
    lock = Path(_git(checkout, "rev-parse", "--path-format=absolute", "--git-path", "index.lock"))
    lock.write_text("", encoding="utf-8")

    resume_recovery._report_pre_mutation_refusal(_refusal(checkout, code), lag.repo, mission_branch=_MISSION_BRANCH, base_sha=None)
    out = _flat(capsys.readouterr().out)

    assert str(lock) in out and "index.lock" in out
    assert not _ADVISES_COMMIT.search(out), out


@BRANCHES
def test_a_lag_with_an_edit_prints_save_the_edit_first_advice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch, branch: str, label: str
) -> None:
    monkeypatch.setenv("COLUMNS", "4000")
    lag = _build_lag(tmp_path, branch)
    (lag.worktree / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    out = _flat(_report(lag, capsys, base_sha=lag.base))

    assert f"git -C {lag.worktree} reset --hard HEAD" in out
    assert _DO_NOT_RECORD in out and "Do NOT use git stash" in out
    assert not _ADVISES_COMMIT.search(out), out
    save = out.index("Save your own edits outside the worktree first")
    refresh = out.index("reset --hard HEAD")
    resume = out.index("spec-kitty consolidate --resume")
    assert save < refresh < resume < out.index("re-apply"), "save, refresh, resume, and only then re-apply"
    assert (lag.worktree / "alpha.txt").read_text(encoding="utf-8") == "genuine edit\n", "the report only prints"


def test_a_dirty_worktree_without_an_anchor_keeps_the_stock_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "4000")
    lag = _build_lag(tmp_path)
    (lag.worktree / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    out = _flat(_report(lag, capsys, base_sha=None))

    assert _COMMIT_ADVICE in out and _DO_NOT_RECORD not in out


def test_genuine_dirt_on_a_refreshed_worktree_keeps_the_stock_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "4000")
    lag = _build_lag(tmp_path)
    _git(lag.worktree, "reset", "-q", "--hard", "HEAD")  # refreshed: no lag left
    (lag.worktree / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    out = _flat(_report(lag, capsys, base_sha=lag.base))

    assert _COMMIT_ADVICE in out and _DO_NOT_RECORD not in out


def test_the_deferring_refusal_keeps_everything_but_the_remedy() -> None:
    original = DestructiveOpRefused(
        error_code=MERGE_UNSAFE_WORKTREE_DIRTY,
        remediation=f"{_COMMIT_ADVICE} it.",
        worktree_path=Path("/w"),
        current_branch="b",
        expected_branch="e",
        dirty_entries=["D x"],
    )

    deferred = resume_recovery._refusal_deferring_to_guidance(original)

    assert (deferred.error_code, deferred.worktree_path, deferred.current_branch, deferred.expected_branch, deferred.dirty_entries) == (
        original.error_code,
        original.worktree_path,
        original.current_branch,
        original.expected_branch,
        original.dirty_entries,
    )
    assert _COMMIT_ADVICE not in str(deferred) and "resume recovery guidance" in str(deferred)


# --- the advice itself, executed verbatim --------------------------------------------------


@pytest.mark.parametrize("stage_the_edit", [False, True])
def test_running_the_advised_commands_keeps_the_edit_and_the_lane_files(tmp_path: Path, stage_the_edit: bool) -> None:
    lag = _build_lag(tmp_path)
    (lag.worktree / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")
    if stage_the_edit:
        _git(lag.worktree, "add", "alpha.txt")
    # A binary edit: a plain ``git diff`` records only "Binary files differ", which ``git apply`` cannot restore.
    binary = bytes(range(256)) * 4
    (lag.worktree / "blob.bin").write_bytes(binary)
    _git(lag.worktree, "add", "blob.bin")

    lines = pf.lag_with_edit_guidance(lag.worktree, label="mission worktree", base_sha=lag.base)
    save, refresh, reapply = _advised_commands(lines)
    assert "alpha.txt" in save and "blob.bin" in save and "lane.py" not in save, "the saved patch never names a path the lag reads as deleted"

    for command in (save, refresh):
        subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
    assert _git(lag.worktree, "status", "--porcelain") == "", "refreshed: nothing lags, the edit lives in the patch"
    subprocess.run(reapply, shell=True, check=True, capture_output=True, text=True)

    assert (lag.worktree / "alpha.txt").read_text(encoding="utf-8") == "genuine edit\n"
    assert (lag.worktree / "blob.bin").read_bytes() == binary, "the binary edit survives the refresh"
    assert (lag.worktree / "lane.py").read_text(encoding="utf-8") == "lane\n", "the lane file the lag had deleted is back"
    assert _git(lag.worktree, "status", "--porcelain").split() == ["M", "alpha.txt", "??", "blob.bin"], "only the operator's edits remain"


def test_the_patch_is_saved_where_a_worktree_removal_cannot_reach_it(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)

    patch_path = pf._resume_edit_patch_path(lag.worktree)

    assert patch_path.parent == (lag.repo / ".git").resolve()
    assert re.fullmatch(r"spec-kitty-resume-edit-wt-[0-9a-f]{8}\.patch", patch_path.name)
    assert lag.worktree not in patch_path.parents


def test_two_worktrees_with_the_same_directory_name_get_distinct_patch_files(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    twin = tmp_path / "elsewhere" / "wt"
    twin.parent.mkdir()
    _git(lag.repo, "worktree", "add", "-q", "-b", _LANE_BRANCH, str(twin), lag.base)

    first, second = pf._resume_edit_patch_path(lag.worktree), pf._resume_edit_patch_path(twin)

    assert first.parent == second.parent and first != second
    assert pf._resume_edit_patch_path(lag.worktree) == first, "stable for the same worktree"


def test_the_patch_path_falls_back_beside_the_checkout_when_git_cannot_say(tmp_path: Path) -> None:
    """Never ``<checkout>/.git/...``: in a linked worktree ``.git`` is a file, not a directory."""
    checkout = tmp_path / "wt"

    with patch.object(pf, "git_common_dir", side_effect=GitTopologyUnavailableError(checkout, "boom")):
        patch_path = pf._resume_edit_patch_path(checkout)

    assert patch_path.parent == tmp_path.resolve() and checkout not in patch_path.parents
    assert patch_path.name.startswith("spec-kitty-resume-edit-wt-")


def test_an_obstructing_untracked_file_is_flagged_and_gets_no_patch_command(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    (lag.worktree / "lane.py").write_text("operator's untracked file on a path HEAD tracks\n", encoding="utf-8")

    lines = pf.lag_with_edit_guidance(lag.worktree, label="mission worktree", base_sha=lag.base)
    text = "\n".join(lines)

    assert "move them out of the worktree first" in text
    assert [command.split()[3] for command in _advised_commands(lines)] == ["reset"], "no tracked edit: nothing to save as a patch"
    assert text.index("move them out") < text.index("reset --hard HEAD") < text.index("re-apply your edits")


def test_no_obstruction_line_without_an_obstructing_file(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    (lag.worktree / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    assert "move them out" not in "\n".join(pf.lag_with_edit_guidance(lag.worktree, label="lane worktree", base_sha=lag.base))


# --- the resume leg of the preflight -------------------------------------------------------


def test_worktrees_with_branch_checked_out_lists_only_that_branch(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)

    assert [path.resolve() for path in ref_advance.worktrees_with_branch_checked_out(lag.repo, _MISSION_BRANCH)] == [lag.worktree.resolve()]
    assert [path.resolve() for path in ref_advance.worktrees_with_branch_checked_out(lag.repo, "main")] == [lag.repo.resolve()]
    assert ref_advance.worktrees_with_branch_checked_out(lag.repo, "no-such-branch") == []
    _git(lag.worktree, "checkout", "-q", "--detach")
    assert ref_advance.worktrees_with_branch_checked_out(lag.repo, _MISSION_BRANCH) == [], "a detached checkout is not on the branch"


def test_the_resume_leg_refuses_a_dirty_mission_worktree_and_skips_the_root(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)

    state = _state({lag.branch: lag.base})

    with pytest.raises(DestructiveOpRefused) as refused:
        entry_preflight._assert_mission_checkouts_clean(lag.repo, _no_lanes(), state)

    assert refused.value.error_code == MERGE_UNSAFE_WORKTREE_DIRTY
    assert refused.value.worktree_path is not None and refused.value.worktree_path.resolve() == lag.worktree.resolve()
    # The root has ``main`` checked out: asking about ``main`` finds only the root, which this leg skips.
    (lag.repo / "alpha.txt").write_text("dirty root\n", encoding="utf-8")
    on_main: Any = SimpleNamespace(target_branch="main", mission_branch="main", lanes=[])
    entry_preflight._assert_mission_checkouts_clean(lag.repo, on_main, state)


def test_the_resume_leg_passes_a_clean_mission_worktree(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _git(lag.worktree, "reset", "-q", "--hard", "HEAD")

    entry_preflight._assert_mission_checkouts_clean(lag.repo, _no_lanes(), _state({}))


# --- wrapper wiring ------------------------------------------------------------------------


def _manifest() -> Any:
    return SimpleNamespace(target_branch="main", mission_branch=_MISSION_BRANCH)


def _retention() -> Any:
    return SimpleNamespace(remove_worktree=True, teardown_coordination=True)


def _run_wrapper(lag: _Lag) -> None:
    resume_recovery._pre_mutation_safety_preflight_with_recovery(lag.repo, "m", _manifest(), _MISSION_ID, lag.repo / "meta", _retention())


def test_the_wrapper_recovers_several_checkouts_but_each_only_once(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    first, second = _refusal(tmp_path / "one"), _refusal(tmp_path / "two")
    again = _refusal(tmp_path / "one")

    with (
        patch.object(resume_recovery, "_pre_mutation_safety_preflight", side_effect=[first, second, again]) as mock_preflight,
        patch.object(resume_recovery, "_coord_worktree_for_refusal", return_value=None),
        patch.object(resume_recovery, "_recover_behind_head_primary_on_resume", return_value=True) as mock_recover,
        patch.object(resume_recovery, "_report_pre_mutation_refusal") as mock_report,
        pytest.raises(typer.Exit) as exit_info,
    ):
        _run_wrapper(lag)

    assert exit_info.value.exit_code == 1
    assert mock_preflight.call_count == 3
    assert [call.args[0] for call in mock_recover.call_args_list] == [first, second], "the already-recovered checkout is not recovered again"
    assert mock_report.call_args.args[0] is again


# --- the resume leg refuses a lag, not retained dirt (#5613 review) ---------------------------


def _retained() -> Any:
    return SimpleNamespace(remove_worktree=False, teardown_coordination=False)


def _run_real_preflight(lag: _Lag, manifest: Any) -> None:
    """The wrapper over the REAL preflight, worktree retention in effect (only the topology/target lookups are stubbed)."""
    with (
        patch_executor_family("_stored_topology_for", return_value=None),
        patch("specify_cli.lanes.single_branch_landing.expected_consolidate_checkout", return_value="main"),
    ):
        resume_recovery._pre_mutation_safety_preflight_with_recovery(lag.repo, "m", manifest, _MISSION_ID, lag.repo / "meta", _retained())


def _refreshed_then_edited(tmp_path: Path) -> _Lag:
    """A mission worktree that does NOT lag (refreshed to its HEAD) and carries a genuine operator edit."""
    lag = _build_lag(tmp_path)
    _git(lag.worktree, "reset", "-q", "--hard", "HEAD")
    (lag.worktree / "alpha.txt").write_text("operator edit\n", encoding="utf-8")
    return lag


def test_a_resume_passes_a_retained_dirty_mission_worktree_that_does_not_lag(tmp_path: Path) -> None:
    lag = _refreshed_then_edited(tmp_path)
    _persist_state(lag, {lag.branch: lag.base})

    _run_real_preflight(lag, _no_lanes())

    assert (lag.worktree / "alpha.txt").read_text(encoding="utf-8") == "operator edit\n", "the retained edit is untouched"


def test_a_resume_still_refuses_a_retained_worktree_that_lags_with_an_edit(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    lag = _build_lag(tmp_path)
    (lag.worktree / "alpha.txt").write_text("operator edit\n", encoding="utf-8")
    _persist_state(lag, {lag.branch: lag.base})

    with pytest.raises(typer.Exit) as exit_info:
        _run_real_preflight(lag, _no_lanes())

    assert exit_info.value.exit_code == 1
    assert _DO_NOT_RECORD in _flat(capsys.readouterr().out)
    assert not (lag.worktree / "lane.py").exists(), "a lag carrying an edit is never reset"


def test_a_resume_still_refuses_a_retained_dirty_worktree_while_a_lane_remains(tmp_path: Path) -> None:
    lag = _refreshed_then_edited(tmp_path)
    _persist_state(lag, {lag.branch: lag.base})
    _git(lag.repo, "branch", _LANE_BRANCH, lag.base)
    unmerged = _git(lag.repo, "commit-tree", "-m", "unmerged lane work", "-p", lag.base, f"{lag.base}^{{tree}}")
    _git(lag.repo, "update-ref", f"refs/heads/{_LANE_BRANCH}", unmerged)
    manifest: Any = SimpleNamespace(target_branch="main", mission_branch=_MISSION_BRANCH, lanes=[SimpleNamespace(lane_id="lane-a", wp_ids=["WP01"])])

    with patch_executor_family("_created_lane_branch", return_value=_LANE_BRANCH), pytest.raises(typer.Exit) as exit_info:
        _run_real_preflight(lag, manifest)

    assert exit_info.value.exit_code == 1


def test_a_resume_refuses_a_retained_dirty_worktree_when_no_anchor_was_recorded(tmp_path: Path) -> None:
    lag = _refreshed_then_edited(tmp_path)
    _persist_state(lag, {})  # no snapshot entry: the absence of a lag cannot be proven

    with pytest.raises(typer.Exit) as exit_info:
        _run_real_preflight(lag, _no_lanes())

    assert exit_info.value.exit_code == 1


def test_a_fresh_run_never_inspects_a_lagging_mission_worktree(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)  # no persisted merge record: not a --resume, so the mission-checkout leg does not run

    _run_real_preflight(lag, _no_lanes())

    assert not (lag.worktree / "lane.py").exists(), "a fresh run neither refuses over nor refreshes the lagging mission worktree"


def test_a_worktree_listing_failure_is_rendered_as_a_refusal(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    lag = _build_lag(tmp_path)
    _git(lag.worktree, "reset", "-q", "--hard", "HEAD")
    _persist_state(lag, {lag.branch: lag.base})

    with (
        patch.object(entry_preflight, "worktrees_with_branch_checked_out", side_effect=ref_advance.RefAdvanceError("git worktree list failed: boom")),
        pytest.raises(typer.Exit) as exit_info,
    ):
        _run_real_preflight(lag, _no_lanes())

    out = _flat(capsys.readouterr().out)
    assert exit_info.value.exit_code == 1
    assert "git worktree list failed: boom" in out and _MISSION_BRANCH in out
