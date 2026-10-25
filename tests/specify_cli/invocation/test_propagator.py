"""Tests for InvocationSaaSPropagator (WP07).

Verifies:
- Non-blocking submit() (< 50ms even with slow mock)
- No-op when _get_saas_client returns None (no error log written)
- Error logged to propagation-errors.jsonl on SaaS failure
- invocation_id present in the event dict passed to client.send_event
- _log_propagation_error swallows OSError (disk full)

Every test drives a client in through the ``_get_saas_client`` seam directly:
with nothing registered (production reality since issue #5 deleted the sync
transport) propagation is a permanent no-op and none of the envelope behaviour
below would execute at all.
"""

from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import MagicMock, patch

import pytest

from specify_cli.invocation.propagator import (
    InvocationSaaSPropagator,
    PROPAGATION_ERRORS_PATH,
    _PENDING_SEND_TASKS,
    _log_propagation_error,
    _propagate_one,
)
from specify_cli.invocation.record import OpCompletedEvent, OpStartedEvent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.unit, pytest.mark.fast]


def make_started_record() -> OpStartedEvent:
    return OpStartedEvent(
        invocation_id="01KPQRX2EVGMRVB4Q1JQBAZJV3",
        profile_id="implementer-fixture",
        action="implement",
        request_text="implement the feature",
        actor="claude",
        mode_of_work="task_execution",
        governance_context_hash="abcdef0123456789",
        governance_context_available=True,
        started_at="2026-04-21T10:00:00Z",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.performance
def test_propagator_non_blocking(tmp_path: pytest.TempPathFactory) -> None:
    """submit() returns in < 50ms even if the SaaS call takes 500ms."""
    record = make_started_record()
    propagator = InvocationSaaSPropagator(tmp_path)

    with patch("specify_cli.invocation.propagator._get_saas_client") as mock_client_factory:
        mock_client = MagicMock()

        def slow_send(*args: object, **kwargs: object) -> None:  # noqa: ARG001
            time.sleep(0.5)

        mock_client.send_event.side_effect = slow_send
        mock_client_factory.return_value = mock_client

        start = time.monotonic()
        propagator.submit(record)
        elapsed = time.monotonic() - start

    assert elapsed < 0.05, f"submit() blocked for {elapsed:.3f}s"
    # Clean up: shut down background thread to avoid leaking threads across tests
    propagator._executor.shutdown(wait=False, cancel_futures=True)


def test_propagator_no_op_when_no_token(tmp_path: pytest.TempPathFactory) -> None:
    """When _get_saas_client returns None, no errors and no log entry."""
    record = make_started_record()

    with patch("specify_cli.invocation.propagator._get_saas_client", return_value=None):
        _propagate_one(record, tmp_path)

    error_log = tmp_path / PROPAGATION_ERRORS_PATH
    assert not error_log.exists(), "Error log should not exist when client is None"


def test_propagator_logs_error_on_saas_failure(tmp_path: pytest.TempPathFactory) -> None:
    """SaaS failure (e.g. RuntimeError) → error logged to propagation-errors.jsonl, no exception."""
    record = make_started_record()

    with patch("specify_cli.invocation.propagator._get_saas_client") as mock_factory:
        mock_client = MagicMock()
        mock_client.send_event.side_effect = RuntimeError("SaaS returned 503")
        mock_factory.return_value = mock_client

        # Must not raise
        _propagate_one(record, tmp_path)

    error_log = tmp_path / PROPAGATION_ERRORS_PATH
    assert error_log.exists(), "propagation-errors.jsonl should be created on SaaS failure"

    entries = [json.loads(line) for line in error_log.read_text().splitlines() if line.strip()]
    assert len(entries) == 1
    assert "503" in entries[0]["error"]
    assert entries[0]["invocation_id"] == record.invocation_id


def test_propagator_sends_invocation_id_in_event_dict(tmp_path: pytest.TempPathFactory) -> None:
    """invocation_id is included in the event dict passed to client.send_event."""
    record = make_started_record()
    captured: list[dict[str, object]] = []

    with patch("specify_cli.invocation.propagator._get_saas_client") as mock_factory:
        mock_client = MagicMock()

        async def mock_send(event_dict: dict[str, object]) -> None:
            captured.append(event_dict)

        mock_client.send_event = mock_send
        mock_factory.return_value = mock_client

        # Must not raise
        _propagate_one(record, tmp_path)

    # Verify no error was logged (success path)
    error_log = tmp_path / PROPAGATION_ERRORS_PATH
    assert not error_log.exists(), "No error log should be written on success"

    # The invocation_id must appear in the captured event dict
    assert len(captured) == 1
    assert captured[0]["invocation_id"] == record.invocation_id
    assert captured[0]["event_type"] == "ProfileInvocationStarted"


def test_started_envelope_field_set_follows_v2_contract(tmp_path: pytest.TempPathFactory) -> None:
    """Started envelope is built 1:1 from OpStartedEvent (op-record-events.md).

    None fields (router_confidence, mission_id, wp_id) are omitted; the v2
    fields governance_context_available and mode_of_work are present.
    """
    record = make_started_record()
    captured: list[dict[str, object]] = []

    with patch("specify_cli.invocation.propagator._get_saas_client") as mock_factory:
        mock_client = MagicMock()

        async def mock_send(event_dict: dict[str, object]) -> None:
            captured.append(event_dict)

        mock_client.send_event = mock_send
        mock_factory.return_value = mock_client
        _propagate_one(record, tmp_path)

    assert len(captured) == 1
    envelope = captured[0]
    assert envelope == {
        "event_type": "ProfileInvocationStarted",
        "invocation_id": record.invocation_id,
        "profile_id": "implementer-fixture",
        "action": "implement",
        "request_text": "implement the feature",
        "actor": "claude",
        "mode_of_work": "task_execution",
        "governance_context_hash": "abcdef0123456789",
        "governance_context_available": True,
        "started_at": "2026-04-21T10:00:00Z",
    }


def test_completed_envelope_field_set_follows_v2_contract(tmp_path: pytest.TempPathFactory) -> None:
    """Completed envelope is built 1:1 from OpCompletedEvent — includes closed_by;
    evidence_ref omitted when None (on-disk parity)."""
    record = OpCompletedEvent(
        invocation_id="01KPQRX2EVGMRVB4Q1JQBAZJV3",
        completed_at="2026-04-21T11:00:00Z",
        outcome="done",
        closed_by="agent",
        evidence_ref=None,
    )
    captured: list[dict[str, object]] = []

    with patch("specify_cli.invocation.propagator._get_saas_client") as mock_factory:
        mock_client = MagicMock()

        async def mock_send(event_dict: dict[str, object]) -> None:
            captured.append(event_dict)

        mock_client.send_event = mock_send
        mock_factory.return_value = mock_client
        _propagate_one(record, tmp_path)

    assert len(captured) == 1
    assert captured[0] == {
        "event_type": "ProfileInvocationCompleted",
        "invocation_id": record.invocation_id,
        "completed_at": "2026-04-21T11:00:00Z",
        "outcome": "done",
        "closed_by": "agent",
    }


def test_propagator_tracks_tasks_until_completion(tmp_path: pytest.TempPathFactory) -> None:
    """Running-loop sends stay referenced until the async task completes."""
    record = make_started_record()
    captured: list[dict[str, object]] = []

    class MockClient:
        async def send_event(self, event_dict: dict[str, object]) -> None:
            captured.append(event_dict)

    async def exercise() -> None:
        with patch(
            "specify_cli.invocation.propagator._get_saas_client",
            return_value=MockClient(),
        ):
            _propagate_one(record, tmp_path)
            assert len(_PENDING_SEND_TASKS) == 1
            await asyncio.gather(*tuple(_PENDING_SEND_TASKS))
            await asyncio.sleep(0)

    asyncio.run(exercise())

    assert not _PENDING_SEND_TASKS
    assert captured[0]["invocation_id"] == record.invocation_id


def test_propagator_error_log_never_raises_on_disk_full(tmp_path: pytest.TempPathFactory) -> None:
    """If propagation error log itself fails (disk full), no exception raised."""
    record = make_started_record()

    # The error log goes through the interim locked append (#6606); make it
    # raise OSError, simulating a full disk.
    with patch("specify_cli.invocation.propagator.append_event_log_lines", side_effect=OSError("disk full")):
        # Must not raise
        _log_propagation_error(tmp_path, record, "test error")
