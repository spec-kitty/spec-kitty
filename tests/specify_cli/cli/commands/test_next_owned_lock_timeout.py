"""#6763 — an owned ``next`` refuses a busy decisions lock instead of crashing.

The owned advancement commits through ``_commit_owned_next_mutations``, which
takes ``decisions/index.json.lock``. Before this fix the wait used a raw
``kernel.locks.machine_file_lock`` and a timeout escaped the whole command as a
``LockAcquireTimeout`` traceback: the agent loop driving ``next`` got no
decision and no JSON document.

These rows drive the real dispatch seam. The lock is held with the same
``machine_file_lock`` helper the command uses (each acquire opens its own
descriptor, so same-process contention is real), the bounded wait is shortened,
and the fix must render the seam's ``DecisionError(LOCK_TIMEOUT)`` on the
command's own ``error_code``/``next_step`` contract.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import typer

from kernel.locks import machine_file_lock
from mission_runtime import MissionTopology, OwnedCheckout
from specify_cli.cli.commands import next_cmd
from specify_cli.decisions.service import _decisions_lock_path

pytestmark = pytest.mark.fast

_SLUG = "unit-owned-mission"


def _fact(tmp_path: Path) -> OwnedCheckout:
    """A fact over a real on-disk layout (a unit stand-in for the validator's output)."""
    repository_root = tmp_path / "repository-root"
    repository_root.mkdir()
    owned_root = tmp_path / "owned-checkout"
    mission_dir = owned_root / "kitty-specs" / _SLUG
    mission_dir.mkdir(parents=True)
    (mission_dir / "meta.json").write_text(json.dumps({"mission_type": "software-dev", "mission_id": "01M3WP19000000000000000003"}), encoding="utf-8")
    return OwnedCheckout._mint(
        repository_root=repository_root,
        owned_root=owned_root,
        mission_dir=mission_dir,
        mission_slug=_SLUG,
        topology=MissionTopology.SINGLE_BRANCH,
        write_branch="codex/owned",
    )


def _materialize_lock(fact: OwnedCheckout) -> Path:
    """Create the sidecar lock so ``runtime_lock.exists()`` is true.

    The command only guards when the decisions service has already created the
    lock; that "no lock file yet" branch must stay untouched (see the control).
    """
    lock = _decisions_lock_path(fact.mission_dir)
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_bytes(b"")
    return lock


def _stub_decision() -> SimpleNamespace:
    return SimpleNamespace(kind="step", wp_id="WP01", action="implement", step_id="S1", prompt_file=None)


def _drive_dispatch(fact: OwnedCheckout, monkeypatch: pytest.MonkeyPatch, *, json_output: bool) -> tuple[BaseException | None, list[str]]:
    """Drive ``_dispatch_advancing_mode`` with only the pre-commit steps faked."""
    printed: list[str] = []
    monkeypatch.setattr(next_cmd, "_pair_previous_lifecycle_record", lambda *a, **k: None)
    monkeypatch.setattr(next_cmd, "decide_next", lambda *a, **k: _stub_decision())
    monkeypatch.setattr(next_cmd, "_emit_mission_next_invoked", lambda *a, **k: None)
    monkeypatch.setattr(next_cmd, "_write_issuance_lifecycle_record", lambda *a, **k: None)
    monkeypatch.setattr(next_cmd, "_print_decision", lambda *_a, **_k: printed.append("printed"))

    raised: BaseException | None = None
    try:
        next_cmd._dispatch_advancing_mode(
            "claude",
            _SLUG,
            "success",
            fact.repository_root,
            json_output,
            None,
            None,
            owned=fact,
        )
    except BaseException as exc:  # noqa: BLE001 - the rows assert on WHAT escaped
        raised = exc
    return raised, printed


def _hold(lock: Path) -> Any:
    return machine_file_lock(lock, blocking=True, timeout_s=5.0)


def test_owned_next_lock_timeout_is_a_refusal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Red on the pre-fix tree: ``LockAcquireTimeout`` escaped with no document."""
    fact = _fact(tmp_path)
    lock = _materialize_lock(fact)
    monkeypatch.setattr("specify_cli.decisions.service._LOCK_ACQUIRE_TIMEOUT_S", 0.2)

    with _hold(lock):
        raised, printed = _drive_dispatch(fact, monkeypatch, json_output=True)

    assert isinstance(raised, typer.Exit), repr(raised)
    assert raised.exit_code == 1
    payload = json.loads(capsys.readouterr().out)
    assert payload["result"] == "error"
    assert payload["error_code"] == "DECISION_LOCK_TIMEOUT"
    assert str(lock) in payload["error"]
    assert payload["lock_path"] == str(lock)
    assert "retry" in payload["next_step"].lower()
    assert "already recorded" in payload["next_step"].lower()
    assert payload["spec_kitty_version"]
    assert printed == [], "a refused commit must not print a decision"


def test_owned_next_lock_timeout_refusal_human_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """The same refusal in the other output mode: ``Error:`` + ``Next:`` on stderr."""
    fact = _fact(tmp_path)
    lock = _materialize_lock(fact)
    monkeypatch.setattr("specify_cli.decisions.service._LOCK_ACQUIRE_TIMEOUT_S", 0.2)

    with _hold(lock):
        raised, printed = _drive_dispatch(fact, monkeypatch, json_output=False)

    assert isinstance(raised, typer.Exit), repr(raised)
    assert raised.exit_code == 1
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "DECISION_LOCK_TIMEOUT" in captured.err
    assert str(lock) in captured.err
    assert "Next:" in captured.err
    assert "retry" in captured.err.lower()
    assert printed == []


def test_owned_next_with_a_free_lock_still_commits_and_prints(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Positive control on the SAME fixture: a free lock commits and prints."""
    fact = _fact(tmp_path)
    _materialize_lock(fact)
    monkeypatch.setattr("specify_cli.decisions.service._LOCK_ACQUIRE_TIMEOUT_S", 0.2)
    committed: list[OwnedCheckout] = []
    monkeypatch.setattr(next_cmd, "_commit_owned_next_changeset", lambda owned, _lock: committed.append(owned))

    raised, printed = _drive_dispatch(fact, monkeypatch, json_output=True)

    # A healthy advancement does not exit: the decision is returned to the
    # caller (only ``kind == "blocked"`` exits 1). What this row pins is that
    # the guarded commit RAN and the decision was printed afterwards.
    assert raised is None, repr(raised)
    assert committed == [fact], "a free lock must still commit the advancement"
    assert printed == ["printed"], "a free lock must still print the decision"
