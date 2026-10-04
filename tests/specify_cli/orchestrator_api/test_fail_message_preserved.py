"""Fail-loud regression for ``_fail`` message-vs-data drop (#3548).

The ``_fail`` helper builds every orchestrator-api failure envelope. Its
pre-fix payload expression ``data or {"message": message}`` silently DROPPED
the human-readable ``message`` whenever a caller supplied a truthy structured
``data`` — the operator lost the explanation on exactly the most actionable
errors (16 of 33 call sites). These tests pin the fail-loud discipline
(epics #3410 / #3549, SC-001 / SC-005): the ``message`` param MUST always reach
the operator inside the envelope's ``data``, AND a caller's structured fields
must survive alongside it.

The seam is asserted directly on the emitted envelope (``_emit`` captured), so
the test pins the operator-visible SIGNAL, not merely the ``error_code``.
"""

from __future__ import annotations

from typing import Any

import pytest
import typer

from specify_cli.orchestrator_api import _common

pytestmark = [pytest.mark.fast]


def _capture_fail_envelope(
    monkeypatch: pytest.MonkeyPatch,
    *,
    command: str,
    error_code: str,
    message: str,
    data: dict[str, Any] | None,
) -> dict[str, Any]:
    """Invoke ``_fail`` and return the envelope it hands to ``_emit``.

    ``_fail`` prints via ``_emit`` and then raises ``typer.Exit(1)``; we patch
    ``_emit`` to intercept the envelope and swallow the expected exit.
    """
    captured: dict[str, Any] = {}

    def _fake_emit(envelope: dict[str, Any]) -> None:
        captured["envelope"] = envelope

    monkeypatch.setattr(_common, "_emit", _fake_emit)

    with pytest.raises(typer.Exit) as exc_info:
        _common._fail(command, error_code, message, data)

    assert exc_info.value.exit_code == 1
    return captured["envelope"]


def test_fail_preserves_message_alongside_structured_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A truthy structured ``data`` must NOT evict the ``message`` param (#3548).

    Pre-fix (``data or {"message": message}``) this took the ``data`` branch and
    the explanation vanished — the operator saw only the structured fields.
    """
    message = "Provider version '1.0.0' is below minimum '2.0.0'"
    structured = {
        "provider_version": "1.0.0",
        "min_supported_provider_version": "2.0.0",
        "api_version": "3.0.0",
    }

    envelope = _capture_fail_envelope(
        monkeypatch,
        command="contract-version",
        error_code="CONTRACT_VERSION_MISMATCH",
        message=message,
        data=dict(structured),
    )

    payload = envelope["data"]
    # The human-readable explanation reaches the operator...
    assert payload["message"] == message
    # ...and every structured field survives alongside it (no drop, no clobber).
    expected_keys = set(structured) | {"message"}
    assert set(payload) == expected_keys
    for key, value in structured.items():
        assert payload[key] == value
    # Envelope contract fidelity is unchanged (NFR-003).
    assert envelope["success"] is False
    assert envelope["error_code"] == "CONTRACT_VERSION_MISMATCH"


def test_fail_without_data_still_carries_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The ``data``-less path keeps the historical single-key ``message`` shape."""
    message = "Mission 'ghost' not found in kitty-specs/"

    envelope = _capture_fail_envelope(
        monkeypatch,
        command="mission-state",
        error_code="MISSION_NOT_FOUND",
        message=message,
        data=None,
    )

    assert envelope["data"] == {"message": message}


def test_fail_caller_message_matches_param_is_not_duplicated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The one caller that puts ``message`` in ``data`` (line 313 seam) passes the
    SAME value as the param; the merge keeps a single coherent ``message`` while
    preserving the caller's structured candidates (#3548).
    """
    message = "read-path not found"
    data = {
        "message": message,
        "mission_slug": "demo-01KV8NPC",
        "coord_candidate": "/repo/.worktrees/demo-coord",
        "primary_candidate": "/repo/kitty-specs/demo",
    }

    envelope = _capture_fail_envelope(
        monkeypatch,
        command="mission-state",
        error_code="STATUS_READ_PATH_NOT_FOUND",
        message=message,
        data=dict(data),
    )

    payload = envelope["data"]
    assert payload["message"] == message
    assert set(payload) == set(data)
    assert payload["coord_candidate"] == "/repo/.worktrees/demo-coord"
    assert payload["primary_candidate"] == "/repo/kitty-specs/demo"
