"""#6653 — the terminality gate evaluates every issue-matrix row it reports on.

Before the fix, ``_issue_matrix_in_mission_rows`` kept only rows whose issue is
a discovered gating reference, and both the done-gate blocker and the merge
terminality gate returned early when no gating reference was discovered. The
gate then printed "No unresolved (in-mission/unknown) issue-matrix rows" and
``consolidate`` landed a Mission whose matrix still had an ``in-mission`` row,
even under ``merge_gates.mode: block``.

Operator decision (mission ``truthful-verdicts-and-gates-01M5WZCP``): at
``done`` every ``in-mission`` row counts, cited or not; with zero gating
references an existing matrix is evaluated whole; no matrix is a PASS that says
so, and a coordination Mission with no matrix never fails on the coordination
probe (#5222 F1). ``approved`` is unchanged.

Fixtures reuse the real-git builders of ``test_merge_gates_issue_matrix.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from specify_cli.policy.merge_gates import GateVerdict
from specify_cli.status import Lane
from specify_cli.tasks.issue_matrix_approval import _issue_matrix_approval_blocker
from tests.policy import test_merge_gates_issue_matrix as _base
from tests.policy.test_merge_gates_issue_matrix import (
    _ISSUE_KEY,
    _TERMINALITY_GATE,
    _build_coord_mission,
    _build_lanes_mission,
    _gate,
    _run_gates,
)

pytestmark = [pytest.mark.unit, pytest.mark.git_repo]

_UNCITED = "#5678"
_NO_REFS_SPEC = "# Spec\n\nNo issue references here.\n"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    _base._init_git_repo(r)
    return r


class TestUncitedInMissionRow:
    def test_block_mode_fails_and_names_the_uncited_row(self, repo: Path) -> None:
        mission_slug = _build_lanes_mission(repo, mid8="01M6653A", primary_matrix={_ISSUE_KEY: "fixed", _UNCITED: "in-mission"})

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.FAIL, gate.details
        assert gate.blocking is True
        assert _UNCITED in gate.details
        assert overall_pass is False

    def test_warn_mode_warns_without_blocking(self, repo: Path) -> None:
        mission_slug = _build_lanes_mission(repo, mid8="01M6653B", primary_matrix={_ISSUE_KEY: "fixed", _UNCITED: "in-mission"})

        overall_pass, gates = _run_gates(repo, mission_slug, mode="warn")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.FAIL
        assert gate.blocking is False
        assert overall_pass is True

    def test_done_blocker_names_the_row_but_approved_accepts_it(self, repo: Path) -> None:
        mission_slug = _build_lanes_mission(repo, mid8="01M6653C", primary_matrix={_ISSUE_KEY: "fixed", _UNCITED: "in-mission"})
        feature_dir = repo / "kitty-specs" / mission_slug

        at_done = _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.DONE)
        at_approved = _issue_matrix_approval_blocker(feature_dir, target_lane=Lane.APPROVED)

        assert at_done is not None and _UNCITED in at_done
        assert at_approved is None

    def test_terminal_verdicts_on_every_row_still_pass(self, repo: Path) -> None:
        """Positive control on the same two-row fixture."""
        mission_slug = _build_lanes_mission(repo, mid8="01M6653D", primary_matrix={_ISSUE_KEY: "fixed", _UNCITED: "not-applicable"})

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")

        assert _gate(gates, _TERMINALITY_GATE).verdict == GateVerdict.PASS
        assert overall_pass is True


class TestZeroGatingReferencesWithAMatrix:
    def test_lanes_mission_in_mission_row_fails(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_base, "_GATING_SPEC_TEXT", _NO_REFS_SPEC)
        mission_slug = _build_lanes_mission(repo, mid8="01M6653E", primary_matrix={_UNCITED: "in-mission"})

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.FAIL, gate.details
        assert _UNCITED in gate.details
        assert overall_pass is False

    def test_lanes_mission_unknown_row_fails(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_base, "_GATING_SPEC_TEXT", _NO_REFS_SPEC)
        mission_slug = _build_lanes_mission(repo, mid8="01M6653F", primary_matrix={_UNCITED: "unknown"})

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")

        assert _gate(gates, _TERMINALITY_GATE).verdict == GateVerdict.FAIL
        assert overall_pass is False

    def test_coord_mission_in_mission_row_at_the_coord_ref_fails(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_base, "_GATING_SPEC_TEXT", _NO_REFS_SPEC)
        mission_slug, _feature_dir = _build_coord_mission(repo, mid8="01M6653G", primary_matrix=None, coord_matrix={_UNCITED: "in-mission"})

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.FAIL, gate.details
        assert _UNCITED in gate.details
        assert overall_pass is False

    def test_one_digit_cited_issue_in_mission_fails(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The reference detector skips one-digit refs; the row still counts."""
        monkeypatch.setattr(_base, "_GATING_SPEC_TEXT", "This mission fixes the crash reported in #8.\n")
        mission_slug = _build_lanes_mission(repo, mid8="01M6653H", primary_matrix={"#8": "in-mission"})

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")

        assert _gate(gates, _TERMINALITY_GATE).verdict == GateVerdict.FAIL
        assert overall_pass is False


class TestZeroGatingReferencesWithoutAMatrix:
    def test_lanes_pass_says_there_was_nothing_to_check(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_base, "_GATING_SPEC_TEXT", _NO_REFS_SPEC)
        mission_slug = _build_lanes_mission(repo, mid8="01M6653I", primary_matrix=None)

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.PASS
        assert "no issue matrix" in gate.details.lower()
        assert "no unresolved" not in gate.details.lower()
        assert overall_pass is True

    def test_coord_mission_never_fails_on_the_probe(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """#5222 F1 kept: no matrix authored at the coord ref is not an error."""
        monkeypatch.setattr(_base, "_GATING_SPEC_TEXT", _NO_REFS_SPEC)
        mission_slug, _feature_dir = _build_coord_mission(repo, mid8="01M6653J", primary_matrix=None, coord_matrix=None)

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.PASS, gate.details
        assert overall_pass is True


class TestUnreadMatrix:
    """Review follow-up: a failed matrix read is reported as unread, never as absent."""

    @staticmethod
    def _failing_partition(monkeypatch: pytest.MonkeyPatch) -> None:
        import mission_runtime

        class _ProbeFailure(RuntimeError):
            code = "SIMULATED_PROBE_FAILURE"

        def _raise(*_args: object, **_kwargs: object) -> object:
            raise _ProbeFailure("git show timed out")

        monkeypatch.setattr(mission_runtime, "resolve_issue_matrix_partition", _raise)

    def test_zero_refs_unread_matrix_passes_and_says_it_was_not_read(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(_base, "_GATING_SPEC_TEXT", _NO_REFS_SPEC)
        mission_slug = _build_lanes_mission(repo, mid8="01M6653K", primary_matrix={_UNCITED: "in-mission"})
        self._failing_partition(monkeypatch)

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.PASS
        assert "not read" in gate.details
        assert "SIMULATED_PROBE_FAILURE" in gate.details
        assert "no issue matrix" not in gate.details.lower()
        assert overall_pass is True

    def test_gating_refs_unread_matrix_still_fails_closed(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        mission_slug = _build_lanes_mission(repo, mid8="01M6653L", primary_matrix={_ISSUE_KEY: "fixed"})
        self._failing_partition(monkeypatch)

        overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.FAIL
        assert gate.blocking is True
        assert overall_pass is False

    def test_coord_ref_without_a_matrix_is_reported_as_not_read(self, repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """#5222 F1 shape: PASS, and the text names the probe code instead of claiming absence."""
        monkeypatch.setattr(_base, "_GATING_SPEC_TEXT", _NO_REFS_SPEC)
        mission_slug, _feature_dir = _build_coord_mission(repo, mid8="01M6653M", primary_matrix=None, coord_matrix=None)

        _overall_pass, gates = _run_gates(repo, mission_slug, mode="block")
        gate = _gate(gates, _TERMINALITY_GATE)

        assert gate.verdict == GateVerdict.PASS
        assert "not read" in gate.details
