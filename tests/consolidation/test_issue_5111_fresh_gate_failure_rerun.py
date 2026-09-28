"""#5111 — a fresh consolidate that fails at a merge gate must not wedge the re-run.

A fresh ``spec-kitty consolidate`` persists ``state.json`` in
``_load_or_create_merge_state`` (``consolidation/resolve.py``) BEFORE
``_phase_gates_and_state`` evaluates the merge gates, but the FR-012
reconciliation marker used to be written only afterwards, inside
``_capture_reconciliation_claim``. A gate failure in that window ("Merge gates
failed") left a marker-less ``state.json`` behind; the operator's next plain
``spec-kitty consolidate`` loaded it as a resume and was refused as a
"pre-fix in-flight merge state" (``detect_legacy_in_flight_state``) — a wedge
with no mutation ever having happened.

These tests drive the real ``spec-kitty consolidate`` typer command. Only the
merge-gate *verdict* is patched (failing on the first run, passing on the
re-run); the state/marker ordering under test runs unpatched. The downstream
mutating phases are isolated by the shared #4764 harness mocks, and reaching
the (mocked) bake proves the re-run went through the full gate path.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

from specify_cli import app as cli_app
from specify_cli.consolidation.reconciliation import detect_legacy_in_flight_state
from specify_cli.consolidation.resolve import _load_or_create_merge_state
from specify_cli.consolidation.state import (
    ConsolidationState,
    clear_state,
    get_state_path,
    load_state,
    save_state,
)
from specify_cli.consolidation.workspace import get_merge_runtime_dir
from tests.consolidation.test_issue_4764_terminus_safety import (
    MISSION_ID,
    MISSION_SLUG,
    _approved_event,
    _bootstrap_coord_mission,
    _init_git_repo,
    _merge_external_mocks,
)

pytestmark = [pytest.mark.integration, pytest.mark.git_repo, pytest.mark.non_sandbox]

_PRE_FIX_REFUSAL = "pre-fix in-flight merge state"
_MARKER_FILENAME = "reconciliation.post-fix"


def _gate_eval(*, passing: bool) -> MagicMock:
    gate = MagicMock()
    gate.verdict = "pass" if passing else "fail"
    gate.blocking = not passing
    gate.gate_name = "evidence"
    gate.details = "all WPs approved" if passing else "synthetic blocking failure"
    evaluation = MagicMock()
    evaluation.overall_pass = passing
    evaluation.gates = [gate]
    return evaluation


def _consolidate(
    repo: Path,
    monkeypatch: pytest.MonkeyPatch,
    *args: str,
    gates_pass: bool,
    on_bake: Callable[..., None] | None = None,
) -> tuple[int, str, dict[str, MagicMock]]:
    monkeypatch.chdir(repo)
    with _merge_external_mocks() as mocks:
        mocks["gates"].return_value = _gate_eval(passing=gates_pass)
        if on_bake is not None:
            mocks["bake"].side_effect = on_bake
        result = CliRunner().invoke(
            cli_app,
            ["consolidate", "--mission", MISSION_SLUG, "--keep-branch", "--keep-worktree", "--yes", *args],
        )
    return result.exit_code, result.output, mocks


@pytest.fixture
def approved_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    _init_git_repo(repo)
    _bootstrap_coord_mission(repo, wp_event=_approved_event())
    return repo


def _marker_path(repo: Path) -> Path:
    return get_merge_runtime_dir(MISSION_ID, repo) / _MARKER_FILENAME


def test_5111_fresh_gate_failure_then_plain_rerun_runs_full_gate_path(approved_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Acceptance (1): fail at a gate, re-run plainly -> full gate path, no pre-fix refusal."""
    code1, out1, _ = _consolidate(approved_repo, monkeypatch, gates_pass=False)
    assert code1 == 1, out1
    assert "Merge gates failed" in out1, out1

    code2, out2, mocks2 = _consolidate(approved_repo, monkeypatch, gates_pass=True)

    assert _PRE_FIX_REFUSAL not in out2, f"a plain re-run after a fresh gate failure must not be refused as a pre-fix in-flight merge state:\n{out2}"
    assert "Detected interrupted merge" not in out2, f"a gate failure mutated nothing; the re-run must be fresh, not an auto-resume:\n{out2}"
    assert mocks2["gates"].called, "the re-run must evaluate the merge gates again"
    assert mocks2["bake"].called, f"the re-run must proceed past the gates and claim capture:\n{out2}"
    assert code2 == 0, out2


def test_5111_fresh_gate_failure_leaves_no_transaction_record(approved_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A pre-mutation exit clears the fresh run's own state AND marker ("the mission is unchanged")."""
    code, out, _ = _consolidate(approved_repo, monkeypatch, gates_pass=False)
    assert code == 1, out

    assert not get_state_path(approved_repo, MISSION_ID).exists(), "a gate failure left a stale state.json behind"
    assert not _marker_path(approved_repo).exists(), "a gate failure left an orphan reconciliation marker behind"


def test_5111_rerun_after_gate_failure_honours_its_own_strategy(approved_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """The re-run is fresh, so the strategy it runs is the one it persists (no F14-class split).

    Attempt 1 persists ``squash`` and fails at a gate; attempt 2 passes ``--strategy merge``.
    Had attempt 1's record survived, attempt 2 would auto-resume and keep ``squash`` on disk
    while executing ``merge``.
    """
    code1, out1, _ = _consolidate(approved_repo, monkeypatch, "--strategy", "squash", gates_pass=False)
    assert code1 == 1, out1

    persisted_at_bake: list[str | None] = []

    def _record_persisted_strategy(*_args: object, **_kwargs: object) -> None:
        state = load_state(approved_repo, MISSION_ID)
        persisted_at_bake.append(None if state is None else str(state.strategy))

    code2, out2, _ = _consolidate(approved_repo, monkeypatch, "--strategy", "merge", gates_pass=True, on_bake=_record_persisted_strategy)

    assert code2 == 0, out2
    assert persisted_at_bake == ["merge"], persisted_at_bake


def test_5111_fresh_state_is_never_on_disk_without_its_marker(tmp_path: Path) -> None:
    """The crash-proof ordering invariant: a fresh transaction record is created marker-first."""
    state, is_resume = _load_or_create_merge_state(
        main_repo=tmp_path,
        mission_slug=MISSION_SLUG,
        canonical_id=MISSION_ID,
        target_branch="main",
        wp_order=["WP01"],
        push_requested=False,
    )

    assert is_resume is False
    assert get_state_path(tmp_path, MISSION_ID).exists()
    assert _marker_path(tmp_path).exists(), "a fresh state.json was persisted without its reconciliation marker"
    assert detect_legacy_in_flight_state(tmp_path, MISSION_ID, is_resume=True) is None


def test_5111_genuinely_pre_fix_state_is_still_refused(tmp_path: Path) -> None:
    """FR-003: a LOADED marker-less state is never stamped by the loader; FR-012 still refuses it."""
    save_state(ConsolidationState(mission_id=MISSION_ID, mission_slug=MISSION_SLUG, target_branch="main", wp_order=["WP01"]), tmp_path)

    _state, is_resume = _load_or_create_merge_state(
        main_repo=tmp_path,
        mission_slug=MISSION_SLUG,
        canonical_id=MISSION_ID,
        target_branch="main",
        wp_order=["WP01"],
        push_requested=False,
    )

    assert is_resume is True
    assert not _marker_path(tmp_path).exists()
    assert detect_legacy_in_flight_state(tmp_path, MISSION_ID, is_resume=True) is not None


def test_5111_legacy_migration_drops_an_orphan_canonical_marker(tmp_path: Path) -> None:
    """A migrated (pre-fix) state must not inherit a stale marker sitting in the canonical dir."""
    legacy_key = MISSION_SLUG
    save_state(ConsolidationState(mission_id=legacy_key, mission_slug=MISSION_SLUG, target_branch="main", wp_order=["WP01"]), tmp_path)
    orphan = _marker_path(tmp_path)
    orphan.parent.mkdir(parents=True, exist_ok=True)
    orphan.write_text("left behind by a pre-#5111 --abort\n", encoding="utf-8")

    state, is_resume = _load_or_create_merge_state(
        main_repo=tmp_path,
        mission_slug=MISSION_SLUG,
        canonical_id=MISSION_ID,
        target_branch="main",
        wp_order=["WP01"],
        push_requested=False,
    )

    assert is_resume is True
    assert state.mission_id == MISSION_ID
    assert not orphan.exists(), "the orphan canonical marker would vouch for a migrated pre-fix state"
    assert detect_legacy_in_flight_state(tmp_path, MISSION_ID, is_resume=True) is not None


def test_5111_abort_clears_state_and_marker(approved_repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``--abort`` drops the marker together with the state (e.g. residue of a hard-killed run)."""
    _load_or_create_merge_state(
        main_repo=approved_repo,
        mission_slug=MISSION_SLUG,
        canonical_id=MISSION_ID,
        target_branch="main",
        wp_order=["WP01"],
        push_requested=False,
    )
    assert _marker_path(approved_repo).exists(), "precondition: a marked transaction record is on disk"

    monkeypatch.chdir(approved_repo)
    abort = CliRunner().invoke(cli_app, ["consolidate", "--mission", MISSION_SLUG, "--abort"])
    assert abort.exit_code == 0, abort.output

    assert not get_state_path(approved_repo, MISSION_ID).exists()
    assert not _marker_path(approved_repo).exists(), (
        "--abort left the reconciliation marker behind; a later hand-built or pre-fix state would then be mistaken for a post-fix transaction"
    )


def test_5111_clear_state_removes_the_marker_with_the_state(tmp_path: Path) -> None:
    """Unit pin: ``clear_state(repo, mission_id)`` is the single transaction-record clear."""
    runtime_dir = get_merge_runtime_dir(MISSION_ID, tmp_path)
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "state.json").write_text("{}", encoding="utf-8")
    (runtime_dir / _MARKER_FILENAME).write_text("x\n", encoding="utf-8")

    assert clear_state(tmp_path, MISSION_ID) is True
    assert not (runtime_dir / "state.json").exists()
    assert not (runtime_dir / _MARKER_FILENAME).exists()


def test_5111_clear_state_without_state_still_removes_an_orphan_marker(tmp_path: Path) -> None:
    """An orphan marker (no state) is dropped too, but the return value stays 'no state cleared'."""
    runtime_dir = get_merge_runtime_dir(MISSION_ID, tmp_path)
    runtime_dir.mkdir(parents=True)
    (runtime_dir / _MARKER_FILENAME).write_text("x\n", encoding="utf-8")

    assert clear_state(tmp_path, MISSION_ID) is False
    assert not (runtime_dir / _MARKER_FILENAME).exists()
