"""Tests for CallbackHandler + CallbackServer (feature 080, WP02 T015).

Two kinds of coverage:

1. **Pure validation** (:class:`CallbackHandler`, :func:`validate_callback_params`):
   happy path, missing ``code``, missing ``state``, CSRF mismatch, SaaS error.

2. **End-to-end loopback** (:class:`CallbackServer`):
   start a real HTTP server on localhost, fire a request at it with
   ``urllib.request.urlopen``, and assert that ``wait_for_callback()``
   returns the expected query parameters. This is deliberately hitting
   real loopback (no browser) — that is the only way to exercise the
   socket/thread machinery end-to-end.
"""

from __future__ import annotations

import asyncio
import threading
from urllib.request import urlopen

import pytest

from specify_cli.auth.errors import (
    CallbackError,
    CallbackTimeoutError,
    CallbackValidationError,
)
from specify_cli.auth.loopback.callback_handler import (
    CallbackHandler,
    validate_callback_params,
)
from specify_cli.auth.loopback.callback_server import CallbackServer


# ---------------------------------------------------------------------------
# CallbackHandler (pure validation)
# ---------------------------------------------------------------------------


pytestmark = [pytest.mark.integration]

def test_callback_handler_happy_path() -> None:
    handler = CallbackHandler(expected_state="csrf-nonce-123")
    code, state = handler.validate({"code": "auth-code-xyz", "state": "csrf-nonce-123"})
    assert code == "auth-code-xyz"
    assert state == "csrf-nonce-123"


def test_callback_handler_missing_code_raises() -> None:
    handler = CallbackHandler(expected_state="csrf-nonce-123")
    with pytest.raises(CallbackValidationError, match="Missing 'code'"):
        handler.validate({"state": "csrf-nonce-123"})


def test_callback_handler_missing_state_raises() -> None:
    handler = CallbackHandler(expected_state="csrf-nonce-123")
    with pytest.raises(CallbackValidationError, match="Missing 'state'"):
        handler.validate({"code": "auth-code-xyz"})


def test_callback_handler_state_mismatch_raises() -> None:
    handler = CallbackHandler(expected_state="expected-nonce-abcdef")
    with pytest.raises(CallbackValidationError, match="State mismatch"):
        handler.validate({"code": "auth-code-xyz", "state": "attacker-nonce-zyxwvu"})


def test_callback_handler_oauth_error_raises_callback_error() -> None:
    handler = CallbackHandler(expected_state="csrf-nonce-123")
    with pytest.raises(CallbackError, match="access_denied"):
        handler.validate(
            {
                "error": "access_denied",
                "error_description": "user declined consent",
            }
        )


def test_callback_handler_oauth_error_without_description() -> None:
    handler = CallbackHandler(expected_state="csrf-nonce-123")
    with pytest.raises(CallbackError, match="invalid_request"):
        handler.validate({"error": "invalid_request"})


def test_validate_callback_params_functional_wrapper() -> None:
    code, state = validate_callback_params(
        {"code": "abc", "state": "xyz"}, expected_state="xyz"
    )
    assert code == "abc"
    assert state == "xyz"


def test_validate_callback_params_rejects_mismatch() -> None:
    with pytest.raises(CallbackValidationError):
        validate_callback_params(
            {"code": "abc", "state": "wrong"}, expected_state="right"
        )


# ---------------------------------------------------------------------------
# CallbackServer (real localhost loopback, no browser)
# ---------------------------------------------------------------------------


@pytest.fixture
def callback_server():
    """Yield a started :class:`CallbackServer` and guarantee cleanup."""
    server = CallbackServer(timeout_seconds=5.0)
    server.start()
    try:
        yield server
    finally:
        server.stop()


def test_callback_server_binds_to_preferred_port_range(callback_server: CallbackServer) -> None:
    # Start succeeded; verify port is in the preferred range OR fell back to OS.
    assert callback_server.port > 0
    # The callback URL should be a localhost loopback URL.
    assert callback_server.callback_url.startswith("http://127.0.0.1:")
    assert callback_server.callback_url.endswith("/callback")


def test_callback_server_port_raises_before_start() -> None:
    server = CallbackServer()
    with pytest.raises(RuntimeError, match="not started"):
        _ = server.port


def test_callback_server_404_for_unknown_path(callback_server: CallbackServer) -> None:
    from urllib.error import HTTPError

    url = f"http://127.0.0.1:{callback_server.port}/not-the-callback"
    with pytest.raises(HTTPError) as exc_info:
        urlopen(url, timeout=2.0)  # noqa: S310 (intentional localhost fetch)
    assert exc_info.value.code == 404


async def test_callback_server_returns_params_when_called(callback_server: CallbackServer) -> None:
    """End-to-end: fire a GET at the callback URL and await the params."""
    url = f"{callback_server.callback_url}?code=AUTH_CODE_ABC&state=CSRF_XYZ"

    def _fire_request() -> None:
        # Small delay to let wait_for_callback start polling first.
        urlopen(url, timeout=2.0)  # noqa: S310 (localhost loopback only)

    t = threading.Thread(target=_fire_request, daemon=True)
    t.start()

    params = await callback_server.wait_for_callback()

    t.join(timeout=2.0)

    assert params == {"code": "AUTH_CODE_ABC", "state": "CSRF_XYZ"}


async def test_callback_server_first_callback_wins(callback_server: CallbackServer) -> None:
    """A second callback hit must not overwrite the first."""
    first_url = f"{callback_server.callback_url}?code=FIRST&state=AAA"
    second_url = f"{callback_server.callback_url}?code=SECOND&state=BBB"

    # Wrapped in to_thread so ruff's ASYNC210 is happy; urlopen is blocking
    # but acceptable here because we're hitting localhost loopback.
    await asyncio.to_thread(urlopen, first_url, timeout=2.0)
    await asyncio.to_thread(urlopen, second_url, timeout=2.0)

    params = await callback_server.wait_for_callback()
    assert params == {"code": "FIRST", "state": "AAA"}


async def test_callback_server_wait_for_callback_times_out() -> None:
    """With no request fired, wait_for_callback must raise CallbackTimeoutError."""
    server = CallbackServer(timeout_seconds=0.3, late_callback_seconds=0.1)
    server.start()
    try:
        with pytest.raises(CallbackTimeoutError, match="timed out"):
            await server.wait_for_callback()
    finally:
        server.stop()


async def test_late_callback_gets_timeout_page_without_accepting_code() -> None:
    server = CallbackServer(timeout_seconds=0.1, late_callback_seconds=0.5)
    server.start()
    try:
        waiting = asyncio.create_task(server.wait_for_callback())
        await asyncio.sleep(0.2)
        response = await asyncio.to_thread(urlopen, f"{server.callback_url}?code=LATE&state=XYZ", timeout=2.0)
        body = response.read().decode()
        assert "timed out" in body.lower()
        assert "spec-kitty auth login" in body
        with pytest.raises(CallbackTimeoutError):
            await waiting
        assert server._server.callback_params is None
    finally:
        server.stop()


async def test_callback_server_wait_for_callback_before_start_raises() -> None:
    server = CallbackServer()
    with pytest.raises(RuntimeError, match="not started"):
        await server.wait_for_callback()


def test_callback_server_stop_is_idempotent() -> None:
    server = CallbackServer()
    server.start()
    server.stop()
    server.stop()  # second call must not raise


def test_callback_server_handles_error_params(callback_server: CallbackServer) -> None:
    """OAuth error params (error=access_denied) must still reach wait_for_callback."""
    # We do NOT pass through CallbackHandler here; the server's job is just
    # to capture the params. Validation is CallbackHandler's responsibility.
    url = f"{callback_server.callback_url}?error=access_denied&error_description=nope"
    urlopen(url, timeout=2.0)  # noqa: S310

    loop = asyncio.new_event_loop()
    try:
        params = loop.run_until_complete(callback_server.wait_for_callback())
    finally:
        loop.close()

    assert params["error"] == "access_denied"
    assert params["error_description"] == "nope"
