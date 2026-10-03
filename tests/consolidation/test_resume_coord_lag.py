"""In-process coverage for the #5571 coordination-worktree behind-own-HEAD lag seam.

The #4997 classifier + in-place ``--resume`` recovery were written for the repository root
checkout. The coordination worktree lags the same way (the mission branch is advanced with
``update-ref`` but its worktree refresh never runs), so the SAME seam is parametrised by
checkout (path + persisted base SHA) rather than copied. These tests call that seam directly,
in-process, against REAL temporary git repositories — the ancestry/diff probes must run for
real — so ``coverage.py`` records every branch (the real-CLI proof lives in
``tests/terminus/test_repro_5571.py``).

Fixture shape: commit ``base`` on ``main``; a linked worktree ``coord`` on branch ``mission``;
``mission`` is advanced to ``advanced`` (adds ``lane.py``) with ``update-ref`` while the
worktree keeps reading ``base``'s tree — ``lane.py`` reads as a staged deletion.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any, NamedTuple
from unittest.mock import patch

import pytest
import typer

from specify_cli.consolidation import executor as ex
from specify_cli.consolidation import preflight as pf
from specify_cli.consolidation.preflight import has_unrefreshed_head_advance, head_is_strictly_ahead_of
from specify_cli.consolidation.state import ConsolidationState, save_state
from specify_cli.core.paths import MissionMetaReadError
from specify_cli.git.destructive_guard import (
    MERGE_UNSAFE_PRIMARY_DIRTY,
    MERGE_UNSAFE_WORKTREE_DIRTY,
    DestructiveOpRefused,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_MISSION_ID = "01M5571UNITLAGTESTMISSION1"
_MISSION_BRANCH = "mission"
_COMMIT_ADVICE = "Commit, stash, or revert"
_DO_NOT_RECORD = "Do NOT stage or record"


class _Lag(NamedTuple):
    repo: Path
    coord: Path
    base: str
    advanced: str


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _build_lag(tmp_path: Path) -> _Lag:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test User")
    (repo / "alpha.txt").write_text("alpha\n", encoding="utf-8")
    _git(repo, "add", "alpha.txt")
    _git(repo, "commit", "-qm", "base")
    base = _git(repo, "rev-parse", "HEAD")
    coord = tmp_path / "coord"
    _git(repo, "worktree", "add", "-q", "-b", _MISSION_BRANCH, str(coord), base)
    (coord / "lane.py").write_text("lane\n", encoding="utf-8")
    _git(coord, "add", "lane.py")
    _git(coord, "commit", "-qm", "lane work")
    advanced = _git(coord, "rev-parse", "HEAD")
    # Interrupted window: ref at ``advanced``, worktree/index still ``base``'s tree.
    _git(coord, "reset", "-q", "--hard", base)
    _git(repo, "update-ref", f"refs/heads/{_MISSION_BRANCH}", advanced, base)
    return _Lag(repo=repo, coord=coord, base=base, advanced=advanced)


def _persist_state(lag: _Lag, *, coord_sha: str | None, target_sha: str | None = None) -> None:
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug="m", target_branch="main", wp_order=["WP01"])
    state.pre_mutation_coord_sha = coord_sha
    state.pre_mutation_target_sha = target_sha
    save_state(state, lag.repo)


def _worktree_refusal(path: Path, code: str = MERGE_UNSAFE_WORKTREE_DIRTY) -> DestructiveOpRefused:
    return DestructiveOpRefused(
        error_code=code,
        remediation=f"{_COMMIT_ADVICE} the local changes in {path}, then resume.",
        worktree_path=path,
        dirty_entries=["D  lane.py"],
    )


# --- preflight helpers ---------------------------------------------------------------------


def test_head_is_strictly_ahead_of_only_for_a_strict_ancestor(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)

    assert head_is_strictly_ahead_of(lag.coord, lag.base) is True
    assert head_is_strictly_ahead_of(lag.coord, lag.advanced) is False  # equal: no lag
    assert head_is_strictly_ahead_of(lag.coord, None) is False
    assert head_is_strictly_ahead_of(lag.coord, "") is False
    assert head_is_strictly_ahead_of(lag.coord, "0" * 40) is False  # unknown object: fail closed
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    assert head_is_strictly_ahead_of(plain, lag.base) is False  # git error: fail closed


def test_has_unrefreshed_head_advance_true_while_the_worktree_lags(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)

    assert has_unrefreshed_head_advance(lag.coord, base_sha=lag.base) is True


def test_has_unrefreshed_head_advance_true_when_a_genuine_edit_is_mixed_in(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    (lag.coord / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    assert has_unrefreshed_head_advance(lag.coord, base_sha=lag.base) is True
    assert pf.is_pure_behind_head_lag(lag.coord, base_sha=lag.base) is False  # advisory only: never authorises a reset


def test_has_unrefreshed_head_advance_false_once_refreshed_or_without_a_base(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)

    assert has_unrefreshed_head_advance(lag.coord, base_sha=None) is False
    assert has_unrefreshed_head_advance(lag.coord, base_sha=lag.advanced) is False  # HEAD == base: no advance
    _git(lag.coord, "reset", "-q", "--hard", "HEAD")
    assert has_unrefreshed_head_advance(lag.coord, base_sha=lag.base) is False  # refreshed: nothing reads in reverse


def test_has_unrefreshed_head_advance_false_for_dirt_on_paths_the_advance_never_touched(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _git(lag.coord, "reset", "-q", "--hard", "HEAD")
    (lag.coord / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    assert has_unrefreshed_head_advance(lag.coord, base_sha=lag.base) is False  # genuine work: the stock remedy is safe


def test_has_unrefreshed_head_advance_false_on_a_git_error(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)

    with patch.object(pf, "run_command", return_value=(128, "", "fatal")):
        assert pf._diff_paths(lag.coord, "HEAD") == set()


# --- checkout selection --------------------------------------------------------------------


def test_lag_checkout_for_primary_dirty_is_the_repository_root(tmp_path: Path) -> None:
    exc = _worktree_refusal(tmp_path, code=MERGE_UNSAFE_PRIMARY_DIRTY)

    checkout = ex._lag_checkout_for_refusal(exc, tmp_path, None)

    assert checkout == ex._LagCheckout(tmp_path, coordination=False)
    assert checkout is not None and checkout.label == "primary checkout"


def test_lag_checkout_for_the_coordination_worktree_refusal(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)

    checkout = ex._lag_checkout_for_refusal(_worktree_refusal(lag.coord), lag.repo, lag.coord)

    assert checkout == ex._LagCheckout(lag.coord, coordination=True)
    assert checkout is not None and checkout.label == "coordination worktree"


def test_lag_checkout_none_for_a_lane_worktree_refusal(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    lane_worktree = tmp_path / "lane-a"
    lane_worktree.mkdir()

    assert ex._lag_checkout_for_refusal(_worktree_refusal(lane_worktree), lag.repo, lag.coord) is None


@pytest.mark.parametrize(
    "code, has_coord",
    [
        (MERGE_UNSAFE_WORKTREE_DIRTY, False),  # no coordination worktree resolved
        ("MERGE_UNSAFE_PRIMARY_OFF_TARGET", True),  # not a dirty-guard code
    ],
)
def test_lag_checkout_none_without_a_matching_coordination_refusal(tmp_path: Path, code: str, has_coord: bool) -> None:
    lag = _build_lag(tmp_path)

    checkout = ex._lag_checkout_for_refusal(_worktree_refusal(lag.coord, code=code), lag.repo, lag.coord if has_coord else None)

    assert checkout is None


def test_lag_checkout_none_when_the_refusal_names_no_worktree(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    exc = DestructiveOpRefused(error_code=MERGE_UNSAFE_WORKTREE_DIRTY, remediation="x")

    assert ex._lag_checkout_for_refusal(exc, lag.repo, lag.coord) is None


def test_lag_checkout_base_sha_selects_the_anchor_per_checkout(tmp_path: Path) -> None:
    state = ConsolidationState(mission_id=_MISSION_ID, mission_slug="m", target_branch="main", wp_order=["WP01"])
    state.pre_mutation_target_sha = "T" * 40
    state.pre_mutation_coord_sha = "C" * 40

    assert ex._LagCheckout(tmp_path, coordination=False).base_sha(state) == "T" * 40
    assert ex._LagCheckout(tmp_path, coordination=True).base_sha(state) == "C" * 40
    assert ex._LagCheckout(tmp_path, coordination=True).base_sha(None) is None


def test_coord_worktree_for_refusal_resolves_only_for_a_generic_worktree_refusal(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    meta = tmp_path / "meta"

    with patch.object(ex, "_resolve_coord_worktree_for_preflight", return_value=lag.coord) as mock_resolve:
        assert ex._coord_worktree_for_refusal(_worktree_refusal(lag.coord), lag.repo, "m", meta) == lag.coord
        assert ex._coord_worktree_for_refusal(_worktree_refusal(lag.repo, MERGE_UNSAFE_PRIMARY_DIRTY), lag.repo, "m", meta) is None

    mock_resolve.assert_called_once_with(lag.repo, "m", meta)


def test_coord_worktree_for_refusal_none_when_unresolvable_or_unreadable(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    exc = _worktree_refusal(lag.coord)

    with patch.object(ex, "_resolve_coord_worktree_for_preflight", return_value=None):
        assert ex._coord_worktree_for_refusal(exc, lag.repo, "m", tmp_path) is None
    with patch.object(ex, "_resolve_coord_worktree_for_preflight", return_value=tmp_path / "gone"):
        assert ex._coord_worktree_for_refusal(exc, lag.repo, "m", tmp_path) is None
    with patch.object(ex, "_resolve_coord_worktree_for_preflight", side_effect=MissionMetaReadError(tmp_path / "meta.json", ValueError("corrupt"))):
        assert ex._coord_worktree_for_refusal(exc, lag.repo, "m", tmp_path) is None


# --- in-place recovery on --resume ---------------------------------------------------------


def _recover(lag: _Lag, exc: DestructiveOpRefused, coord_worktree: Path | None) -> bool:
    return ex._recover_behind_head_primary_on_resume(exc, lag.repo, _MISSION_ID, mission_branch=_MISSION_BRANCH, coord_worktree=coord_worktree)


def test_resume_refreshes_a_pure_coordination_lag_in_place(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=lag.base)

    assert _recover(lag, _worktree_refusal(lag.coord), lag.coord) is True

    assert (lag.coord / "lane.py").read_text(encoding="utf-8") == "lane\n"
    assert _git(lag.coord, "status", "--porcelain") == ""
    assert "Recovered a behind-own-HEAD coordination worktree" in capsys.readouterr().out


def test_fresh_merge_never_refreshes_a_dirty_coordination_worktree(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)  # no persisted state: not a --resume

    assert _recover(lag, _worktree_refusal(lag.coord), lag.coord) is False

    assert not (lag.coord / "lane.py").exists()


def test_a_genuine_edit_on_top_of_the_lag_is_never_reset(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=lag.base)
    (lag.coord / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    assert _recover(lag, _worktree_refusal(lag.coord), lag.coord) is False

    assert (lag.coord / "alpha.txt").read_text(encoding="utf-8") == "genuine edit\n"
    assert not (lag.coord / "lane.py").exists()


def test_an_untracked_file_obstructing_a_restored_path_is_never_overwritten(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=lag.base)
    (lag.coord / "lane.py").write_text("operator's untracked file\n", encoding="utf-8")

    assert _recover(lag, _worktree_refusal(lag.coord), lag.coord) is False

    assert (lag.coord / "lane.py").read_text(encoding="utf-8") == "operator's untracked file\n"


def test_the_target_anchor_does_not_prove_a_coordination_lag(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=None, target_sha=lag.base)  # wrong anchor for this checkout

    assert _recover(lag, _worktree_refusal(lag.coord), lag.coord) is False

    assert not (lag.coord / "lane.py").exists()


def test_a_lane_worktree_is_never_a_recovery_candidate(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=lag.base)

    assert _recover(lag, _worktree_refusal(lag.coord), None) is False  # coordination worktree not resolved

    assert not (lag.coord / "lane.py").exists()


def test_a_failed_reset_is_reported_and_does_not_recover(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=lag.base)

    with patch.object(ex, "run_command", return_value=(1, "", "fatal: unable to write index\n")) as mock_run:
        assert _recover(lag, _worktree_refusal(lag.coord), lag.coord) is False

    assert mock_run.call_args.kwargs["cwd"] == lag.coord
    assert f"`git reset --hard HEAD` failed in {lag.coord}" in " ".join(capsys.readouterr().out.split())


def test_a_blocking_index_lock_is_not_recovered(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=lag.base)
    Path(_git(lag.coord, "rev-parse", "--path-format=absolute", "--git-path", "index.lock")).write_text("", encoding="utf-8")

    assert _recover(lag, _worktree_refusal(lag.coord), lag.coord) is False

    assert not (lag.coord / "lane.py").exists()


# --- refusal report ------------------------------------------------------------------------


def _report(lag: _Lag, exc: DestructiveOpRefused, *, base_sha: str | None, coord_worktree: Path | None, capsys: pytest.CaptureFixture[str]) -> str:
    ex._report_pre_mutation_refusal(exc, lag.repo, mission_branch=_MISSION_BRANCH, base_sha=base_sha, coord_worktree=coord_worktree)
    return " ".join(capsys.readouterr().out.split())


def test_report_pure_coordination_lag_prints_reset_guidance_not_commit_advice(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    lag = _build_lag(tmp_path)

    out = _report(lag, _worktree_refusal(lag.coord), base_sha=lag.base, coord_worktree=lag.coord, capsys=capsys)

    assert "Resume recovery guidance" in out
    assert _DO_NOT_RECORD in out
    assert f"git -C {lag.coord} reset --hard HEAD" in out


def test_report_lag_with_a_genuine_edit_never_advises_committing(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    lag = _build_lag(tmp_path)
    (lag.coord / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    out = _report(lag, _worktree_refusal(lag.coord), base_sha=lag.base, coord_worktree=lag.coord, capsys=capsys)

    assert _COMMIT_ADVICE not in out
    assert _DO_NOT_RECORD in out
    assert "Save your own edits outside the worktree first" in out
    assert "D lane.py" in out  # (whitespace-collapsed) the dirty entries are still reported
    assert "Merge aborted before any state change" in out


def test_report_genuine_dirt_without_a_lag_keeps_the_stock_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    lag = _build_lag(tmp_path)
    _git(lag.coord, "reset", "-q", "--hard", "HEAD")  # refreshed: no lag left
    (lag.coord / "alpha.txt").write_text("genuine edit\n", encoding="utf-8")

    out = _report(lag, _worktree_refusal(lag.coord), base_sha=lag.base, coord_worktree=lag.coord, capsys=capsys)

    assert _COMMIT_ADVICE in out
    assert _DO_NOT_RECORD not in out


def test_report_fresh_merge_without_a_base_keeps_the_stock_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    lag = _build_lag(tmp_path)

    out = _report(lag, _worktree_refusal(lag.coord), base_sha=None, coord_worktree=lag.coord, capsys=capsys)

    assert _COMMIT_ADVICE in out
    assert _DO_NOT_RECORD not in out


def test_report_lane_worktree_refusal_keeps_the_stock_remedy(tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("COLUMNS", "400")
    lag = _build_lag(tmp_path)

    out = _report(lag, _worktree_refusal(lag.repo / "lane-a"), base_sha=lag.base, coord_worktree=lag.coord, capsys=capsys)

    assert _COMMIT_ADVICE in out
    assert _DO_NOT_RECORD not in out


# --- wrapper wiring ------------------------------------------------------------------------


def _manifest(mission_branch: str = _MISSION_BRANCH) -> Any:
    return SimpleNamespace(target_branch="main", mission_branch=mission_branch)


def _retention() -> Any:
    return SimpleNamespace(remove_worktree=True, teardown_coordination=True)


def test_wrapper_recovers_a_pure_coordination_lag_then_retries_the_preflight(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=lag.base)
    refusal = _worktree_refusal(lag.coord)

    def _preflight(*_args: object, **_kwargs: object) -> None:
        if (lag.coord / "lane.py").exists():
            return
        raise refusal

    with (
        patch.object(ex, "_pre_mutation_safety_preflight", side_effect=_preflight) as mock_preflight,
        patch.object(ex, "_resolve_coord_worktree_for_preflight", return_value=lag.coord),
    ):
        ex._pre_mutation_safety_preflight_with_recovery(lag.repo, "m", _manifest(), _MISSION_ID, tmp_path / "meta", _retention())

    assert mock_preflight.call_count == 2
    assert (lag.coord / "lane.py").exists()


def test_wrapper_threads_the_coordination_anchor_into_the_refusal_report(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=lag.base, target_sha="T" * 40)
    refusal = _worktree_refusal(lag.coord)

    with (
        patch.object(ex, "_pre_mutation_safety_preflight", side_effect=refusal),
        patch.object(ex, "_resolve_coord_worktree_for_preflight", return_value=lag.coord),
        patch.object(ex, "_recover_behind_head_primary_on_resume", return_value=False),
        patch.object(ex, "_report_pre_mutation_refusal") as mock_report,
        pytest.raises(typer.Exit) as exit_info,
    ):
        ex._pre_mutation_safety_preflight_with_recovery(lag.repo, "m", _manifest(), _MISSION_ID, tmp_path / "meta", _retention())

    assert exit_info.value.exit_code == 1
    mock_report.assert_called_once()
    assert mock_report.call_args.kwargs["base_sha"] == lag.base
    assert mock_report.call_args.kwargs["coord_worktree"] == lag.coord


def test_wrapper_reports_a_refusal_that_persists_after_recovery(tmp_path: Path) -> None:
    lag = _build_lag(tmp_path)
    _persist_state(lag, coord_sha=lag.base)
    refusal = _worktree_refusal(lag.coord)
    still_refused = _worktree_refusal(lag.coord)

    with (
        patch.object(ex, "_pre_mutation_safety_preflight", side_effect=[refusal, still_refused]),
        patch.object(ex, "_resolve_coord_worktree_for_preflight", return_value=lag.coord),
        patch.object(ex, "_report_pre_mutation_refusal") as mock_report,
        pytest.raises(typer.Exit),
    ):
        ex._pre_mutation_safety_preflight_with_recovery(lag.repo, "m", _manifest(), _MISSION_ID, tmp_path / "meta", _retention())

    mock_report.assert_called_once()
    assert mock_report.call_args.args[0] is still_refused
    assert (lag.coord / "lane.py").read_text(encoding="utf-8") == "lane\n"  # the recovery did refresh the worktree
