"""Focused unit tests for the owned-mode mark-status recovery reconstruction.

#3865: the owned ``except`` in ``_do_mark_status`` previously inlined the
cause-chain walk, the two ``git show`` reconstructions and the event-id
diffing; those branches had only end-to-end coverage
(``tests/integration/test_owned_checkout_mark_status.py``). They live in
``_reconstruct_applied_events`` now, and this file exercises every branch
directly with a scripted ``subprocess.run`` — no real git, no CLI.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from mission_runtime import OwnedCheckout

from specify_cli.cli.commands.agent import tasks_mark_status as ms
from specify_cli.cli.commands.agent.tasks_mark_status import _reconstruct_applied_events
from tests._owned_fixtures import mint_test_fact

pytestmark = [pytest.mark.unit, pytest.mark.fast]

_RECOVERY_SHA = "f" * 40
_REL_EVENTS = "kitty-specs/demo/status.events.jsonl"


class _RecoveryFailure(RuntimeError):
    """Exception shape the transactional emit stamps its recovery commit on."""

    def __init__(self, commit_sha: str | None) -> None:
        super().__init__("injected recovery failure after commit")
        self.commit_sha = commit_sha


@pytest.fixture
def owned(tmp_path: Path) -> OwnedCheckout:
    # Owned checkout must be a distinct root from the repository root
    # (OwnedCheckout.__post_init__ invariant); the mission dir stays under
    # root/kitty-specs/<slug> as before.
    primary = tmp_path / "primary"
    root = tmp_path / "owned"
    mission = root / "kitty-specs" / "demo"
    mission.mkdir(parents=True)
    return mint_test_fact(repository_root=primary, owned_root=root, mission_dir=mission, mission_slug="demo", write_branch="kitty/demo")


@pytest.fixture
def events_path(owned: OwnedCheckout) -> Path:
    return owned.mission_dir / "status.events.jsonl"


def _event(event_id: str, wp_id: str = "WP01") -> str:
    return json.dumps({"event_id": event_id, "wp_id": wp_id})


def _fake_git(
    monkeypatch: pytest.MonkeyPatch,
    blobs: dict[str, str],
    failures: frozenset[str] = frozenset(),
) -> list[tuple[list[str], dict[str, object]]]:
    """Script ``git show`` inside the module; record every invocation."""
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(cmd: list[str], **kwargs: object) -> SimpleNamespace:
        calls.append((cmd, dict(kwargs)))
        ref = cmd[2]
        if ref in failures:
            return SimpleNamespace(returncode=128, stdout="", stderr="fatal: bad object")
        return SimpleNamespace(returncode=0, stdout=blobs.get(ref, ""), stderr="")

    monkeypatch.setattr(ms, "subprocess", SimpleNamespace(run=run))
    return calls


def test_no_commit_sha_on_chain_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
) -> None:
    calls = _fake_git(monkeypatch, {})

    detected = _reconstruct_applied_events(owned, RuntimeError("no sha rides this"), events_path)

    assert detected == []
    assert calls == []


@pytest.mark.parametrize("commit_sha", [None, ""])
def test_empty_commit_sha_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
    commit_sha: str | None,
) -> None:
    calls = _fake_git(monkeypatch, {})

    detected = _reconstruct_applied_events(owned, _RecoveryFailure(commit_sha), events_path)

    assert detected == []
    assert calls == []


def test_non_string_commit_sha_is_ignored(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
) -> None:
    class NonStringSha(RuntimeError):
        commit_sha: int = 123

    calls = _fake_git(monkeypatch, {})

    detected = _reconstruct_applied_events(owned, NonStringSha("bogus stamp"), events_path)

    assert detected == []
    assert calls == []


def test_diff_reports_only_rows_new_in_the_recovery_commit(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
) -> None:
    committed = f"{_event('ev-parent')}\n{_event('ev-recovery', wp_id='WP02')}\n"
    calls = _fake_git(
        monkeypatch,
        {f"{_RECOVERY_SHA}:{_REL_EVENTS}": committed, f"{_RECOVERY_SHA}^:{_REL_EVENTS}": f"{_event('ev-parent')}\n"},
    )

    detected = _reconstruct_applied_events(owned, _RecoveryFailure(_RECOVERY_SHA), events_path)

    assert detected == [{"event_id": "ev-recovery", "wp_id": "WP02"}]
    assert [cmd for cmd, _ in calls] == [
        ["git", "show", f"{_RECOVERY_SHA}:{_REL_EVENTS}"],
        ["git", "show", f"{_RECOVERY_SHA}^:{_REL_EVENTS}"],
    ]
    assert all(kwargs["cwd"] == owned.owned_root for _, kwargs in calls)


def test_sha_on_explicit_cause_is_found(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
) -> None:
    outer = RuntimeError("wrapped the stamped failure")
    outer.__cause__ = _RecoveryFailure(_RECOVERY_SHA)
    _fake_git(monkeypatch, {f"{_RECOVERY_SHA}:{_REL_EVENTS}": f"{_event('ev-recovery')}\n"})

    detected = _reconstruct_applied_events(owned, outer, events_path)

    assert [row["event_id"] for row in detected] == ["ev-recovery"]


def test_sha_on_implicit_context_is_found(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
) -> None:
    outer = RuntimeError("handled the stamped failure during unwinding")
    outer.__context__ = _RecoveryFailure(_RECOVERY_SHA)
    _fake_git(monkeypatch, {f"{_RECOVERY_SHA}:{_REL_EVENTS}": f"{_event('ev-recovery')}\n"})

    detected = _reconstruct_applied_events(owned, outer, events_path)

    assert [row["event_id"] for row in detected] == ["ev-recovery"]


def test_cycle_in_cause_chain_terminates_without_sha(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
) -> None:
    first = RuntimeError("first")
    second = RuntimeError("second")
    first.__cause__ = second
    second.__context__ = first
    calls = _fake_git(monkeypatch, {})

    detected = _reconstruct_applied_events(owned, first, events_path)

    assert detected == []
    assert calls == []


def test_parent_without_events_blob_reports_all_committed_rows(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
) -> None:
    committed = f"{_event('ev-first')}\n{_event('ev-second')}\n"
    _fake_git(
        monkeypatch,
        {f"{_RECOVERY_SHA}:{_REL_EVENTS}": committed},
        failures=frozenset({f"{_RECOVERY_SHA}^:{_REL_EVENTS}"}),
    )

    detected = _reconstruct_applied_events(owned, _RecoveryFailure(_RECOVERY_SHA), events_path)

    assert [row["event_id"] for row in detected] == ["ev-first", "ev-second"]


def test_missing_committed_blob_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
) -> None:
    _fake_git(
        monkeypatch,
        {},
        failures=frozenset({f"{_RECOVERY_SHA}:{_REL_EVENTS}"}),
    )

    detected = _reconstruct_applied_events(owned, _RecoveryFailure(_RECOVERY_SHA), events_path)

    assert detected == []


@pytest.mark.parametrize("side", ["committed", "parent"])
def test_malformed_log_row_suppresses_detection(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
    side: str,
) -> None:
    good = f"{_event('ev-parent')}\n"
    blobs = {
        f"{_RECOVERY_SHA}:{_REL_EVENTS}": f"{good}not-json\n",
        f"{_RECOVERY_SHA}^:{_REL_EVENTS}": good,
    }
    if side == "parent":
        blobs[f"{_RECOVERY_SHA}^:{_REL_EVENTS}"] = "not-json\n"
    _fake_git(monkeypatch, blobs)

    detected = _reconstruct_applied_events(owned, _RecoveryFailure(_RECOVERY_SHA), events_path)

    assert detected == []


@pytest.mark.parametrize("side", ["committed", "parent"])
def test_log_row_missing_event_id_suppresses_detection(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    events_path: Path,
    side: str,
) -> None:
    keyless = json.dumps({"wp_id": "WP01"}) + "\n"
    blobs = {
        f"{_RECOVERY_SHA}:{_REL_EVENTS}": keyless,
        f"{_RECOVERY_SHA}^:{_REL_EVENTS}": "",
    }
    if side == "parent":
        blobs[f"{_RECOVERY_SHA}^:{_REL_EVENTS}"] = keyless
        blobs[f"{_RECOVERY_SHA}:{_REL_EVENTS}"] = f"{_event('ev-recovery')}\n"
    _fake_git(monkeypatch, blobs)

    detected = _reconstruct_applied_events(owned, _RecoveryFailure(_RECOVERY_SHA), events_path)

    assert detected == []


def test_unknown_events_path_returns_empty(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
) -> None:
    calls = _fake_git(monkeypatch, {})

    detected = _reconstruct_applied_events(owned, _RecoveryFailure(_RECOVERY_SHA), None)

    assert detected == []
    assert calls == []


def test_events_path_outside_owned_root_propagates(
    monkeypatch: pytest.MonkeyPatch,
    owned: OwnedCheckout,
    tmp_path: Path,
) -> None:
    _fake_git(monkeypatch, {})
    outside = tmp_path.parent / "outside-owned-root" / "status.events.jsonl"

    with pytest.raises(ValueError):
        _reconstruct_applied_events(owned, _RecoveryFailure(_RECOVERY_SHA), outside)
