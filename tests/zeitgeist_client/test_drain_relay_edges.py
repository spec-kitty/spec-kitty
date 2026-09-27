"""Drain gates every relay network edge before any network attempt, thread
spawn, or credential read.

Drain is **on** by default through the root autouse fixture in
``tests/conftest.py``; a test opts into drain-off with the ``drain_off``
fixture. This file proves three edges:

* ``transport.ZeitgeistClient.offer()`` returns the new
  ``OfferOutcome.DRAIN_DISABLED`` before any network attempt (FR-004).
* ``filtered_stream.FilteredStream.seed_from_snapshot``/``watch`` raise
  ``hosted_posture.DrainDisabled`` before an opener is built (FR-005).
* ``history.read_history`` raises ``hosted_posture.DrainDisabled`` before
  ``credentials.load`` is even consulted (NFR-003's "0 credential-store
  reads" for this file).

Each edge also gets a drain-ON parity assertion: the existing behaviour is
unaffected when drain is enabled (the default, root-fixture posture).
"""

from __future__ import annotations

from typing import Any

import pytest

from specify_cli.core import hosted_posture
from specify_cli.zeitgeist_client import budget, filtered_stream, history, operability, transport

pytestmark = pytest.mark.fast


def _client_config(**overrides: object) -> transport.ClientConfig:
    base: dict[str, object] = {
        "relay_url": "http://127.0.0.1:1",
        "token": "test-token",  # noqa: S106 - placeholder identity, never a real credential
        "harness": "claude-code",
        "session_id": "sess-1",
        "agent_id": "agent-1",
        "repo": "spec-kitty",
        "branch": "main",
    }
    base.update(overrides)
    return transport.ClientConfig(**base)


def _stream_config(**overrides: object) -> filtered_stream.TeamStreamConfig:
    base: dict[str, object] = {
        "relay_url": "http://127.0.0.1:1",
        "capability_credential": "cap-token",  # noqa: S106
    }
    base.update(overrides)
    return filtered_stream.TeamStreamConfig(**base)


def _forbid(monkeypatch: pytest.MonkeyPatch, target: Any, name: str) -> None:
    """Patch ``target.<name>`` to raise if ever called — the "zero calls"
    proof required on every gated edge."""

    def _raise(*_args: object, **_kwargs: object) -> Any:
        raise AssertionError(f"{target}.{name} must not be called when drain is off")

    monkeypatch.setattr(target, name, _raise)


# --- transport.offer() -------------------------------------------------


def test_offer_returns_drain_disabled_with_zero_elapsed_and_no_network_attempt(drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid(monkeypatch, budget, "run_with_deadline")
    _forbid(monkeypatch, budget.NoRedirects, "build")
    client = transport.ZeitgeistClient(_client_config())

    result = client.offer("presence.publish", {"kind": "command"})

    assert result.outcome is transport.OfferOutcome.DRAIN_DISABLED
    assert result.elapsed_s == 0.0
    # Never misclassified as an unreachable-relay drop (F-1).
    assert result.outcome is not transport.OfferOutcome.DROPPED_UNREACHABLE


def test_presence_returns_drain_disabled_under_drain_off(drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid(monkeypatch, budget, "run_with_deadline")
    client = transport.ZeitgeistClient(_client_config())

    result = client.presence("command")

    assert result.outcome is transport.OfferOutcome.DRAIN_DISABLED


def test_offer_drain_on_parity_reaches_the_network_path_unchanged(monkeypatch: pytest.MonkeyPatch) -> None:
    """Drain is on by default (root autouse fixture) — offer() must reach its
    normal network path exactly as before this WP."""

    def _fake_run_with_deadline(_fn: Any, *, deadline_s: float) -> budget.DeadlineOutcome[tuple[int, bytes]]:
        return budget.DeadlineOutcome(completed=True, result=(200, b"{}"), error=None, elapsed_s=0.01)

    monkeypatch.setattr(budget, "run_with_deadline", _fake_run_with_deadline)
    client = transport.ZeitgeistClient(_client_config())

    result = client.offer("presence.publish", {"kind": "command"})

    assert result.outcome is transport.OfferOutcome.SENT


# --- filtered_stream.seed_from_snapshot() / watch() ---------------------


def test_seed_from_snapshot_raises_drain_disabled_before_building_an_opener(drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid(monkeypatch, budget.NoRedirects, "build")
    stream = filtered_stream.FilteredStream(_stream_config())

    with pytest.raises(hosted_posture.DrainDisabled):
        stream.seed_from_snapshot(timeout_s=1.0)


def test_watch_raises_drain_disabled_on_first_advance_before_building_an_opener(drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid(monkeypatch, budget.NoRedirects, "build")
    stream = filtered_stream.FilteredStream(_stream_config())

    generator = stream.watch(idle_timeout_s=1.0)  # constructs the generator only, runs no body
    with pytest.raises(hosted_posture.DrainDisabled):
        next(generator)  # the gate must fire on the FIRST next(), not at construction


def test_seed_from_snapshot_drain_on_parity_still_builds_an_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    class _FakeOpener:
        def open(self, *_args: object, **_kwargs: object) -> Any:
            raise urllib_http_error()

    def _fake_build() -> Any:
        calls.append(True)
        return _FakeOpener()

    monkeypatch.setattr(budget.NoRedirects, "build", staticmethod(_fake_build))
    stream = filtered_stream.FilteredStream(_stream_config())

    with pytest.raises(Exception):  # noqa: B017, PT011 - only proving the gate did not fire; the HTTP fault is incidental
        stream.seed_from_snapshot(timeout_s=1.0)

    assert calls == [True]


def test_watch_drain_on_parity_still_builds_an_opener(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def _fake_build() -> Any:
        calls.append(True)

        class _FakeOpener:
            def open(self, *_args: object, **_kwargs: object) -> Any:
                raise urllib_http_error()

        return _FakeOpener()

    monkeypatch.setattr(budget.NoRedirects, "build", staticmethod(_fake_build))
    stream = filtered_stream.FilteredStream(_stream_config())

    generator = stream.watch(idle_timeout_s=1.0)
    with pytest.raises(Exception):  # noqa: B017, PT011 - only proving the gate did not fire
        next(generator)

    assert calls == [True]


def urllib_http_error() -> Exception:
    import urllib.error

    return urllib.error.URLError("no server listening (drain-on parity double)")


# --- history.read_history() ---------------------------------------------


def test_read_history_raises_drain_disabled_before_credentials_load(drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
    _forbid(monkeypatch, history.credentials, "load")
    _forbid(monkeypatch, budget, "run_with_deadline")
    _forbid(monkeypatch, budget.NoRedirects, "build")

    with pytest.raises(hosted_posture.DrainDisabled):
        history.read_history("host/owner/repo")


def test_read_history_drain_off_fires_before_argument_validation(drain_off: None, monkeypatch: pytest.MonkeyPatch) -> None:
    """The gate is the honest, cheap refusal — a drain-off caller never needs
    valid arguments to get it (an invalid window_s would otherwise raise
    ``ValueError`` first)."""
    _forbid(monkeypatch, history.credentials, "load")

    with pytest.raises(hosted_posture.DrainDisabled):
        history.read_history("host/owner/repo", window_s=-1)


def test_read_history_drain_on_parity_still_consults_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[bool] = []

    def _fake_load(*, repo: str) -> None:
        calls.append(True)
        return None

    monkeypatch.setattr(history.credentials, "load", _fake_load)

    from specify_cli.zeitgeist_client import subscription

    with pytest.raises(subscription.NotCheckedOut):
        history.read_history("host/owner/repo")

    assert calls == [True]


# --- operability.timeout_drill / DropSignal (D8) -------------------------


def test_timeout_drill_reports_a_distinct_skip_under_drain_off(drain_off: None) -> None:
    """A drain-off canary never exercised the unreachable target, so it must
    report neither a vacuous "pass" nor a misleading "fail"."""
    result = operability.timeout_drill()

    assert result.outcome == "skipped: drain off"
    assert result.offer.outcome == transport.OfferOutcome.DRAIN_DISABLED.value


def test_drop_signal_never_reports_drain_disabled_as_a_dropped_frame() -> None:
    """D8: OfferOutcome.DRAIN_DISABLED must never be in operability's
    _DROPPED_OUTCOMES set -- a clean, expected skip is not a lost frame."""
    fake_result = transport.OfferResult(outcome=transport.OfferOutcome.DRAIN_DISABLED, request_id="r1", elapsed_s=0.0)

    drop_sig = operability.DropSignal.from_result(fake_result)

    assert drop_sig.dropped is False
    assert drop_sig.reason is None
