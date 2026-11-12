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
from specify_cli.consolidation.landed_coordination import (
    LANDED_COORDINATION_REF_PREFIX,
    LandedCoordinationRefError,
    clear_landed_coordination_tip,
    landed_coordination_ref,
    landed_coordination_tip,
    record_landed_coordination_tip,
)
from specify_cli.consolidation.run_state import _CoordCheckpoint
from specify_cli.consolidation.state import ConsolidationState, load_state

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
    assert landed_coordination_tip(repo.root, _COORD) == repo.projected


def test_a_proven_late_window_advances_the_persisted_tip_and_the_ref(repo: _Repo) -> None:
    state = _state(repo, anchor=repo.landing, coord_tip=repo.projected)
    run = _run(repo, is_resume=True, state=state, in_memory_tip=None)
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)

    phase_teardown._advance_approved_tip(run, _COORD, repo.late)

    assert run.coord_tip_after_projection == repo.late
    saved = load_state(repo.root, state.mission_id)
    assert saved is not None and saved.coord_tip_after_projection == repo.late
    assert landed_coordination_tip(repo.root, _COORD) == repo.late


def test_an_advance_without_a_pass_anchor_persists_nothing(repo: _Repo) -> None:
    state = _state(repo, anchor=None, coord_tip=None)
    run = _run(repo, is_resume=False, state=state, in_memory_tip=repo.projected)

    phase_teardown._advance_approved_tip(run, _COORD, repo.late)

    assert run.coord_tip_after_projection == repo.late
    assert state.coord_tip_after_projection is None
    assert landed_coordination_tip(repo.root, _COORD) is None


def test_no_ref_is_written_when_the_checkpoint_names_the_target(repo: _Repo) -> None:
    run = _run(repo, is_resume=False, state=_state(repo, anchor=None, coord_tip=None))
    run.coord_checkpoint = _CoordCheckpoint(ref=_TARGET, sha=repo.base)

    phase_teardown.record_landed_coordination_ref(run, repo.projected)

    assert landed_coordination_tip(repo.root, _COORD) is None
    assert landed_coordination_tip(repo.root, _TARGET) is None


def test_a_ref_write_failure_never_fails_the_landing(repo: _Repo, caplog: pytest.LogCaptureFixture) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.late)
    run = _run(repo, is_resume=False, state=_state(repo, anchor=None, coord_tip=None))

    phase_teardown.record_landed_coordination_ref(run, repo.projected)  # an ancestor: refused, logged

    assert landed_coordination_tip(repo.root, _COORD) == repo.late
    assert "Could not record the landed coordination tip" in caplog.text


# -- the landed-coordination ref (#4041) ---------------------------------------------------------------------


def test_the_ref_is_created_read_and_advanced(repo: _Repo) -> None:
    assert landed_coordination_tip(repo.root, _COORD) is None

    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)  # same tip: a no-op
    assert landed_coordination_tip(repo.root, _COORD) == repo.projected

    record_landed_coordination_tip(repo.root, _COORD, repo.late)
    assert landed_coordination_tip(repo.root, _COORD) == repo.late
    assert landed_coordination_ref(f"refs/heads/{_COORD}") == f"{LANDED_COORDINATION_REF_PREFIX}{_COORD}"


def test_the_ref_never_moves_to_a_tip_that_does_not_descend_from_it(repo: _Repo) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.late)

    with pytest.raises(LandedCoordinationRefError, match="not an ancestor"):
        record_landed_coordination_tip(repo.root, _COORD, repo.landing)
    with pytest.raises(LandedCoordinationRefError):
        record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    assert landed_coordination_tip(repo.root, _COORD) == repo.late


def test_the_ref_rejects_empty_input(repo: _Repo) -> None:
    with pytest.raises(ValueError, match="must name a commit"):
        record_landed_coordination_tip(repo.root, _COORD, "")
    with pytest.raises(ValueError, match="needs a coordination branch"):
        landed_coordination_ref("refs/heads/")


def test_clearing_the_ref_is_idempotent(repo: _Repo) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)

    assert clear_landed_coordination_tip(repo.root, _COORD) is True
    assert clear_landed_coordination_tip(repo.root, _COORD) is True
    assert landed_coordination_tip(repo.root, _COORD) is None


def test_a_rollback_that_restores_the_target_deletes_the_ref(repo: _Repo) -> None:
    """F4: the landing the ref describes is undone, so the ref goes with the PASS anchor."""
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    state = _state(repo, anchor=None, coord_tip=None)
    state.pre_mutation_refs = {_TARGET: repo.base}
    state.post_mutation_refs = {_TARGET: repo.landing}

    report = rollback.rollback_to_snapshot(repo.root, state, target_branch=_TARGET)

    assert _git(repo.root, "rev-parse", _TARGET) == repo.base, report.render()
    assert landed_coordination_tip(repo.root, _COORD) is None


def test_the_rollback_helper_leaves_a_target_anchored_record_alone(repo: _Repo) -> None:
    record_landed_coordination_tip(repo.root, _COORD, repo.projected)
    state = _state(repo, anchor=None, coord_tip=None)
    state.pre_mutation_coord_ref = _TARGET

    rollback._clear_landed_coordination_ref(repo.root, state)

    assert landed_coordination_tip(repo.root, _COORD) == repo.projected
