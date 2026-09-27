"""Every relay MCP tool pre-flights
``hosted_posture.require_drain("relay")`` and lets ``DrainDisabled``
propagate uncaught, so FastMCP turns it into a structured tool-error result
carrying the guidance text -- never a swallowed generic error, never a real
credential-store or subscription read.

In-process client/server coverage via ``mcp.shared.memory`` (no subprocess,
no real stdio pipe), following the pattern in ``tests/zeitgeist_client/
test_mcp_stdio.py``.
"""

from __future__ import annotations

import pytest
from mcp.shared.memory import create_connected_server_and_client_session

from specify_cli.zeitgeist_client import mcp_stdio

pytestmark = pytest.mark.fast

_REPO = "github.com/acme/spec-kitty"

_TOOL_ARGS: dict[str, dict[str, object]] = {
    "zeitgeist_status": {"repo": _REPO},
    "zeitgeist_watch": {"repo": _REPO},
    "zeitgeist_activity": {"repo": _REPO},
    "zeitgeist_send": {"repo": _REPO, "kind": "message", "body": "hello"},
    "zeitgeist_reply": {"repo": _REPO, "reply_to": "some-message-id", "body": "hello"},
    "zeitgeist_read": {"repo": _REPO},
    "zeitgeist_inbox": {"repo": _REPO},
}


def _forbid_credential_and_subscription_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.zeitgeist_client import credentials, subscription

    def _raise_credentials(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("credentials.load must not be called when drain is off")

    def _raise_resolve_stream(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("subscription.resolve_stream must not be called when drain is off")

    monkeypatch.setattr(credentials, "load", _raise_credentials)
    monkeypatch.setattr(subscription, "resolve_stream", _raise_resolve_stream)


@pytest.mark.asyncio
@pytest.mark.parametrize("tool_name", sorted(_TOOL_ARGS))
async def test_each_relay_tool_reports_a_tool_error_with_drain_guidance(drain_off: None, monkeypatch: pytest.MonkeyPatch, tool_name: str) -> None:
    _forbid_credential_and_subscription_reads(monkeypatch)
    server = mcp_stdio.build_server()
    async with create_connected_server_and_client_session(server) as client:
        result = await client.call_tool(tool_name, _TOOL_ARGS[tool_name])

    assert result.isError
    text = " ".join(c.text for c in result.content if hasattr(c, "text"))
    assert "Live drain is off" in text


@pytest.mark.asyncio
async def test_server_still_exposes_all_seven_relay_tools_under_drain_off(drain_off: None) -> None:
    """The gate refuses each call, not registration -- the tool surface is
    unchanged regardless of drain posture."""
    server = mcp_stdio.build_server()
    async with create_connected_server_and_client_session(server) as client:
        listed = await client.list_tools()
        names = {t.name for t in listed.tools}
    assert names == set(_TOOL_ARGS)
