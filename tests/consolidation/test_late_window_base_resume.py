"""Where a resumed teardown's late window starts, and the landed-coordination ref (#7491, #4041, #4380 item 2).

Mission coord-closeout-leftovers WP02. The coordination tip a verified landing covered is persisted
with the reconciliation PASS anchor (``ConsolidationState.coord_tip_after_projection``) and recorded
as ``refs/spec-kitty/landed-coordination/<branch>``. A ``--resume`` starts its late window there only
when the landing is verified and the tip is still on the coordination branch; otherwise it keeps the
pre-mutation snapshot. These cells pin both arms on a tiny real repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.consolidation import phase_gate, phase_teardown, rollback
from specify_cli.consolidation import landed_coordination
from specify_cli.consolidation.landed_coordination import LandedCoordinationRefError, clear_landed_coordination_tip, record_landed_coordination_tip
from specify_cli.consolidation.run_state import CoordinationTeardownError, _CoordCheckpoint
from specify_cli.consolidation.state import ConsolidationState, load_state
from specify_cli.git.ref_advance import RefAdvanceError

pytestmark = [pytest.mark.git_repo, pytest.mark.fast]

_TARGET = "main"
_COORD = "kitty/mission-demo-01M7491B"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def _commit(repo: Path, name: str) -> str:
    (repo / name).write_text(f"{name}\n", encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-qm", f"add {name}")
    return _git(repo, "rev-parse", "HEAD")


class _Repo:
    """A target branch and a coordination branch cut from it, each with its own commits."""

    def __init__(self, root: Path) -> None:
        self.root = root
        root.mkdir()
        _git(root, "init", "-q", "-b", _TARGET)
        _git(root, "config", "user.email", "t@example.com")
        _git(root, "config", "user.name", "t")
        _git(root, "config", "commit.gpgsign", "false")
        self.base = _commit(root, "base.txt")
        _git(root, "checkout", "-qb", _COORD)
        self.pre_mutation = _commit(root, "coord-1.txt")
        self.projected = _commit(root, "coord-2.txt")
        self.late = _commit(root, "coord-late.txt")
        _git(root, "checkout", "-q", _TARGET)
        self.landing = _commit(root, "landing.txt")

    def rewrite_coordination_branch(self) -> None:
        """Point the coordination branch at an unrelated history: the persisted tip is no longer on it."""
        _git(self.root, "checkout", "-q", "-b", "rewritten", self.base)
        rewritten = _commit(self.root, "rewritten.txt")
        _git(self.root, "checkout", "-q", _TARGET)
        _git(self.root, "branch", "-f", _COORD, rewritten)


@pytest.fixture
def repo(tmp_path: Path) -> _Repo:
    return _Repo(tmp_path / "repo")


def _state(repo: _Repo, *, anchor: str | None, coord_tip: str | None) -> ConsolidationState:
    return ConsolidationState(
        mission_id="01M7491B00000000000000000",
        mission_slug="demo-01M7491B",
        target_branch=_TARGET,
        wp_order=["WP01"],
        pre_mutation_coord_sha=repo.pre_mutation,
        pre_mutation_coord_ref=_COORD,
        reconciliation_passed_target_sha=anchor,
        coord_tip_after_projection=coord_tip,
    )


def _run(repo: _Repo, *, is_resume: bool, state: ConsolidationState, in_memory_tip: str | None = None) -> Any:
    return SimpleNamespace(
        main_repo=repo.root,
        is_resume=is_resume,
        state=state,
        coord_tip_after_projection=in_memory_tip,
        coord_checkpoint=_CoordCheckpoint(ref=_COORD, sha=repo.pre_mutation),
        lanes_manifest=SimpleNamespace(mission_branch=_COORD, target_branch=_TARGET),
        mission_slug=state.mission_slug,
    )


# -- base selection (FR-003) ---------------------------------------------------------------------------------


def test_first_run_starts_at_the_in_memory_post_projection_tip(repo: _Repo) -> None:
    run = _run(repo, is_resume=False, state=_state(repo, anchor=None, coord_tip=None), in_memory_tip=repo.projected)

    assert phase_teardown._late_window_base(run) == repo.projected


def test_verified_resume_starts_at_the_persisted_tip(repo: _Repo) -> None:
    run = _run(repo, is_resume=True, state=_state(repo, anchor=repo.landing, coord_tip=repo.projected))

    assert phase_teardown._late_window_base(run) == repo.projected


def test_verified_resume_falls_back_when_the_tip_left_the_coordination_branch(repo: _Repo) -> None:
    repo.rewrite_coordination_branch()
    run = _run(repo, is_resume=True, state=_state(repo, anchor=repo.landing, coord_tip=repo.projected))

    assert phase_teardown._late_window_base(run) == repo.pre_mutation


def test_unverified_resume_keeps_the_pre_mutation_snapshot(repo: _Repo) -> None:
    """The target moved off the PASS anchor (no cleanup started): the landing is not verified for this resume."""
    run = _run(repo, is_resume=True, state=_state(repo, anchor=repo.base, coord_tip=repo.projected))

    assert phase_teardown._late_window_base(run) == repo.pre_mutation


def test_legacy_record_without_a_persisted_tip_keeps_the_pre_mutation_snapshot(repo: _Repo) -> None:
    run = _run(repo, is_resume=True, state=_state(repo, anchor=repo.landing, coord_tip=None))

    assert phase_teardown._late_window_base(run) == repo.pre_mutation


def test_a_tip_git_cannot_read_falls_back(repo: _Repo) -> None:
    run = _run(repo, is_resume=True, state=_state(repo, anchor=repo.landing, coord_tip="f" * 40))

    assert phase_teardown._late_window_base(run) == repo.pre_mutation


def test_a_legacy_record_loads_without_the_tip() -> None:
    raw = _state_dict_without_tip()

    assert ConsolidationState.from_dict(raw).coord_tip_after_projection is None


def _state_dict_without_tip() -> dict[str, Any]:
    raw: dict[str, Any] = ConsolidationState(
        mission_id="m", mission_slug="m", target_branch=_TARGET, wp_order=["WP01"], reconciliation_passed_target_sha="a" * 40
    ).to_dict()
    raw.pop("coord_tip_after_projection", None)
    return raw


# -- the pair (FR-004) ---------------------------------------------------------------------------------------


def _bare_state() -> ConsolidationState:
    return ConsolidationState(mission_id="m", mission_slug="m", target_branch=_TARGET, wp_order=[])


def test_clear_drops_the_anchor_and_the_tip_together() -> None:
    state = _bare_state()
    state.restore_reconciliation_pass("a", "c")

    assert state.clear_reconciliation_pass() is True
    assert state.reconciliation_pass_pair() == (None, None)


def test_restore_puts_back_the_pair_it_was_given() -> None:
    state = _bare_state()
    state.restore_reconciliation_pass("b", "d")

    assert state.restore_reconciliation_pass("a", "c") is True
    assert state.reconciliation_pass_pair() == ("a", "c")
    assert state.restore_reconciliation_pass("a", "c") is False


def test_a_tip_is_never_restored_without_its_anchor() -> None:
    state = _bare_state()

    assert state.restore_reconciliation_pass(None, "c") is False
    assert state.reconciliation_pass_pair() == (None, None)


def test_the_pass_record_persists_the_tip_and_the_ref_in_one_go(repo: _Repo) -> None:
    state = _state(repo, anchor=None, coord_tip=None)
    run = _run(repo, is_resume=False, state=state, in_memory_tip=repo.projected)

    phase_gate._record_reconciliation_pass(run, repo.landing)

    saved = load_state(repo.root, state.mission_id)
    assert saved is not None and saved.reconciliation_pass_pair() == (repo.landing, repo.projected)
    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) == repo.projected


def test_a_proven_late_window_advances_the_persisted_tip_and_the_ref(repo: _Repo) -> None:
    state = _state(repo, anchor=repo.landing, coord_tip=repo.projected)
    run = _run(repo, is_resume=True, state=state, in_memory_tip=None)
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)

    phase_teardown._advance_approved_tip(run, _COORD, repo.late)

    assert run.coord_tip_after_projection == repo.late
    saved = load_state(repo.root, state.mission_id)
    assert saved is not None and saved.coord_tip_after_projection == repo.late
    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) == repo.late


def test_an_advance_without_a_pass_anchor_persists_nothing(repo: _Repo) -> None:
    state = _state(repo, anchor=None, coord_tip=None)
    run = _run(repo, is_resume=False, state=state, in_memory_tip=repo.projected)

    phase_teardown._advance_approved_tip(run, _COORD, repo.late)

    assert run.coord_tip_after_projection == repo.late
    assert state.coord_tip_after_projection is None
    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) is None


def test_no_ref_is_written_when_the_checkpoint_names_the_target(repo: _Repo) -> None:
    run = _run(repo, is_resume=False, state=_state(repo, anchor=None, coord_tip=None))
    run.coord_checkpoint = _CoordCheckpoint(ref=_TARGET, sha=repo.base)

    phase_teardown.record_landed_coordination_ref(run, repo.projected)

    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) is None
    assert landed_coordination.landed_coordination_tip(repo.root, _TARGET) is None


def test_a_ref_write_failure_never_fails_the_landing(repo: _Repo, caplog: pytest.LogCaptureFixture) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.late)
    run = _run(repo, is_resume=False, state=_state(repo, anchor=None, coord_tip=None))

    phase_teardown.record_landed_coordination_ref(run, repo.projected)  # an ancestor: refused, logged

    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) == repo.late
    assert "Could not record the landed coordination tip" in caplog.text


# -- the landed-coordination ref (#4041) ---------------------------------------------------------------------


def test_the_ref_is_created_read_and_advanced(repo: _Repo) -> None:
    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) is None

    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)  # same tip: a no-op
    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) == repo.projected

    record_landed_coordination_tip(repo.root, _COORD, repo.late)
    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) == repo.late
    assert landed_coordination.landed_coordination_ref(f"refs/heads/{_COORD}") == f"{landed_coordination.LANDED_COORDINATION_REF_PREFIX}{_COORD}"


def test_the_ref_never_moves_to_a_tip_that_does_not_descend_from_it(repo: _Repo) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.late)

    with pytest.raises(LandedCoordinationRefError, match="not an ancestor"):
        record_landed_coordination_tip(repo.root, _COORD, repo.landing)
    with pytest.raises(LandedCoordinationRefError):
        record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) == repo.late


def test_the_ref_rejects_empty_input(repo: _Repo) -> None:
    with pytest.raises(ValueError, match="must name a commit"):
        record_landed_coordination_tip(repo.root, _COORD, "")
    with pytest.raises(ValueError, match="needs a coordination branch"):
        landed_coordination.landed_coordination_ref("refs/heads/")


def test_clearing_the_ref_is_idempotent(repo: _Repo) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)

    assert clear_landed_coordination_tip(repo.root, _COORD) is True
    assert clear_landed_coordination_tip(repo.root, _COORD) is True
    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) is None


def test_a_rollback_that_restores_the_target_deletes_the_ref(repo: _Repo) -> None:
    """F4: the landing the ref describes is undone, so the ref goes with the PASS anchor."""
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    state = _state(repo, anchor=None, coord_tip=None)
    state.pre_mutation_refs = {_TARGET: repo.base}
    state.post_mutation_refs = {_TARGET: repo.landing}

    report = rollback.rollback_to_snapshot(repo.root, state, target_branch=_TARGET)

    assert _git(repo.root, "rev-parse", _TARGET) == repo.base, report.render()
    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) is None


def test_a_landed_ref_that_would_not_clear_is_a_not_restored_outcome(repo: _Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale ref would let a later reclaim treat the undone landing as proved: it is reported, and the record is not re-baselined."""
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    monkeypatch.setattr(landed_coordination, "clear_landed_coordination_tip", lambda _root, _branch: False)
    state = _state(repo, anchor=None, coord_tip=None)
    state.pre_mutation_refs = {_TARGET: repo.base}
    state.post_mutation_refs = {_TARGET: repo.landing}

    report = rollback.rollback_to_snapshot(repo.root, state, target_branch=_TARGET)

    assert report.landed_ref_kept == _COORD
    assert not report.fully_restored and not report.rebaselineable
    assert f"git update-ref -d refs/spec-kitty/landed-coordination/{_COORD}" in report.render()


def test_the_rollback_helper_leaves_a_target_anchored_record_alone(repo: _Repo) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    state = _state(repo, anchor=None, coord_tip=None)
    state.pre_mutation_coord_ref = _TARGET

    rollback._clear_landed_coordination_ref(repo.root, state)

    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) == repo.projected


@pytest.mark.parametrize("coord_ref", ["", "refs/heads/"], ids=("empty", "heads-prefix-only"))
def test_the_rollback_helper_never_raises_on_an_unusable_coordination_ref(repo: _Repo, coord_ref: str) -> None:
    """Best effort: a record whose coordination ref names no branch neither raises nor touches any ref."""
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    state = _state(repo, anchor=None, coord_tip=None)
    state.pre_mutation_coord_ref = coord_ref

    rollback._clear_landed_coordination_ref(repo.root, state)

    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) == repo.projected


# -- #4380 item 2: the kept-branch refusal says what is true ------------------------------------------------


_DELETE_REFUSAL = "cannot lock ref 'refs/heads/kitty/mission-demo-01M7491B': File exists"


def _teardown_run(repo: _Repo, monkeypatch: pytest.MonkeyPatch) -> Any:
    run = _run(repo, is_resume=True, state=_state(repo, anchor=repo.landing, coord_tip=repo.projected))
    for name in ("_refuse_unlanded_topic_primary", "_land_late_coordination_commits", "_fold_coord_status_before_flatten"):
        monkeypatch.setattr(phase_teardown, name, lambda _run: None)
    monkeypatch.setattr(phase_teardown, "_teardown_coord_worktree", lambda _run: None)
    monkeypatch.setattr(phase_teardown, "_refused_mission_branch_delete", lambda _run, _tip: _DELETE_REFUSAL)
    return run


def test_kept_branch_text_with_the_worktree_gone_names_the_refused_delete(repo: _Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    run = _teardown_run(repo, monkeypatch)

    with pytest.raises(CoordinationTeardownError) as refused:
        phase_teardown._teardown_coordination_triple(run)

    message = str(refused.value)
    assert "still exists after teardown" in message and "No worktree has it checked out" in message, message
    assert "compare-and-swap delete" in message and "consolidate --resume" in message, message
    assert _DELETE_REFUSAL in message and "see the warning above" not in message, message
    assert "stay consistent" not in message and "git worktree list" not in message, message


def test_kept_branch_text_names_the_worktree_that_still_holds_it(repo: _Repo, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    holder = tmp_path / "holder"
    _git(repo.root, "worktree", "add", "-q", str(holder), _COORD)
    run = _teardown_run(repo, monkeypatch)

    with pytest.raises(CoordinationTeardownError) as refused:
        phase_teardown._teardown_coordination_triple(run)

    message = str(refused.value)
    assert "checked out in" in message and holder.name in message and "git worktree list" in message, message


def test_kept_branch_text_when_worktrees_cannot_be_listed(repo: _Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    run = _teardown_run(repo, monkeypatch)

    def _unlistable(*_args: object, **_kwargs: object) -> list[Path]:
        raise RefAdvanceError("worktree list failed")

    monkeypatch.setattr(phase_teardown, "worktrees_with_branch_checked_out", _unlistable)

    message = phase_teardown._branch_kept_after_teardown_message(run, _DELETE_REFUSAL)

    assert "could not be listed" in message and "worktree list failed" in message, message


# -- a normal teardown clears the landed-coordination ref (MINOR-1, #7598 closeout) ----------------------------


def _stub_teardown_legs(monkeypatch: pytest.MonkeyPatch, *, delete_refusal: str | None) -> None:
    """Every teardown leg but the ref clear is a no-op; the branch delete answers *delete_refusal*."""
    for leg in (
        "_refuse_unlanded_topic_primary",
        "_land_late_coordination_commits",
        "_fold_coord_status_before_flatten",
        "_flatten_coordination_metadata_after_branch_delete",
    ):
        monkeypatch.setattr(phase_teardown, leg, lambda _run: None)
    monkeypatch.setattr(phase_teardown, "_mission_branch_tip", lambda _run: None)
    monkeypatch.setattr(phase_teardown, "_teardown_coord_worktree", lambda _run: None)
    monkeypatch.setattr(phase_teardown, "_refused_mission_branch_delete", lambda _run, _tip: delete_refusal)
    monkeypatch.setattr(phase_teardown, "_branch_kept_after_teardown_message", lambda _run, refusal: refusal)


def test_a_teardown_that_deletes_the_branch_clears_its_landed_ref(repo: _Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    _stub_teardown_legs(monkeypatch, delete_refusal=None)

    phase_teardown._teardown_coordination_triple(_run(repo, is_resume=False, state=_state(repo, anchor=None, coord_tip=None)))

    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) is None


def test_a_teardown_whose_branch_delete_refused_keeps_the_landed_ref(repo: _Repo, monkeypatch: pytest.MonkeyPatch) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    _stub_teardown_legs(monkeypatch, delete_refusal="cannot delete")

    with pytest.raises(CoordinationTeardownError):
        phase_teardown._teardown_coordination_triple(_run(repo, is_resume=False, state=_state(repo, anchor=None, coord_tip=None)))

    assert landed_coordination.landed_coordination_tip(repo.root, _COORD) == repo.projected


def test_a_landed_ref_clear_failure_never_fails_the_teardown(repo: _Repo, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    _stub_teardown_legs(monkeypatch, delete_refusal=None)
    monkeypatch.setattr(landed_coordination, "clear_landed_coordination_tip", lambda _root, _branch: False)

    phase_teardown._teardown_coordination_triple(_run(repo, is_resume=False, state=_state(repo, anchor=None, coord_tip=None)))

    assert "Could not delete the landed-coordination ref" in caplog.text
