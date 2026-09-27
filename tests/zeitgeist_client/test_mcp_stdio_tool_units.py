"""Direct, synchronous unit coverage of the campsite-first extraction in
``mcp_stdio.py`` -- ``_bind_tool`` and the module-level ``_tool_zeitgeist_*``
bodies, called directly with a fake
``resolved`` settings object rather than through a real FastMCP client
session (``tests/zeitgeist_client/test_mcp_stdio.py`` owns that end-to-end
surface). Kept in a separate, non-``asyncio``-marked file: these tests are
plain sync functions, and ``test_mcp_stdio.py``'s module-level
``pytestmark = [..., pytest.mark.asyncio]`` would otherwise warn on every one
of them ("marked with '@pytest.mark.asyncio' but it is not an async
function").
"""

from __future__ import annotations

import inspect
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from specify_cli.zeitgeist_client import mcp_stdio, moments

pytestmark = pytest.mark.fast


def _settings(**overrides: Any) -> moments.MomentSettings:
    """The same explicit-settings builder ``test_mcp_stdio.py`` uses,
    duplicated locally: ``tests/`` is intentionally not importable as a
    package (pytest.ini keeps ``.`` off ``pythonpath``), so a private helper
    in a sibling test module cannot be imported directly."""
    values: dict[str, Any] = {
        "agents": moments.MomentsMode.TEAM,
        "repos": (),
        "missions": (),
        "teammates": (),
        "kinds": (),
        "rate_per_minute": moments.DEFAULT_RATE_PER_MINUTE,
    }
    values.update(overrides)
    return moments.MomentSettings(**values)


def test_bind_tool_strips_the_tool_prefix_and_preserves_behaviour() -> None:
    def _tool_example(resolved: moments.MomentSettings, x: int = 1) -> int:
        """An example tool body."""
        return len(resolved.repos) + x

    resolved = _settings(repos=("github.com/acme/widget",))
    bound = mcp_stdio._bind_tool(_tool_example, resolved)

    assert bound.__name__ == "example"
    assert bound.__doc__ == "An example tool body."
    assert bound(2) == 3  # the bound `resolved` is applied; only `x` remains
    assert list(inspect.signature(bound).parameters) == ["x"]


def test_tool_zeitgeist_status_reports_withheld_by_repos_filter() -> None:
    resolved = _settings(repos=("github.com/acme/widget",))
    result = mcp_stdio._tool_zeitgeist_status(resolved, repo="github.com/acme/other")
    assert result == {"repo": "github.com/acme/other", "presence": [], "focus": [], "withheld_by": "repos_filter"}


def test_tool_zeitgeist_read_reports_withheld_by_repos_filter() -> None:
    resolved = _settings(repos=("github.com/acme/widget",))
    result = mcp_stdio._tool_zeitgeist_read(resolved, repo="github.com/acme/other")
    assert result == {"repo": "github.com/acme/other", "messages": [], "withheld_by": "repos_filter"}


def test_tool_zeitgeist_read_returns_the_authored_service_result(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.live_work import authored

    calls: list[tuple[str, int, int]] = []

    def _fake_read_conversation(repo: str, *, thread: str | None, window_s: int, max_messages: int) -> dict[str, Any]:
        calls.append((repo, window_s, max_messages))
        return {"repo": repo, "messages": [], "coverage": {}}

    monkeypatch.setattr(authored, "read_conversation", _fake_read_conversation)
    resolved = _settings()

    result = mcp_stdio._tool_zeitgeist_read(resolved, repo="github.com/acme/spec-kitty", window_s=120, max_messages=5)

    assert result == {"repo": "github.com/acme/spec-kitty", "messages": [], "coverage": {}}
    assert calls == [("github.com/acme/spec-kitty", 120, 5)]


def test_tool_zeitgeist_inbox_reports_withheld_by_repos_filter() -> None:
    resolved = _settings(repos=("github.com/acme/widget",))
    result = mcp_stdio._tool_zeitgeist_inbox(resolved, repo="github.com/acme/other")
    assert result == {"repo": "github.com/acme/other", "messages": [], "withheld_by": "repos_filter"}


def test_tool_zeitgeist_inbox_returns_the_authored_service_result(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.live_work import authored

    calls: list[str] = []

    def _fake_inbox(repo: str, *, consumer: str | None, window_s: int, max_messages: int, acknowledge: str | None, replay: bool) -> dict[str, Any]:
        calls.append(repo)
        return {"repo": repo, "messages": [], "receipt": None}

    monkeypatch.setattr(authored, "inbox", _fake_inbox)
    resolved = _settings()

    result = mcp_stdio._tool_zeitgeist_inbox(resolved, repo="github.com/acme/spec-kitty")

    assert result == {"repo": "github.com/acme/spec-kitty", "messages": [], "receipt": None}
    assert calls == ["github.com/acme/spec-kitty"]


def test_tool_zeitgeist_send_validates_an_explicit_repo_before_sending(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.live_work import authored

    calls: list[tuple[str, str]] = []

    def _fake_send(kind: str, body: str, *, cwd: Path, audience: str | None, thread: str | None, allow_truncate: bool) -> Any:
        calls.append((kind, body))
        return SimpleNamespace(as_dict=lambda: {"outcome": "accepted"})

    monkeypatch.setattr(authored, "send", _fake_send)
    resolved = _settings()

    result = mcp_stdio._tool_zeitgeist_send(resolved, "message", "hi team", repo="github.com/acme/spec-kitty")

    assert result == {"outcome": "accepted"}
    assert calls == [("message", "hi team")]


def test_tool_zeitgeist_send_rejects_a_malformed_explicit_repo() -> None:
    from specify_cli.zeitgeist_client.resolution import StoreKeyError

    resolved = _settings()
    with pytest.raises(StoreKeyError):
        mcp_stdio._tool_zeitgeist_send(resolved, "message", "hi team", repo="widget")


def test_tool_zeitgeist_reply_validates_an_explicit_repo_before_replying(monkeypatch: pytest.MonkeyPatch) -> None:
    from specify_cli.live_work import authored

    calls: list[tuple[str, str]] = []

    def _fake_reply(reply_to: str, body: str, *, cwd: Path, audience: str | None, allow_truncate: bool) -> Any:
        calls.append((reply_to, body))
        return SimpleNamespace(as_dict=lambda: {"outcome": "accepted"})

    monkeypatch.setattr(authored, "reply", _fake_reply)
    resolved = _settings()

    result = mcp_stdio._tool_zeitgeist_reply(resolved, "msg-1", "hi back", repo="github.com/acme/spec-kitty")

    assert result == {"outcome": "accepted"}
    assert calls == [("msg-1", "hi back")]
